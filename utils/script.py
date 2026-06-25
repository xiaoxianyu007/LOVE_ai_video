"""
utils/script.py — 文案读取：中英双语逐句配对
========================================
"""
import re
from pathlib import Path


_CN_NUMS = "零一二三四五六七八九十"

def _episode_to_patterns(episode):
    """把 1 → ["1", "一"], 2 → ["2", "二"] 等。"""
    cn = _CN_NUMS[episode] if episode < len(_CN_NUMS) else str(episode)
    return [str(episode), cn]


def _read_episode(path, episode=1):
    """
    读取指定集的文案。
    返回：(title, paragraphs) 列表

    支持标题格式：
      - 中文：第N集（一/二/三...）: 标题
      - 英文：Episode N: 标题  /  EP N: 标题
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"找不到文案: {path}")

    text = Path(path).read_text(encoding="utf-8")
    forms = _episode_to_patterns(episode)

    # 终止条件（任何形式的"其他集"标题）— 注意：必须排除当前集
    # Episode 2~99, EP 2~99, 第2集~第99集（中文数字也排除）
    # 关键：必须跟上 : 或 ：才是标题，避免误匹配"第八集团军"等
    cn_nums = "".join(_CN_NUMS)
    stop_lookahead = "|".join([
        rf"第[二三四五六七八九十百\d]{{1,3}}集\s*[:：]",
        rf"Episode\s+[2-9]\d*\s*[:：]",
        rf"EP\s+[2-9]\d*\s*[:：]",
    ])

    patterns = []
    for f in forms:
        # 中文：第N集：标题
        # 用 [\s\S]+?（非贪婪）匹配任意字符，停止条件：下一集标题或文件末尾
        patterns.append(rf"第{f}集[:：]([\s\S]+?)(?={stop_lookahead}|$)")
    # 英文：Episode N: 标题  /  EP N:
    patterns.append(rf"Episode\s+{episode}\s*[:：]([\s\S]+?)(?={stop_lookahead}|$)")
    patterns.append(rf"EP\s+{episode}\s*[:：]([\s\S]+?)(?={stop_lookahead}|$)")

    for pattern in patterns:
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if m:
            block = m.group(1).strip()
            # 按空行分段落
            parts = re.split(r'\n\s*\n', block)
            # 第一行是标题行（如果是单行 <50 字符，且后面有空行+正文）
            # 启发式：取首行作为标题，剩下的作为段落
            if len(parts) >= 2 and len(parts[0]) < 80 and parts[0].count('\n') == 0:
                # 首行无换行 → 当标题
                title = parts[0].strip()
                paragraphs = [p.strip() for p in parts[1:] if p.strip()]
            else:
                # 没明显标题，整个 block 当一段
                title = ""
                paragraphs = [block] if block else []
            return title, paragraphs

    raise ValueError(f"在 {path} 中找不到第{episode}集")


def _split_sentences(text):
    """按句末标点拆分。"""
    return [s.strip() for s in re.split(r'(?<=[。！？.!?])', text) if s.strip()]


def load_episode_sentences(en_path, zh_path, episode=1, n_sentences=None):
    """
    加载中英双语逐句配对。
    返回: (title_en, title_zh, [(en, zh), ...])
    """
    en_title, en_paras = _read_episode(en_path, episode)
    zh_title, zh_paras = _read_episode(zh_path, episode)

    en_sents, zh_sents = [], []
    for p in en_paras:
        en_sents.extend(_split_sentences(p))
    for p in zh_paras:
        zh_sents.extend(_split_sentences(p))

    # 对齐：取 min
    n = min(len(en_sents), len(zh_sents))
    if n_sentences:
        n = min(n, n_sentences)
    pairs = list(zip(en_sents[:n], zh_sents[:n]))
    return en_title, zh_title, pairs
