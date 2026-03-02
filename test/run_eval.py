#!/usr/bin/env python3
"""eval runner: spawns backend with a given config, runs eval data, prints precision/recall/F1.

usage:
    python test/run_eval.py --config configs/eval_run_1.toml
    python test/run_eval.py --config configs/eval_run_2.toml --data test/eval.json
    python test/run_eval.py --config config.toml --no-server   # if server already running

eval.json format: each item must have 'text' and 'expected_classification' (SAFE|LOW_RISK|HIGH_RISK).
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DATA = Path(__file__).parent / "eval.json"
LABELS = ["SAFE", "LOW_RISK", "HIGH_RISK"]

def parse_args():
    p = argparse.ArgumentParser(description="Noupe pipeline eval runner")
    p.add_argument("--config", required=True, help="path to config.toml to use for this run")
    p.add_argument("--data", default=str(DEFAULT_DATA), help="path to eval JSON (default: test/eval.json)")
    p.add_argument("--port", type=int, default=8000, help="backend port (default: 8000)")
    p.add_argument("--no-server", action="store_true", help="skip spawning server (assume already running)")
    p.add_argument("--timeout", type=int, default=60, help="seconds to wait for server startup (default: 60)")
    return p.parse_args()

def wait_for_server(url, timeout):
    health = f"{url}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False

def classify(url, text, entity_id=None):
    payload = {"text": text}
    if entity_id:
        payload["entity_id"] = entity_id
    req = urllib.request.Request(
        f"{url}/classify",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def compute_metrics(pairs):
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    for pred, exp in pairs:
        if pred == exp:
            tp[exp] += 1
        else:
            fp[pred] += 1
            fn[exp] += 1
    per_class = {}
    for label in LABELS:
        p_denom = tp[label] + fp[label]
        r_denom = tp[label] + fn[label]
        precision = tp[label] / p_denom if p_denom else 0.0
        recall = tp[label] / r_denom if r_denom else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        support = r_denom
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
    macro_p = sum(v["precision"] for v in per_class.values()) / len(LABELS)
    macro_r = sum(v["recall"] for v in per_class.values()) / len(LABELS)
    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(LABELS)
    accuracy = sum(tp.values()) / len(pairs) if pairs else 0.0
    return per_class, macro_p, macro_r, macro_f1, accuracy

def main():
    args = parse_args()
    config_path = os.path.abspath(args.config)
    data_path = os.path.abspath(args.data)
    api_url = f"http://127.0.0.1:{args.port}"

    if not os.path.exists(config_path):
        print(f"[error] config not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(data_path):
        print(f"[error] eval data not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    with open(data_path) as f:
        data = json.load(f)

    server_proc = None
    if not args.no_server:
        venv_python = REPO_ROOT / ".venv" / "bin" / "python"
        python = str(venv_python) if venv_python.exists() else sys.executable
        env = {**os.environ, "NOUPE_CONFIG": config_path}
        cmd = [python, "-m", "uvicorn", "backend.main:app",
               "--host", "0.0.0.0", "--port", str(args.port)]
        print(f"[eval] config  : {config_path}")
        print(f"[eval] data    : {data_path}")
        print(f"[eval] starting backend...")
        server_proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), env=env)
        if not wait_for_server(api_url, args.timeout):
            print("[error] server did not start in time", file=sys.stderr)
            server_proc.kill()
            sys.exit(1)
        print(f"[eval] server ready on {api_url}")

    try:
        pairs = []
        print()
        for item in data:
            test_id = item.get("id", "?")
            text = item.get("text", "")
            expected = item.get("expected_classification", "").upper().strip()
            entity_id = item.get("entity_id")
            if not expected:
                print(f"[skip] id={test_id}: missing expected_classification")
                continue
            if expected not in LABELS:
                print(f"[skip] id={test_id}: unknown label '{expected}' (must be SAFE|LOW_RISK|HIGH_RISK)")
                continue
            try:
                resp = classify(api_url, text, entity_id)
                predicted = resp.get("classification", "").upper().strip()
                match = "✓" if predicted == expected else "✗"
                print(f"  [{match}] id={test_id:<4} expected={expected:<10} predicted={predicted}")
                pairs.append((predicted, expected))
            except urllib.error.URLError as e:
                print(f"  [error] id={test_id}: request failed — {e}")
            except Exception as e:
                print(f"  [error] id={test_id}: {e}")

        if not pairs:
            print("[eval] no valid pairs — nothing to evaluate")
            return

        per_class, macro_p, macro_r, macro_f1, accuracy = compute_metrics(pairs)

        print()
        print("=" * 56)
        print(f"  config  : {os.path.basename(config_path)}")
        print(f"  samples : {len(pairs)}")
        print(f"  accuracy: {accuracy:.4f}")
        print()
        print(f"  {'label':<12} {'precision':>10} {'recall':>10} {'f1':>10} {'support':>8}")
        print(f"  {'-' * 54}")
        for label in LABELS:
            m = per_class[label]
            print(f"  {label:<12} {m['precision']:>10.4f} {m['recall']:>10.4f} {m['f1']:>10.4f} {m['support']:>8}")
        print(f"  {'-' * 54}")
        print(f"  {'macro':<12} {macro_p:>10.4f} {macro_r:>10.4f} {macro_f1:>10.4f}")
        print("=" * 56)

    finally:
        if server_proc:
            server_proc.send_signal(signal.SIGINT)
            server_proc.wait()
            print("\n[eval] server stopped")

if __name__ == "__main__":
    main()
