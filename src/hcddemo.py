#!/usr/bin/env python3
"""
hcddemo.py — HCD発表用 Semantic Attractor デモ

モデル : Qwen2.5-3B-Instruct (fp16・非量子化)
推論   : vLLM 決定論モード (T=0, seed=42×10) → 温度上昇 (seed=42〜51) → 崩壊まで
表示   : 生成文プレビュー・アトラクター・SHA-256ハッシュ(12桁)
実行   : /home/tqy/miniconda3/envs/sglang/bin/python src/hcddemo.py

課題1: 素数をひとつ選び、詩を書け。
課題2: 正多面体をひとつ選び、短編サスペンスを書け。
"""

import os, sys, hashlib, argparse
from datetime import datetime
from pathlib import Path

class Tee:
    """標準出力とファイルに同時書き込み"""
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"
os.environ["VLLM_USE_FLASHINFER_SAMPLER"] = "0"

from vllm import LLM, SamplingParams
from vllm.v1.attention.backends.registry import AttentionBackendEnum

# ── ANSI ──────────────────────────────────────────────────
R  = "\033[0m"
BO = "\033[1m"
DI = "\033[2m"
RD = "\033[91m"
GR = "\033[92m"
YL = "\033[93m"
BL = "\033[94m"
MG = "\033[95m"
CY = "\033[96m"

# ── 設定 ───────────────────────────────────────────────────
MODEL_PATH = (
    "/home/tqy/models/hub/models--Qwen--Qwen2.5-3B-Instruct"
    "/snapshots/aa8e72537993ba99e69dfaafa59ed015b17504d1"
)
SYSTEM_JA  = "あなたは創造的で知識豊富なアシスタントです。"
N_REPEAT   = 10
TEMPS      = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5]
SEED_BASE  = 42   # T=0: 全試行 SEED_BASE / T>0: SEED_BASE + temp_idx*N_REPEAT + i

TASKS = [
    {
        "id":      "PRIME",
        "name":    "素数と詩",
        "prompt":  "素数をひとつ選び、詩を書け。",
        # 先頭にマッチしやすいものを並べる（部分文字列: 長い→短い）
        "attract": ["11", "13", "17", "19", "23", "29", "7", "5", "3", "2"],
        "hallu":   [],          # 既知の幻覚（存在しない概念）
        "tokens":  1500,
    },
    {
        "id":      "POLY",
        "name":    "正多面体サスペンス",
        "prompt":  "正多面体をひとつ選び、短編サスペンスを書け。",
        "attract": ["正四面体", "正六面体", "正八面体", "正十二面体", "正二十面体",
                    "四面体", "六面体", "八面体", "十二面体", "二十面体"],
        "hallu":   ["正五面体", "正七面体", "正九面体"],  # AWQ幻覚（実在しない正多面体）
        "tokens":  1500,
    },
]

# ── ユーティリティ ─────────────────────────────────────────
def sha12(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]

def detect(text: str, attractors: list, hallu: list) -> tuple:
    """返値: (検出文字列 | None, is_hallucination: bool)"""
    for h in hallu:
        if h in text:
            return h, True
    for a in attractors:
        if a in text:
            return a, False
    return None, False

def bar(width=60, char="─") -> str:
    return char * width

def dominant(found: list) -> tuple:
    """最多出現アトラクターとその個数を返す"""
    detected = [a for a in found if a is not None]
    if not detected:
        return None, 0
    d = max(set(detected), key=detected.count)
    return d, detected.count(d)

def collapse_summary(found: list, baseline: str | None) -> str:
    """
    T=0 以降のサマリー。
    - baseline: T=0 で選ばれたアトラクター（比較基準）
    - found: このTで検出されたアトラクター列 (None = 未検出)
    """
    n = len(found)
    detected   = [a for a in found if a is not None]
    n_detected = len(detected)
    unique     = sorted(set(detected))

    if n_detected == 0:
        return f"{RD}{BO}✗ 崩壊 — アトラクター消失 (0/{n}){R}"

    dom, dom_cnt = dominant(found)

    if dom_cnt == n:
        # 全試行が同一アトラクター
        if baseline is None or dom == baseline:
            return f"{GR}{BO}✓ 完全安定 — {dom} ({n}/{n}){R}"
        else:
            return f"{CY}{BO}→ 移行安定 — {baseline} → {dom} ({n}/{n}){R}"
    elif dom_cnt >= n * 0.6:
        others = [a for a in unique if a != dom]
        return (f"{YL}⚠ 揺らぎ — 支配: {dom} ({dom_cnt}/{n})  "
                f"他: {', '.join(others)}{R}")
    else:
        return f"{RD}✗ 崩壊 — 分散 ({n_detected}/{n}) : {', '.join(unique)}{R}"

# ── メイン ─────────────────────────────────────────────────
def main(task_filter=None):
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = results_dir / f"hcddemo_{timestamp}.txt"
    log_file = open(log_path, "w", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, log_file)
    print(f"[ログ保存先: {log_path}]\n")

    print(f"\n{BO}{CY}{bar(60,'═')}{R}")
    print(f"{BO}{CY}  Semantic Attractor Demo  ／  HCD発表{R}")
    print(f"{CY}  モデル : Qwen2.5-3B-Instruct  (fp16・非量子化){R}")
    print(f"{CY}  繰り返し: {N_REPEAT} 回 ／ 温度: {TEMPS}{R}")
    print(f"{CY}  seed   : T=0 → {SEED_BASE}×{N_REPEAT}固定 / T>0 → temp_idx×{N_REPEAT}+{SEED_BASE}+i (各温度独立){R}")
    print(f"{CY}  実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}{R}")
    print(f"{BO}{CY}{bar(60,'═')}{R}\n")

    print(f"{DI}モデルをロード中...{R}", flush=True)
    llm = LLM(
        model=MODEL_PATH,
        dtype="float16",
        enforce_eager=True,
        max_model_len=2048,
        gpu_memory_utilization=0.75,
        attention_backend=AttentionBackendEnum.TRITON_ATTN,
        enable_prefix_caching=False,   # 温度間KVキャッシュ汚染を防止
    )
    tokenizer = llm.get_tokenizer()
    print(f"{GR}モデルロード完了{R}\n")

    active_tasks = [t for t in TASKS if task_filter is None or t["id"] == task_filter]
    for task in active_tasks:
        print(f"\n{BO}{MG}{bar(60,'━')}{R}")
        print(f"{BO}{MG}  課題: {task['name']}{R}")
        print(f"{BO}{MG}  プロンプト: 「{task['prompt']}」{R}")
        print(f"{BO}{MG}{bar(60,'━')}{R}")

        messages = [
            {"role": "system", "content": SYSTEM_JA},
            {"role": "user",   "content": task["prompt"]},
        ]
        prompt_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        baseline     = None   # T=0 の支配アトラクター
        prev_collapse = False

        for temp_idx, temp in enumerate(TEMPS):
            is_det = (temp == 0.0)
            seed_start = SEED_BASE if is_det else SEED_BASE + temp_idx * N_REPEAT
            seed_end   = seed_start if is_det else seed_start + N_REPEAT - 1
            print(f"\n  {BO}{YL}T = {temp:.1f}{R}  "
                  f"{DI}{'(決定論: seed固定)' if is_det else f'(確率論: seed={seed_start}〜{seed_end})'}{R}")
            print(f"  {DI}{bar(55,'-')}{R}")

            hashes    = []
            attractors = []   # (attractor_str | None) のリスト

            for i in range(N_REPEAT):
                seed = SEED_BASE if is_det else SEED_BASE + temp_idx * N_REPEAT + i
                # T=0 は vLLM が 0.01 にクランプするため 0.01 を直接指定
                temperature = 0.01 if is_det else float(temp)
                params = SamplingParams(
                    temperature=temperature,
                    top_p=1.0,
                    max_tokens=task["tokens"],
                    seed=seed,
                )
                out  = llm.generate([prompt_text], params, use_tqdm=False)[0]
                text = out.outputs[0].text.strip()

                h          = sha12(text)
                att, is_h  = detect(text, task["attract"], task["hallu"])
                preview    = text.replace('\n', ' ')[:60]
                if len(text) > 60:
                    preview += "…"

                hashes.append(h)
                attractors.append(att)

                # アトラクター表示（幻覚は赤、正常は緑、未検出は赤）
                if att and is_h:
                    att_disp = f"{RD}{BO}[幻覚]{att}{R}"
                elif att:
                    att_disp = f"{GR}{BO}{att}{R}"
                else:
                    att_disp = f"{RD}未検出{R}"

                hash_note = ""
                if is_det and i > 0:
                    hash_note = f"  {DI}{'=前回' if h == hashes[0] else '≠前回'}{R}"

                print(f"  試行{i+1:02d}  {DI}hash={h}{R}{hash_note}  seed={seed}  {att_disp}")
                print(f"  {DI}       └ {preview}{R}")
                # ファイルにのみ全文を追記
                log_file.write(
                    f"\n--- 全文 [{task['id']} T={temp:.1f} 試行{i+1:02d} seed={seed}] ---\n"
                    f"{text}\n"
                    f"--- END ---\n"
                )
                log_file.flush()

            # ── サマリー ──
            print(f"\n  {DI}{bar(55,'-')}{R}")

            if is_det:
                baseline = attractors[0]  # T=0 の基準アトラクター
                all_same = len(set(hashes)) == 1
                hash_note = (f"{GR}全ハッシュ一致 ✓{R}" if all_same
                             else f"{RD}ハッシュ不一致 ✗{R}")
                print(f"  ハッシュ判定: {hash_note}")
                det_cnt = sum(1 for a in attractors if a)
                if det_cnt == 0:
                    print(f"  {RD}{BO}基準アトラクター: 未検出{R}")
                else:
                    dom_a, _ = dominant(attractors)
                    print(f"  {GR}基準アトラクター: {dom_a}{R}")
            else:
                print(f"  {collapse_summary(attractors, baseline)}")

            # 2温度連続崩壊でスキャン終了
            n_det = sum(1 for a in attractors if a)
            if n_det == 0:
                if prev_collapse:
                    print(f"\n  {RD}2温度連続崩壊 → スキャン終了{R}")
                    break
                prev_collapse = True
            else:
                prev_collapse = False

        print()

    print(f"\n{BO}{CY}{bar(60,'═')}{R}")
    print(f"{BO}{CY}  デモ完了{R}")
    print(f"{BO}{CY}{bar(60,'═')}{R}\n")

    sys.stdout = sys.__stdout__
    log_file.close()
    print(f"[ログ保存完了: {log_path}]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["PRIME", "POLY"], default=None,
                        help="実行する課題を限定 (デフォルト: 両方)")
    args = parser.parse_args()
    main(task_filter=args.task)
