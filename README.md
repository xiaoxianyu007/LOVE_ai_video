# AI Video Pipeline

全自动 AI 短视频生成流水线：**文案 → LLM 提示词 → ComfyUI 生图 → Edge-TTS 配音 → CPU 视差背景 → 字幕合成**。

支持 8 个历史纪录片系列（楚汉争霸 5 集、西汉 40 集、拿破仑 22 集、隆美尔、秦帝国等）。

---

## 快速开始

```bash
# 1. 激活环境
conda activate pixelle_video

# 2. 进入项目
cd ~/Oray/Mi/Pixelle-Video/ai_video_pipeline

# 3. 单集测试（已有图片则跳过生图）
python pipeline.py --episode 1 --all --skip-image --skip-llm

# 4. 批量运行全部 45 集（楚汉 5 + 西汉 40）
bash batch_run.sh
```

## 批量运行

```bash
bash batch_run.sh                     # 全部 45 集
bash batch_run.sh chu_han             # 楚汉争霸 5 集
bash batch_run.sh western_han         # 西汉 40 集
bash batch_run.sh western_han 1-10    # 西汉 1-10 集
bash batch_run.sh chu_han 3-5         # 楚汉 3-5 集
```

## 支持系列

| 系列 | 集数 | 绘画风格 | 文案文件 |
|------|------|---------|---------|
| `chu_han` | 5 | 新国风数字工笔重彩 | `data/chu_han_{en,zh}.txt` |
| `western_han` | 40 | 新国风数字工笔重彩 | `data/western_han_{en,zh}.txt` |
| `rommel` | — | 扁平矢量插画 | `data/rommel_{en,zh}.txt` |
| `qin_empire` | — | 扁平中式插画 | `data/qin_empire_{en,zh}.txt` |
| `enlightenment` | 22 | 扁平矢量插画 | `data/enlightenment_{en,zh}.txt` |
| `european_theater` | — | 扁平矢量插画 | `data/european_theater_{en,zh}.txt` |
| `pacific_theater` | — | 扁平矢量插画 | `data/pacific_theater_{en,zh}.txt` |

## 命令行参数

| 参数 | 说明 |
|------|------|
| `--episode N` | 集号（必填） |
| `--all` | 处理该集所有句子 |
| `--n N` | 只处理前 N 句（默认 3） |
| `--series {name}` | 系列名（见上表） |
| `--skip-image` | 跳过 ComfyUI 生图（已有图片则跳过，缺失自动补生成） |
| `--skip-tts` | 跳过 TTS 语音合成 |
| `--skip-llm` | 跳过 LLM 提示词生成（直接用英文原文作 prompt） |
| `--force` | 强制重新生成，忽略所有缓存 |
| `--lang en` | TTS 语言（仅英文，中文 TTS 断词问题已移除） |

## 6 阶段管线

```
文案文件 → 阶段1 加载文案（中英逐句配对）
         → 阶段2 LLM 提示词（DeepSeek v4，英文句子→生图 prompt）
         → 阶段3 ComfyUI 生图（Flux 模型，确定性 seed 防抖动）
         → 阶段4 Edge-TTS 配音（AriaNeural，4线程并行）
         → 阶段5 CPU 视差背景（7种运镜轮换）
         → 阶段6 合成（片头 → xfade 转场 → 双语字幕 → 音频 → 输出）
```

### 阶段1：加载文案
- 从 `data/{系列名}_{en,zh}.txt` 读取中英双语脚本
- 正则匹配 `Episode N: Title` / `第N集：标题` 自动分集
- 中英句子 1:1 配对，取 min 长度对齐

### 阶段2：LLM 提示词
- 调用 DeepSeek v4 将英文句子转为 ComfyUI 生图 prompt
- 自动拼接系列风格词（config.py 中的 `style` 字段）
- 支持 `--skip-llm` 跳过，直接用英文原文作 prompt

### 阶段3：ComfyUI 生图
- 调用本地 ComfyUI（http://127.0.0.1:8188）
- 确定性 seed = `episode * 1000 + i`，保证重跑结果一致
- 断点续跑：文件存在则跳过，缺失自动补生成
- 兜底：ComfyUI 失败时生成纯色图，不中断流程

### 阶段4：Edge-TTS 配音
- 仅英文 TTS：`en-US-AriaNeural`（自然度 4.8/5，清晰度 4.9/5）
- 情感微调：按句末标点自动分类（平静/正常/激昂/高潮），调整语速和音高
- 4 线程并行生成，逐句缓存
- 时长兜底：TTS 失败时返回 0 秒，不影响后续流程

### 阶段5：CPU 视差背景
- 纯 CPU remap 实现，无需 GPU
- 7 种运镜按顺序循环：sweep_right / sweep_left / push_in / rise / drift_diagonal / dolly_zoom / focus_right
- 振幅：水平 20% 画面宽，垂直 14% 画面高，推拉 16%
- 每句时长 = TTS 时长 + 句间静音（0.8s）
- 缓存检测：源图未更新则跳过

### 阶段6：合成
- 片头标题卡（3s，含英文和中文标题）
- 背景 xfade 交叉淡化转场（0.8s）
- 音频 concat 拼接（句间 0.8s 静音）
- 双语字幕：英文白色在上，中文亮黄在下，半透明黑底
- alpha 叠加合成 → 输出 `final/ep{XX}_{series}.mp4`

## 资源隔离

每集的图片、TTS、背景视频均按 `ep{episode:02d}` 子目录隔离，**杜绝跨集复用**：

```
output/western_han/images/ep01/img_000.png   # 第 1 集图片
output/western_han/images/ep02/img_000.png   # 第 2 集图片（完全独立）
output/audio_en/ep01/aud_000.mp3             # 第 1 集 TTS
output/audio_en/ep02/aud_000.mp3             # 第 2 集 TTS（完全独立）
output/western_han/bg/ep01/bg_000.mp4        # 第 1 集视差背景
output/western_han/bg/ep02/bg_000.mp4        # 第 2 集视差背景（完全独立）
```

## 项目结构

```
ai_video_pipeline/
├── config.py              # 所有可调参数（单文件改完即生效）
├── pipeline.py            # 6 阶段主流程
├── batch_run.sh           # 批量运行脚本（楚汉 + 西汉）
├── README.md
├── SCRIPT_GUIDE.md        # 文案撰写指南（格式 + 规则 + 示例）
├── utils/
│   ├── script.py          # 中英双语逐句配对 + 自动分集
│   ├── llm.py             # LLM 调用（句子→图像提示词）
│   ├── comfyui.py         # ComfyUI HTTP 客户端（生图 + 轮询）
│   ├── tts.py             # Edge-TTS（标点增强 + 情感微调 + 防截断）
│   ├── depth.py           # CPU 伪深度图生成（sobel + 高斯模糊）
│   ├── parallax.py        # 纯 CPU remap 视差动效
│   ├── subtitle.py        # 透明底中英双语字幕（Pillow 渲染）
│   └── ffmpeg.py          # 音视频合成（concat filter + overlay alpha）
├── workflows/
│   └── selfhost/
│       └── image_flux.json # ComfyUI 工作流（Flux 生图）
├── data/
│   ├── western_han_zh.txt  # 西汉中文文案（40 集，约 550 句）
│   ├── western_han_en.txt  # 西汉英文文案（40 集）
│   ├── chu_han_zh.txt      # 楚汉中文文案（5 集）
│   ├── chu_han_en.txt      # 楚汉英文文案（5 集）
│   ├── enlightenment_*.txt # 拿破仑/启蒙系列文案
│   ├── rommel_*.txt        # 隆美尔系列文案
│   ├── qin_empire_*.txt    # 秦帝国系列文案
│   └── ...                 # 其他系列文案
└── output/                # 自动生成（已 gitignore）
    ├── {series}/images/ep{XX}/   # 生图缓存
    ├── {series}/bg/ep{XX}/       # 视差背景视频
    ├── audio_en/ep{XX}/          # 英文 TTS 音频
    ├── audio_zh/                 # 中文 TTS（未使用）
    ├── title/                    # 片头标题卡
    ├── subtitle/                 # 字幕 PNG（临时）
    └── final/                    # 最终成片
```

## 参数调优

所有参数在 `config.py` 顶部，改完即生效：

```python
# ── 系列配置 ──
SERIES = "rommel"                              # 默认系列
SERIES_CONFIG = {                              # 每个系列的风格/文案/负面提示词
    "western_han": {
        "script_en": "data/western_han_en.txt",
        "script_zh": "data/western_han_zh.txt",
        "style": "New Chinese Style Digital Gongbi...",
        "neg": "text, watermark, modern elements...",
        "image_density": 1,
        "parallel_workers": 3,                 # ComfyUI 并行数
    },
    ...
}

# ── LLM ──
LLM_API_KEY  = os.getenv("LLM_API_KEY", "...")  # DeepSeek API Key
LLM_BASE_URL = "https://www.packyapi.com/v1"
LLM_MODEL    = "deepseek-v4-flash"

# ── ComfyUI ──
COMFYUI_URL       = "http://127.0.0.1:8188"    # ComfyUI 地址
COMFYUI_TIMEOUT   = 300                        # 单图最长等待（秒）
COMFYUI_RETRY     = 2                          # 失败重试次数
IMAGE_W, IMAGE_H  = 512, 896                   # 输出尺寸

# ── TTS ──
TTS_VOICE_EN = "en-US-AriaNeural"              # 英文女声（推荐）
TTS_RATE     = "-15%"                          # 语速
TTS_PITCH    = "+0Hz"                          # 音高

# ── 视差 ──
PARALLALLAX_X  = 0.20                          # 水平振幅（20% 画面宽）
PARALLAX_Y  = 0.14                             # 垂直振幅
ZOOM_AMP    = 0.16                             # 推拉幅度
PERIOD      = 8.0                              # 周期（秒）
MOTIONS = ["sweep_right", "sweep_left", "push_in", "rise",
           "drift_diagonal", "dolly_zoom", "focus_right"]

# ── 合成 ──
RES_W, RES_H    = 720, 1280                    # 输出分辨率
FPS             = 24
XFADE_DUR       = 0.8                          # 转场时长
SILENCE_DUR     = 0.8                          # 句间静音
TITLE_CARD_DUR  = 3.0                          # 片头时长

# ── 字幕 ──
SUB_FONT_EN     = 20                           # 英文字号
SUB_FONT_ZH     = 22                           # 中文字号
SUB_Y_START     = 0.06                         # 距顶部比例
SUB_EN_COLOR    = (255, 255, 255, 255)         # 亮白英文
SUB_ZH_COLOR    = (255, 255, 80, 255)          # 亮黄中文
```

## 添加新系列

1. 创建 `data/{系列名}_en.txt` 和 `data/{系列名}_zh.txt`（格式见 `SCRIPT_GUIDE.md`）
2. 在 `config.py` 的 `SERIES_CONFIG` 中添加条目（含风格提示词和负面提示词）
3. 运行：`python pipeline.py --episode 1 --all --series {系列名}`

## 断点续跑

所有阶段均支持缓存，第二次运行自动跳过已生成的文件：

| 阶段 | 缓存路径 | 跳过条件 |
|------|---------|---------|
| ComfyUI 生图 | `output/{series}/images/ep{XX}/img_{NNN}.png` | 文件存在 |
| TTS 音频 | `output/audio_en/ep{XX}/aud_{NNN}.mp3` | 文件存在 + 时长 > 0 |
| 视差背景 | `output/{series}/bg/ep{XX}/bg_{NNN}.mp4` | 文件存在 且 源图 mtime ≤ bg mtime |
| 字幕 PNG | `output/subtitle/sub_{NNN}.png` | 文件存在（非 force） |
| 片头标题卡 | `output/title/title_{series}_ep{NN}_{lang}.mp4` | 文件存在 |

加 `--force` 忽略所有缓存，强制重新生成全部内容。

## 依赖

- Python 3.10+
- conda 环境 `pixelle_video`
- 核心库：opencv-python, numpy, edge-tts, pillow, httpx, loguru
- FFmpeg（环境内安装）
- (可选) ComfyUI + Flux 模型用于生图

## 许可

MIT