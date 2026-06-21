# LocalLLM-bench: 表層/深層解離の定量化

Qwen2.5-3B-Instruct（fp16）を対象に、LLMの生成における**表層（全文hash）と深層（概念選択）の解離**を定量化する実験プロジェクト。

## 中核的問い

> 同一プロンプトへの出力が run 間で変動するとき、「何を書くか（概念）」は安定し「どう書くか（全文）」だけが揺れているのか？

## 主要発見

- **表層/深層の完全解離（CR2）**: 素数選択は1000/1000で「13」に収束（深層安定）、全文hash は 345+ 種（表層発散）
- **双安定アトラクター（CR4）**: 正多面体選択は四面体 ~62% / 十二面体 ~38% の離散basin — 単一トークン差で分岐
- **温度依存性**: temp=0 では GPU/FP 非再現性由来の表層揺れが残存（He 2025 再現）、temp>0 では両層ともに拡散

## 公開ファイル構成

```
LocalLLM-bench/
├── src/
│   ├── hcddemo.py              温度別 hash/概念収束測定（Table 2 データ生成）
│   ├── benchmark_v23d_hf.py    1000run 大規模再現性測定（HuggingFace直接）
│   └── c5_cudagraph_ab.py      CUDAグラフ有無による表層変動比較
│
├── results/
│   ├── hcddemo_20260601_072255.txt          温度別測定ログ（CR2/CR4/FY）
│   ├── v23D_hf_20260608_142028.csv          CR2/CR4 各500run（TEMP=0.1）
│   ├── v23D2_hf_20260609_142919.csv         CR2/CR4 各500run（TEMP=0.1, run2）
│   ├── c5_cudagraph_A_eager_OFF_*.csv       CUDAグラフOFF条件
│   └── c5_cudagraph_B_eager_ON_*.csv        CUDAグラフON条件
│
├── docs/
│   ├── references.md            参考文献リスト
│   ├── test_cases_master.md     テストケース定義（TC/GN/CR/SA/FY系）
│   ├── inference_engine_deps_2080ti.md  推論エンジン依存事項
│   └── ACKNOWLEDGMENTS.md
│
└── scripts/
    ├── run_vllm_server.sh       vLLM サーバ起動スクリプト（Linux）
    └── run_vllm_server.bat      vLLM サーバ起動スクリプト（Windows）
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

## 関連ドキュメント

- 参考文献: `docs/references.md`
- テストケース定義: `docs/test_cases_master.md`
- 推論エンジン依存事項: `docs/inference_engine_deps_2080ti.md`
