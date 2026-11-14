r"""Replay the real T02 review in a fresh output folder, completely offline.

Run from the repo: .\.venv\Scripts\python.exe demo/run_demo.py
The original out/poc and archived evaluation results remain unchanged.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    evidence = root / "reports/review_queue.csv"
    output = root / "out/demo_runs" / uuid.uuid4().hex[:10]
    output.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, "-X", "utf8", "-m", "src.main", "--config", "configs/lab.yaml",
               "--track", "t02", "--output", str(output), "--run-name", "demo", "--offline", "--seed", "42"]

    def run():
        subprocess.run(command, cwd=root, check=True)
        return json.loads((output / "decision.json").read_text(encoding="utf-8"))

    print("1. Fresh run without human decisions", flush=True)
    initial = run()
    assert initial["status"] == "HOLD" and initial["reason_code"] == "REVIEW_INCOMPLETE"
    print("PASS: HOLD while waiting for human review", flush=True)

    print("2. Replay the student's archived, real review CSV", flush=True)
    shutil.copyfile(evidence, output / "review_queue_reviewed.csv")
    after = run()
    assert after["status"] == "RECAPTURE" and after["metrics"]["confirmed_reviews"] == 20
    with (output / "final_actions.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert sum(r["pred_action"] == "KEEP" for r in rows) == 11
    assert sum(r["pred_action"] == "RECAPTURE" for r in rows) == 9
    assert sum(r["pred_action"] == "HOLD" for r in rows) == 76
    print("PASS: 11 KEEP, 9 RECAPTURE, 76 outside-queue HOLD", flush=True)

    def count_reviews():
        events = [json.loads(s) for s in (output / "audit_log.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
        return sum(e["action"] == "human_review" for e in events)

    assert count_reviews() == 20
    print("3. Repeat run to check append-only audit without duplicate reviews", flush=True)
    assert run()["status"] == "RECAPTURE"
    assert count_reviews() == 20
    print("PASS: still exactly 20 human_review events", flush=True)
    print(f"Demo output: {output}", flush=True)
    print(f"Open review page: {output / 'contact_sheet.html'}", flush=True)


if __name__ == "__main__":
    main()
