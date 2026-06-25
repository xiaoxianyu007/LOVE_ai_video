#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════
#  批量运行脚本 — 楚汉争霸(5集) + 西汉(40集)
#  ⚠ 使用前请确保 ComfyUI 已启动:
#    cd ~/.Mao_data/comfyui && conda activate zimage && python main.py --listen 127.0.0.1 --port 8188
# ═══════════════════════════════════════════════════════════════

cd /home/shuju46/Oray/Mi/Pixelle-Video/ai_video_pipeline

SERIES=${1:-"all"}   # 参数: chu_han / western_han / all
EPISODES=${2:-"all"} # 参数: 具体集号如 "1-5" 或 "all"

echo "=========================================="
echo "  AI Video Pipeline 批量运行"
echo "  系列: $SERIES | 集数: $EPISODES"
echo "=========================================="

# ── 楚汉争霸（5 集）────────────────────────────────
run_chu_han() {
    echo ""
    echo "【系列】楚汉争霸 (5集)"
    echo "=========================================="

    for ep in 1 2 3 4 5; do
        echo ""
        echo "━━━ 楚汉 第 ${ep} 集 ━━━"
        echo "  清理旧 TTS 和 BG (保留图片)..."
        rm -rf "output/audio_en/ep$(printf '%02d' $ep)"
        rm -f "output/chu_han/bg/ep$(printf '%02d' $ep)/"*.mp4
        rm -f "output/final/ep$(printf '%02d' $ep)_chu_han.mp4"
        rm -rf "output/subtitle"
        rm -f "output/title/title_chu_han_ep$(printf '%02d' $ep)_"*.mp4

        echo "  生成第 ${ep} 集..."
        python pipeline.py --episode "$ep" --all --series chu_han --skip-llm
        echo "  ✓ 第 ${ep} 集完成"
    done
}

# ── 西汉（40 集）──────────────────────────────────
run_western_han() {
    echo ""
    echo "【系列】西汉 (40集)"
    echo "=========================================="

    for ep in $(seq 1 40); do
        echo ""
        echo "━━━ 西汉 第 ${ep} 集 ━━━"
        echo "  清理旧 TTS 和 BG (保留图片)..."
        rm -rf "output/audio_en/ep$(printf '%02d' $ep)"
        rm -f "output/western_han/bg/ep$(printf '%02d' $ep)/"*.mp4
        rm -f "output/final/ep$(printf '%02d' $ep)_western_han.mp4"
        rm -rf "output/subtitle"
        rm -f "output/title/title_western_han_ep$(printf '%02d' $ep)_"*.mp4

        echo "  生成第 ${ep} 集..."
        python pipeline.py --episode "$ep" --all --series western_han --skip-llm
        echo "  ✓ 第 ${ep} 集完成"
    done
}

# ── 选择性运行（指定范围）─────────────────────────
run_range() {
    local series=$1
    local start=$2
    local end=$3
    local name=$4

    echo ""
    echo "【系列】$name ($start-$end 集)"
    echo "=========================================="

    for ep in $(seq "$start" "$end"); do
        echo ""
        echo "━━━ ${name} 第 ${ep} 集 ━━━"
        echo "  清理旧 TTS 和 BG (保留图片)..."
        rm -rf "output/audio_en/ep$(printf '%02d' $ep)"
        rm -f "output/${series}/bg/ep$(printf '%02d' $ep)/"*.mp4
        rm -f "output/final/ep$(printf '%02d' $ep)_${series}.mp4"
        rm -rf "output/subtitle"
        rm -f "output/title/title_${series}_ep$(printf '%02d' $ep)_"*.mp4

        echo "  生成第 ${ep} 集..."
        python pipeline.py --episode "$ep" --all --series "$series" --skip-llm
        echo "  ✓ 第 ${ep} 集完成"
    done
}

# ── 主调度 ──────────────────────────────────────
case "$SERIES" in
    "chu_han")
        if [ "$EPISODES" = "all" ]; then
            run_chu_han
        else
            IFS='-' read -r start end <<< "$EPISODES"
            run_range "chu_han" "$start" "$end" "楚汉"
        fi
        ;;
    "western_han")
        if [ "$EPISODES" = "all" ]; then
            run_western_han
        else
            IFS='-' read -r start end <<< "$EPISODES"
            run_range "western_han" "$start" "$end" "西汉"
        fi
        ;;
    "all")
        run_chu_han
        run_western_han
        ;;
    *)
        echo "用法: bash batch_run.sh [系列] [集数范围]"
        echo "  系列: chu_han / western_han / all (默认 all)"
        echo "  集数: all (默认) / 1-5 / 10-20"
        echo ""
        echo "示例:"
        echo "  bash batch_run.sh                     # 全部 45 集"
        echo "  bash batch_run.sh chu_han             # 楚汉 5 集"
        echo "  bash batch_run.sh western_han         # 西汉 40 集"
        echo "  bash batch_run.sh western_han 1-10    # 西汉 1-10 集"
        echo "  bash batch_run.sh chu_han 3-5         # 楚汉 3-5 集"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "  ✓ 全部完成!"
echo "  输出目录: output/final/"
echo "=========================================="