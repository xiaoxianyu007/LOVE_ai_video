"""
utils/llm.py — LLM 调用：全篇英文文案 → 连贯图像提示词
=====================================================
核心理念：
  一次性输入一集全部文案，让 LLM 理解完整的叙事弧线、
  识别重复出现的角色/场景/道具，生成有场景衔接的连贯提示词。
  所有提示词生成完毕后再批量生图，保证视觉一致性。
"""
import json
import re
import time
import httpx
from loguru import logger

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


SYSTEM_PROMPT = """You are a narrative visual director for AI image generation. You receive a complete episode script (multiple sentences) and must produce a visually coherent storyboard with scene continuity.

WORKFLOW:
1. Read ALL sentences and understand the complete narrative arc
2. Identify recurring elements: characters, locations, props, visual motifs
3. Define canonical visual descriptions for each recurring element (used verbatim in prompts)
4. Write a scene plan mapping which sentences belong to which scene/location
5. Generate exactly one image prompt per sentence, ensuring visual continuity

CRITICAL RULES FOR PROMPTS:
- Each prompt is ONE visual scene (30-60 words)
- Every prompt MUST start with the exact artistic style phrase
- When a character appears in multiple prompts, COPY their canonical visual_desc verbatim
- When a location persists across sentences, COPY its canonical visual_desc verbatim
- Vary composition: wide establishing shots, medium action shots, close-ups for emotion
- If scene changes (e.g. palace to battlefield), describe the new location clearly
- Historical period-accurate clothing, architecture, weapons, vehicles, landscapes

FORBIDDEN — NEVER mention:
- text, letters, words, numbers, typography, writing, captions, labels, signatures, watermarks, logos
- flags, banners, national flags, party flags, military flags, any flag on poles or walls
- emblems, badges, insignia, coats of arms, crests, medals, rank patches, armbands
- political symbols (swastika, hammer and sickle, rising sun, eagle emblem, star emblem)
- maps, charts, diagrams, cartography, atlas, globes, borders, territory outlines, compass
- portraits of leaders, propaganda posters, slogans

OUTPUT FORMAT (JSON only, no explanation):
{
  "scene_plan": "Brief 2-3 sentence overview of the visual narrative arc",
  "recurring_elements": {
    "characters": [{"name": "ShortName", "visual_desc": "consistent physical description used in every prompt"}],
    "locations": [{"name": "LocationName", "visual_desc": "consistent setting description used in every prompt"}]
  },
  "prompts": ["prompt1", "prompt2", ...]
}"""


def _chat(messages, retries=3, timeout=180, max_tokens=16384):
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
                    "max_tokens": max_tokens,
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
    """从 LLM 输出中提取 JSON，宽容处理截断/换行/代码块。"""
    # 1. 去 markdown 代码块
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    # 2. 找最外层 JSON 块
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
    输入：英文句子列表（一整集） + 系列风格提示
    输出：图像提示词列表（与输入一一对应，缺失时用原句兜底）

    LLM 一次性看到全部文案，分析叙事弧线后生成连贯的提示词。
    """
    style = style_hint if style_hint else "documentary illustration"
    n = len(sentences)

    user = f"""Artistic style: {style}

Complete episode script ({n} sentences):
{chr(10).join(f"{i+1}. {s}" for i, s in enumerate(sentences))}

Generate {n} visually coherent image prompts. Output JSON only."""

    logger.info(f"  发送 {n} 句文案到 LLM，请求生成连贯提示词...")
    # 动态计算 max_tokens：每句预留 200 tokens（含 JSON 开销），最少 4096
    est_tokens = max(4096, n * 250)
    raw = _chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ], max_tokens=est_tokens)

    if raw is None:
        logger.warning("LLM 不可用，全部用原句兜底")
        return list(sentences)

    parsed = _parse_json(raw)
    if not parsed or "prompts" not in parsed:
        logger.warning(f"LLM 输出非 JSON: {raw[:200]}，全部用原句兜底")
        return list(sentences)

    # 日志输出场景规划
    if "scene_plan" in parsed:
        logger.info(f"  场景规划: {parsed['scene_plan'][:100]}...")
    if "recurring_elements" in parsed:
        chars = parsed["recurring_elements"].get("characters", [])
        locs = parsed["recurring_elements"].get("locations", [])
        if chars:
            logger.info(f"  重复角色: {len(chars)} 个")
        if locs:
            logger.info(f"  场景位置: {len(locs)} 个")

    prompts = parsed["prompts"]
    # 对齐长度
    if len(prompts) < n:
        logger.warning(f"LLM 仅返回 {len(prompts)} 条提示词（期望 {n}），用原句补齐")
        while len(prompts) < n:
            prompts.append(sentences[len(prompts)])
    elif len(prompts) > n:
        logger.warning(f"LLM 返回 {len(prompts)} 条提示词（期望 {n}），截断多余")
        prompts = prompts[:n]
    return prompts