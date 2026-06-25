# 文案撰写指南

## 文件格式

每集需要两个文件，放在 `data/` 目录下：

```
data/{系列名}_en.txt   # 英文文案
data/{系列名}_zh.txt   # 中文文案
```

### 格式要求

```
Episode 1: 英文标题
第一集：中文标题

英文段落1。英文段落2。英文段落3。

中文段落1。中文段落2。中文段落3。

Episode 2: 下一集标题
第二集：下一集中文标题

...
```

### 关键规则

1. **标题行**：`Episode N: Title`（英文）和 `第N集：标题`（中文），N 可以是数字（1, 2, 3...）或中文数字（一, 二, 三...）
2. **空行分隔**：用空行分隔不同段落
3. **句末标点**：每句必须以 `.` `!` `?`（英文）或 `。` `！` `？`（中文）结尾，程序以此拆分句子
4. **中英对齐**：中文和英文的句子数必须一致（程序取 min 对齐）
5. **集间分隔**：下一集标题行自动终止当前集

## 高质量文案要点

### 1. 句子长度

- 每句建议 **15-40 个中文字** 或 **10-25 个英文词**
- 太短（< 10 字）：TTS 语速过快，视差无时间展示
- 太长（> 70 字）：TTS 可能断句异常，观众听感疲劳

### 2. 避免 TTS 读错

TTS 是按标点断句的，以下情况会导致读错：

| 问题 | 示例 | 修正 |
|------|------|------|
| 缩写被拆开 | "U.S. Army" | 写成 "US Army" |
| 数字被逐字读 | "1941年" | ✅ 正确，TTS 会读"一九四一年" |
| 专有名词被拆 | "Pan-zer" | 写成 "Panzer" |
| 拼音被读成英文 | "Xi'an" | 写成 "西安" |
| 长词无标点 | "德军装甲师指挥部" | 加标点："德军装甲师，指挥部" |

### 3. 文案节奏

每集文案推荐结构：

```
开头（1-2句）→ 吸引注意，抛出悬念
引入（2-3句）→ 介绍时间地点人物
展开（3-5句）→ 核心事件描述
高潮（1-2句）→ 关键转折或成就
结局（1-2句）→ 留下悬念，为下一集铺垫
```

### 4. 绘画风格

每集文案应有对应的**绘画风格提示**，在 `config.py` 的 `SERIES_CONFIG` 中配置：

```python
"qin_empire": {
    "style": "Simple flat Chinese illustration, clean ink-like lines, "
             "minimalist composition, stylized ancient architecture",
    "neg": "nudity, modern elements, text, watermark, flag, banner, "
           "emblem, badge, map, chart, photorealistic, 3D render, "
           "low quality, blurry",
}
```

风格建议：
- 所有系列统一使用**扁平矢量插画风格**（flat vector illustration / graphic novel）
- **禁止**：文字、符号、旗帜、徽章、地图、政治符号、照片级写实、3D 渲染

### 5. 示例：隆美尔第1集

```
Episode 1: The Desert Fox Rises
第一集：沙漠之狐的崛起

In the spring of 1941, a German general arrived in Tripoli to salvage a desperate situation. His name was Erwin Rommel, and within weeks he would transform the North African campaign into a legend. The British called him the Desert Fox, a grudging tribute to his tactical brilliance and audacity. He was a master of mobile warfare, leading his Afrika Korps across the vast Libyan desert with breathtaking speed and precision.

1941年春，一位德国将军抵达的黎波里，他的任务是扭转北非战场的危局。他叫埃尔温·隆美尔，短短几周内就将北非战役变成了一段传奇。英国人叫他沙漠之狐，这是对他战术天才和胆略的无奈致敬。他是机动战的大师，率领非洲军团以惊人的速度和精准穿越广袤的利比亚沙漠。
```

## 添加新系列

1. 创建 `data/{系列名}_en.txt` 和 `data/{系列名}_zh.txt`
2. 在 `config.py` 的 `SERIES_CONFIG` 中添加条目（含风格提示词）
3. 运行：`python pipeline.py --episode 1 --all --series {系列名}`