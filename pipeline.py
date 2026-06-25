"""
pipeline.py — 主流程：6 阶段全自动生成短视频
==========================================
用法：
  python pipeline.py --episode 1 --all
  python pipeline.py --episode 1 --all --series rommel
  python pipeline.py --episode 1 --skip-image --skip-llm
"""
import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

import config
from utils.script import load_episode_sentences
from utils.llm import generate_image_prompts
from utils.comfyui import generate_one as gen_image, check_comfyui
from utils.tts import generate as gen_audio
from utils.parallax import render as render_bg
from utils.subtitle import make_subtitle_png
from utils.ffmpeg import (
    concat_videos_xfade, concat_audios_with_silence,
    make_subtitle_video, overlay_subtitle_alpha,
)


def _get_series_config(series_name):
    if series_name in config.SERIES_CONFIG:
        return config.SERIES_CONFIG[series_name]
    # 回退：把 series_name 当作文件名前缀
    return {
        "script_en": f"data/{series_name}_en.txt",
        "script_zh": f"data/{series_name}_zh.txt",
        "style": config.SERIES_CONFIG.get("rommel", {}).get("style", ""),
        "neg": config.SERIES_CONFIG.get("rommel", {}).get("neg", ""),
        "image_density": 1,
    }


def setup_dirs(series_name, episode=1):
    sp = config.series_paths(series_name)
    for d in [config.OUTPUT_DIR,
              sp["images"], f"{sp['images']}/ep{episode:02d}",
              sp["bg"], f"{sp['bg']}/ep{episode:02d}",
              config.AUDIO_DIR, config.AUDIO_DIR_ZH, config.AUDIO_DIR_EN,
              f"{config.AUDIO_DIR_EN}/ep{episode:02d}",
              config.SUBTITLE_DIR, config.TITLE_DIR,
              config.FINAL_DIR]:
        Path(d).mkdir(parents=True, exist_ok=True)


def phase1_load_script(series_cfg, episode, n_sentences=None):
    logger.info("=" * 60)
    logger.info("【阶段 1/6】加载文案")
    logger.info("=" * 60)
    en_t, zh_t, pairs = load_episode_sentences(
        series_cfg["script_en"], series_cfg["script_zh"], episode, n_sentences)
    logger.info(f"  标题: {en_t} | {zh_t}")
    logger.info(f"  句数: {len(pairs)}")
    return en_t, zh_t, pairs


def phase2_gen_prompts(pairs, style_hint, skip=False):
    logger.info("=" * 60)
    logger.info("【阶段 2/6】LLM 生成图像提示词")
    logger.info("=" * 60)
    if skip:
        logger.info("  跳过（--skip-llm）")
        return [en for en, zh in pairs]
    en_sents = [en for en, zh in pairs]
    prompts = generate_image_prompts(en_sents, style_hint=style_hint)
    for i, ((en, zh), p) in enumerate(zip(pairs, prompts)):
        logger.info(f"  [{i+1}/{len(pairs)}] {p[:60]}...")
    return prompts


def _make_blank_image(out, w, h):
    """生成纯色兜底图，优先 cv2，回退 PIL。"""
    try:
        import numpy as np
        import cv2
        blank = np.full((h, w, 3), 30, dtype=np.uint8)
        cv2.imwrite(out, blank)
    except Exception:
        from PIL import Image
        Image.new("RGB", (w, h), (30, 30, 30)).save(out)


def phase3_gen_images(prompts, series_cfg, series_name, skip=False, episode=1):
    logger.info("=" * 60)
    logger.info("【阶段 3/6】ComfyUI 生图")
    logger.info("=" * 60)
    sp = config.series_paths(series_name)
    images_dir = f"{sp['images']}/ep{episode:02d}"
    if skip:
        logger.info("  跳过（--skip-image），检查已有图片，缺失的自动生成...")
        out_paths = []
        missing = 0
        for i in range(len(prompts)):
            out = f"{images_dir}/img_{i:03d}.png"
            if Path(out).exists():
                out_paths.append(out)
            else:
                missing += 1
        if missing == 0:
            logger.info("  全部图片已就绪，无需生图")
            return out_paths
        logger.info(f"  缺失 {missing} 张图片，自动调用 ComfyUI 补生成...")

    check_comfyui()
    style = series_cfg.get("style", "")
    neg = series_cfg.get("neg", config.SERIES_CONFIG["rommel"]["neg"])
    out_paths = []
    for i, prompt in enumerate(prompts):
        out = f"{images_dir}/img_{i:03d}.png"
        if skip and Path(out).exists():
            out_paths.append(out)
            continue
        try:
            full_prompt = f"{style}. {prompt}" if style else prompt
            seed = episode * 1000 + i
            gen_image(full_prompt, neg, out, seed=seed)
            out_paths.append(out)
        except Exception as e:
            logger.error(f"  ✗ 第{i}张失败: {e}，生成纯色兜底")
            _make_blank_image(out, config.IMAGE_W, config.IMAGE_H)
            out_paths.append(out)
    return out_paths


def phase4_gen_audio(pairs, lang="zh", skip=False, force=False, episode=1):
    """lang: 'zh' 或 'en'"""
    voice = config.TTS_VOICE_ZH if lang == "zh" else config.TTS_VOICE_EN
    audio_base = config.AUDIO_DIR_ZH if lang == "zh" else config.AUDIO_DIR_EN
    audio_dir = f"{audio_base}/ep{episode:02d}"
    Path(audio_dir).mkdir(parents=True, exist_ok=True)
    label = "中文" if lang == "zh" else "英文"

    logger.info("=" * 60)
    logger.info(f"【阶段 4/6】Edge-TTS {label}语音合成 ({voice})")
    logger.info("=" * 60)
    if skip:
        logger.info("  跳过（--skip-tts）")
        return [(f"{audio_dir}/aud_{i:03d}.mp3", 0)
                for i in range(len(pairs))]

    from utils.ffmpeg import _probe_dur
    # 并行生成所有句子的 TTS
    results = [None] * len(pairs)

    def _gen_one(idx, en, zh):
        out = f"{audio_dir}/aud_{idx:03d}.mp3"
        if not force and Path(out).exists():
            dur = _probe_dur(out)
            if dur > 0:
                return (idx, out, dur, True)
        text = zh if lang == "zh" else en
        try:
            dur = gen_audio(text, out, voice=voice)
            return (idx, out, dur, False)
        except Exception as e:
            logger.error(f"  ✗ 第{idx}句 TTS 失败: {e}")
            return (idx, out, 0, False)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_gen_one, i, en, zh): i for i, (en, zh) in enumerate(pairs)}
        for fut in as_completed(futures):
            idx, out, dur, cached = fut.result()
            results[idx] = (out, dur)
            tag = "缓存" if cached else ""
            logger.info(f"  [{idx+1}/{len(pairs)}] {dur:.1f}s {tag}")
    return results


def phase5_render_bg(images, audio_durs, series_name, force=False, episode=1):
    logger.info("=" * 60)
    logger.info("【阶段 5/6】CPU remap 视差背景")
    logger.info("=" * 60)
    sp = config.series_paths(series_name)
    bg_dir = f"{sp['bg']}/ep{episode:02d}"
    Path(bg_dir).mkdir(parents=True, exist_ok=True)
    bg_paths = [None] * len(images)

    def _render_one(idx, img, aud, dur):
        bg_dur = dur + config.SILENCE_DUR
        out = f"{bg_dir}/bg_{idx:03d}.mp4"
        if not force and Path(out).exists():
            img_mtime = Path(img).stat().st_mtime if Path(img).exists() else 0
            bg_mtime = Path(out).stat().st_mtime
            if img_mtime <= bg_mtime:
                return (idx, out, True)
        motion = config.MOTIONS[idx % len(config.MOTIONS)]
        try:
            render_bg(img, bg_dur, out, motion)
            return (idx, out, False)
        except Exception as e:
            logger.error(f"  ✗ 第{idx}段视差失败: {e}，使用静态图兜底")
            try:
                subprocess.run(
                    [config.FFMPEG_PATH, "-y", "-loop", "1", "-i", img,
                     "-t", str(bg_dur), "-r", str(config.FPS),
                     "-vf", f"scale={config.RES_W}:{config.RES_H}",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p",
                     "-preset", "veryfast", "-crf", str(config.CRF), out],
                    capture_output=True, timeout=120, check=True)
            except Exception as e2:
                logger.error(f"  ✗ 静态图兜底也失败: {e2}")
            return (idx, out, False)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_render_one, i, img, aud, dur): i
                   for i, (img, (aud, dur)) in enumerate(zip(images, audio_durs))}
        for fut in as_completed(futures):
            idx, out, cached = fut.result()
            bg_paths[idx] = out
            tag = "缓存" if cached else ""
            logger.info(f"  [{idx+1}/{len(images)}] {Path(out).name} {tag}")
    return bg_paths


def phase6_compose(bg_paths, audio_results, sub_pairs, out_path,
                   en_title="", zh_title="", force=False, lang="zh", series_name="", episode=1):
    """lang: 'zh' 或 'en'，决定 TTS 语言；字幕始终中英双语同时显示。"""
    logger.info("=" * 60)
    logger.info(f"【阶段 6/6】音视频合成 ({'中文' if lang == 'zh' else '英文'})")
    logger.info("=" * 60)
    audio_dir = f"{config.AUDIO_DIR_ZH if lang == 'zh' else config.AUDIO_DIR_EN}/ep{episode:02d}"
    sp = config.series_paths(series_name) if series_name else {"bg": config.BG_DIR}
    bg_dir = f"{sp['bg']}/ep{episode:02d}"

    # 0. 片头标题卡（缓存按系列+集号隔离，避免换集/换系列显示旧标题）
    title_video = None
    if en_title or zh_title:
        title_video = f"{config.TITLE_DIR}/title_{series_name}_ep{episode:02d}_{lang}.mp4"
        if not force and Path(title_video).exists():
            logger.info(f"  片头缓存命中: {Path(title_video).name}")
        else:
            logger.info("  生成片头标题卡...")
            from utils.ffmpeg import make_title_card
            make_title_card(en_title, zh_title, title_video)

    # 1. 背景 xfade 拼接（标题卡插入最前面）
    all_bg = ([title_video] if title_video else []) + bg_paths
    bg_merged = f"{bg_dir}/_merged.mp4"
    logger.info("  背景 xfade 拼接...")
    concat_videos_xfade(all_bg, bg_merged, config.XFADE_DUR)

    # 2. 音频 concat（标题卡期间加静音）
    audio_paths = [a for a, _ in audio_results]
    if title_video:
        title_silence = f"{audio_dir}/_title_silence.mp3"
        subprocess.run(
            [config.FFMPEG_PATH, "-y", "-f", "lavfi", "-i",
             f"anullsrc=r=24000:cl=mono", "-t", str(config.TITLE_CARD_DUR),
             title_silence],
            check=True, capture_output=True, timeout=30)
        audio_paths = [title_silence] + audio_paths
    audio_merged = f"{audio_dir}/_merged.mp3"
    logger.info("  音频拼接...")
    concat_audios_with_silence(audio_paths, audio_merged, config.SILENCE_DUR)

    # 3. 生成逐句字幕 PNG — 始终中英双语同时显示
    logger.info("  生成逐句字幕（中英双语）...")
    sub_pngs = []
    seg_durs = []
    for i, (en, zh) in enumerate(sub_pairs):
        sub_png = f"{config.SUBTITLE_DIR}/sub_{i:03d}.png"
        if not force and Path(sub_png).exists():
            logger.info(f"    字幕缓存命中: sub_{i:03d}.png")
        else:
            make_subtitle_png(
                en, zh, sub_png,
                width=config.RES_W, height=config.RES_H,
                en_size=config.SUB_FONT_EN, zh_size=config.SUB_FONT_ZH,
                y_start_ratio=config.SUB_Y_START,
                en_color=config.SUB_EN_COLOR,
                zh_color=config.SUB_ZH_COLOR,
                stroke_color=config.SUB_STROKE,
                bg_alpha=config.SUB_BG_ALPHA,
                max_text_width=config.SUB_MAX_WIDTH,
            )
        sub_pngs.append(sub_png)
        dur = audio_results[i][1] + config.SILENCE_DUR if i < len(audio_results) else config.SILENCE_DUR
        seg_durs.append(dur)

    # 标题卡期间显示空字幕（透明）
    if title_video:
        empty_sub = f"{config.SUBTITLE_DIR}/sub_empty.png"
        if not force or not Path(empty_sub).exists():
            from PIL import Image
            Image.new("RGBA", (config.RES_W, config.RES_H), (0, 0, 0, 0)).save(empty_sub)
        sub_pngs = [empty_sub] + sub_pngs
        seg_durs = [config.TITLE_CARD_DUR] + seg_durs

    # 4. 拼接字幕视频（带 alpha 通道）
    sub_video = f"{config.SUBTITLE_DIR}/_merged.mov"
    logger.info("  字幕视频拼接...")
    make_subtitle_video(list(zip(sub_pngs, seg_durs)), sub_video, fps=config.FPS)

    # 5. alpha 叠加
    logger.info(f"  合成 → {out_path}")
    overlay_subtitle_alpha(bg_merged, sub_video, out_path, audio_merged)

    # 清理临时
    for f in [bg_merged, sub_video] + sub_pngs:
        try: os.remove(f)
        except OSError: pass
    if title_video:
        try: os.remove(title_silence)
        except OSError: pass
    try: os.remove(audio_merged)
    except OSError: pass

    sz = os.path.getsize(out_path) / 1024 / 1024
    logger.info(f"  ✓ 完成: {out_path} ({sz:.1f} MB)")


def main():
    p = argparse.ArgumentParser(description="AI 短视频自动生成")
    p.add_argument("--episode", type=int, required=True, help="集号")
    p.add_argument("--all", action="store_true", help="处理该集所有句")
    p.add_argument("--n", type=int, default=3, help="默认处理前 N 句")
    p.add_argument("--series", default=None, help="系列名（rommel/qin_empire/enlightenment...）")
    p.add_argument("--skip-image", action="store_true", help="跳过生图")
    p.add_argument("--skip-tts", action="store_true", help="跳过 TTS")
    p.add_argument("--skip-llm", action="store_true", help="跳过 LLM")
    p.add_argument("--force", action="store_true", help="强制重新生成，忽略缓存")
    p.add_argument("--lang", default="en", choices=["en"],
                   help="TTS语言（仅英文，中文TTS断词问题无法解决，已移除。字幕始终中英双语）")
    args = p.parse_args()

    series_name = args.series or config.SERIES
    series_cfg = _get_series_config(series_name)
    logger.info(f"  系列: {series_name} | 风格: {series_cfg['style'][:50]}...")
    if args.force:
        logger.info("  --force: 强制重新生成，忽略所有缓存")

    setup_dirs(series_name, episode=args.episode)
    t0 = time.time()

    n_sents = None if args.all else args.n
    en_title, zh_title, pairs = phase1_load_script(series_cfg, args.episode, n_sents)

    prompts = phase2_gen_prompts(pairs, series_cfg.get("style", ""), args.skip_llm)
    images = phase3_gen_images(prompts, series_cfg, series_name, args.skip_image, episode=args.episode)

    # 仅英文 TTS（中文 TTS 断词问题无法解决，已移除）
    # 字幕始终中英双语同时显示
    audio_results = phase4_gen_audio(pairs, lang="en", skip=args.skip_tts, force=args.force, episode=args.episode)
    bg_paths = phase5_render_bg(images, audio_results, series_name, force=args.force, episode=args.episode)

    out = f"{config.FINAL_DIR}/ep{args.episode:02d}_{series_name}.mp4"
    phase6_compose(bg_paths, audio_results, pairs, out,
                   en_title=en_title, zh_title=zh_title, force=args.force,
                   lang="en", series_name=series_name, episode=args.episode)

    elapsed = time.time() - t0
    logger.info(f"=" * 60)
    logger.info(f"✓ 全流程完成: {elapsed/60:.1f} 分钟")
    logger.info(f"  输出: {config.FINAL_DIR}/")


if __name__ == "__main__":
    main()