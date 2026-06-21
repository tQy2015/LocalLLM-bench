@echo off
REM ============================================================
REM vLLM v26 HTTP API サーバー起動スクリプト
REM 対象マシン: OMEN (RTX 2080 Ti, Ubuntu + WSL2)
REM モデル: Qwen/Qwen2.5-3B-Instruct (fp16)
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo vLLM v26 API Server Launcher
echo ============================================================
echo.

REM WSL2 から Ubuntu のセッション内で vLLM サーバーを起動
REM (OMEN マシンが Ubuntu ネイティブなら直接 bash で、WSL経由なら以下)

REM 方法 A: WSL2 で実行（Windows から OMEN に SSH 接続可能な場合）
REM wsl --distribution Ubuntu --cd /home/tqy/Dropbox/melon ...

REM 方法 B: ネイティブ Linux 環境（推奨・直接 bash）
REM bash コマンドを使う場合、Git Bash または WSL bash をパス指定

REM ============================================================
REM 前提確認
REM ============================================================

echo [1/3] 環境確認...

REM conda sglang 環境が有効か確認（WSL2 経由）
wsl bash -c "test -d /home/tqy/miniconda3/envs/sglang && echo sglang 環境: OK || echo sglang 環境: 未検出"

echo.
echo [2/3] vLLM サーバー起動中...
echo ポート: 8000
echo モデル: Qwen/Qwen2.5-3B-Instruct
echo 精度: float16
echo GPU メモリ利用率: 0.90
echo 最大トークン長: 4096
echo 最大同時シーケンス: 260
echo Attention Backend: TRITON_ATTN
echo.

REM ============================================================
REM vLLM サーバー起動
REM ============================================================

REM WSL2 経由での実行
wsl bash -c ^
  "cd /home/tqy/Dropbox/melon && " ^
  "export VLLM_USE_FLASHINFER_SAMPLER=0 && " ^
  "export VLLM_WORKER_MULTIPROC_METHOD=spawn && " ^
  "source /home/tqy/.bashrc && " ^
  "conda activate sglang && " ^
  "vllm serve Qwen/Qwen2.5-3B-Instruct " ^
  "--port 8000 " ^
  "--dtype float16 " ^
  "--gpu-memory-utilization 0.90 " ^
  "--max-model-len 4096 " ^
  "--max-num-seqs 260 " ^
  "--attention-backend TRITON_ATTN"

echo.
echo [3/3] サーバー終了
echo.

pause
