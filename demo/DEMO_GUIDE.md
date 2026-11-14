# Hướng dẫn demo T02

**Hướng dẫn chính theo PDF giảng viên:** mở [DEMO_6_BUOC.md](DEMO_6_BUOC.md). Tài liệu bên dưới mô tả bộ slide và công cụ phát lại bằng chứng 20 ảnh; không thay cho bước duyệt trực tiếp một mục trong hướng dẫn 6 bước.

Mở `demo/T02_Demo_G04.pptx` để trình chiếu 5 slide. Phần Notes của từng slide có lời dẫn và nguồn bằng chứng.

## Lời dẫn cho 5 slide

1. **Bài toán:** từ 96 ảnh giả lập, ưu tiên 20 ảnh nghi lỗi để người kiểm tra quyết định. Bài làm cá nhân của Nguyễn Việt Anh, có trợ lý AI hỗ trợ phần code và kiểm thử.
2. **Dữ liệu và luồng chạy:** 56 ảnh dev để chọn tham chiếu/ngưỡng; 40 ảnh eval để đối chiếu nội bộ. Pipeline có đủ load, process, rank, review, decide. Nhãn tự gán, đã xem khi đối chiếu, không phải GT kín của giảng viên.
3. **Kết quả:** random tìm 4/6 ảnh lỗi nặng trong top-20 eval; baseline và PoC đều 6/6. Cả hai Precision@20=30%, chưa có cải thiện ở chỉ số chính. PoC giảm ảnh usable vào queue ban đêm nhưng tăng ở ban ngày.
4. **Lỗi cụ thể:** ảnh `img_17_2` lóa nặng nhưng máy chưa kết luận lỗi nặng; ảnh `img_16_2` mờ nhẹ nhưng máy đề xuất chụp lại. Người duyệt sửa cả hai. Chỉ số xếp hạng cao không có nghĩa ngưỡng tự phân loại tốt.
5. **Kết quả người duyệt:** queue thật từ 96 ảnh có 20 ảnh, người học giữ 11 và yêu cầu chụp lại 9. Quyết định chung RECAPTURE chỉ cho queue. 76 ảnh ngoài queue vẫn HOLD. Có 59 test đạt, 39 test cần GT bị skip.

## Chạy demo offline

Trong thư mục gốc project, chạy:

```powershell
.\.venv\Scripts\python.exe demo/run_demo.py
```

Lệnh tạo một thư mục mới dưới `out/demo_runs/` rồi thực hiện:

1. Chạy PoC khi chưa có file duyệt: kết quả **HOLD**.
2. Chép `reports/review_queue.csv`, là file người học đã duyệt thật, vào thư mục demo và chạy lại: **11 KEEP, 9 RECAPTURE**, quyết định chung **RECAPTURE**.
3. Chạy lại lần nữa: audit vẫn có đúng **20 human_review**, không ghi trùng các quyết định cũ.

Đây là **phát lại bằng chứng duyệt đã có**, không phải tự tạo một lượt người duyệt mới. Terminal in đường dẫn trang review và các output để mở xem.
Thư mục `out/poc/` và các số liệu đánh giá đã lưu trong `reports/` không bị ghi đè.

## Các file nên mở khi trình bày

- `contact_sheet.html` trong thư mục demo vừa được in ra: ảnh và lựa chọn đã duyệt.
- `decision.json`: RECAPTURE, reason_code, owner, scope và số ảnh đã duyệt.
- `audit_log.jsonl`: ai duyệt, sửa từ gì sang gì; lọc action=`human_review` được 20 sự kiện.
- `reports/table1_baseline_vs_poc.md`: bảng so sánh do script sinh.
- `reports/evidence/pytest.txt`: kết quả test thực tế đã lưu.

## Những chỗ cần nói chính xác

- Top-20 eval lấy trong **40 ảnh eval**. Queue duyệt thật lấy trong **96 ảnh**. Vì vậy bảng đánh giá có 6 ảnh lỗi nặng trong top-20, còn queue duyệt thật có 9 ảnh cần chụp lại.
- Chỉ mức 2 là positive trong bộ nhãn nội bộ. Mức 1 vẫn dùng được.
- Nhận ra vùng/vật khác với đọc được chữ biển số. Không kết luận ảnh lỗi nặng chỉ vì chữ biển số nhỏ hoặc không đọc được.
- Không nói PoC vượt baseline ở Recall@20 hay Precision@20. Không nói kết quả nội bộ là điểm chính thức.
- Số runtime trong báo cáo lấy từ lần chạy đã lưu. Khi chạy demo lại, thời gian có thể khác; không sửa tay số liệu cũ.
- Chưa có kiểm thử dữ liệu thật, out-of-domain, ablation hoặc bằng chứng freeze đúng phút 180.
- Chỉ tạo tag `demo`/`final` và cập nhật SHA khi có commit thật. Không dùng tag để giả nhận thời điểm chưa thực hiện.
