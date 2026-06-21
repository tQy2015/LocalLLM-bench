# Acknowledgments

**プロジェクト:** LocalLLM-bench / Semantic Attractor 研究  
**作成:** 2026-06-06

> 本研究は Logit Lens（nostalgebraist, 2020）を測定基盤とし、Triton バックエンドにより sm_75 環境での vLLM 稼働を実現した。  
> 推論・計測・解析パイプラインは HuggingFace Transformers・vLLM・PyTorch を中心とするオープンソーススタックで構成される。  
> Qwen2.5-3B-Instruct（Alibaba Cloud）を主対象モデルとして使用した。

---

## 中核技術への謝辞

### Logit Lens

本研究の全測定基盤は **nostalgebraist** が 2020 年に提案した Logit Lens 手法に依拠する。

> nostalgebraist. "Interpreting GPT: the logit lens." LessWrong, 2020.  
> https://www.lesswrong.com/posts/AcKRB8wDpdaN6v6ru/interpreting-gpt-the-logit-lens

Logit Lens なくして本研究の TRGL 中間収束・結晶化タイミング・フレーム効果の定量化は不可能であった。nostalgebraist のオープンな知識共有に感謝する。

Tuned Lens（Belrose et al., 2023; arXiv:2303.08112）は手法的バイアスの参照先として活用した。

---

### vLLM Triton アテンションバックエンド（vllm-project/vllm）

本研究の vLLM 実験環境（RTX 2080 Ti / sm_75）は Flash-Attention 2 の sm_80+ 要件を満たさない。vLLM プロジェクトが実装した Triton 製アテンションカーネル（`VLLM_USE_TRITON_ATTN=1`）はこのハードウェア制約を迂回し、sm_75 上での vLLM 稼働を可能にした唯一の手段であった。

CUDAグラフ非決定論の定量化（v23-G/H）も同バックエンドの ON/OFF 比較として設計されており、この実装なしにはアーキテクチャ的検証が成立しない。

当カーネルは Triton コンパイラ（triton-lang/triton; Philippe Tillet, H.T. Kung, David Cox. MAPL 2019 — MIT License）を用いて記述されている。

---

## フレームワーク・ライブラリ

| ライブラリ | 役割 | ライセンス |
|---|---|---|
| **HuggingFace Transformers** | `output_hidden_states=True` による全層隠れ状態取得（Logit Lens 実装基盤） | Apache 2.0 |
| **vLLM** (vllm-project/vllm) | logprobs 取得・enforce_eager AB テスト・バッチ推論 | Apache 2.0 |
| **PyTorch** | テンソル演算・CUDA 管理 | BSD-3-Clause |
| **AutoAWQ** | Qwen2.5-3B-AWQ モデルの推論（量子化比較実験 v23-F） | MIT |

---

## モデル

| モデル | 提供元 | ライセンス |
|---|---|---|
| **Qwen2.5-3B-Instruct** (FP16) | Alibaba Cloud / Qwen Team | Apache 2.0 |
| **Qwen2.5-3B-Instruct-AWQ** | Alibaba Cloud / Qwen Team (AWQ: Casper Hansen) | Apache 2.0 |

---

*主たる研究（推論・計測・解析パイプライン）はすべてオープンソースツールで構成される。*  
*文書作成・データ管理の一部には Microsoft 365 製品を使用している。*  
*学術的先行研究は `./references.md` を参照。*
