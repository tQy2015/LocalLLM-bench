#!/bin/bash
# ============================================================
# vLLM v26 HTTP API サーバー起動スクリプト
# 対象マシン: OMEN (RTX 2080 Ti, Ubuntu)
# モデル: Qwen/Qwen2.5-3B-Instruct (fp16)
# ============================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MELON_ROOT="$(dirname "$PROJECT_ROOT")"

echo ""
echo "============================================================"
echo "vLLM v26 API Server Launcher"
echo "============================================================"
echo ""

# ============================================================
# 前提確認
# ============================================================

echo "[1/4] 環境確認..."

# Conda sglang 環境の確認
if [ ! -d "/home/tqy/miniconda3/envs/sglang" ]; then
  echo "❌ conda sglang 環境が見つかりません"
  exit 1
fi
echo "✓ sglang 環境: OK"

# GPU の確認
if ! nvidia-smi &>/dev/null; then
  echo "❌ nvidia-smi が実行できません（GPU ドライバが未インストール）"
  exit 1
fi

GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
CUDA_DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
echo "✓ GPU: $GPU_NAME"
echo "✓ CUDA Driver: $CUDA_DRIVER"

# Qwen モデルが ~/.cache/huggingface にあるか確認
if [ ! -d "$HOME/.cache/huggingface/hub/models--Qwen--Qwen2.5-3B-Instruct" ]; then
  echo "⚠️  Qwen モデルが未ダウンロードです。初回実行時に自動ダウンロードされます（~8分）"
fi

echo ""
echo "[2/4] vLLM サーバー起動中..."
echo "  ポート: 8000"
echo "  モデル: Qwen/Qwen2.5-3B-Instruct"
echo "  精度: float16"
echo "  GPU メモリ利用率: 0.90"
echo "  最大トークン長: 4096"
echo "  最大同時シーケンス: 260"
echo "  Attention Backend: TRITON_ATTN"
echo ""

# ============================================================
# 環境変数設定
# ============================================================

export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_WORKER_MULTIPROC_METHOD=spawn

# ============================================================
# conda 環境の有効化と vLLM サーバー起動
# ============================================================

source /home/tqy/miniconda3/bin/activate sglang

vllm serve Qwen/Qwen2.5-3B-Instruct \
  --port 8000 \
  --dtype float16 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 4096 \
  --max-num-seqs 260 \
  --attention-backend TRITON_ATTN

echo ""
echo "[3/4] サーバーシャットダウン"
echo ""
