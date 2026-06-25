"""
utils/subtitle.py — 双语字幕 PNG（透明底 · alpha 叠加）
=================================================
关键设计：
  1. 透明背景 → 无绿底、无遮挡（直接 alpha 叠加到视频）
  2. 字幕偏上（屏幕上方 6%~25% 区域）→ 不遮人物
  3. 中英双行：EN 在上（小字），ZH 在下（大字），黄色中文
  4. 字体回退：优先 Noto CJK → 文泉驿 → DejaVu → Pillow 默认
  5. 自动换行：按像素宽度折行，超出宽度自动断
  6. Pillow 原生 stroke_width + stroke_fill → 清晰描边，不糊
"""
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

# ═══════════════════════════════════════════════════════════
#  字体查找（优先 CJK → 西文）
# ═══════════════════════════════════════════════════════════
_FONT_CACHE = {}

def _find_font(size, bold=True):
    """查找第一个可用的字体，返回 ImageFont 实例。"""
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    candidates = []
    if bold:
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _FONT_CACHE[key] = font
                return font
            except Exception:
                continue
    # 终极回退
    font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def _wrap_text(draw, text, font, max_width):
    """按字符折行（中文友好）。"""
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def make_subtitle_png(en_text, zh_text, out_path,
                      width=720, height=1280,
                      en_size=28, zh_size=34,
                      en_color=(255, 255, 255, 255),        # 亮白英文
                      zh_color=(255, 255, 80, 255),          # 亮黄中文
                      stroke_color=(0, 0, 0, 160),           # 半透明黑描边
                      bg_alpha=200,                           # 背景条不透明度（78%）
                      max_text_width=660,
                      y_start_ratio=0.06):
    """
    生成透明底双语字幕 PNG（Pillow 原生 stroke 渲染）。

    参数
    ----
    en_size / zh_size : 字号（参考 720x1280 分辨率）
    y_start_ratio : 字幕起始 Y 坐标（0.0=顶部, 1.0=底部）
    bg_alpha : 背景条不透明度 (0-255)，行业推荐 70-80% → 180-204
    stroke_color : Pillow 原生 stroke_fill 颜色
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    en_font = _find_font(en_size, bold=True)
    zh_font = _find_font(zh_size, bold=True)

    # 折行
    en_lines = _wrap_text(draw, en_text, en_font, max_text_width) or [""]
    zh_lines = _wrap_text(draw, zh_text, zh_font, max_text_width) or [""]

    # 行高
    en_line_h = en_size + 10
    zh_line_h = zh_size + 10
    gap = 12
    total_h = len(en_lines) * en_line_h + len(zh_lines) * zh_line_h + gap

    y = int(height * y_start_ratio)

    # ── 计算文本实际宽度，用于背景自适应 ──
    max_tw = 0
    for line in en_lines:
        bbox = draw.textbbox((0, 0), line, font=en_font)
        max_tw = max(max_tw, bbox[2] - bbox[0])
    for line in zh_lines:
        bbox = draw.textbbox((0, 0), line, font=zh_font)
        max_tw = max(max_tw, bbox[2] - bbox[0])

    # ── 半透明黑底背景条（自适应文本宽度，带渐变边缘）──
    pad = 16
    bg_pad_x = 24                     # 左右额外留白
    bg_left = (width - max_tw) // 2 - bg_pad_x
    bg_right = (width - max_tw) // 2 + max_tw + bg_pad_x
    rect_top = max(0, y - pad)
    rect_bot = min(height, y + total_h + pad)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # 主体背景条
    od.rectangle([(bg_left, rect_top), (bg_right, rect_bot)],
                 fill=(0, 0, 0, bg_alpha))
    # 渐变边缘：上下各 5px 淡出
    for i in range(5):
        alpha = int(bg_alpha * (i + 1) / 6)
        od.rectangle([(bg_left, rect_top - 5 + i), (bg_right, rect_top - 5 + i + 1)],
                     fill=(0, 0, 0, alpha))
        od.rectangle([(bg_left, rect_bot + 4 - i), (bg_right, rect_bot + 5 - i)],
                     fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # ── Pillow 原生 stroke 渲染（清晰不糊）──
    def draw_text(draw_obj, xy, text, font, fill, stroke):
        draw_obj.text(xy, text, font=font, fill=fill,
                      stroke_width=2, stroke_fill=stroke)

    # ── EN 行 ──
    for line in en_lines:
        bbox = draw.textbbox((0, 0), line, font=en_font)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        draw_text(draw, (x, y), line, en_font, en_color, stroke_color)
        y += en_line_h

    y += gap

    # ── ZH 行 ──
    for line in zh_lines:
        bbox = draw.textbbox((0, 0), line, font=zh_font)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        draw_text(draw, (x, y), line, zh_font, zh_color, stroke_color)
        y += zh_line_h

    img.save(out_path, "PNG")