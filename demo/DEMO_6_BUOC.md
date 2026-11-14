# Demo trực tiếp T02 theo 6 bước

Đối chiếu theo `DEMO_CHUNG_CAC_NHOM.pdf` do người học cung cấp. Bộ 5 slide chỉ hỗ trợ giới thiệu; phần chính là trình diễn trực tiếp dưới đây.
Nguyễn Việt Anh làm cá nhân, đảm nhận các vai trò điều phối, dữ liệu, xử lý, kiểm tra, người duyệt và thử ca khó. Code/test có trợ lý AI hỗ trợ.

## Bước 01. Nêu bài toán

Nói: “Tôi làm T02 để ưu tiên ảnh mờ, tối, lóa hoặc vỡ hình cần kiểm tra. Máy đưa ra hàng chờ 20 ảnh; người duyệt quyết định giữ, chụp lại hoặc tạm giữ.”

Mở slide 1 hoặc `docs/tracks/T02.md`. Nêu đầu ra: bảng xếp hạng, quyết định từng ảnh và audit log.

## Bước 02. Mở một mẫu đầu vào

Mở `fixtures/t02_raw_qc/images/img_16_2.jpg` và dòng tương ứng trong `fixtures/t02_raw_qc/images.csv`.

Nói: “Đây là ảnh synthetic của đề, CC0-1.0 theo manifest; thuộc cam_A, ban ngày, split eval. Nhãn tự kiểm của tôi là mờ nhẹ, vẫn dùng được vì còn xác định được vật và đường nét chính.”

Đây là kết quả tự kiểm, không phải điểm chính thức hoặc GT kín của giảng viên.

## Bước 03. Chạy bản thử

Nói: “Baseline dùng độ nét Laplacian toàn ảnh. PoC thêm tham chiếu camera/ánh sáng và tín hiệu tối/lóa. Tham số đã chọn từ dev và không đổi sau eval.”

Chạy từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe demo/live_demo.py start
```

Lệnh tạo phiên mới dưới `out/demo_live/`, chạy offline và in đường dẫn `review_queue.csv`, `before_item.csv` và `duyet_1_anh.html`.
Mở queue top-20 và trang một ảnh. Máy đề xuất RECAPTURE cho `img_16_2`; hành động cuối trước khi người duyệt quyết định là HOLD.

## Bước 04. Duyệt một mục

Trên `duyet_1_anh.html`, tự nhập tên, xem ảnh và chọn quyết định. Nếu giữ đánh giá đã chốt, chọn **Vẫn dùng được — giữ ảnh**.
Tự ghi lý do quan sát của bạn rồi tải CSV. File mới tên `t02_live_review.csv`.

Trang không điền sẵn quyết định cũ. Demo này yêu cầu đủ quyết định, người duyệt và lý do thật.

## Bước 05. Chạy lại và kiểm thay đổi

Sau khi tải file, chạy:

```powershell
.\.venv\Scripts\python.exe demo/live_demo.py apply --review "D:\00_Downloads\t02_live_review.csv"
```

Nếu file tải về có tên khác, thay đường dẫn bằng tên thật. Mở các file trong phiên mới:

- `before_after.csv`: đúng image_id, đề xuất máy và quyết định trước/sau người duyệt.
- `audit_log.jsonl`: ai duyệt, sửa từ gì sang gì, vì sao.
- `final_actions.csv`: hành động cuối của ảnh vừa duyệt.
- `decision.json`: quyết định chung của queue.

Nếu chọn giữ ảnh, đề xuất máy là RECAPTURE nhưng hành động cuối của ảnh là KEEP. Điểm xếp hạng gốc không đổi.
**Phiên mới chỉ duyệt một ảnh nên quyết định chung vẫn HOLD**, không giả nhận đã duyệt đủ 20.
Kết quả 11 KEEP/9 RECAPTURE trong báo cáo thuộc vòng duyệt 20 ảnh đã làm trước đó, lưu riêng trong `reports/`.

## Bước 06. Nêu hiệu quả và giới hạn

Mở `reports/table1_baseline_vs_poc.md`, `reports/evidence/pytest.txt` và ảnh `img_17_2.jpg`.

Nói:

- Baseline và PoC cùng tìm đủ 6/6 lỗi nặng trong top-20 eval, Precision@20 đều 30%. Chưa có cải thiện chỉ số chính.
- PoC giảm ảnh usable vào queue ban đêm từ 7/15 còn 4/15, nhưng ban ngày tăng từ 6/17 lên 10/17.
- `img_17_2` bị lóa nặng nhưng score dưới ngưỡng tự phân loại dù vẫn vào queue. Máy có thể ưu tiên đúng nhưng đề xuất hành động sai.
- Ngưỡng PoC chỉ nhận đúng 1/6 ảnh lỗi nặng trong eval. Không chỉnh ngưỡng trên eval để làm đẹp kết quả.
- Có 59 test đạt, 39 test cần GT bị skip. Bộ nhãn là kết quả tự kiểm, không phải điểm chấm chính thức.

Top-20 eval chọn trong 40 ảnh eval. Queue duyệt thật chọn trong toàn bộ 96 ảnh. Hai pool khác nhau.

## Phát lại bằng chứng cũ khi cần

`python demo/run_demo.py` phát lại vòng duyệt 20 ảnh đã có, kiểm 11 KEEP/9 RECAPTURE và audit không trùng. Lệnh này không thay thao tác duyệt trực tiếp ở bước 04.
Các phiên demo mới không ghi đè `out/poc/`, nhãn thủ công, bảng so sánh hoặc báo cáo gốc.
