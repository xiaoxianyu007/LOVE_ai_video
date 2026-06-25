"""
utils/ffmpeg.py — 音视频合成（x fade 背景 + alpha 字幕 + 音频）
======================================================
关键设计：
  1. 背景视频 xfade 拼接（句间平滑转场）
  2. 字幕用透明 PNG 直接 alpha 叠加（无需 chromakey 绿底）
  3. 音频 concat + 句间静音
  4. 片头标题卡生成
"""
import os
import subprocess
from loguru import logger

from config import (
    FFMPEG_PATH, FFPROBE_PATH, RES_W, RES_H, FPS, TITLE_CARD_DUR,
    SUB_FONT_EN, SUB_FONT_ZH, SUB_EN_COLOR, SUB_ZH_COLOR,
    SUB_STROKE, SUB_BG_ALPHA, CRF, PRESET,
)


def _probe_dur(path):
    if not os.path.exists(path):
        logger.warning(f"  _probe_dur: 文件不存在 {path}")
        return 0.0
    r = subprocess.run(
        [FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, timeout=10)
    try:
        return float(r.stdout.strip()) if r.stdout.strip() else 0.0
    except ValueError:
        logger.warning(f"  _probe_dur: 无法解析时长 {path}: {r.stdout[:100]}")
        return 0.0


def concat_videos_xfade(bg_paths, out_path, xfade_dur=0.8):
    """
    多段背景视频 xfade 拼接。
    自动处理极短视频（dur < xfade 时跳过转场，直接硬切）。
    """
    if len(bg_paths) == 1:
        subprocess.run(["cp", bg_paths[0], out_path], check=True)
        return _probe_dur(out_path)

    n = len(bg_paths)
    parts = []
    for p in bg_paths:
        parts.append(f"-i {p}")
    inputs = " ".join(parts)

    filters = []
    cur = "0:v"
    offset = 0
    for i in range(1, n):
        prev_dur = _probe_dur(bg_paths[i - 1])
        # 保护：prev_dur <= 0 或 < xfade_dur 时，用 xfade_dur 兜底，避免 offset 递减
        if prev_dur <= 0 or prev_dur < xfade_dur:
            logger.warning(
                f"  ⚠ bg_{i-1:03d} 时长异常 ({prev_dur:.1f}s)，"
                f"转场自动降级为硬切"
            )
            prev_dur = xfade_dur
        offset += prev_dur - xfade_dur
        next_in = f"{i}:v"
        out_label = f"v{i}" if i < n - 1 else "vout"
        filters.append(
            f"[{cur}][{next_in}]xfade=transition=fade:duration={xfade_dur}"
            f":offset={offset}[{out_label}]"
        )
        cur = out_label

    filter_str = ";\n".join(filters)
    cmd = (
        f"{FFMPEG_PATH} -y -loglevel error "
        f"{inputs} "
        f'-filter_complex "{filter_str}" '
        f'-map "[vout]" -c:v libx264 -preset veryfast -crf 26 '
        f'-pix_fmt yuv420p {out_path}'
    )
    subprocess.run(cmd, shell=True, check=True, timeout=600)
    return _probe_dur(out_path)


def concat_audios_with_silence(audio_paths, out_path, silence_dur=0.8):
    """
    拼接音频，句间插入静音。
    """
    silence = out_path.replace(".mp3", "_silence.mp3")
    subprocess.run(
        [FFMPEG_PATH, "-y", "-f", "lavfi", "-i",
         f"anullsrc=r=24000:cl=mono", "-t", str(silence_dur),
         silence],
        check=True, capture_output=True, timeout=30)

    txt = os.path.abspath(out_path.replace(".mp3", "_list.txt"))
    with open(txt, "w") as f:
        abs_silence = os.path.abspath(silence)
        for i, ap in enumerate(audio_paths):
            f.write(f"file '{os.path.abspath(ap)}'\n")
            if i < len(audio_paths) - 1:
                f.write(f"file '{abs_silence}'\n")
    # 使用 concat filter 重编码，避免 -c copy 导致的 MP3 头不兼容
    inputs = []
    for ap in audio_paths:
        inputs.extend(["-i", ap])
    for _ in range(len(audio_paths) - 1):
        inputs.extend(["-i", silence])
    # 交错排列：file0, silence, file1, silence, ..., fileN
    interleaved = []
    for i in range(len(audio_paths)):
        interleaved.append(f"[{i}:a]")
        if i < len(audio_paths) - 1:
            interleaved.append(f"[{len(audio_paths) + i}:a]")
    n = len(interleaved)
    filter_str = f"{''.join(interleaved)}concat=n={n}:v=0:a=1[out]"
    subprocess.run(
        [FFMPEG_PATH, "-y"] + inputs +
        ["-filter_complex", filter_str, "-map", "[out]",
         "-c:a", "mp3", "-q:a", "2", out_path],
        check=True, capture_output=True, timeout=120)
    try: os.remove(silence)
    except OSError: pass
    try: os.remove(txt)
    except OSError: pass
    return _probe_dur(out_path)


def make_subtitle_video(subtitle_pairs, out_path, fps=24):
    """
    将多张字幕 PNG（带 alpha）拼接成视频，每张显示指定时长。

    参数
    ----
    subtitle_pairs : list of (png_path, duration_sec)
    out_path : 输出 .mov 路径（PNG 编码保留 alpha）
    """
    import os
    seg_dir = os.path.dirname(out_path)

    # Step 1: 每张 PNG 转为单段 MOV（PNG 编码保留 alpha 通道）
    seg_files = []
    for i, (png_path, dur) in enumerate(subtitle_pairs):
        seg_path = os.path.join(seg_dir, f"_sub_seg_{i:03d}.mov")
        cmd = [
            FFMPEG_PATH, "-y", "-loglevel", "error",
            "-loop", "1", "-i", png_path,
            "-t", str(dur),
            "-c:v", "png", "-pix_fmt", "rgba",
            "-vf", f"fps={fps}",
            seg_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        seg_files.append(seg_path)

    # Step 2: concat demuxer 拼接所有段
    txt = out_path.replace(".mov", "_list.txt")
    with open(txt, "w") as f:
        for sf in seg_files:
            f.write(f"file '{os.path.abspath(sf)}'\n")

    cmd = [
        FFMPEG_PATH, "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", txt,
        "-c:v", "png", "-pix_fmt", "rgba",
        "-r", str(fps),
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)

    # 清理
    try:
        os.remove(txt)
    except OSError:
        pass
    for sf in seg_files:
        try:
            os.remove(sf)
        except OSError:
            pass

    logger.info(f"  字幕视频已生成: {out_path}")
    return out_path


def overlay_subtitle_alpha(bg_path, sub_path, out_path, audio_path=None):
    """
    背景 + 字幕（透明 PNG alpha 叠加）+ 音频。
    无需 chromakey 绿底，直接 alpha 混合。
    """
    cmd = [
        FFMPEG_PATH, "-y", "-loglevel", "error",
        "-i", bg_path, "-i", sub_path,
    ]
    if audio_path:
        cmd += ["-i", audio_path]

    cmd += [
        "-filter_complex",
        "[1:v]format=rgba[sub];[0:v][sub]overlay=0:0:format=auto",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-pix_fmt", "yuv420p", "-shortest",
    ]
    if audio_path:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd.append(out_path)
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    return _probe_dur(out_path)


def make_title_card(en_title, zh_title, out_path):
    """
    生成片头标题卡视频（黑底 + 中英双语标题，渐入动画）。
    """
    import tempfile
    from PIL import Image, ImageDraw

    from utils.subtitle import _find_font

    # ── 渲染标题 PNG ──
    img = Image.new("RGB", (RES_W, RES_H), (10, 10, 18))
    draw = ImageDraw.Draw(img)

    # 标题字号
    title_en_size = SUB_FONT_EN + 12
    title_zh_size = SUB_FONT_ZH + 14
    en_font = _find_font(title_en_size, bold=True)
    zh_font = _find_font(title_zh_size, bold=True)

    # 分行
    def _wrap(draw_obj, text, font, max_w):
        lines, cur = [], ""
        for ch in text:
            bbox = draw_obj.textbbox((0, 0), cur + ch, font=font)
            if bbox[2] - bbox[0] > max_w and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines

    max_w = RES_W - 120
    en_lines = _wrap(draw, en_title, en_font, max_w) or [en_title]
    zh_lines = _wrap(draw, zh_title, zh_font, max_w) or [zh_title]

    en_line_h = title_en_size + 12
    zh_line_h = title_zh_size + 14
    gap = 20
    total_h = (len(en_lines) * en_line_h +
               len(zh_lines) * zh_line_h + gap)

    # 居中绘制
    y = (RES_H - total_h) // 2
    for line in en_lines:
        bbox = draw.textbbox((0, 0), line, font=en_font)
        tw = bbox[2] - bbox[0]
        x = (RES_W - tw) // 2
        draw.text((x, y), line, font=en_font, fill=SUB_EN_COLOR[:3],
                  stroke_width=2, stroke_fill=SUB_STROKE[:3])
        y += en_line_h
    y += gap
    for line in zh_lines:
        bbox = draw.textbbox((0, 0), line, font=zh_font)
        tw = bbox[2] - bbox[0]
        x = (RES_W - tw) // 2
        draw.text((x, y), line, font=zh_font, fill=SUB_ZH_COLOR[:3],
                  stroke_width=2, stroke_fill=SUB_STROKE[:3])
        y += zh_line_h

    # 底部装饰线
    line_y = RES_H // 2 + total_h // 2 + 40
    draw.rectangle([(RES_W // 4, line_y), (RES_W * 3 // 4, line_y + 2)],
                   fill=(180, 180, 120))

    png_path = os.path.join(tempfile.gettempdir(), "_title_card.png")
    img.save(png_path)

    # ── 渲染为视频（fade-in 效果）──
    fade_frames = max(1, int(TITLE_CARD_DUR * FPS * 0.5))
    n_frames = int(TITLE_CARD_DUR * FPS)
    cmd = [
        FFMPEG_PATH, "-y", "-loglevel", "error",
        "-loop", "1", "-i", png_path,
        "-t", str(TITLE_CARD_DUR),
        "-vf", (f"fps={FPS},"
                f"fade=in:0:{fade_frames},"
                f"fade=out:{n_frames - fade_frames}:{fade_frames}"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", PRESET, "-crf", str(CRF),
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    try:
        os.remove(png_path)
    except OSError:
        pass
    logger.info(f"  片头标题卡已生成: {out_path}")