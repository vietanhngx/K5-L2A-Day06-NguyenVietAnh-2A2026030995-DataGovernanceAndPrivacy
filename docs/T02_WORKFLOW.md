# T02 cá nhân: chạy và duyệt ảnh trên Windows

## Chạy offline

```powershell
# Ví dụ nối dây ngẫu nhiên theo hướng dẫn học viên
.\.venv\Scripts\python.exe -m src.main --track t02 --pipeline src.examples.random_baseline --output out/random_baseline --run-name random --offline --seed 42

# Baseline bắt buộc của đề T02: Laplacian toàn ảnh
.\.venv\Scripts\python.exe -m src.main --track t02 --pipeline src.baseline_t02 --output out/baseline --run-name baseline --offline --seed 42

# PoC: độ nét theo camera/điều kiện sáng, vùng đường tối, vùng cháy sáng
.\.venv\Scripts\python.exe -m src.main --track t02 --output out/poc --run-name poc --offline --seed 42

# Test; dùng cùng môi trường đã setup
.\.venv\Scripts\python.exe -m pytest -o addopts= -q
```

Mỗi lần chạy baseline/PoC xuất `raw_predictions.csv`, `ranked_review.csv`, `review_queue.csv`,
`contact_sheet.html`, `final_actions.csv`, `decision.json`, `decision_log.csv` và `run_info.json`.
`audit_log.jsonl` ghi sự kiện bắt đầu chạy, vấn đề provenance và quyết định người duyệt nếu có.

## Người duyệt thao tác

1. Mở `out/poc/contact_sheet.html` bằng trình duyệt. Không cần mạng.
2. Nhập tên, xem từng ảnh và chọn **giữ ảnh**, **cần chụp lại** hoặc **để xem lại**.
3. Bấm tải CSV, chép file vào `out/poc/review_queue_reviewed.csv`.
4. Chạy lại lệnh PoC. Xem quyết định từng ảnh trong `final_actions.csv` và sự kiện trong `audit_log.jsonl`.

Đây là vòng duyệt **đề xuất của máy**, không tự động lấy nhãn nội bộ làm lựa chọn reviewer.
Dự đoán gốc nằm riêng ở `raw_predictions.csv`. Ảnh chưa duyệt giữ `HOLD`; `model_action` là gợi ý gốc.
Điểm xếp hạng không đổi sau khi người duyệt sửa hành động, nên metric ranking đo khả năng ưu tiên của máy.

## Nhãn và tham số

- Nhãn nội bộ được người học xác nhận: `data/manual/t02_manual_labels.csv`.
- Không phải GT chính thức của giảng viên; không tạo `fixtures/*/gt/`.
- `configs/t02_calibration.json` được sinh từ **56 ảnh dev**, dùng 4 ảnh lỗi nặng theo nhãn nội bộ.
- Ngưỡng được chọn theo F1 trên dev, với quy tắc hòa điểm chọn ít báo nhầm hơn rồi chọn ngưỡng cao hơn.
- PoC hiện là heuristic, không có bộ phân loại lỗi nén chuyên biệt; không khẳng định xử lý tốt mọi loại lỗi.
- Pipeline chỉ đọc ảnh/metadata, manifest và tham số đã lưu; không đọc nhãn thủ công.
- Công cụ `tools.calibrate_t02` từ chối ghi đè tham số đã chốt. Muốn đổi protocol phải dùng file cấu hình mới và ghi rõ lý do.
- Nhãn eval đã được xem khi đối chiếu thủ công với trợ lý. Không mô tả tập này là hidden eval hay đánh giá mù.
- Đã chạy đánh giá nội bộ theo metric contract được người học duyệt. Kết quả chạy ở `out/internal_eval/`, bản lưu nộp bài ở `reports/`; báo cáo đã được điền theo nội dung người học rà soát.

## Đánh giá nội bộ (giữ nguyên tham số đã chốt)

```powershell
.\.venv\Scripts\python.exe -m tools.evaluate_t02_internal
```

Lệnh kiểm tra đủ nhãn, hash ảnh, hash nhãn dev so với calibration, seed/offline và pool prediction;
lưu dấu vân tay đầu vào trước khi chấm. Nếu nhãn, calibration, predictions hoặc metric contract khác lần đã chốt,
lệnh từ chối ghi đè kết quả trong cùng thư mục. Không tự chỉnh thuật toán dựa trên eval.

Kết quả gồm metric chuẩn của `src.evaluate`, bảng so sánh do `src.compare` sinh, slices theo ánh sáng/camera,
bootstrap theo cảnh và kết quả từng ảnh. Bootstrap chỉ lấy lại mẫu từ 10 cảnh eval đã có; kể cả khi CI recall
thu hẹp về 1.0, không được suy ra hệ thống hoàn hảo trên dữ liệu mới.

Phải phân biệt **xếp hạng top-20** với **phân loại tự động theo ngưỡng**: đưa được ảnh lỗi vào queue không có nghĩa
máy đã phân loại ảnh đó đúng. Runtime là thời gian E2E (cả trích đặc trưng dùng chung và dựng giao diện), không phải
benchmark riêng của phép Laplacian hay riêng của mô hình.

## Chính sách đã được người học duyệt

`configs/lab.yaml` đã bật `review_gate_approved: true` sau khi người học xác nhận.
Nếu cấu hình không khai báo hoặc đặt `false`, hệ thống giữ `HOLD` chờ phê duyệt chính sách.
Quy tắc được chấp nhận:

- Chưa duyệt hết top-20, còn ảnh bỏ qua hoặc chưa quyết định: `HOLD`.
- Đã duyệt hết, có ảnh cần chụp lại: `RECAPTURE`.
- Đã duyệt hết, tất cả ảnh trong hàng chờ dùng được: `KEEP` **chỉ cho hàng chờ đã duyệt**.

Không tự điền reviewer, không tự ký duyệt. Quyết định chung chỉ áp dụng cho hàng chờ đã duyệt.
