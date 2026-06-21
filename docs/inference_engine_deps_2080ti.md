# RTX 2080 Ti 推論エンジン構成・モジュール依存関係

**作成日:** 2026-05-31  
**最終更新:** 2026-06-08（HTTP サーバーモード手順追記・`--attention-backend` CLI 引数確定）  
**対象ハードウェア:** NVIDIA GeForce RTX 2080 Ti  
**調査目的:** v19 実験環境の設計および長期実験基盤の整備

---

## 1. ハードウェアプロファイル

| 項目 | 値 |
|---|---|
| GPU | NVIDIA GeForce RTX 2080 Ti |
| アーキテクチャ | Turing |
| Compute Capability | **sm_75** |
| VRAM | 11 GB |
| CUDA ドライバ | **595.71.05**（Driver Version / CUDA 13.2）|
| 起動カーネル | **6.8.0-117-generic**（これ以外で起動するとドライバ不整合） |
| conda 環境 | `sglang`（torch 2.11.0+cu130） |

### 1.1 カーネルバージョンに関する重要注意

このマシンは 2026-05-05 に NVIDIA ドライバ 595.71 が部分インストールされた。  
カーネル 6.8.0-117-generic に対応するモジュールのみが存在する。

```
起動カーネル 6.8.0-117-generic → nvidia モジュール 595.71 → nvidia-smi OK ✅
起動カーネル 6.8.0-111-generic → nvidia モジュール 580.142（旧） → Driver mismatch → Error 804 ❌
```

GRUB DEFAULT=0 かつ grub-update 済みのため、通常再起動では 117 が選ばれる。

---

## 2. sm_75 における推論カーネルの互換性マップ

### 2.1 Attention カーネル

| ライブラリ | バージョン | sm_75 対応 | 確認方法・備考 |
|---|---|---|---|
| flash-attn 2.x | 2.0〜2.8.x | **○** | Turing 以降（sm_75+）を明示サポート |
| flash-attn 3.x | 3.x | **✗** | sm_80+（Ampere 以降）必須 |
| flash-attn 4.x (CUTE) | 4.0.0b14 | **✗** | `assert arch // 10 in [8,9,10,11,12]` → sm_75 は 7 で拒否 |
| flashinfer precompiled cubin | 0.6.11.post2 | **✗** | ファイル名に `sm100f` のみ（Blackwell 専用） |
| flashinfer JIT sampler | 0.6.11 | **✗** | CCCL ヘッダーが CUDA 13.x nvcc と非互換（build error） |
| PyTorch SDPA | 2.x | **○** | フォールバック attention。sm_75 対応 |
| **vLLM TRITON_ATTN** | **0.22.0** | **○** | `TritonAttentionBackend.supports_compute_capability` = `True`（全GPU） |
| vLLM FLASH_ATTN bundled | 0.22.0 | **✗** | `_vllm_fa2_C.abi3.so`：`strings` で `-arch sm_80` のみ確認 |

### 2.2 Rotary Embedding（vLLM 0.22.0 の実装）

vLLM 0.22.0 の rotary embedding は **2種類**のパスを持つ：

| パス | コード | sm_75 対応 | 用途 |
|---|---|---|---|
| `forward_cuda()` | `vllm_flash_attn.ops.triton.rotary`（`@triton.jit`） | **○** | CUDA GPU（今回） |
| `forward_hip()` | 外部 `flash_attn.ops.triton.rotary`（2.x API） | — | AMD GPU（HIP）専用 |

`forward_cuda()` が使う `vllm_flash_attn.ops.triton.rotary` は C++ バイナリではなく  
**純粋 Triton JIT カーネル**であり、sm_75 でコンパイル・実行可能。

### 2.3 bfloat16 制限（vLLM 0.22.0）

```python
# vllm/platforms/cuda.py
if dtype == torch.bfloat16:
    if not has_device_capability(80):
        raise ValueError(...)  # sm_75 では bfloat16 使用不可
# float16 は制限なし ← Qwen2.5-3B-Instruct fp16 で問題なし
```

---

## 3. 推論フレームワーク別 動作状態

### 3.1 sglang 0.5.12（動作不可・永続的）

```
sglang 0.5.12.post1
  └─ flash-attn-4 == 4.0.0b14 (必須)
       └─ flash_attn/cute/interface.py
            └─ assert arch // 10 in [8,9,10,11,12]  ← sm_75 = 7 → AssertionError
  └─ flashinfer-cubin == 0.6.11.post1 (必須)
       └─ precompiled: sm_100 (Blackwell) 専用
```

**判定: sm_75 では根本的に実行不可**

---

### 3.2 vLLM 0.22.0（sglang 環境・パッチ適用後 動作確認済み ✅）

```
conda env: sglang
  ├─ torch 2.11.0+cu130                    ✓ CUDA 13.2 ドライバと一致
  ├─ vllm 0.22.0
  │    ├─ attention backend: TRITON_ATTN   ✓ sm_75 で自動選択
  │    │    └─ triton_attn.py → Triton JIT カーネル（sm_75 対応）
  │    ├─ rotary embedding: forward_cuda() ✓ Triton JIT（sm_75 対応）
  │    └─ sampler: PyTorch-native          ✓ VLLM_USE_FLASHINFER_SAMPLER=0 で指定
  ├─ flash-attn-4 4.0.0b14               存在するが rotary パッチで無害化済み
  └─ flashinfer 0.6.11.post2             存在するが TRITON_ATTN 選択時は使用されない
```

**判定: 動作確認済み（2026-05-31）。v19 Phase 1 で使用可能 ✅**

---

### 3.3 HF transformers（sglang 環境・動作確認済み ✅）

```
conda env: sglang
  ├─ transformers 5.6.0
  ├─ torch 2.11.0+cu130                    ✓
  ├─ flash-attn-4（存在するが HF は自動スキップ → SDPA fallback）
  └─ AutoModelForCausalLM
       ├─ output_hidden_states=True → Logit Lens 計算可能 ✓
       └─ generate(output_scores=True) → pos=0 logits 取得可能 ✓
```

**判定: 動作確認済み。Phase 2 (Logit Lens) で使用 ✅**

---

### 3.4 vLLM 0.6.6（vllm-sm75 環境・実現不可）

```
conda env: vllm-sm75（試行済み・廃棄）
  ├─ torch 2.5.1+cu124  → Error 804（CUDA 13.x driver と cu12 runtime が非互換）
  └─ torch 2.1.2+cu118  → Error 804（同上。cu12 runtime パッケージが残存していたため）
```

**判定: このマシン（CUDA 13.x driver）では cu12x 系 torch は永続的に動作不可。廃棄。**

---

## 4. 実環境アーキテクチャ（確定版）

```
┌──────────────────────────────────────────────────────────────┐
│  conda env: sglang                                           │
│                                                              │
│  torch 2.11.0+cu130  ←→  CUDA Driver 595.71 (kernel 117)   │
│  transformers 5.6.0                                          │
│  vllm 0.22.0（パッチ済み）                                    │
│  flash-attn-4 4.0.0b14（存在するが両エンジンとも無害化済み）   │
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │ Phase 1              │  │ Phase 2                      │ │
│  │ vLLM + TRITON_ATTN   │  │ HF transformers              │ │
│  │ logprobs=20 取得      │  │ output_hidden_states=True    │ │
│  │ 動作確認済み ✅        │  │ 動作確認済み ✅               │ │
│  └──────────────────────┘  └──────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘

共通リソース:
  CUDA Driver 595.71 (kernel 6.8.0-117-generic でのみ有効)
  RTX 2080 Ti GPU（逐次利用・同時起動禁止）
  Qwen/Qwen2.5-3B-Instruct（~/.cache/huggingface 共有）
```

---

## 5. 実験フェーズと実行環境の対応

| フェーズ | 内容 | 使用エンジン | 状態 |
|---|---|---|---|
| Phase 1 | pos=0 logprobs 取得 | vLLM 0.22.0 + TRITON_ATTN | 動作確認済み ✅ |
| Phase 2 | HF Logit Lens 全層軌跡 | HF transformers 5.6.0 | 動作確認済み ✅ |
| Phase 3 | vLLM ↔ Logit Lens 整合確認 | 両者 | 未実施 |
| Phase 4 | 層軌跡グラフ生成 | Python (matplotlib) | 未実施 |

---

## 6. vLLM 0.22.0 on sm_75 の起動手順（確定版）

### 6.1 前提確認

```bash
# ① カーネルバージョン確認（117 でなければ再起動）
uname -r
# → 6.8.0-117-generic

# ② GPU 認識確認
nvidia-smi
# → Driver Version: 595.71.05  CUDA Version: 13.2  RTX 2080 Ti

# ③ PyTorch CUDA 確認
/home/tqy/miniconda3/envs/sglang/bin/python -c \
  "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# → True NVIDIA GeForce RTX 2080 Ti
```

### 6.2 必須パッチ（適用済み・再インストール時は再適用が必要）

**対象ファイル:**
```
/home/tqy/miniconda3/envs/sglang/lib/python3.11/site-packages/
  vllm/model_executor/layers/rotary_embedding/common.py
```

**修正箇所（行 138–143）：**

```python
# 修正前（flash-attn 4.x で ModuleNotFoundError）:
self.apply_rotary_emb_flash_attn = None
if not current_platform.is_cpu() and find_spec("flash_attn") is not None:
    from flash_attn.ops.triton.rotary import apply_rotary
    self.apply_rotary_emb_flash_attn = apply_rotary

# 修正後（適用済み）:
self.apply_rotary_emb_flash_attn = None
if not current_platform.is_cpu() and find_spec("flash_attn") is not None:
    try:
        from flash_attn.ops.triton.rotary import apply_rotary
        self.apply_rotary_emb_flash_attn = apply_rotary
    except ImportError:
        pass  # flash-attn 4.x (CUTE API) has no ops.triton; skip
```

**理由:** sglang 環境の flash-attn-4 は `flash_attn` モジュール名を持つが  
`flash_attn.ops` サブモジュールが存在しない。`find_spec` が True を返した後に  
import が失敗するため、try/except でスキップする必要がある。

### 6.3 Python コード（v19 Phase 1 実装パターン）

```python
import os
os.environ['VLLM_WORKER_MULTIPROC_METHOD'] = 'spawn'
os.environ['VLLM_USE_FLASHINFER_SAMPLER'] = '0'  # ※必須（後述）

from vllm import LLM, SamplingParams
from vllm.v1.attention.backends.registry import AttentionBackendEnum

llm = LLM(
    model='Qwen/Qwen2.5-3B-Instruct',
    dtype='float16',                              # bfloat16 は sm_75 不可
    enforce_eager=True,                           # CUDAGraph 不使用（安定動作）
    max_model_len=512,
    gpu_memory_utilization=0.80,                  # モデル ~5.8GB + KV キャッシュ分
    attention_backend=AttentionBackendEnum.TRITON_ATTN,  # sm_75 向け明示指定
)

params = SamplingParams(
    temperature=0.0,
    max_tokens=5,
    logprobs=20,    # ※上限 20（vLLM 0.22.0 の制約）
)

outputs = llm.generate(
    ['古代ギリシャで最も根源とされた元素を1つ選べ：火、水、土、風\n答え：'],
    params,
)

# pos=0 のトークン確率を取得
logprobs_at_pos0 = outputs[0].outputs[0].logprobs[0]
for tok_id, logprob in logprobs_at_pos0.items():
    print(f'tok={tok_id:6d}  logprob={logprob.logprob:8.4f}  decoded={repr(logprob.decoded_token)}')
```

### 6.4 起動時ログの確認ポイント

正常起動時に以下のログが出ること：

**in-process モード（`LLM()`）:**
```
[topk_topp_sampler.py] FlashInfer top-p/top-k sampling disabled via
                       VLLM_USE_FLASHINFER_SAMPLER=0; using PyTorch-native sampler.
[cuda.py] Using AttentionBackendEnum.TRITON_ATTN backend.
```

**HTTP サーバーモード（`vllm serve`）:**
```
INFO ... [topk_topp_sampler.py:70] FlashInfer top-p/top-k sampling disabled via
         VLLM_USE_FLASHINFER_SAMPLER=0; using PyTorch-native sampler.
INFO ... [cuda.py:380] Using TRITON_ATTN attention backend out of potential backends:
         ['TRITON_ATTN', 'FLEX_ATTENTION'].
```

### 6.5 HTTP サーバーモード起動（`vllm serve` / v25 以降）

#### ⚠️ 重要: `VLLM_ATTENTION_BACKEND` 環境変数は**存在しない**

このビルド（vLLM 0.22.0）には `VLLM_ATTENTION_BACKEND` という環境変数が定義されていない。  
HTTP サーバーの attention backend 指定は **`--attention-backend` CLI 引数**で行う。

```bash
VLLM_USE_FLASHINFER_SAMPLER=0 \
VLLM_WORKER_MULTIPROC_METHOD=spawn \
vllm serve Qwen/Qwen2.5-3B-Instruct \
  --port 8000 \
  --dtype float16 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 4096 \
  --max-num-seqs 64 \
  --attention-backend TRITON_ATTN
```

#### Python スクリプトから subprocess で起動する場合

```python
import os, subprocess

cmd = [
    "vllm", "serve", "Qwen/Qwen2.5-3B-Instruct",
    "--port", "8000",
    "--dtype", "float16",
    "--gpu-memory-utilization", "0.90",
    "--max-model-len", "4096",
    "--max-num-seqs", "64",
    "--attention-backend", "TRITON_ATTN",   # ← CLI 引数で指定（env var 不可）
]
env = os.environ.copy()
env["VLLM_USE_FLASHINFER_SAMPLER"]  = "0"    # env var で有効
env["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn" # CUDA fork 安全対策
proc = subprocess.Popen(cmd, env=env, ...)
```

**動作確認:** 2026-06-08 benchmark_v25_vllm_batch_ndet.py --repeat 1 で成功 ✅

---

## 7. 実測値（2026-05-31 EL_ja 動作確認）

```
プロンプト: 古代ギリシャで最も根源とされた元素を1つ選べ：火、水、土、風
           答え：
pos=0 top tokens:
  土  logprob=-0.0946  p ≈ 0.910  ← attractor
  火  logprob=-2.9540  p ≈ 0.052
  水  logprob=-4.9149  p ≈ 0.007
  その logprob=-5.4227
  風  logprob=-5.5243  p ≈ 0.004
```

---

## 8. 既知制約と対処

| 制約 | 内容 | 状況 |
|---|---|---|
| 起動カーネル制限 | 6.8.0-111 以前で起動すると Error 804 | **GRUB DEFAULT=0 で 117 が選択される** |
| torch cu12x + CUDA 13.x | Error 804（forward compat 非対応） | **永続的制約。cu130 のみ使用可** |
| vLLM FLASH_ATTN | `_vllm_fa2_C.abi3.so` が sm_80+ 専用 | **in-process: `attention_backend=AttentionBackendEnum.TRITON_ATTN`、HTTP: `--attention-backend TRITON_ATTN`** |
| rotary embedding クラッシュ | flash-attn 4.x API が `ops.triton` を持たない | **パッチ適用済み** |
| FlashInfer sampler JIT | CUDA 13.x + flashinfer CCCL が非互換（build error） | **`VLLM_USE_FLASHINFER_SAMPLER=0` で無効化** |
| logprobs 上限 | vLLM 0.22.0 は `logprobs` 最大 20 | **実験設計で 20 以下に設定** |
| bfloat16 不可 | vLLM が sm_75 で明示的に拒否 | **float16 を使用** |
| GPU メモリ競合 | vLLM + HF の同時起動 | **必ず逐次実行** |

---

## 9. 調査経緯（2026-05-31）

| 時系列 | 内容 |
|---|---|
| 午前 | vllm-sm75 env 構築試行 → torch cu124 → Error 804 |
| 午前 | Error 804 の原因を cu12 ランタイムと誤判断 |
| 午前 | cuInit(0) で直接確認 → 804 → システムレベルの障害と確定 |
| 午前 | kernel 580.142 ≠ libcuda.so 580.159 を発見 |
| 午前 | vLLM 0.22.0 の backend priority ソースを調査 → TRITON_ATTN 発見 |
| 午前 | rotary embedding のパッチ適用 |
| 午後 | カーネル 6.8.0-117 に GRUB 更新・再起動 → Driver 595.71 統一 |
| 午後 | TRITON_ATTN + PyTorch sampler の組み合わせを発見 |
| 午後 | EL_ja logprobs 取得成功・動作確認完了 |

---

## 10. 将来の拡張可能性（v20 以降）

| 実験 | 必要な理由 | 実現手段 |
|---|---|---|
| v20-A 32TC 展開 | バッチ推論で VRAM 消費増大 | HF generate() バッチ処理 |
| v20-B 崩壊温度対応 | 多温度 × 32TC = 長時間占有 | HF generate() ループ |
| v20-C Semantic Heating | ノイズ注入 + 推論 | HF forward() + custom noise |
| 7B モデル比較 | 3050 Ti (4GB) では fp16 不可 | HF（11GB VRAM 活用） |
| 異エンジン間 P 値検証 | 論文の方法論的基盤 | **vLLM 0.22.0 + TRITON_ATTN で同一マシン実現可能 ✅** |

---

*作成: TQY Kobayashi / HAL大阪 R&D*  
*関連: `docs/test_plan_v19_p_measurement.md` — v19 実験計画*  
*関連: `docs/test_plan_v19_p.md` — v19 実験計画（要約版）*
