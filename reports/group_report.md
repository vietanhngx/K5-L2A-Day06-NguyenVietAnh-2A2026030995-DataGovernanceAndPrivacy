# Group Report — Day 06 Data Lab (Field-to-Release PoC)

> Điền đầy đủ, cụ thể, không viết chung chung. Mọi con số phải lấy từ file do script sinh ra
> (`reports/metrics_*.json`, `reports/table1_baseline_vs_poc.md`) — không gõ tay, không làm tròn mất đơn vị.
> 3–5 trang (hoặc README + report.md tương đương).

## 00 · Header

| Mục | Giá trị |
|---|---|
| Group ID | G04 |
| Challenge | T02 · Raw QC Triage |
| Thành viên (5–6) + vai trò | Nguyễn Việt Anh — mã học viên 2A2026030995, làm cá nhân; tự gán nhãn, duyệt ảnh, chốt policy; triển khai và kiểm thử có trợ lý AI hỗ trợ. Không có thành viên khác. |
| Git URL | https://github.com/vietanhngx/K5-L2A-Day06-NguyenVietAnh-2A2026030995-DataGovernanceAndPrivacy.git |
| Tag `demo-180m` (commit) | `demo` |
| Tag `final-24h` (commit) | `final` |
| Deadline (giờ VN) | 12:00 ngày 15/11/2026 |

## 01 · Problem statement

- Ai bị ảnh hưởng / ai chịu hậu quả khi hệ thống sai? Người kiểm ảnh và người dùng dữ liệu gán nhãn: bỏ sót ảnh lỗi làm giảm khả năng quan sát; báo nhầm làm tốn budget duyệt hoặc bỏ ảnh vẫn dùng được.
- Điểm nghẽn cụ thể: chỉ duyệt được 20 ảnh trong một lượt; cần xếp ảnh đáng nghi lên trước và có người quyết định cuối.
- Đầu vào → đầu ra: 96 ảnh JPEG synthetic và images.csv → đặc trưng chất lượng/score → ranked_review.csv, hàng chờ top-20 và contact_sheet.html → final_actions.csv, audit_log.jsonl, decision.json.
- Tiêu chí GO / HOLD / REWORK (chốt trước khi chạy eval): chưa duyệt đủ hoặc còn ảnh chưa quyết định → HOLD; đủ lượt duyệt, có ảnh cần chụp lại → RECAPTURE (REWORK); đủ lượt duyệt, toàn bộ queue dùng được → KEEP (GO), chỉ cho các ảnh trong queue. Chính sách được người học chấp nhận trước lần chấm eval nội bộ.
- Giả định của nhóm (cần DPO/legal/domain owner xác nhận): mục tiêu nội bộ là nhận ra vật, vị trí và đường viền chính; không bắt buộc đọc chữ biển số. Mức 2 là lỗi nặng, mức 0/1 vẫn dùng được. Đây là tiêu chí học tập; chưa có xác nhận từ domain owner độc lập.

## 02 · Data & provenance

| Split | N | Nguồn / link | License | Synthetic? |
|---|---|---|---|---|
| dev | 56 ảnh; 4 lỗi nặng | fixtures/t02_raw_qc; manifest của repo | CC0-1.0 theo manifest | Có |
| eval / heldout | 40 ảnh; 6 lỗi nặng | fixtures/t02_raw_qc; giữ nguyên split gốc | CC0-1.0 theo manifest | Có |

- Schema & class mapping: image_id, path, camera_id, light, split; nhãn nội bộ thêm defect_type (none/blur/glare/dark/compression), severity 0/1/2 và is_defect=1 chỉ khi severity=2. Đủ 96 nhãn do người học chấp nhận; không có GT chính thức trong repo.
- Seed: 42 · Cách chia split (theo scene/group/segment?): giữ nguyên split theo cảnh gốc trong fixture, 24 cảnh × 4 ảnh; dev 14 cảnh và eval 10 cảnh. Không chia lại theo từng ảnh.
- `manifest.csv` verified (sha256): có; kiểm tra thực tế 14 manifests, 0 failing — lệnh: `python -m tools.verify_manifests`
- Dữ liệu thật dùng (nếu có) và cách xây GT cho nó: không dùng dữ liệu thật. Người học tự gán 96 ảnh synthetic, trợ lý đưa ý kiến đối chiếu, người học quyết định nhãn cuối trong data/manual/t02_manual_labels.csv; không gọi đây là GT giảng viên hoặc đánh giá mù.

## 03 · Research & design

- 2–3 references (URL + ngày xem) và **vì sao** chọn kỹ thuật: https://docs.opencv.org/4.13.0/d5/db5/tutorial_laplace_operator.html (xem 14/11/2026): Giải thích toán tử Laplacian và phản ứng với đường biên; dùng để đối chiếu mô tả baseline. Code dùng primitive SciPy trong repo, không sao chép pipeline OpenCV. ; https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.label.html (xem 14/11/2026): Mô tả gán nhãn các vùng pixel liên thông; dùng để đo vùng trắng cháy sáng lớn nhất trong PoC. Chọn heuristic CPU để chạy offline và giải thích được tín hiệu; tài liệu được đọc khi rà soát mô tả kỹ thuật.
- Sơ đồ data flow (input → process → rank/QC → review → decision → report): ảnh + metadata → xác minh manifest → trích đặc trưng → score với tham số dev đã chốt → top-20 → người duyệt KEEP/RECAPTURE/HOLD → áp sửa đổi + audit → quyết định queue → script đánh giá nội bộ.
- Thành phần offline (model/weights + checksum + license nếu có): không dùng model pretrained hoặc weights; dùng NumPy/Pillow/SciPy và hạ tầng repo. Calibration SHA256: a7f8d3dc6d9e7bc35cadd77caac5087b24c37b7fd6a7f5d6bdcfea106ee2be73. Môi trường Python 3.13.15; ảnh synthetic CC0-1.0 theo manifest.
- Trade-offs đã cân nhắc: baseline đơn giản; PoC thêm tham chiếu camera/ánh sáng và tín hiệu vùng tối/lóa để giảm phụ thuộc độ nét toàn ảnh. Đổi lại tăng độ phức tạp và lệch theo nhóm; kết quả chính không tốt hơn baseline, ngưỡng tự phân loại còn yếu. Không có bộ phân loại nén ảnh chuyên biệt.

## 04 · Baseline vs PoC

- Baseline (mô tả, version/config, commit): src.baseline_t02; score=1/(Laplacian variance+1e-6), ngưỡng 0.549755621994803 từ dev. Config configs/t02_calibration.json. HEAD khi đo là b0ce8bf của starter, working tree chưa commit tại thời điểm đo; code sau đó được lưu trong commit 595f906. Hash nguồn lúc đo có trong protocol_lock.json.
- PoC (mô tả, version/config, commit): t02-qc-v1, src/pipeline.py + src/t02_qc.py; lấy max của tín hiệu mờ theo camera/ánh sáng, vùng đường tối và vùng cháy sáng; ngưỡng 37.3380679965657. HEAD khi đo b0ce8bf; bản triển khai sau đó được lưu trong commit 595f906. Random seed 42 chỉ là đối chứng tham khảo (Recall@20=4/6).
- Cùng budget / cùng heldout / cùng seed: xác nhận cùng B=20, 40 ảnh eval và seed 42; tham chiếu/ngưỡng chỉ dùng dev và giữ nguyên sau eval. Eval đã được xem khi đối chiếu nhãn, không phải hidden test. Top-20 eval khác queue duyệt thật top-20 trên 96 ảnh.

**Bảng 1 · Baseline vs PoC & hard slices** — dán output của
`python -m src.compare reports/metrics_baseline.json reports/metrics_poc.json`:

| Metric (unit) | Baseline | PoC | Δ & chú thích |
|---|---|---|---|
| Primary: Defect Recall@20 | 6/6 = 1.0000 | 6/6 = 1.0000 | Δ=0.0000; higher; PoC không vượt baseline. |
| Hard-slice: False alarm in top-20, night | 7/15 = 0.4667 | 4/15 = 0.2667 | Δ=-0.2000; lower; N=16, denominator=15 ảnh usable. |
| Review@B / miss / FP | Precision=6/20 = 0.3000; miss=0, usable trong queue=14 | Precision=6/20 = 0.3000; miss=0, usable trong queue=14 | Δ precision=0.0000; B=20 trên eval; đây là queue xếp hạng, không phải phân loại theo ngưỡng. |
| Runtime / 100 items | 0.4284 s | 0.4584 s | Δ=0.0300 s; CPU=AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD; E2E gồm trích đặc trưng chung và HTML, không phải thời gian thuật toán riêng. |

## 05 · Evaluation protocol

- Công thức primary metric, đơn vị đánh giá, TP/FP/FN, denominator: image; positive=mức 2. Trên top-20 eval, hai phương pháp đều TP=6, FP=14, FN=0; Recall=TP/(TP+FN), Precision=TP/20. Phân loại theo ngưỡng báo riêng: baseline TP=0/FP=0/FN=6/TN=34; PoC TP=1/FP=2/FN=5/TN=32 (xem `reports/metric_contract.md`).
- Threshold / budget B / K và lúc chốt: B=20, seed=42; tham số từ dev lưu trong configs/t02_calibration.json. Metric contract được ghi nhận chốt lúc 02:22:11 ngày 15/11/2026 giờ VN, sau khi người học đồng ý và trước khi chấm eval nội bộ; không ghi lùi mốc phút 30 của lớp.
- Độ bất định (CI/bootstrap/variance) khi N nhỏ: bootstrap theo 10 cảnh eval, 2.000 lần, seed 42; 1.992 lần có positive để tính recall. CI95 recall baseline=[0.8299242424242426, 1.0], PoC=[1.0, 1.0]; precision cả hai=[0.1, 0.55]. CI PoC suy biến do resampling tập nhỏ, không chứng minh tổng quát hoàn hảo.
- Lệnh evaluate chính xác: `python -m src.evaluate --track t02 --gt data/manual/t02_manual_labels.csv --pred out/poc/ranked_review.csv --split eval --budget 20 --run-name poc_internal --out reports/metrics_poc.json`; script tổng hợp: `python -m tools.evaluate_t02_internal`.

## 06 · Result slices

| Slice | N | Baseline | PoC | Ghi chú |
|---|---|---|---|---|
| light=night, false alarm trong top-20 eval | 16 ảnh; 15 usable | 7/15 = 0.4667 | 4/15 = 0.2667 | Ít ảnh usable bị đưa vào queue hơn; không đồng nghĩa tự động loại ảnh. |
| camera=cam_B, usable trong top-20 eval | 12 ảnh; 10 usable | 7/10 = 0.7000 | 3/10 = 0.3000 | Cả hai vẫn tìm 2/2 ảnh lỗi nặng; mẫu nhỏ. |

- Failure case 1 (ảnh/metadata + root cause): img_17_2 (eval/day/cam_A), nhãn glare mức 2. PoC xếp hạng 5 trên eval nhưng pred_is_defect=0: tín hiệu lóa chưa vượt ngưỡng chung đã fit dev. Ảnh lọt nếu chỉ dùng phân loại ngưỡng; người duyệt đã chọn chụp lại. Đây là phân tích heuristic, không phải nguyên nhân đã kiểm chứng bằng ablation.
- Failure case 2: img_16_2 (eval/day/cam_A), nhãn blur mức 1, score cao hơn ngưỡng nên máy đề xuất chụp lại; người duyệt sửa thành KEEP. Ngưỡng độ nét không phân biệt tốt ranh giới mờ nhẹ vẫn dùng được với mờ nặng. Ở toàn nhóm day, false alarm trong top-20 tăng từ 6/17 lên 10/17; đêm giảm từ 7/15 xuống 4/15.
- Latency / compute (máy, CPU, ms/item): Windows-11-10.0.26300-SP0; AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD; Python 3.13.15. Baseline E2E=0.4113 s/96 ảnh (4.2844 ms/ảnh), PoC=0.4401 s/96 ảnh (4.5844 ms/ảnh). Đây là một lần đo mỗi phương pháp, chưa benchmark lặp.

## 07 · Human & decision

- Review queue (file, B, cách ưu tiên): out/poc/review_queue.csv, B=20 trên toàn bộ 96 ảnh, score cao duyệt trước. Người học duyệt đủ 20: 11 KEEP, 9 RECAPTURE; 76 ảnh ngoài queue vẫn HOLD. Không nhầm với top-20 chỉ trên 40 ảnh eval.
- Cách override + audit log (`out/audit_log.jsonl`): reviewer “Nguyen Viet Anh” chọn trên contact_sheet.html, xuất CSV và chạy lại PoC; 6 edit từ RECAPTURE sang KEEP, 5 edit từ KEEP sang RECAPTURE, 9 approve (4 RECAPTURE, 5 KEEP). Có 20 sự kiện human_review trong out/poc/audit_log.jsonl; chạy lại không ghi trùng cùng quyết định. Dự đoán gốc ở raw_predictions.csv. Clone mới chưa có CSV duyệt sẽ HOLD; muốn phát lại bằng chứng, chép reports/review_queue.csv thành out/poc/review_queue_reviewed.csv rồi chạy lại. Không tự lấy nhãn đối chiếu để điền reviewer.
- Decision policy + `reason_code` + owner: đã bật review_gate_approved sau khi người học đồng ý; quyết định hiện RECAPTURE (canonical REWORK), reason_code=CONFIRMED_SEVERE_DEFECT; owner=Nguyễn Việt Anh — người thực hiện và tự review; scope=t02:review_queue.
- Khi nào HOLD/REWORK thay vì tự động release: HOLD khi chưa duyệt đủ, còn skip/escalate hoặc policy chưa được duyệt; REWORK/RECAPTURE nếu người duyệt xác nhận có ảnh lỗi nặng. KEEP chỉ xác nhận queue đã duyệt, không release toàn bộ tập 96 ảnh.

## 08 · Reproduce & tests

```bash
.\.venv\Scripts\python.exe -m pip install -r requirements.txt  # tạo .venv trước bằng py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m src.main --input fixtures/t02_raw_qc --config configs/lab.yaml --output out/poc --offline --seed 42
.\.venv\Scripts\python.exe -m src.evaluate --track t02 --gt data/manual/t02_manual_labels.csv --pred out/poc/ranked_review.csv --split eval --budget 20 --run-name poc_internal --out reports/metrics_poc.json
.\.venv\Scripts\python.exe -m pytest -q
```

- Output của `pytest -q`: chạy tương đương `python -m pytest -o addopts= -q`: 59 passed, 39 skipped; không failed. Skip là test requires_gt vì thiếu overlay giảng viên. Có 12 test T02 gồm E2E offline, tái lập, override/audit, input thiếu và review sai/cũ; log kiểm tra lưu trong reports/evidence/pytest.txt.
- Máy / CPU / OS / Python: AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD; Windows-11-10.0.26300-SP0; Python 3.13.15 · git sha: b0ce8bf (HEAD tại thời điểm đo); commit triển khai 595f906. protocol_lock.json lưu SHA256 code/nhãn/calibration lúc đánh giá; bản xuất sạch từ commit 595f906 đã tái lập kết quả (reports/evidence/final_repro_check.json).

## 09 · Limitations & ethics

- Rủi ro pháp lý / PII / license: chỉ dùng ảnh synthetic CC0-1.0 theo manifest; không dùng ảnh người/biển số thật. Chưa đánh giá quyền sử dụng dữ liệu ngoài fixture; nếu mở rộng cần kiểm nguồn/license và quyền xử lý tương ứng.
- Điều chưa biết; false alarms; nếu scale 10× thì sao: nhãn chủ quan của một người, có trợ lý đối chiếu; eval đã được xem và chỉ có 6 positive, không phải hidden GT. Hai phương pháp cùng Recall@20=1 và Precision@20=0.3; không chứng minh PoC tốt hơn. Ngưỡng PoC chỉ bắt 1/6 positive, bỏ 5; có 2 FP. Chưa kiểm dữ liệu thật, 10 ảnh out-of-domain, scale 10×, thời gian người duyệt hoặc ablation.
- Không tuyên bố "đạt GDPR / luật Việt Nam" từ checklist tự động; giả định cần DPO/legal xác nhận: PoC kiểm chất lượng ảnh, không phải công cụ chứng nhận tuân thủ. Chưa có DPO/legal thẩm định; không đưa ra kết luận pháp lý.
- Kế hoạch cải tiến: trong protocol mới, bổ sung nhãn dev độc lập cho glare/nén và trường hợp giáp ranh; nghiên cứu ngưỡng riêng theo loại lỗi, kiểm out-of-domain và ablation. Chưa thực hiện; không đổi ngưỡng trên eval hiện tại để làm đẹp kết quả.

## 10 · Team contribution

**Bảng 2 · Individual contribution evidence** (đối chiếu với `git shortlog -sne --all` và `reports/team_contributions.csv`)

| Học viên | Git author/email | Module / vai trò | Commit SHA / diff chứng minh | Trình bày? |
|---|---|---|---|---|
| Nguyễn Việt Anh (2A2026030995) | vietanhngx / ngvietanh240605@gmail.com | Bài cá nhân: gán nhãn 96 ảnh, duyệt 20 ảnh, chốt policy; code/test có trợ lý AI hỗ trợ. | 595f906b1ca4e60970c35d9d104517ddec808bf0 — code/config, nhãn, tests, bằng chứng và bộ demo; kiểm tra bằng git show --stat 595f906. | Chưa trình bày trên lớp; đã chuẩn bị bộ demo trong demo/ |
| Không áp dụng — bài cá nhân | Không có thành viên khác | Data + GT | Không áp dụng | Không áp dụng |
| Không áp dụng — bài cá nhân | Không có thành viên khác | Core algorithm | Không áp dụng | Không áp dụng |
| Không áp dụng — bài cá nhân | Không có thành viên khác | Metric + tests | Không áp dụng | Không áp dụng |
| Không áp dụng — bài cá nhân | Không có thành viên khác | Review queue + report | Không áp dụng | Không áp dụng |
| Không áp dụng — bài cá nhân | Không có thành viên khác | Research / ablation / debate | Không áp dụng | Không áp dụng |

## 11 · References

| URL | Ngày xem | 1–2 dòng ý nghĩa (không chép nguyên văn) |
|---|---|---|
| https://docs.opencv.org/4.13.0/d5/db5/tutorial_laplace_operator.html<br>https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.label.html | 14/11/2026 (cả hai nguồn) | Giải thích toán tử Laplacian và phản ứng với đường biên; dùng để đối chiếu mô tả baseline. Code dùng primitive SciPy trong repo, không sao chép pipeline OpenCV.<br>Mô tả gán nhãn các vùng pixel liên thông; dùng để đo vùng trắng cháy sáng lớn nhất trong PoC. |

---

**Bảng 3 · Checklist chốt khi nộp**

- [ ] Link repo và tag cuối cùng trong README; input mẫu không chứa PII thật.
- [x] Đúng 1 lệnh run, 1 lệnh evaluate, 1 lệnh tests; không cần download khi chạy.
- [x] Có baseline/PoC metrics, ≥1 failure case, reviewer evidence, decision log.
- [x] Có license/source provenance, data splits, seed, offline environment, GT/eval N.
- [x] Mỗi thành viên có ≥1 commit thực chất và được nêu minh bạch trong bảng trên.
