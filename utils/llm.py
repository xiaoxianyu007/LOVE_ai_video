"""
utils/llm.py — LLM 调用：英文句子 → 英文图像提示词
=============================================
关键设计：
  1. 复用 config 中的 LLM 配置
  2. JSON 解析健壮（截断/换行/尾部逗号）
  3. 失败回退：直接用原句作为提示词
"""
import json
import re
import time
import httpx
from loguru import logger

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


# 提示词模板：让 LLM 输出结构化 JSON
SYSTEM_PROMPT = """You are a visual scene describer for AI image generation. For each English sentence, output a concise visual scene description (30-50 words) matching the given artistic style.

RULES:
1. Describe exactly what the scene should look like: (a) main subject & action, (b) foreground elements, (c) background setting
2. Historical period-accurate clothing, architecture, weapons, vehicles, landscapes
3. Use the specified artistic style in every prompt
4. FORBIDDEN — NEVER describe or mention:
   - text, letters, words, numbers, typography, writing, captions, labels, signatures, watermarks, logos
   - flags, banners, national flags, party flags, military flags, any flag on poles or walls
   - emblems, badges, insignia, coats of arms, crests, medals, rank patches, armbands
   - political symbols (swastika, hammer and sickle, rising sun, eagle emblem, star emblem)
   - maps, charts, diagrams, cartography, atlas, globes, borders, territory outlines, compass
   - portraits of leaders, propaganda posters, slogans

Output format (JSON only, no explanation):
{"prompts": ["prompt1", "prompt2", ...]}"""


def _chat(messages, retries=3, timeout=60):
    """调用 OpenAI 兼容接口，带重试。"""
    for i in range(retries):
        try:
            r = httpx.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": LLM_MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"LLM 第{i+1}次失败: {e}")
            time.sleep(2)
    return None


def _parse_json(text):
    """从 LLM 输出中提取 JSON 数组，宽容处理截断/换行/代码块。"""
    # 1. 去 markdown 代码块
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    # 2. 找 JSON 块
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        # 3. 尝试修补：尾部缺 "}]"
        s = m.group(0).rstrip(", \n")
        if not s.endswith("]"):
            s += "]"
        if not s.endswith("}"):
            s += "}"
        try:
            return json.loads(s)
        except Exception:
            return None


def generate_image_prompts(sentences, style_hint=""):
    """
    输入：英文句子列表 + 系列风格提示
    输出：图像提示词列表（与输入一一对应，缺失时用原句兜底）
    """
    style = style_hint if style_hint else "documentary illustration"
    user = f"""Artistic style: {style}

Sentences:
{chr(10).join(f"{i+1}. {s}" for i, s in enumerate(sentences))}

Output JSON only."""

    raw = _chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])

    if raw is None:
        logger.warning("LLM 不可用，全部用原句兜底")
        return list(sentences)

    parsed = _parse_json(raw)
    if not parsed or "prompts" not in parsed:
        logger.warning(f"LLM 输出非 JSON: {raw[:200]}，全部用原句兜底")
        return list(sentences)

    prompts = parsed["prompts"]
    # 对齐长度
    while len(prompts) < len(sentences):
        prompts.append(sentences[len(prompts)])
    return prompts[:len(sentences)]
