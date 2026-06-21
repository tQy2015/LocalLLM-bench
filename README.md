# LocalLLM-bench: Semantic Attractor 研究

Qwen2.5-3B-Instruct（fp16）を対象に、LLMがオープン選択課題において**どのように概念を決定するか**を Logit Lens で層別に解析する実験プロジェクト。

## 中核的問い

> 「何を選ぶか」ではなく「どのように選ぶか」——決定プロセスの層構造

## 主要発見（v21 時点）

- **TRGL中間収束**: 自由選択時に最終概念確定より15〜20層前に属性トークンが出現
- **自由選択 vs 固定選択**: TRGLは自由選択固有、固定条件では消失 → 選択探索プロセスの一部
- **フレーム効果**: 確信度（P値）を変調するが結晶化タイミングは変えない
- **JA/EN非対称**: JA=四面体（高強度）、EN=icosahedron（一極集中）→ 訓練データ分布の反映

## ディレクトリ構成

```
LocalLLM-bench/
├── src/
│   ├── benchmark_v20.py    現役: known_attractor除去版（12条件）
│   ├── benchmark_v21.py    現役: 自由選択vs固定比較（36条件）
│   ├── benchmark_v11〜v19  参照用（アーカイブ前の旧版）
│   └── archive/            v9以前・非番号系スクリプト
│
├── results/
│   ├── v20_*.csv           v20実験結果
│   ├── v21_*.csv           v21実験結果（Exp A/B/combined）
│   ├── v11〜v19系 CSV      参照用結果
│   └── archive/            v9以前・ハードウェアベンチ系
│
├── docs/
│   ├── paper_outline_v1.md      論文アウトライン
│   ├── references.md            参考文献リスト
│   ├── hypothesis_specification.md  仮説定義
│   ├── test_cases_master.md     TCマスターリスト
│   ├── analysis_v12_semantic_attractors.md  v12主要分析
│   ├── inference_engine_deps_2080ti.md      環境依存事項
│   ├── test_plans/              実験計画書（v11以降）
│   ├── reports/                 実験サマリー（v10以降）
│   └── archive/                 旧計画・雑多ドキュメント
│
├── papers/                  参考論文PDF
├── models/                  モデルファイル
└── archive/                 v4以前スクリプト
```

## 実行環境

| マシン | GPU | アーキ | VRAM | 推論エンジン | 用途 |
|---|---|---|---|---|---|
| Desktop (OMEN) | RTX 2080 Ti | Turing / sm_75 | 11GB | vLLM + HF | 正典環境・表層/深層実験 |
| Workstation (HP Z240) | Quadro M4000 | Maxwell / sm_52 | 8GB | HF direct のみ | Logit Lens・ε測定 |
| Laptop | RTX 3050 Ti | Ampere / sm_86 | 4GB | vLLM（AWQ） | クロスアーキ検証（補助） |

- モデル: `Qwen/Qwen2.5-3B-Instruct` fp16（正典）/ AWQ（Ampere補助）
- Python: conda / transformers / accelerate / vllm

詳細: `docs/inference_engine_deps_2080ti.md`

## 次実験候補（v22）

| 実験 | 目的 |
|---|---|
| Semantic Heating | TRGL層への摂動 → 因果証明 |
| CR2 固定 vs 自由 | 素数「素」中間収束の検証 |
| 他モデル再現 | Llama-3.2-3B で TRGL 類似現象確認 |

## 関連ドキュメント

- 参考文献: `docs/references.md`
- テストケース定義: `docs/test_cases_master.md`
- 推論エンジン依存事項: `docs/inference_engine_deps_2080ti.md`
