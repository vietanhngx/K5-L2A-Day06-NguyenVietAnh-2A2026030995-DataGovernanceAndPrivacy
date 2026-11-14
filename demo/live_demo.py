"""Live T02 demo: start a blank one-item review, then apply the user's CSV."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.common.review import load_review_decisions
from src.t02_review_page import render
import pandas as pd

ITEM = "img_16_2"
BASE = ROOT / "out/demo_live"


def run(session: Path) -> None:
    subprocess.run([sys.executable, "-X", "utf8", "-m", "src.main", "--config", "configs/lab.yaml",
                    "--track", "t02", "--output", str(session), "--run-name", "demo_live",
                    "--offline", "--seed", "42"], cwd=ROOT, check=True)


def save_row(path: Path, row: dict) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


def start() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    session = BASE / uuid.uuid4().hex[:10]
    session.mkdir(exist_ok=False)
    run(session)
    queue = pd.read_csv(session / "review_queue.csv", keep_default_na=False)
    one = queue[queue.item_id == ITEM].copy()
    if len(one) != 1:
        raise ValueError(f"{ITEM} is not in this run's top-20; review demo setup")
    final = pd.read_csv(session / "final_actions.csv", keep_default_na=False)
    save_row(session / "before_item.csv", final[final.image_id == ITEM].iloc[0].to_dict())
    page_path = session / "duyet_1_anh.html"
    render(one, page_path, ROOT / "fixtures/t02_raw_qc")
    page = page_path.read_text(encoding="utf-8")
    page = page.replace("Duyệt 20 ảnh máy ưu tiên", f"Duyệt trực tiếp một ảnh: {ITEM}")
    page = page.replace("Lý do (có thể bỏ trống)", "Lý do bạn chọn (bắt buộc cho demo này)")
    page = page.replace("Đây là bước duyệt đề xuất của máy, khác với bộ nhãn đối chiếu bạn đã tạo.",
                        "Bạn tự nhập tên, chọn quyết định và ghi lý do. Trang này không điền sẵn nhãn hoặc quyết định cũ.")
    page = page.replace("key='t02-review-'", f"key='t02-live-{session.name}-'")
    page = page.replace("a.download='review_queue_reviewed.csv'", "a.download='t02_live_review.csv'")
    page = page.replace("chép file <b>review_queue_reviewed.csv</b> vào cùng thư mục với trang này, rồi chạy lại PoC.",
                        "chạy lệnh apply trong hướng dẫn demo để nhập file t02_live_review.csv và chạy lại PoC.")
    marker = " const url=URL.createObjectURL"
    assert page.count(marker) == 1
    page = page.replace(marker,
                        " if(cards.some(c=>!c.querySelector('.action').value||!c.querySelector('.note').value.trim())){alert('Chọn quyết định và ghi lý do trước khi tải file.');return;}\n" + marker)
    page_path.write_text(page, encoding="utf-8")
    (BASE / "latest.json").write_text(json.dumps({"session": session.name, "item_id": ITEM}), encoding="utf-8")
    print(f"\nẢnh đầu vào: {ROOT / 'fixtures/t02_raw_qc/images' / (ITEM + '.jpg')}")
    print(f"Trang duyệt mới: {page_path}")
    print(f"Trước khi duyệt: {session / 'before_item.csv'}")
    print('Sau khi tải CSV, chạy: .\\.venv\\Scripts\\python.exe demo/live_demo.py apply --review "D:\\00_Downloads\\t02_live_review.csv"')


def apply(review_path: Path) -> None:
    state = json.loads((BASE / "latest.json").read_text(encoding="utf-8"))
    session = BASE / state["session"]
    if session.resolve().parent != BASE.resolve():
        raise ValueError("Invalid demo session path")
    reviewed = load_review_decisions(review_path)
    if len(reviewed) != 1 or reviewed.iloc[0].item_id != ITEM:
        raise ValueError(f"Dùng file t02_live_review.csv của trang mới; cần đúng một quyết định cho {ITEM}.")
    row = reviewed.iloc[0]
    if not row.review_note.strip() or not row.reviewed_at.strip():
        raise ValueError("Demo cần lý do và thời điểm duyệt thật; quay lại trang và nhập trước khi xuất CSV.")
    queue = pd.read_csv(session / "review_queue.csv").set_index("item_id")
    if abs(float(row.score) - float(queue.loc[ITEM, "score"])) > 1e-6 or row.suggested_action != queue.loc[ITEM, "suggested_action"]:
        raise ValueError("File duyệt không khớp hàng chờ của phiên demo hiện tại.")
    if row.reviewer_decision in {"edit", "reject"} and row.override_value.strip().upper() not in {"KEEP", "RECAPTURE"}:
        raise ValueError("Quyết định sửa phải là KEEP hoặc RECAPTURE.")
    destination = session / "review_queue_reviewed.csv"
    if destination.exists() and destination.read_bytes() != review_path.read_bytes():
        import hashlib
        backup = session / ("review_previous_" + hashlib.sha256(destination.read_bytes()).hexdigest()[:12] + ".csv")
        if not backup.exists():
            shutil.copyfile(destination, backup)
    shutil.copyfile(review_path, destination)
    run(session)
    before = pd.read_csv(session / "before_item.csv").iloc[0]
    final = pd.read_csv(session / "final_actions.csv")
    after = final[final.image_id == ITEM].iloc[0]
    comparison = {"image_id": ITEM, "model_action": before.model_action,
                  "before_human_action": before.pred_action, "after_human_action": after.pred_action,
                  "reviewer": row.reviewer, "review_note": row.review_note, "reviewed_at": row.reviewed_at}
    save_row(session / "before_after.csv", comparison)
    print(f"\n{ITEM}: máy đề xuất {before.model_action}; trước duyệt {before.pred_action}; sau duyệt {after.pred_action}.")
    print(f"Người duyệt: {row.reviewer}; lý do: {row.review_note}")
    print(f"So trước/sau: {session / 'before_after.csv'}")
    print(f"Lịch sử: {session / 'audit_log.jsonl'}")
    print("Quyết định chung vẫn HOLD nếu chưa duyệt đủ 20 ảnh; một mục có thể đã có quyết định cuối riêng.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("start")
    applied = sub.add_parser("apply")
    applied.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "start":
        start()
    else:
        apply(args.review)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
