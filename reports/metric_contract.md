# Metric contract (khai báo bắt buộc — chốt ở phút 30, trước khi chạy eval)

> Các metric chuẩn đã được cài trong `src/metrics/tracks.py`. File này là nơi nhóm **cam kết** cách dùng chúng.
> Không đổi testset, threshold hay trọng số sau khi đã thấy kết quả eval.

| Mục | Khai báo của nhóm |
|---|---|
| Track | T02 · Raw QC Triage · G04 · cá nhân |
| Primary metric (tên đúng như evaluator in ra) | Defect Recall@B; kèm Precision@B |
| Tăng tốt hay giảm tốt? | higher cho Recall và Precision; lower cho bỏ sót/báo nhầm |
| Đơn vị đánh giá (image / region / pair / release / batch / case …) | image |
| Công thức + numerator / denominator | Recall@20 = số ảnh is_defect=1 trong top-20 eval / tổng ảnh is_defect=1 trong eval. Precision@20 = số ảnh is_defect=1 trong top-20 eval / 20. Nhãn nội bộ: chỉ severity=2 là positive; severity=0 hoặc 1 là negative. |
| Cách ghép prediction ↔ GT (IoU? id? tolerance?) | Ghép một-một theo image_id với nhãn thủ công nội bộ; không có GT chính thức của giảng viên. |
| Candidate pool cố định | fixtures/t02_raw_qc: 96 ảnh, 24 cảnh gốc; dev 56 ảnh, eval 40 ảnh. Không đổi split. |
| Review budget B / K | B=20. Evaluator lọc eval rồi lấy top-20 của 40 ảnh eval. Queue duyệt thật lấy top-20 của toàn bộ 96 ảnh: hai pool này phải được báo riêng. |
| Seed | 42 |
| Threshold policy (chọn trên dev như thế nào) | configs/t02_calibration.json, chỉ dùng dev để lấy tham chiếu và tối đa F1 nhị phân; hòa điểm ưu tiên ít FP rồi ngưỡng cao hơn. Baseline: score=1/(Laplacian variance+1e-6), ngưỡng 0.549755621994803. PoC: max tín hiệu mờ/tối/lóa, ngưỡng 37.3380679965657. Không sửa sau khi xem eval. |
| Eval split (không dùng để tune) | split=eval, 40 ảnh và 6 ảnh lỗi nặng theo nhãn nội bộ. Nhãn đã được người học và trợ lý xem để đối chiếu, không mô tả là đánh giá mù hoặc hidden eval. Pipeline không đọc file nhãn. |
| Chỉ số lỗi xấu (miss / false alarm / false reject) | Ảnh lỗi nặng không nằm top-20; ảnh usable (mức 0/1) nằm top-20. Báo riêng lỗi của dự đoán nhị phân theo ngưỡng, không đồng nhất với lỗi xếp hạng. |
| Slices sẽ báo cáo (≥2) | light=day/dusk/night và camera_id=cam_A/cam_B; thêm loại lỗi nếu có mẫu. |
| Cách báo độ bất định khi N nhỏ (Wilson CI / bootstrap) | Bootstrap theo cảnh gốc, 2.000 lần, seed 42, percentile 2.5–97.5%; mỗi lần tính lại top-20. Loại lần bootstrap không có positive khỏi CI recall và báo số lần hợp lệ. CI chỉ thể hiện biến thiên trong tập nội bộ nhỏ. |
| Ngày giờ chốt + người chốt | 15/11/2026 02:22:11 (Asia/Saigon), sau khi Nguyễn Việt Anh chấp nhận nội dung qua hội thoại và trước khi chạy eval nội bộ. Tham số đã được sinh từ dev trước đó; không ghi lùi mốc phút 30 của lớp. |

Nếu baseline = 0 thì ghi rõ "baseline = 0" thay vì phần trăm cải thiện.

Baseline chính là Laplacian toàn ảnh; random seed 42 chỉ là đối chứng tham khảo theo hướng dẫn học viên.
Các số liệu kết quả phải do script sinh ra. Không tuyên bố cải thiện nếu số đo không chứng minh được.
