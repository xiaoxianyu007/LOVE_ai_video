#!/bin/bash
# ============================================================
# ai_video_pipeline 启动脚本
# 用法：
#   bash start.sh 1 --all              # 集1，全部句
#   bash start.sh 1 3                  # 集1，前3句
#   bash start.sh 1 --all --skip-image # 跳过生图
# ============================================================
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 找到 conda 并激活 pixelle_video 环境
if [ -f "/home/shuju46/miniconda3/etc/profile.d/conda.sh" ]; then
    source /home/shuju46/miniconda3/etc/profile.d/conda.sh
elif command -v conda &> /dev/null; then
    source "$(conda info --base)/etc/profile.d/conda.sh"
else
    echo "❌ conda 未安装"
    exit 1
fi
conda activate pixelle_video

# 检查 ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ffmpeg 未安装"
    exit 1
fi

# 检查 ComfyUI（可选）
echo "🔍 检查 ComfyUI..."
if curl -s --connect-timeout 3 http://127.0.0.1:8188/prompt > /dev/null 2>&1; then
    echo "✓ ComfyUI 运行中"
else
    echo "⚠ ComfyUI 未运行（如跳过生图则无影响）"
fi

echo ""
echo "============================================"
echo "🎬 ai_video_pipeline"
echo "============================================"
echo ""

EP="${1:-1}"
shift 2>/dev/null || true
python pipeline.py --episode "$EP" "$@"