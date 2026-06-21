# 参考文献リスト

**管理日:** 2026-06-20  
**プロジェクト:** LocalLLM-bench / Semantic Attractor 研究

---

## A. Logit Lens・層別予測の可視化

### A1. Logit Lens（原型）
- **著者:** nostalgebraist (blog post)
- **年:** 2020
- **URL:** https://www.lesswrong.com/posts/AcKRB8wDpdaN6v6ru/interpreting-gpt-the-logit-lens
- **概要:** 中間層の隠れ状態に直接 lm_head を適用して次トークン予測を可視化する手法の原型提案
- **本研究との関係:** 本研究が使用する基本手法

### A2. Tuned Lens
- **著者:** Belrose et al.
- **年:** 2023
- **arXiv:** 2303.08112
- **URL:** https://arxiv.org/abs/2303.08112
- **概要:** 層ごとに affine 変換を学習し、中間層の予測歪みを補正。Logit Lens の精緻化版
- **本研究との関係:** 手法的バイアスの参照先。Tuned Lens は本研究では未適用（限界として言及）

### A3. LogitLens4LLMs
- **著者:** Hernandez et al.
- **年:** 2025
- **arXiv:** 2503.11667
- **URL:** https://arxiv.org/abs/2503.11667
- **概要:** GQA・RMS-norm 等を持つ現代的 LLM（Llama, Mistral 等）への Logit Lens 拡張
- **本研究との関係:** 手法の適用範囲の参照

### A4. Token Prediction Refinement
- **著者:** （著者未確認）
- **年:** 2025
- **arXiv:** 2501.15054
- **URL:** https://arxiv.org/abs/2501.15054
- **概要:** LLM の層別トークン予測精緻化過程の解析。Essential Layers の同定
- **本研究との関係:** 層別決定解析の関連研究

---

## B. 層別決定構造・Phase 解析

### B1. Decision Representation Transitions
- **著者:** Shi, Boyu et al.
- **年:** 2026
- **arXiv:** 2605.07271
- **URL:** https://arxiv.org/abs/2605.07271
- **概要:** 層プルーニングによる性能崩壊を研究。MCQ タスクで Silent Phase（正解未予測）と Decisive Phase（正解出現）の二相構造を発見。Decisive Phase の除去が即時崩壊を招く
- **本研究との関係:** 最重要比較対象。本研究はオープン選択に拡張し、二相の間に属性収束という第三相を発見

---

## C. 概念アトラクター・Transformer 動力学

### C1. Concept Attractors in LLMs ★最重要競合論文★
- **著者:** Chytas, Sotirios Panagiotis; Singh, Vikas (U. Wisconsin-Madison)
- **年:** 2025（2025-12-30 投稿）
- **arXiv:** 2601.11575
- **URL:** https://arxiv.org/abs/2601.11575
- **OpenReview:** https://openreview.net/forum?id=qnLj1BEHQj
- **概要:** IFS（反復関数系）で Transformer 層を縮約写像と定式化。意味的に近いプロンプトが同じ層で類似表現に収束するという「概念アトラクター」を定義・実証。翻訳・幻覚低減・guardrailing への応用
- **本研究との差異:**
  - Chytas & Singh: アトラクターの**存在と応用**（What）
  - 本研究: アトラクターへの**収束過程の層構造**（How）——中間収束・結晶化タイミング・フレーム干渉・自由選択 vs 固定選択の比較

### C2. Transformer Dynamics（神経科学的アプローチ）
- **著者:** Fernando, Jesseba; Guitchounts, Grigori
- **年:** 2025
- **arXiv:** 2502.12131
- **URL:** https://arxiv.org/abs/2502.12131
- **概要:** 残差ストリームを動的システムとして解析。低層で attractor-like dynamics を確認。層を経るにつれ activations が加速・密化
- **本研究との関係:** 動的システム視点の理論的背景。本研究の「Silent Phase → 属性収束 → 概念結晶化」の解釈フレームと整合

### C3. Identity as Attractor
- **著者:** （著者未確認）
- **年:** 2026
- **arXiv:** 2604.12016
- **URL:** https://arxiv.org/abs/2604.12016
- **概要:** LLM 活性化空間における agent identity のアトラクター的幾何証拠
- **本研究との関係:** アトラクター研究の周辺

### C4. How to Tame Your LLM: Semantic Collapse in Continuous Systems ★深層側 最重要競合（新規・2026-06-20 追加）★
- **著者:** C. M. Wyss
- **年:** 2025（2025-12-04 投稿）
- **arXiv:** 2512.05162
- **URL:** https://arxiv.org/abs/2512.05162
- **概要:** LLM を連続状態機械（Continuous State Machine）として定式化。転送作用素のスペクトル分解により、臨界スケールを超えるとスペクトルが有限個の支配的モード＝安定セマンティック・アトラクターに収束することを示す。**Semantic Characterization Theorem (SCT)**: 転送作用素の主固有関数が有限個の「不変意味の spectral basin」を誘導し、各々が o-minimal 構造で定義可能 → 連続活性多様体から離散的シンボリック意味論が創発する機構を理論証明
- **本研究との差異（要警戒・差別化必須）:**
  - Wyss: 深層概念収束の**理論的定式化と証明**（連続→有限離散 basin の創発・固有関数レベル）
  - 本研究: その basin を**固定入力下で経験的に定量測定**し、**表層（全文 hash）の非決定性との解離**を分離測定（理論証明でなく実測現象）。Wyss は表層の FP/バッチ非決定性とは接続していない
- **関連:** Multi-LLM Systems Exhibit Robust Semantic Collapse (arXiv:2605.17193, 2026) — 複数 LLM 系での semantic collapse の頑健性

---

## D. Semantic Interpretability の限界

### D1. LLMs Explain't
- **著者:** （著者未確認）
- **年:** 2026
- **arXiv:** 2601.22928
- **URL:** https://arxiv.org/abs/2601.22928
- **概要:** Transformer における semantic interpretability の限界を論じる post-mortem
- **本研究との関係:** 解釈可能性の限界を認識した上での実証的アプローチの位置付けに使用可

---

## E. Representation Collapse・情報過圧縮

### E1. Transformers need glasses
- **著者:** （著者未確認）
- **年:** 2024
- **arXiv:** 2406.04267
- **URL:** https://arxiv.org/abs/2406.04267
- **概要:** Language タスクにおける情報 over-squashing の問題
- **本研究との関係:** 深層での representation collapse の理論的背景

### E2. Transformer Representation Capacity
- **著者:** （著者未確認）
- **年:** 2025
- **arXiv:** 2502.09245
- **URL:** https://arxiv.org/abs/2502.09245
- **概要:** Transformer の表現容量の未活用に関する研究
- **本研究との関係:** 層ごとの情報圧縮・展開の理論的背景

---

## F. Mechanistic Interpretability 全般

### F1. Practical Review of Mechanistic Interpretability
- **著者:** （著者未確認）
- **年:** 2024
- **arXiv:** 2407.02646
- **URL:** https://arxiv.org/abs/2407.02646
- **概要:** Transformer-based LLM の Mechanistic Interpretability 手法のレビュー
- **本研究との関係:** 研究領域の位置付け

### F2. Developmental Interpretability Review
- **著者:** （著者未確認）
- **年:** 2025（2025-08 以降）
- **arXiv:** 2508.15841
- **URL:** https://arxiv.org/abs/2508.15841
- **概要:** LLM の Developmental Interpretability レビュー
- **本研究との関係:** 関連分野のレビュー

---

## G. 温度制御・Attention

### G1. Selective Attention
- **著者:** （著者未確認）
- **年:** 2024
- **arXiv:** 2411.12892
- **URL:** https://arxiv.org/abs/2411.12892
- **概要:** 原理的なコンテキスト制御による Transformer 強化。Temperature scaling の softmax への効果
- **本研究との関係:** 温度効果の理論的参照

---

## I. FP/バッチ非決定性（表層機構・本研究の表層側 直系）★2026-06-20 新設★

### I1. Defeating Nondeterminism in LLM Inference ★表層側 最重要・直系★
- **著者:** Thinking Machines Lab（He et al.）
- **年:** 2025（2025-09 公開）
- **URL:** https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
- **概要:** temp=0/greedy でも同一プロンプトの出力が揺れる主因は **バッチ分散**（FP 非結合性単体でなく、バッチサイズ依存の縮約順＝RMSNorm/matmul/attention カーネルが batch-invariant でないこと）と特定。**batch-invariant カーネルで 1000/1000 完全一致を達成**。実例: 通常カーネルで 80 種の出力・token 102 まで一致し token 103 で分岐（992 回 "Queens, New York" / 8 回 "New York City"）
- **本研究との関係（核心・直系）:**
  - 本研究の表層非決定（CR4 62:38・A-2 fork・C5）は**この系譜の追試・拡張**。共有プレフィックス→後方トークン分岐の構造が一致
  - **スタンスの差**: He は非決定を「消すべきバグ」として扱う（batch-invariant 化）。本研究は「特徴づけるべき2層構造」として扱い、**深層概念収束との解離を定量化**する。He の "Queens vs NYC"（意味同一・表層のみ分岐）は解離の実例だが He 自身は解離として主題化していない
  - 本研究の C-0.6b（fp16 2ulp タイ破り）は He 機構の最小実例の精密化

### I2. 非決定性の prefix-tree／臨界決定点フレーム
- **著者:** （He 派生・複数, 2025-2026）
- **参考:** arXiv:2511.20621 (DiFR) / arXiv:2511.02620 ほか
- **概要:** 同一プロンプトへの複数応答をトークン単位の prefix tree で可視化。fork point（プレフィックス共有から分岐する点）で非決定を定量化。経験的に **約 95% のノードが単一子・5% が二分岐・0.2% が高次分岐**＝「大半は決定的・臨界決定点のみ揺れる」パターン
- **本研究との関係:** 本研究の「冒頭一致・後方 fork」「離散 basin 分岐」はこの既知パターンの再観測。論文では「表層 fork 構造は既知」と明記し、貢献を**深層との解離の定量化**に絞ること

### I3. Non-Determinism of "Deterministic" LLM Settings
- **著者:** （著者未確認）
- **年:** 2024
- **arXiv:** 2408.04667
- **URL:** https://arxiv.org/html/2408.04667v5
- **概要:** deterministic 設定の 5 LLM × 8 タスクでも run 間で精度が最大 15% 変動・全タスクで再現する LLM は皆無
- **本研究との関係:** 表層非決定の実務的影響の参照

### I4. LLMs Show Surface-Form Brittleness Under Paraphrase Stress Tests
- **著者:** （著者未確認）
- **年:** 2025
- **arXiv:** 2510.08616
- **URL:** https://arxiv.org/pdf/2510.08616
- **概要:** 意味保存の言い換えでも LLM 予測が不安定＝表層形ロバスト性の欠如
- **本研究との関係:** ⚠️ **本研究と方向が逆**（入力 paraphrase → 出力変化）。本研究は固定入力 → 出力の表層揺れ。混同しないこと・対比として言及可

---

## H. その他関連

### H1. Autonomous Image Generation Loops
- **引用ID:** PMC12827715
- **概要:** 複数温度での semantic drift の追跡。温度変化が semantic attractor の basin of attraction を変えないことを発見
- **本研究との関係:** 温度とアトラクターの関係の比較対象

---

## 未確認・要詳細調査

以下は v12 analysis で言及されたが著者・タイトルを未確認のもの：

| arXiv ID | メモ |
|---|---|
| 2508.18290 | "Semantic Attractors and the Emergence of Meaning: Towards a Teleological Model of AGI" |

---

## 今後追加候補

- Logit Lens を MCQ 以外（創作・詩）に適用した研究
- Frame effect on LLM generation（フレーム効果の先行研究）
- Cross-lingual attractor 研究（JA/EN で異なるアトラクターを持つことの言語学的背景）
- Sparse Autoencoder (SAE) による概念分解（TRGL のような中間トークンの意味論的解釈に利用可能か）
