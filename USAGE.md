# AI Video Pipeline 使用指南

## 项目结构

```
ai_video_pipeline/          # 主项目目录（conda: pixelle_video）
├── config.py               # 所有可调参数集中管理
├── pipeline.py             # 主流程：6 阶段全自动生成短视频
├── fix_pinyin.py           # 修复英文文案拼音→音标（解决 TTS 逐字母念问题）
├── clean_tts_keep_images.py # 只删除 TTS 音频，保留图片
├── data/                   # 文案文件
│   ├── rommel_en/zh.txt        # 隆美尔系列（二战北非）
│   ├── european_theater_en/zh.txt  # 欧洲战场（二战）
│   ├── pacific_theater_en/zh.txt   # 太平洋战场（二战）
│   ├── qin_empire_en/zh.txt       # 秦帝国
│   ├── enlightenment_en/zh.txt    # 启蒙运动
│   ├── chu_han_en/zh.txt          # 楚汉争霸
│   └── western_han_en/zh.txt      # 西汉
├── utils/                  # 各阶段工具
│   ├── script.py           # 文案加载、分句
│   ├── llm.py              # LLM 生成图像提示词
│   ├── comfyui.py          # ComfyUI API 客户端
│   ├── tts.py              # Edge-TTS 语音生成
│   ├── parallax.py         # 2.5D 视差动效（纯 CPU remap）
│   ├── subtitle.py         # 字幕 PNG 生成
│   ├── ffmpeg.py           # FFmpeg 合成
│   └── depth.py            # 伪深度图生成
├── workflows/              # ComfyUI 工作流 JSON
│   ├── selfhost/           # 自部署工作流
│   │   ├── image_flux.json       # Flux 生图
│   │   └── image_qwen.json       # Qwen 生图
│   └── runninghub/         # RunningHub 工作流
│       ├── image_flux.json
│       ├── image_qwen.json
│       └── ...
├── output/                 # 输出目录（gitignore）
└── workflows/              # ComfyUI 工作流（软链到上级）
```

## 环境要求

### Conda 环境

| 用途 | Conda 环境 | 说明 |
|------|-----------|------|
| **本项目** | `pixelle_video` | 运行 pipeline.py 等所有代码 |
| **ComfyUI** | `zimage` | 启动 ComfyUI 生图服务 |

```bash
# 激活本环境
conda activate pixelle_video

# ComfyUI 单独的环境（启动 ComfyUI 时使用）
conda activate zimage
```

### ComfyUI

- **路径**: `/home/shuju46/.Mao_data/comfyui/`
- **环境**: `zimage`
- **工作流 JSON**: `ai_video_pipeline/workflows/selfhost/image_flux.json`
- **端口**: `http://127.0.0.1:8188`

启动方式：
```bash
conda activate zimage
cd /home/shuju46/.Mao_data/comfyui
python main.py
```

### FFmpeg

- **绝对路径**: `/home/shuju46/miniconda3/envs/pixelle_video/bin/ffmpeg`
- 由 config.py 中的 `FFMPEG_PATH` 指定

## 快速开始

### 生成单集视频

```bash
conda activate pixelle_video
cd /home/shuju46/Oray/Mi/Pixelle-Video/ai_video_pipeline

# 生成第 1 集（默认系列 rommel）
python pipeline.py --episode 1 --all

# 指定系列生成
python pipeline.py --episode 3 --all --series western_han
python pipeline.py --episode 1 --all --series chu_han
```

### 跳过某阶段

```bash
# 跳过生图（使用已有图片）
python pipeline.py --episode 1 --skip-image

# 跳过 LLM 提示词生成
python pipeline.py --episode 1 --skip-llm

# 跳过全部已有阶段（只重新合成视频）
python pipeline.py --episode 1 --skip-image --skip-llm
```

## 6 阶段流程详解

```
阶段 1/6: 加载文案       → data/*_en.txt + *_zh.txt → 按 episode 切分
阶段 2/6: LLM 生成提示词 → 英文文案 → LLM → 图像 prompt
阶段 3/6: ComfyUI 生图   → prompt → ComfyUI API → PNG
阶段 4/6: TTS 语音       → 中/英文 → Edge-TTS → MP3
阶段 5/6: 视差动效       → PNG + 深度图 → 2.5D 视差视频 → MP4
阶段 6/6: 合成           → 视频片段 + 音频 + 字幕 → 最终视频
```

## 可用系列

| 配置 Key | 系列 | 绘画风格 |
|----------|------|----------|
| `rommel` | 隆美尔（二战北非） | 战地记者手绘速写 |
| `european_theater` | 欧洲战场（二战） | 战地记者手绘速写 |
| `pacific_theater` | 太平洋战场（二战） | 战地记者手绘速写 |
| `qin_empire` | 秦帝国 | 中国风扁平插画 |
| `chu_han` | 楚汉争霸 | 新国风数字工笔重彩 |
| `western_han` | 西汉 | 新国风数字工笔重彩 |
| `enlightenment` | 启蒙运动 | 扁平矢量插画 |

## 参数调优

所有参数集中在 `config.py` 一个文件中，修改即生效：

### 视差动效参数

```python
PARALLAX_X  = 0.20   # 水平位移幅度（20%画面宽）
PARALLAX_Y  = 0.14   # 垂直位移幅度（14%画面高）
ZOOM_AMP    = 0.16   # 缩放幅度
DEPTH_AMP   = 0.65   # 深度影响强度
```

sweep_left/right 已在 parallax.py 中单独降低 70%，修改 config.py 中以上参数会影响所有动效。

### TTS 语音

```python
TTS_VOICE_ZH = "zh-CN-YunyangNeural"   # 中文：云扬（纪录片男声）
TTS_VOICE_EN = "en-US-AriaNeural"      # 英文：Aria（女声）
```

### 输出分辨率

```python
RES_W = 720   # 宽
RES_H = 1280  # 高（竖屏 9:16）
FPS   = 24
```

### 绘画风格

每个系列在 `SERIES_CONFIG` 中有 `style`（正面提示词）和 `neg`（负面提示词）两个字段，修改后下次生图生效。

## 辅助脚本

### 修复英文文案拼音发音

```
功能：将中文拼音转为英文可读音标，解决 TTS 逐字母念拼音的问题
      例如：Han Xin → Hahn Sheen, Xiang Yu → Shyahng Yoo

用法：python fix_pinyin.py
```

该脚本会修改 `data/*_en.txt` 文件，将拼音替换为音标拼写。

### 清理 TTS 音频

```bash
# 预览（不实际删除）
python clean_tts_keep_images.py

# 执行删除
python clean_tts_keep_images.py --do-it
```

保留所有图片 `.png`，只删除输出目录下的 mp3 文件。

## 输出目录结构

```
output/
├── {series_name}/         # 按系列隔离
│   ├── images/ep{nn}/     # ComfyUI 生成的 PNG
│   └── bg/ep{nn}/         # 视差动效渲染的 MP4
├── audio_en/ep{nn}/       # 英文 TTS MP3
├── audio_zh/ep{nn}/       # 中文 TTS MP3
├── subtitle/              # 字幕 PNG
├── title/                 # 标题卡
└── final/                 # 最终合成视频
```

## 常见问题

### Q: 动效太强 / 太弱？
调整 `config.py` 中的 `PARALLAX_X`、`ZOOM_AMP`、`DEPTH_AMP`。sweep_left/right 已单独降低 70%，如需调整到其他比例，修改 `utils/parallax.py` 中对应 motion 的倍率。

### Q: TTS 发音不准？
- 英文文案有中文拼音 → 运行 `python fix_pinyin.py` 自动转换
- TTS 音色不满意 → 修改 `config.py` 中的 `TTS_VOICE_ZH` 和 `TTS_VOICE_EN`
- 语速/音高 → 修改 `TTS_RATE` 和 `TTS_PITCH`
