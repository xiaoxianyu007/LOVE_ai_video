"""
utils/tts.py — Edge-TTS 语音合成（带标点增强+情感微调）
=================================================
"""
import asyncio
import os
import re
import subprocess
import tempfile
from pathlib import Path

import edge_tts
from loguru import logger

from config import (
    TTS_VOICE, TTS_RATE, TTS_PITCH,
    EMO_CALM, EMO_NORMAL, EMO_PASSIONATE, EMO_DRAMATIC,
    FFMPEG_PATH, FFPROBE_PATH,
)

# 并发控制：Edge-TTS 单 IP 建议 ≤ 5 并发
_SEM = asyncio.Semaphore(5)

_COMMA_BEFORE = [
    "然而", "但是", "因此", "于是", "接着", "最后", "最终",
    "不过", "可是", "所以", "此外", "同时", "随后", "此后",
]

_COMMA_PATTERNS = [
    (r'(?<=。)(\d{4}年)',         r'，\1'),
    (r'(?<=。)(到了\d{4}年)',      r'，\1'),
    (r'(?<=。)(在.{2,8}，)',       r'，\1'),
]


def _enhance_text(text: str) -> str:
    for ch in ['\u200b', '\u200c', '\u200d', '\ufeff', '\ufffd']:
        text = text.replace(ch, '')
    for word in _COMMA_BEFORE:
        text = re.sub(rf'(?<![，。！？、：；\s]){word}', rf'，{word}', text)
    for pat, repl in _COMMA_PATTERNS:
        text = re.sub(pat, repl, text)
    parts = re.split(r'([，。！？、：；])', text)
    result = []
    for i, chunk in enumerate(parts):
        if len(chunk) > 70 and i % 2 == 0:
            best = -1
            for m in re.finditer(r'(?<=[了的是在和把与被将从后前也而])', chunk):
                if 25 < m.start() < len(chunk) - 15:
                    best = m.start()
            if best > 0:
                result.append(chunk[:best] + '，')
                result.append(chunk[best:])
            else:
                result.append(chunk)
        else:
            result.append(chunk)
    return ''.join(result).strip()


def _split_sentences(text: str):
    return [s.strip() for s in re.split(r'(?<=[。！？.!?])', text) if s.strip()]


def _classify(s: str):
    if not s: return "normal"
    if s.endswith(("！", "!")):
        return "dramatic" if (s.count("！") + s.count("!")) > 1 else "passionate"
    if s.endswith(("？", "?")):
        return "passionate"
    if len(s) > 60:
        return "calm"
    return "normal"


_EMO_MAP = {
    "calm": EMO_CALM, "normal": EMO_NORMAL,
    "passionate": EMO_PASSIONATE, "dramatic": EMO_DRAMATIC,
}


async def _gen_one_async(text, rate, pitch, out, voice):
    """核心 TTS 生成（无并发控制，由调用方管理）。"""
    cleaned = text.strip()
    if not cleaned or len(cleaned) <= 1:
        subprocess.run(
            [FFMPEG_PATH, "-y", "-f", "lavfi", "-i",
             "anullsrc=r=24000:cl=mono,atrim=duration=1.0",
             "-ac", "1", "-ar", "24000", out],
            capture_output=True, timeout=30)
        return
    # 最低合理时长估算：中文 0.2s/字，英文 0.25s/词（约为 0.05s/字符）
    if _is_english(cleaned):
        word_count = len(cleaned.split())
        min_dur = max(0.5, word_count * 0.25)
    else:
        min_dur = max(0.5, len(cleaned) * 0.2)
    for attempt in range(5):
        try:
            await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(out)
            dur = _probe_dur(out)
            if dur >= min_dur:
                return
            logger.warning(f"  TTS 时长异常 {dur:.1f}s < {min_dur:.1f}s，重试{attempt+1}: {text[:20]}")
            await asyncio.sleep(3)
        except Exception as e:
            logger.warning(f"  TTS 重试{attempt+1}: {e}")
            await asyncio.sleep(3)
    raise RuntimeError(f"TTS 5次失败: {text[:30]}")


async def _gen_one_sem(text, rate, pitch, out, voice):
    """带并发限流的单次 TTS 生成。"""
    async with _SEM:
        await _gen_one_async(text, rate, pitch, out, voice)


def _probe_dur(path):
    try:
        r = subprocess.run(
            [FFPROBE_PATH, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10)
        return float(r.stdout.strip()) if r.stdout.strip() else 0.0
    except Exception:
        return 0.0


def _subsplit_long(text: str):
    """Edge-TTS 超过 8 字容易截断末尾字，必须拆小。最小 chunk 3 字。"""
    MAX_CHUNK = 8
    MIN_CHUNK = 3
    if len(text) <= MAX_CHUNK:
        return [text]
    # 按标点拆分，保留标点
    parts = re.split(r'(?<=[，。！？,.!?])', text)
    result = []
    buf = ""
    for p in parts:
        if len(buf) + len(p) <= MAX_CHUNK:
            buf += p
        else:
            if buf:
                result.append(buf)
            buf = p
    if buf:
        result.append(buf)
    # 兜底：硬切超长段，保证每段 ≥ MIN_CHUNK
    final = []
    for chunk in result:
        while len(chunk) > MAX_CHUNK:
            cut = max(MIN_CHUNK, min(MAX_CHUNK, len(chunk) - MIN_CHUNK))
            final.append(chunk[:cut])
            chunk = chunk[cut:]
        if chunk:
            final.append(chunk)
    return final if final else [text]


def _is_english(text: str) -> bool:
    """判断文本是否主要为英文（ASCII 占比 > 60%）。"""
    if not text:
        return False
    ascii_count = sum(1 for c in text if ord(c) < 128)
    return ascii_count / len(text) > 0.6


async def _generate_async(text: str, output_path: str, voice: str = None) -> float:
    """异步版本：英文直接整句生成，中文走分词增强逻辑。"""
    voice = voice or TTS_VOICE

    if _is_english(text):
        # 英文：跳过中文分词/增强逻辑，直接整句生成
        rate, pitch = _EMO_MAP[_classify(text)]
        await _gen_one_async(text, rate, pitch, output_path, voice)
        return _probe_dur(output_path)

    # 中文：走原有的增强+分词+chunk 逻辑
    text = _enhance_text(text)
    sentences = _split_sentences(text) or [text]

    all_segs = []
    for s in sentences:
        all_segs.extend(_subsplit_long(s))

    if len(all_segs) == 1:
        rate, pitch = _EMO_MAP[_classify(all_segs[0])]
        await _gen_one_async(all_segs[0], rate, pitch, output_path, voice)
        return _probe_dur(output_path)

    # 并发生成所有 chunk
    segs = []
    async def _gen_chunk(idx, s):
        rate, pitch = _EMO_MAP[_classify(s)]
        sp = os.path.join(tempfile.gettempdir(), f"_tts_{idx}.mp3")
        await _gen_one_sem(s, rate, pitch, sp, voice)
        d = _probe_dur(sp)
        if d < 0.2:
            logger.warning(f"  ⚠ chunk{idx} 时长异常 ({d:.1f}s): {s[:20]}")
        return (idx, sp)

    tasks = [_gen_chunk(i, s) for i, s in enumerate(all_segs)]
    results = await asyncio.gather(*tasks)
    segs = [sp for _, sp in sorted(results)]

    tmp = output_path.replace(".mp3", "_c.mp3")
    try:
        # concat filter 重编码
        inputs = []
        for sp in segs:
            inputs.extend(["-i", sp])
        n = len(segs)
        filter_parts = "".join(f"[{i}:a]" for i in range(n))
        filter_str = f"{filter_parts}concat=n={n}:v=0:a=1[out]"
        subprocess.run(
            [FFMPEG_PATH, "-y"] + inputs +
            ["-filter_complex", filter_str, "-map", "[out]",
             "-c:a", "mp3", "-q:a", "2", tmp],
            capture_output=True, timeout=120, check=True)
        total_dur = _probe_dur(tmp)
        expected = sum(_probe_dur(sp) for sp in segs)
        if total_dur < expected * 0.85:
            raise RuntimeError(f"拼接时长异常: {total_dur:.1f}s < {expected:.1f}s")
        os.replace(tmp, output_path)
    except Exception as e:
        logger.warning(f"  TTS 拼接失败: {e}，降级为单次完整请求")
        for sp in segs:
            try: os.remove(sp)
            except OSError: pass
        try:
            rate, pitch = _EMO_MAP[_classify(text)]
            await _gen_one_async(text, rate, pitch, tmp, voice)
            d = _probe_dur(tmp)
            if d > 0.5:
                os.replace(tmp, output_path)
            else:
                raise RuntimeError(f"单次完整请求时长异常: {d:.1f}s")
        except Exception as e2:
            logger.warning(f"  单次完整请求也失败: {e2}，使用静音")
            subprocess.run(
                [FFMPEG_PATH, "-y", "-f", "lavfi", "-i",
                 "anullsrc=r=24000:cl=mono,atrim=duration=3.0",
                 "-ac", "1", "-ar", "24000", output_path],
                capture_output=True, timeout=30)
    for sp in segs:
        try: os.remove(sp)
        except OSError: pass
    return _probe_dur(output_path)


def generate(text: str, output_path: str, voice: str = None) -> float:
    """同步入口：单句 TTS 合成。"""
    return asyncio.run(_generate_async(text, output_path, voice))