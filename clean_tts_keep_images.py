#!/usr/bin/env python3
"""
只删除 TTS 音频文件，保留所有图片。
用法：
  python clean_tts_keep_images.py          # 预览模式（不实际删除）
  python clean_tts_keep_images.py --do-it  # 实际执行删除
"""
import os
import sys
import shutil
from pathlib import Path

AUDIO_DIRS = [
    "output/audio",
    "output/audio_zh",
    "output/audio_en",
]

DO_IT = "--do-it" in sys.argv


def main():
    total_files = 0
    total_size = 0

    for adir in AUDIO_DIRS:
        if not os.path.isdir(adir):
            print(f"  [跳过] 目录不存在: {adir}")
            continue

        mp3_files = list(Path(adir).rglob("*.mp3"))
        if not mp3_files:
            print(f"  [空] {adir}")
            continue

        dir_size = sum(f.stat().st_size for f in mp3_files)
        total_files += len(mp3_files)
        total_size += dir_size

        print(f"\n  {adir}: {len(mp3_files)} 个 mp3, {dir_size/1024/1024:.1f} MB")

        for f in sorted(mp3_files):
            if DO_IT:
                f.unlink()
                print(f"    ✗ 已删除: {f}")
            else:
                print(f"    - {f}")

    print(f"\n{'='*60}")
    if DO_IT:
        print(f"  已删除: {total_files} 个 mp3 文件, 释放 {total_size/1024/1024:.1f} MB")
        # 清理空目录
        for adir in AUDIO_DIRS:
            for root, dirs, files in os.walk(adir, topdown=False):
                if not files and not dirs:
                    try:
                        os.rmdir(root)
                        print(f"  已清理空目录: {root}")
                    except OSError:
                        pass
    else:
        print(f"  预览模式: {total_files} 个 mp3 文件, 共 {total_size/1024/1024:.1f} MB")
        print(f"  加上 --do-it 参数执行实际删除")

    # 图片不受影响
    image_count = 0
    for root, dirs, files in os.walk("output"):
        image_count += sum(1 for f in files if f.endswith(".png"))
    print(f"  图片文件保留: {image_count} 个 .png")


if __name__ == "__main__":
    main()