"""
config.py — 所有可调参数集中（单文件修改即生效）
=============================================
用法：
  python pipeline.py --episode 1 --all
  python pipeline.py --episode 1 --all --series qin_empire
"""
import os

# ═══════════════════════════════════════════════════════════
#  系列选择（决定文案文件 + 绘画风格）
# ═══════════════════════════════════════════════════════════
SERIES = "rommel"   # 默认系列，命令行 --series 可覆盖

# 每个系列的配置
SERIES_CONFIG = {
    "rommel": {
        "script_en": "data/rommel_en.txt",
        "script_zh": "data/rommel_zh.txt",
        "style": "Hand-drawn battlefield sketch, war correspondent field journal illustration, "
                 "pencil and ink wash on aged paper, rough expressive lines, sepia tones, desert warfare theme",
        "neg": "nudity, bare skin, text, watermark, signature, logo, letters, words, "
               "typography, caption, label, writing, flag, banner, national flag, "
               "party flag, military flag, emblem, badge, insignia, coat of arms, "
               "crest, medal, rank patch, armband, swastika, hammer and sickle, "
               "rising sun, political symbol, map, chart, diagram, cartography, "
               "atlas, globe, border, territory, compass, portrait of leader, "
               "propaganda poster, slogan, banner with text, "
               "smooth vector art, clean digital lines, flat color blocks, "
               "modern elements, photorealistic, 3D render, realistic shading, "
               "detailed texture, complex background, hyperrealistic, "
               "cinematic lighting, Chinese people, Asian features, "
               "Chinese architecture, low quality, blurry, deformed, "
               "vibrant colors, saturated, polished illustration, anime, cartoon",
        "image_density": 1,
    },
    "qin_empire": {
        "script_en": "data/qin_empire_en.txt",
        "script_zh": "data/qin_empire_zh.txt",
        "style": "Flat Chinese ink illustration, clean brush-like lines, "
                 "minimalist composition, muted earth tones, ancient architecture and figures, paper texture background",
        "neg": "nudity, modern elements, Western architecture, text, watermark, "
               "signature, logo, letters, words, typography, caption, label, "
               "writing, flag, banner, national flag, emblem, badge, insignia, "
               "coat of arms, crest, medal, political symbol, map, chart, "
               "diagram, cartography, atlas, globe, border, territory, compass, "
               "portrait of leader, propaganda poster, slogan, banner with text, "
               "photorealistic, 3D render, realistic shading, detailed texture, "
               "complex background, hyperrealistic, cinematic lighting, "
               "low quality, blurry, deformed",
        "image_density": 1,
    },
    "enlightenment": {
        "script_en": "data/enlightenment_en.txt",
        "script_zh": "data/enlightenment_zh.txt",
        "style": "Flat vector illustration, clean bold lines, warm muted palette, "
                 "stylized 18th century European scenes, sparse composition, graphic novel aesthetic",
        "neg": "nudity, modern elements, text, watermark, signature, logo, letters, "
               "words, typography, caption, label, writing, flag, banner, "
               "national flag, emblem, badge, insignia, coat of arms, crest, "
               "medal, political symbol, map, chart, diagram, cartography, "
               "atlas, globe, border, territory, compass, portrait of leader, "
               "propaganda poster, slogan, banner with text, "
               "photorealistic, 3D render, realistic shading, detailed texture, "
               "complex background, hyperrealistic, cinematic lighting, "
               "low quality, blurry, deformed",
        "image_density": 1,
    },
    "european_theater": {
        "script_en": "data/european_theater_en.txt",
        "script_zh": "data/european_theater_zh.txt",
        "style": "Hand-drawn battlefield sketch, pencil and ink wash on aged paper, "
                 "rough expressive lines, sepia tones, European war ruins and rubble texture, documentary feel",
        "neg": "nudity, bare skin, text, watermark, signature, logo, letters, words, "
               "typography, caption, label, writing, flag, banner, national flag, "
               "party flag, military flag, emblem, badge, insignia, coat of arms, "
               "crest, medal, rank patch, armband, swastika, hammer and sickle, "
               "political symbol, map, chart, diagram, cartography, "
               "atlas, globe, border, territory, compass, portrait of leader, "
               "propaganda poster, slogan, banner with text, "
               "smooth vector art, clean digital lines, flat color blocks, "
               "modern elements, photorealistic, 3D render, realistic shading, "
               "detailed texture, complex background, hyperrealistic, "
               "cinematic lighting, low quality, blurry, deformed, "
               "vibrant colors, saturated, polished illustration, anime, cartoon",
        "image_density": 1,
    },
    "pacific_theater": {
        "script_en": "data/pacific_theater_en.txt",
        "script_zh": "data/pacific_theater_zh.txt",
        "style": "Hand-drawn battlefield sketch, pencil and ink wash on aged paper, "
                 "rough expressive lines, sepia tones, naval vessels and island landscapes, documentary feel",
        "neg": "nudity, bare skin, text, watermark, signature, logo, letters, words, "
               "typography, caption, label, writing, flag, banner, national flag, "
               "party flag, military flag, emblem, badge, insignia, coat of arms, "
               "crest, medal, rank patch, armband, rising sun, swastika, "
               "political symbol, map, chart, diagram, cartography, "
               "atlas, globe, border, territory, compass, portrait of leader, "
               "propaganda poster, slogan, banner with text, "
               "smooth vector art, clean digital lines, flat color blocks, "
               "modern elements, photorealistic, 3D render, realistic shading, "
               "detailed texture, complex background, hyperrealistic, "
               "cinematic lighting, low quality, blurry, deformed, "
               "vibrant colors, saturated, polished illustration, anime, cartoon",
        "image_density": 1,
    },
    "chu_han": {
        "script_en": "data/chu_han_en.txt",
        "script_zh": "data/chu_han_zh.txt",
        "style": "Chinese ink brush painting, ink wash on textured rice paper, "
                 "Han dynasty historical scenes, traditional costume and architecture, "
                 "warm earth tones, minimal composition, negative space",
        "neg": "text, watermark, signature, logo, letters, words, typography, caption, "
               "label, writing, modern elements, anachronisms, bright neon colors, "
               "saturated anime colors, 3D render, photorealistic, realistic shading, "
               "detailed texture, complex background, hyperrealistic, cinematic lighting, "
               "Western architecture, modern clothing, modern weapons, "
               "nudity, bare skin, deformed, blurry, low quality",
        "image_density": 1,
        "parallel_workers": 3,
    },
    "western_han": {
        "script_en": "data/western_han_en.txt",
        "script_zh": "data/western_han_zh.txt",
        "style": "Chinese ink brush painting, ink wash on textured rice paper, "
                 "Western Han dynasty historical scenes, court scenes, cavalry formations, "
                 "desert and steppe landscapes, Silk Road caravans, warm earth tones",
        "neg": "text, watermark, signature, logo, letters, words, typography, caption, "
               "label, writing, modern elements, anachronisms, bright neon colors, "
               "saturated anime colors, 3D render, photorealistic, realistic shading, "
               "detailed texture, complex background, hyperrealistic, cinematic lighting, "
               "Western architecture, modern clothing, modern weapons, "
               "nudity, bare skin, deformed, blurry, low quality",
        "image_density": 1,
        "parallel_workers": 3,
    },
}

# ═══════════════════════════════════════════════════════════
#  LLM（提示词生成）
# ═══════════════════════════════════════════════════════════
# 优先从环境变量 LLM_API_KEY 读取，否则使用默认值
LLM_API_KEY  = os.getenv("LLM_API_KEY", "sk-AZ2YS0JP3mr2QzS9nV0eJKYZ9Caeb0MVHlZ7kjWNe7yun6pE")
LLM_BASE_URL = "https://www.packyapi.com/v1"
LLM_MODEL    = "deepseek-v4-flash"

# ═══════════════════════════════════════════════════════════
#  ComfyUI（生图）
# ═══════════════════════════════════════════════════════════
COMFYUI_URL       = "http://127.0.0.1:8188"
COMFYUI_WORKFLOW  = "workflows/selfhost/image_flux.json"
COMFYUI_TIMEOUT   = 300    # 单图最长等待秒数
COMFYUI_RETRY     = 2      # 失败重试次数

# 图像尺寸（ComfyUI 输出）
IMAGE_W = 512
IMAGE_H = 896

# ═══════════════════════════════════════════════════════════
#  TTS（Edge-TTS · 标点增强 · 情感 · 双语言）
# ═══════════════════════════════════════════════════════════
TTS_VOICE_ZH   = "zh-CN-YunyangNeural"   # 中文男声 · 纪录片风格（低沉有力）
TTS_VOICE_EN   = "en-US-AriaNeural"      # 英文女声 · 自然度4.8/5清晰度4.9/5（替代发音不准的JennyNeural）

TTS_RATE       = "-15%"                  # 整体语速
TTS_PITCH      = "+0Hz"                  # 整体音高
TTS_BITRATE    = "128k"

# 兼容旧代码
TTS_VOICE      = TTS_VOICE_ZH

# 情感微调（按句末标点自动分类）
EMO_CALM       = ("-24%", "-6Hz")   # 平静
EMO_NORMAL     = (TTS_RATE, TTS_PITCH)
EMO_PASSIONATE = ("-10%", "+4Hz")   # 激昂
EMO_DRAMATIC   = ("-4%",  "+10Hz")  # 高潮

# ═══════════════════════════════════════════════════════════
#  视差（2.5D · 纯CPU remap · cubic ease-out 快速动效）
#  振幅参考：CapCut / AE 2.5D 模板，位移 15%~20% 画面宽
# ═══════════════════════════════════════════════════════════
PARALLAX_X  = 0.20   # 水平视差 20% 画面宽（原始值）
PARALLAX_Y  = 0.14   # 垂直视差 14% 画面高（原始值）
ZOOM_AMP    = 0.16   # 推拉幅度 16%（原始值）
DEPTH_GAMMA = 0.90   # 深度 gamma 拉伸
DEPTH_AMP   = 0.65   # 近景最大位移占比（原始值）
PERIOD      = 8.0    # 一周期秒数
PHASE       = 1.0

# 输出分辨率
RES_W       = 720
RES_H       = 1280
FPS         = 24

# motion 轮换池（7种，按顺序循环 — 业界经典动效）
MOTIONS = ["sweep_right", "sweep_left", "push_in", "rise", "drift_diagonal", "dolly_zoom", "focus_right"]

# ═══════════════════════════════════════════════════════════
#  视频合成
# ═══════════════════════════════════════════════════════════
XFADE_DUR      = 0.8    # 句间转场秒数
SILENCE_DUR    = 0.8    # 句间静音秒数
TITLE_CARD_DUR = 3.0    # 片头标题卡时长（秒）
CRF            = 26
PRESET         = "veryfast"

# ═══════════════════════════════════════════════════════════
#  字幕样式（Pillow 原生 stroke_width=2 渲染，清晰不糊）
#  行业标准：字高 5-7% 屏高，背景 78% 不透明度，2px 描边
# ═══════════════════════════════════════════════════════════
SUB_FONT_EN   = 20      # 英文字号
SUB_FONT_ZH   = 22      # 中文字号
SUB_Y_START   = 0.06     # 字幕起始位置
SUB_BG_ALPHA  = 200      # 背景条不透明度（78%）
SUB_EN_COLOR  = (255, 255, 255, 255)   # 亮白英文
SUB_ZH_COLOR  = (255, 255, 80, 255)    # 亮黄中文
SUB_STROKE    = (0, 0, 0, 160)         # 半透明黑描边（Pillow 原生）
SUB_MAX_WIDTH = 680

# ═══════════════════════════════════════════════════════════
#  文件路径
# ═══════════════════════════════════════════════════════════
OUTPUT_DIR     = "output"
AUDIO_DIR      = f"{OUTPUT_DIR}/audio"
AUDIO_DIR_ZH   = f"{OUTPUT_DIR}/audio_zh"
AUDIO_DIR_EN   = f"{OUTPUT_DIR}/audio_en"
SUBTITLE_DIR   = f"{OUTPUT_DIR}/subtitle"
TITLE_DIR      = f"{OUTPUT_DIR}/title"
FINAL_DIR      = f"{OUTPUT_DIR}/final"

# 兼容旧代码（默认系列）
IMAGES_DIR     = f"{OUTPUT_DIR}/images"
BG_DIR         = f"{OUTPUT_DIR}/bg"


def series_paths(series_name):
    """按系列隔离的图片/BG 目录，避免跨系列覆盖。"""
    base = f"{OUTPUT_DIR}/{series_name}"
    return {
        "images": f"{base}/images",
        "bg": f"{base}/bg",
    }

# 绝对路径（conda 环境）
FFMPEG_PATH  = "/home/shuju46/miniconda3/envs/pixelle_video/bin/ffmpeg"
FFPROBE_PATH = "/home/shuju46/miniconda3/envs/pixelle_video/bin/ffprobe"