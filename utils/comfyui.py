"""
utils/comfyui.py — ComfyUI 客户端：提示词 → 图片
=============================================
关键设计：
  1. 启动检查：服务未启动直接报错（不默默等待）
  2. 断点续跑：已下载图片跳过
  3. Workflow 注入：替换 CLIPTextEncode 文本 + KSampler 随机种子
  4. 轮询 + 重试
"""
import json
import os
import time
import uuid
from pathlib import Path

import httpx
from loguru import logger

from config import (
    COMFYUI_URL, COMFYUI_TIMEOUT, COMFYUI_RETRY,
    IMAGE_W, IMAGE_H, COMFYUI_WORKFLOW, SERIES_CONFIG,
)


def _check_alive():
    """启动检查：服务挂了直接抛错。"""
    try:
        r = httpx.get(f"{COMFYUI_URL}/prompt", timeout=5)
        if r.status_code != 200:
            raise RuntimeError(f"ComfyUI 返回 {r.status_code}")
        return True
    except Exception as e:
        raise RuntimeError(
            f"ComfyUI 未启动或不可用 ({COMFYUI_URL})\n"
            f"  启动命令: cd ~/.Mao_data/comfyui && conda activate zimage "
            f"&& python main.py --listen 127.0.0.1 --port 8188\n"
            f"  错误: {e}"
        )


def _find_text_nodes(workflow):
    """在工作流中找 CLIPTextEncode 节点，区分正负面。

    text 字段可能是字符串（硬编码）或列表（节点引用），
    无法直接用 text.lower() 判断时，通过节点 title 辅助区分。
    """
    positives, negatives = [], []
    unclassified = []

    for nid, node in workflow.items():
        if node.get("class_type") != "CLIPTextEncode":
            continue

        text = node.get("inputs", {}).get("text", "")
        title = node.get("_meta", {}).get("title", "")

        # 按 text 内容判断（仅当为字符串时）
        if isinstance(text, str):
            if any(k in text.lower() for k in ["positive", "pos"]):
                positives.append(nid)
                continue
            if any(k in text.lower() for k in ["negative", "neg"]):
                negatives.append(nid)
                continue

        # 按 title 判断（如 "CLIP Text Encode (Prompt)" / "(Negative)"）
        if isinstance(title, str):
            if any(k in title.lower() for k in ["positive", "pos", "prompt"]):
                positives.append(nid)
                continue
            if any(k in title.lower() for k in ["negative", "neg"]):
                negatives.append(nid)
                continue

        unclassified.append(nid)

    # 未被分类的按顺序对半分（兼容节点引用类 workflow）
    if unclassified:
        mid = len(unclassified) // 2
        positives.extend(unclassified[:mid])
        negatives.extend(unclassified[mid:])

    return positives, negatives


def _wait(prompt_id, timeout=COMFYUI_TIMEOUT):
    """轮询等待任务完成。"""
    start = time.time()
    while time.time() - start < timeout:
        r = httpx.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10)
        if r.status_code == 200 and r.json():
            history = r.json()
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for nid, out in outputs.items():
                    if "images" in out and out["images"]:
                        return out["images"][0]["filename"]
        time.sleep(2)
    raise TimeoutError(f"ComfyUI 任务超时 ({timeout}s)")


def _download(filename, out_path):
    """下载生成的图片。"""
    url = f"{COMFYUI_URL}/view"
    # ComfyUI 的 view 接口需要 filename + subfolder + type
    r = httpx.get(url, params={"filename": filename, "type": "output"},
                  timeout=60)
    r.raise_for_status()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(r.content)


def _load_workflow():
    """加载 workflow JSON。"""
    # 先从项目根目录找
    p = Path(__file__).parent.parent / COMFYUI_WORKFLOW
    if not p.exists():
        p = Path(COMFYUI_WORKFLOW)
    if not p.exists():
        raise FileNotFoundError(f"找不到 workflow: {COMFYUI_WORKFLOW}")
    return json.loads(p.read_text())


def _inject_prompts(workflow, pos, neg):
    """把正负提示词注入到 workflow 中。"""
    positives, negatives = _find_text_nodes(workflow)
    # 平均分配（如果多个正/负节点，复制内容）
    for i, nid in enumerate(positives):
        workflow[nid]["inputs"]["text"] = pos
    for i, nid in enumerate(negatives):
        workflow[nid]["inputs"]["text"] = neg


def generate_one(prompt, neg, out_path, seed=None):
    """
    单次生图（带重试）。
    
    Parameters
    ----------
    prompt : str
        正面提示词
    neg : str
        负面提示词
    out_path : str
        输出图片路径（.png）
    seed : int, optional
        随机种子，None 则随机
    """
    out_path = str(out_path)
    if Path(out_path).exists():
        logger.info(f"  ✓ 缓存命中: {Path(out_path).name}")
        return out_path

    if seed is None:
        import random
        seed = random.randint(0, 2**63)

    workflow = _load_workflow()
    _inject_prompts(workflow, prompt, neg)

    for attempt in range(1, COMFYUI_RETRY + 1):
        try:
            wf = json.loads(json.dumps(workflow))
            # 注入 seed 到所有 KSampler 节点
            for nid, node in wf.items():
                if node.get("class_type") == "KSampler":
                    node["inputs"]["seed"] = seed + attempt - 1
            client_id = str(uuid.uuid4())
            r = httpx.post(
                f"{COMFYUI_URL}/prompt",
                json={"prompt": wf, "client_id": client_id},
                timeout=30,
            )
            r.raise_for_status()
            prompt_id = r.json()["prompt_id"]
            logger.info(f"  → 任务 {prompt_id} 已提交（第{attempt}次）")

            filename = _wait(prompt_id)
            _download(filename, out_path)
            logger.info(f"  ✓ 已保存: {Path(out_path).name}")
            return out_path
        except Exception as e:
            logger.warning(f"  ✗ 第{attempt}次失败: {e}")
            if attempt >= COMFYUI_RETRY:
                raise
            time.sleep(3)


def check_comfyui():
    """公开启动检查接口。"""
    return _check_alive()
