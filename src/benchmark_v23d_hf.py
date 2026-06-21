"""
benchmark_v23d_hf.py
v23-D / v23-D2: HF direct / bs=1 / temp=0.1 / 500run 拡散観測

実験:
  D  (default):  TC順序 CR2 → CR4 → FY  basin depth 相対順序確認
  D2 (--reverse): TC順序 FY  → CR4 → CR2 TC実行順序独立性検証

実行:
  # v23-D (試走 10run)
  python benchmark_v23d_hf.py --repeat 10

  # v23-D 本番
  python benchmark_v23d_hf.py

  # v23-D2 本番
  python benchmark_v23d_hf.py --reverse

作成: 2026-06-08
ベース: benchmark_v23_hf_batch_ndet.py
参照: docs/test_plans/test_plan_v23_future_checks.md
"""

import os
import csv
import time
import hashlib
import socket
import argparse
import warnings
from datetime import datetime
from collections import Counter

TIMESTAMP      = datetime.now().strftime("%Y%m%d_%H%M%S")
MODEL_NAME     = "Qwen/Qwen2.5-3B-Instruct"
DTYPE_STR      = "float16"
TEMPERATURE    = 0.1
BATCH_SIZE     = 1
REPEAT         = 500
MAX_NEW_TOKENS = 1000

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR   = os.path.join(PROJECT_ROOT, "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CR_SYSTEM = "あなたは創造的で知識豊富なアシスタントです。"

TC_D = [
    {"id": "CR2", "name": "素数と詩",
     "system": CR_SYSTEM,
     "prompt": "素数をひとつ選び、詩を書け。"},
    {"id": "CR4", "name": "正多面体サスペンス",
     "system": CR_SYSTEM,
     "prompt": "正多面体をひとつ選び、短編サスペンスを書け。"},
    {"id": "FY",  "name": "Feynman",
     "system": None,
     "prompt": "Tell me about Richard Feynman."},
]

TC_D2 = [
    {"id": "FY",  "name": "Feynman",
     "system": None,
     "prompt": "Tell me about Richard Feynman."},
    {"id": "CR4", "name": "正多面体サスペンス",
     "system": CR_SYSTEM,
     "prompt": "正多面体をひとつ選び、短編サスペンスを書け。"},
    {"id": "CR2", "name": "素数と詩",
     "system": CR_SYSTEM,
     "prompt": "素数をひとつ選び、詩を書け。"},
]


def load_model():
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    dtype = torch.float16 if DTYPE_STR == "float16" else torch.bfloat16
    print(f"[HF] モデルロード中: {MODEL_NAME}  dtype={DTYPE_STR}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, padding_side="left")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, torch_dtype=dtype, device_map="auto"
    )
    model.eval()
    if torch.cuda.is_available():
        vram  = torch.cuda.get_device_properties(0).total_memory / 1e9
        alloc = torch.cuda.memory_allocated(0) / 1e9
        print(f"[HF] ロード完了 | {torch.cuda.get_device_name(0)} "
              f"({vram:.1f}GB) | 使用: {alloc:.1f}GB")
    return model, tokenizer


def build_prompt(tokenizer, system, user):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )


def generate_one(model, tokenizer, prompt):
    import torch
    enc = tokenizer(
        [prompt], return_tensors="pt", padding=True,
        truncation=True, max_length=2048,
    ).to(model.device)
    with torch.no_grad():
        output = model.generate(
            **enc,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True,
            temperature=TEMPERATURE,
            pad_token_id=tokenizer.pad_token_id,
        )
    input_len  = enc["input_ids"].shape[1]
    gen_tokens = output[0, input_len:].tolist()
    reply      = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
    return reply, len(gen_tokens)


def collect_env():
    import torch
    return {
        "hostname":  socket.gethostname(),
        "gpu":       torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "torch_ver": torch.__version__,
        "dtype":     DTYPE_STR,
    }


def run_experiment(model, tokenizer, tc_list, exp_name, repeat, env):
    rows = []
    hash_counters = {tc["id"]: Counter() for tc in tc_list}

    print(f"\n実験: {exp_name}  temp={TEMPERATURE}  bs={BATCH_SIZE}  repeat={repeat}")
    print(f"TC順序: {' → '.join(tc['id'] for tc in tc_list)}")
    print("-" * 60)

    for run in range(1, repeat + 1):
        for tc in tc_list:
            prompt = build_prompt(tokenizer, tc["system"], tc["prompt"])
            t0 = time.time()
            try:
                reply, n_tok = generate_one(model, tokenizer, prompt)
                elapsed = time.time() - t0
                tps     = round(n_tok / elapsed, 2) if elapsed > 0 else 0
                h       = hashlib.sha256(reply.encode()).hexdigest()[:16]
                hash_counters[tc["id"]][h] += 1
                dominant = hash_counters[tc["id"]].most_common(1)[0][0]
                dom_pct  = hash_counters[tc["id"]][dominant] / run * 100
                print(f"  [{tc['id']}] run={run:4d} | {elapsed:.1f}s {tps:5.1f}tok/s "
                      f"hash={h}  dominant={dominant[:8]} ({dom_pct:.0f}%)")
                rows.append({
                    "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "experiment":  exp_name,
                    **env,
                    "framework":   "hf_direct",
                    "batch_size":  BATCH_SIZE,
                    "temperature": TEMPERATURE,
                    "model":       MODEL_NAME,
                    "tc_id":       tc["id"],
                    "tc_name":     tc["name"],
                    "run":         run,
                    "elapsed_sec": round(elapsed, 3),
                    "tok_per_sec": tps,
                    "gen_tokens":  n_tok,
                    "reply_len":   len(reply),
                    "reply_hash":  h,
                    "reply":       reply[:300],
                    "status":      "OK",
                })
            except Exception as e:
                print(f"  [{tc['id']}] run={run:4d} ERROR: {e}")
                rows.append({
                    "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "experiment":  exp_name,
                    **env,
                    "framework":   "hf_direct",
                    "batch_size":  BATCH_SIZE,
                    "temperature": TEMPERATURE,
                    "model":       MODEL_NAME,
                    "tc_id":       tc["id"],
                    "tc_name":     tc["name"],
                    "run":         run,
                    "elapsed_sec": 0,
                    "tok_per_sec": 0,
                    "gen_tokens":  0,
                    "reply_len":   0,
                    "reply_hash":  "",
                    "reply":       str(e)[:200],
                    "status":      "ERROR",
                })
    return rows


def save_csv(rows, path):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n[保存] {path}  ({len(rows)}行)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reverse", action="store_true",
                        help="TC順序を逆転 (v23-D2: FY→CR4→CR2)")
    parser.add_argument("--repeat", type=int, default=REPEAT)
    args = parser.parse_args()

    if args.reverse:
        tc_list  = TC_D2
        exp_name = "v23_D2_hf"
        suffix   = "v23D2_hf"
    else:
        tc_list  = TC_D
        exp_name = "v23_D_hf"
        suffix   = "v23D_hf"

    out_path = os.path.join(OUTPUT_DIR, f"{suffix}_{TIMESTAMP}.csv")
    model, tokenizer = load_model()
    env = collect_env()

    rows = []
    try:
        rows = run_experiment(model, tokenizer, tc_list, exp_name, args.repeat, env)
    except KeyboardInterrupt:
        print("\n[中断] 途中結果を保存します")
    finally:
        save_csv(rows, out_path)

    # 最終サマリ
    if rows:
        print("\n=== 最終サマリ ===")
        from collections import Counter as C
        for tc in tc_list:
            tc_rows = [r for r in rows if r["tc_id"] == tc["id"] and r["status"] == "OK"]
            if tc_rows:
                hashes = C(r["reply_hash"] for r in tc_rows)
                print(f"  {tc['id']}: {len(tc_rows)}run  {dict(hashes.most_common(3))}")


if __name__ == "__main__":
    main()
