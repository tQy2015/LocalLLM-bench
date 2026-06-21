"""
c5_cudagraph_ab.py  —  T28: CUDAグラフ寄与の within-config 分離測定（C5）

目的:
  「CUDAグラフは run間非再現性の源泉か、それとも決定論的シフトのみか」を分離測定する。
  v23-G/H の旧判定基準（within-config と cross-config の混同）を修正した設計。

条件:
  A = enforce_eager OFF（CUDAグラフ ON・vLLM 既定）
  B = enforce_eager ON （CUDAグラフ OFF・eager 実行）

測定軸:
  - within-config: 同一条件を R 回反復し unique hash 数 / dominant 率を見る
                   → グラフ ON で unique > グラフ OFF なら「グラフ由来 run間非決定」
                   → ほぼ同じなら「グラフは run分散源でない」（限定的・残差はアテンション経路）
  - cross-config : A の dominant hash ≠ B の dominant hash なら「グラフの決定論的シフト」

バッチ regime（重要）:
  bs=1 では A' で既に ~0%（1000/1000）と判明済 → グラフ寄与は bs=1 で上界 ~0。
  グラフの寄与は **バッチ圧下でこそ問題化** するため、target を (bs-1) 個のダミーと
  同時投入してバッチを形成する（v25/v26 と同方式）。バッチ構成は A/B で同一に固定。

モデル/精度:
  既定 = Qwen2.5-3B-Instruct（fp16・正典）。⚠️ 4GB GPU（3050Ti 等）では fp16 不可 →
  --model で AWQ を指定可能だが、AWQ は cross-config の交絡（アトラクター移動）が入るため
  「グラフ単体の within-config 分離」目的にはやむを得ない代替（結果に交絡注記が必要）。

実行環境（sm_75 / 2080Ti で必須・deps doc 準拠）:
  --attention-backend TRITON_ATTN / VLLM_USE_FLASHINFER_SAMPLER=0 / multiproc=spawn
  （Ampere sm_86 では無害なので付けたまま comparable に保つ）

実行例:
  # スモーク（両条件・bs=1,16・各20回）
  python -u c5_cudagraph_ab.py --repeat 20 --batch 1 16
  # 本走（両条件・bs=1,16・各500回・CR2+CR4+FY）
  python -u c5_cudagraph_ab.py --repeat 500 --batch 1 16 --tc CR2,CR4,FY
  # 条件Aのみ
  python -u c5_cudagraph_ab.py --condition A --repeat 500
  # AWQ 代替（4GB機）
  python -u c5_cudagraph_ab.py --model Qwen/Qwen2.5-3B-Instruct-AWQ --dtype auto

作成: 2026-06-19（T28・base: benchmark_v24_enforce_eager_ab.py + benchmark_v25_vllm_batch_ndet.py）
"""

import csv
import concurrent.futures
import hashlib
import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import json
from collections import Counter
from datetime import datetime

# ============================================================
# Configuration
# ============================================================

TIMESTAMP    = datetime.now().strftime("%Y%m%d_%H%M%S")
VLLM_HOST    = "http://127.0.0.1:8000"
VLLM_BIN     = os.environ.get("VLLM_BIN", "vllm")

DEFAULT_MODEL  = "Qwen/Qwen2.5-3B-Instruct"
DEFAULT_DTYPE  = "float16"
DEFAULT_REPEAT = 500
DEFAULT_BATCH  = [1, 16]
DEFAULT_TEMPS  = [0.0]            # GPU 数値経路の分離 → greedy 既定
DUMMY_MAX_TOK  = 50
TC_MAX_TOK     = 1500
TIMEOUT_SEC    = 180
SERVER_TIMEOUT = 360

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR   = os.path.join(PROJECT_ROOT, "results")
LOG_DIR      = os.path.join(PROJECT_ROOT, "logs")
DUMMY_JSON   = os.path.join(os.path.dirname(PROJECT_ROOT), "shared", "dummy_prompts_v1.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ============================================================
# テストケース
# ============================================================

CR_SYSTEM = "あなたは創造的で知識豊富なアシスタントです。"

ALL_CASES = [
    {"id": "CR2", "name": "素数と詩",          "system": CR_SYSTEM, "prompt": "素数をひとつ選び、詩を書け。"},
    {"id": "CR4", "name": "正多面体サスペンス", "system": CR_SYSTEM, "prompt": "正多面体をひとつ選び、短編サスペンスを書け。"},
    {"id": "FY",  "name": "Feynman",           "system": None,      "prompt": "Tell me about Richard Feynman."},
]
ALL_CASES_MAP = {tc["id"]: tc for tc in ALL_CASES}
DEFAULT_TC = "CR2,FY"   # CR2=深 basin / FY=中 basin（basin 深度で寄与が変わる対照）

# ============================================================
# ダミープロンプト（バッチ形成用）
# ============================================================

def load_dummy_prompts() -> list:
    with open(DUMMY_JSON, encoding="utf-8") as f:
        data = json.load(f)
    texts = [p["text"] for p in data["prompts"]]
    assert len(texts) >= 1, "dummy_prompts が空"
    return texts

# ============================================================
# vLLM サーバー管理（sm_75 互換・deps doc 準拠）
# ============================================================

def start_vllm_server(enforce_eager: bool, model: str, dtype: str,
                      gpu_util: float, vllm_bin: str) -> subprocess.Popen:
    cmd = [
        vllm_bin, "serve", model,
        "--port", "8000",
        "--dtype", dtype,
        "--gpu-memory-utilization", str(gpu_util),
        "--max-model-len", "4096",
        "--max-num-seqs", "64",
        "--attention-backend", "TRITON_ATTN",
    ]
    if enforce_eager:
        cmd.append("--enforce-eager")

    label    = "ON" if enforce_eager else "OFF"
    env = os.environ.copy()
    env["VLLM_USE_FLASHINFER_SAMPLER"]  = "0"
    env["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"

    log_path = os.path.join(LOG_DIR, f"c5_eager{label}_{TIMESTAMP}.log")
    print(f"\n[vLLM] 起動: enforce_eager={label}  (CUDAグラフ={'OFF' if enforce_eager else 'ON'})", flush=True)
    print(f"[vLLM] model={model} dtype={dtype} backend=TRITON_ATTN sampler=OFF", flush=True)
    print(f"[vLLM] ログ: {log_path}", flush=True)
    log_fp = open(log_path, "w")
    proc   = subprocess.Popen(cmd, stdout=log_fp, stderr=log_fp, preexec_fn=os.setsid, env=env)
    proc._log_fp = log_fp
    return proc


def wait_for_server(timeout: int = SERVER_TIMEOUT) -> bool:
    url      = f"{VLLM_HOST}/health"
    deadline = time.time() + timeout
    print(f"[vLLM] 起動待ち（最大{timeout}秒）", end="", flush=True)
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    print(f" 完了", flush=True)
                    return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(5)
    print(" タイムアウト", flush=True)
    return False


def stop_vllm_server(proc: subprocess.Popen):
    print("[vLLM] 停止中...", flush=True)
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=30)
    except Exception as e:
        print(f"[vLLM] SIGTERM失敗({e}), SIGKILL", flush=True)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
    if hasattr(proc, "_log_fp"):
        proc._log_fp.close()
    print("[vLLM] 停止完了", flush=True)
    time.sleep(5)

# ============================================================
# 環境情報 / HTTP
# ============================================================

def collect_env_info() -> dict:
    try:
        import torch
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A"
    except Exception:
        gpu = "N/A"
    try:
        import vllm
        vllm_ver = vllm.__version__
    except Exception:
        vllm_ver = "unknown"
    return {"hostname": socket.gethostname(), "gpu": gpu, "vllm_ver": vllm_ver}


_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def post_chat(model, messages, max_tokens, temperature):
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "temperature": temperature}
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(f"{VLLM_HOST}/v1/chat/completions",
                                  data=data, headers={"Content-Type": "application/json"})
    with _opener.open(req, timeout=TIMEOUT_SEC) as r:
        return json.loads(r.read())

# ============================================================
# 1 run = target + (bs-1) dummy を同時投入し、target の hash を取得
# ============================================================

def measure_batch_once(tc, model, temperature, batch_size, dummies, dummy_cursor) -> dict:
    """target を 1 件 + dummy を (batch_size-1) 件、同時並行で投入。target 行を返す。"""
    target_msgs = []
    if tc["system"]:
        target_msgs.append({"role": "system", "content": tc["system"]})
    target_msgs.append({"role": "user", "content": tc["prompt"]})

    # バッチ構成（A/B で同一になるよう dummy は決定論的に巡回選択）
    reqs = [("target", target_msgs, TC_MAX_TOK)]
    for k in range(batch_size - 1):
        d = dummies[(dummy_cursor + k) % len(dummies)]
        reqs.append(("dummy", [{"role": "user", "content": d}], DUMMY_MAX_TOK))

    start = time.time()
    target_resp = None
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as ex:
            futs = {ex.submit(post_chat, model, m, mt, temperature): kind
                    for (kind, m, mt) in reqs}
            for fut in concurrent.futures.as_completed(futs):
                kind = futs[fut]
                resp = fut.result()
                if kind == "target":
                    target_resp = resp
        elapsed = time.time() - start

        reply  = target_resp["choices"][0]["message"]["content"].strip()
        finish = target_resp["choices"][0]["finish_reason"]
        rhash  = hashlib.sha256(reply.encode()).hexdigest()[:16]
        return {"reply": reply, "finish": finish, "hash": rhash,
                "elapsed": elapsed, "status": "OK"}
    except Exception as e:
        return {"reply": str(e)[:200], "finish": "ERROR", "hash": "",
                "elapsed": time.time() - start, "status": "ERROR"}

# ============================================================
# 1 条件分の実験（逐次 CSV 保存）
# ============================================================

def run_condition(enforce_eager, model, temps, batches, repeat, cases,
                  dummies, env_info, host_tag) -> tuple[list, str]:
    condition = "B_eager_ON" if enforce_eager else "A_eager_OFF"
    csv_path  = os.path.join(OUTPUT_DIR, f"c5_cudagraph_{condition}_{host_tag}_{TIMESTAMP}.csv")
    fieldnames = None
    all_rows   = []

    print(f"\n{'='*64}")
    print(f"条件: {condition}  model={model}  temps={temps}  batch={batches}  repeat={repeat}")
    print(f"出力: {csv_path}")
    print(f"{'='*64}", flush=True)

    for temperature in temps:
        for bs in batches:
            for tc in cases:
                print(f"\n  [{condition}] temp={temperature} bs={bs} {tc['id']}", flush=True)
                cursor = 0
                for r in range(1, repeat + 1):
                    res = measure_batch_once(tc, model, temperature, bs, dummies, cursor)
                    cursor += max(0, bs - 1)
                    row = {
                        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "experiment":  "c5_cudagraph_ab",
                        **env_info,
                        "condition":   condition,
                        "enforce_eager": enforce_eager,
                        "batch_size":  bs,
                        "temperature": temperature,
                        "model":       model,
                        "tc_id":       tc["id"],
                        "tc_name":     tc["name"],
                        "run":         r,
                        "elapsed_sec": round(res["elapsed"], 3),
                        "reply_len":   len(res["reply"]),
                        "finish":      res["finish"],
                        "reply_hash":  res["hash"],
                        "reply":       res["reply"][:300],
                        "status":      res["status"],
                    }
                    all_rows.append(row)
                    if fieldnames is None:
                        fieldnames = list(row.keys())
                        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                            csv.DictWriter(f, fieldnames=fieldnames).writeheader()
                    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
                        csv.DictWriter(f, fieldnames=fieldnames).writerow(row)
                    if r <= 3 or r % 100 == 0:
                        print(f"    run {r:4d} | {res['elapsed']:.1f}s {row['reply_len']:4d}字 "
                              f"hash={res['hash']} {res['status']}", flush=True)

    ok = sum(1 for r in all_rows if r["status"] == "OK")
    print(f"\n[{condition}] 完了: {len(all_rows)}件 OK={ok}", flush=True)
    return all_rows, csv_path

# ============================================================
# within / cross-config サマリ（判定の核）
# ============================================================

def summarize(results_a, results_b, temps, batches, cases):
    print(f"\n{'='*64}")
    print("=== within / cross-config 判定 ===")
    print("  within: 同条件 R回の unique hash 数（少=決定的） / dominant率")
    print("  cross : A(graphON) と B(graphOFF) の dominant hash 一致か")
    print(f"{'='*64}")

    def stats(rows, tc_id, temp, bs):
        hs = [r["reply_hash"] for r in rows
              if r["tc_id"] == tc_id and r["temperature"] == temp
              and r["batch_size"] == bs and r["status"] == "OK"]
        if not hs:
            return None
        top, cnt = Counter(hs).most_common(1)[0]
        return {"n": len(hs), "uniq": len(set(hs)), "dom": cnt, "dom_hash": top,
                "dom_rate": cnt / len(hs)}

    for temp in temps:
        for bs in batches:
            for tc in cases:
                sa = stats(results_a, tc["id"], temp, bs) if results_a else None
                sb = stats(results_b, tc["id"], temp, bs) if results_b else None
                line = f"  temp={temp} bs={bs:3d} {tc['id']:<4}"
                if sa:
                    line += f" | A(graphON): {sa['uniq']:3d}種 dom={sa['dom']}/{sa['n']}({sa['dom_rate']*100:.0f}%)"
                if sb:
                    line += f" | B(graphOFF): {sb['uniq']:3d}種 dom={sb['dom']}/{sb['n']}({sb['dom_rate']*100:.0f}%)"
                if sa and sb:
                    cross = "同一" if sa["dom_hash"] == sb["dom_hash"] else "⚠️相違(決定論的シフト)"
                    # within-config 差: グラフ ON の unique がOFFを有意に上回るか（粗判定）
                    within = "グラフ寄与あり?" if sa["uniq"] > sb["uniq"] + 1 else "グラフ寄与~なし"
                    line += f" | cross={cross} | within={within}"
                print(line, flush=True)

    print("\n  判定指針:")
    print("  - bs=1 で A・B とも uniq≈1 → 既知の bs=1 ~0% を再確認（健全性）")
    print("  - bs>1 で A(graphON).uniq ≈ B(graphOFF).uniq → グラフは run分散源でない（限定的・確定）")
    print("  - bs>1 で A.uniq >> B.uniq            → グラフ由来 within-config 非決定（寄与あり）")
    print("  - dom_hash A≠B                        → グラフの決定論的シフト（非決定とは別物）")

# ============================================================
# エントリーポイント
# ============================================================

def main():
    ap = argparse.ArgumentParser(description="T28/C5: CUDAグラフ within-config 分離 AB")
    ap.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    ap.add_argument("--batch",  type=int, nargs="+", default=DEFAULT_BATCH)
    ap.add_argument("--temp",   type=float, nargs="+", default=DEFAULT_TEMPS)
    ap.add_argument("--tc",     default=DEFAULT_TC, help="カンマ区切り（例: CR2,CR4,FY）")
    ap.add_argument("--model",  default=DEFAULT_MODEL)
    ap.add_argument("--dtype",  default=DEFAULT_DTYPE, help="fp16機=float16 / AWQ機=auto")
    ap.add_argument("--gpu-util", type=float, default=0.85)
    ap.add_argument("--condition", choices=["AB", "A", "B"], default="AB")
    ap.add_argument("--ab-order",  choices=["A_first", "B_first"], default="A_first")
    ap.add_argument("--vllm-bin",  default=VLLM_BIN)
    args = ap.parse_args()

    temps   = sorted(set(args.temp))
    batches = sorted(set(args.batch))
    tc_ids  = [t.strip() for t in args.tc.split(",") if t.strip()]
    cases   = [ALL_CASES_MAP[t] for t in tc_ids if t in ALL_CASES_MAP]
    assert cases, f"有効な TC がありません: {args.tc}"

    dummies  = load_dummy_prompts()
    env_info = collect_env_info()
    host_tag = env_info["hostname"].split("-")[0].lower()[:8] or "host"

    print("=== c5_cudagraph_ab.py (T28) ===")
    print(f"model={args.model} dtype={args.dtype} temps={temps} batch={batches} repeat={args.repeat}")
    print(f"TC={[c['id'] for c in cases]}  condition={args.condition} order={args.ab_order}")
    print(f"[env] host={env_info['hostname']} gpu={env_info['gpu']} vllm={env_info['vllm_ver']}")
    if "3B-Instruct-AWQ" in args.model:
        print("⚠️ AWQ モデル: cross-config に量子化交絡が入る。within-config 分離のみ有効。")
    print(f"推定: 1条件 = {len(temps)*len(batches)*len(cases)*args.repeat} 回", flush=True)

    order = ([("A", False), ("B", True)] if args.ab_order == "A_first"
             else [("B", True), ("A", False)])

    results_a, results_b = [], []
    for label, eager in order:
        if args.condition != "AB" and args.condition != label:
            print(f"[SKIP] 条件{label}")
            continue
        proc = start_vllm_server(eager, args.model, args.dtype, args.gpu_util, args.vllm_bin)
        try:
            if not wait_for_server(SERVER_TIMEOUT):
                print(f"[ERROR] 起動タイムアウト 条件{label}。"
                      f"{'（graphON が sm_75 で失敗した可能性＝それ自体が知見）' if not eager else ''}")
                stop_vllm_server(proc)
                continue
            rows, _ = run_condition(eager, args.model, temps, batches, args.repeat,
                                    cases, dummies, env_info, host_tag)
            if eager:
                results_b = rows
            else:
                results_a = rows
        finally:
            stop_vllm_server(proc)

    if results_a or results_b:
        summarize(results_a, results_b, temps, batches, cases)
    else:
        print("[INFO] 結果なし。")


if __name__ == "__main__":
    main()
