# Báo cáo thực hành Day 3

- Mã học viên theo lớp: 2A202603084
- Ngày / CVAT local: 11–12/11/2026 / CVAT Community v2.74.1 local (Docker Desktop + WSL 2), http://localhost:8080
- Công cụ đã dùng:
  - Gợi ý mask tự động: **YOLO11x-seg** (COCO, cho person/car/bus/truck/motorcycle/bicycle/traffic light) và **SegFormer-B2 Cityscapes** (cho road/sidewalk/building/vegetation/sky/pole/traffic sign), chạy bằng [`tools/preannotate.py`](../../tools/preannotate.py).
  - Tạo 9 task, import gợi ý và export ZIP bằng cvat-sdk qua [`tools/cvat_tasks.py`](../../tools/cvat_tasks.py).
  - Sửa thủ công trong CVAT: đổi label trong bảng Objects, vẽ thêm mask bằng Brush, sửa biên mask.
  - Trợ lý AI Claude Code đã viết hai script trên và hướng dẫn thao tác CVAT, đồng thời soạn report này từ ghi chú sửa mask của tôi, có đối chiếu với dữ liệu CVAT.
  - Không dùng SAM.

## 1. Bài đã nộp

Tất cả task đều bắt đầu từ gợi ý tự động. Cột "Sửa thủ công" ghi những gì tôi đã đổi so với gợi ý; "không" nghĩa là ZIP chứa gợi ý của máy, chưa chỉnh. **Lần 1** là sửa trước khi xem đáp án; **lần 2** là sửa **sau khi** đã chạy scorer với đáp án ba tier (`tiers_gt.zip`) và xem vị trí vật bị sót.

| Task | File ZIP đúng tên | Hoàn thành mấy ảnh | Sửa thủ công | Điểm tối đa (coach chấm sau) |
| --- | --- | ---: | --- | ---: |
| easy_semantic | `submissions/easy_semantic.zip` | 3 / 3 | không | 20 |
| medium_instance | `submissions/medium_instance.zip` | 3 / 3 | Lần 1: không. Lần 2: `000000181542.jpg` thêm mask person shape 66–72 | 32 |
| hard_panoptic | `submissions/hard_panoptic.zip` | 2 / 2 | Lần 1: `000000460147.jpg` 1 mask truck → car. Lần 2: `000000350023.jpg` thêm car shape 47, 48 và traffic light shape 49 | 30 |
| cp1_holes | `submissions/cp1_holes.zip` | 1 / 1 | 2 mask truck → car | 3 |
| cp2_slice | `submissions/cp2_slice.zip` | 1 / 1 | thêm 1 mask bus | 3 |
| cp5_occlusion | `submissions/cp5_occlusion.zip` | 1 / 1 | Lần 1: 1 mask truck → car, thêm 17 mask car (shape 23–39). Lần 2: thêm car shape 38, person shape 39, car shape 40–47 (tổng 47 mask) | 3 |
| cp3_thin | `submissions/cp3_thin.zip` | 1 / 1 | không | 3 |
| cp4_curb | `submissions/cp4_curb.zip` | 1 / 1 | không | 3 |
| cp6_coverage | `submissions/cp6_coverage.zip` | 1 / 1 | sửa mask building; thêm 1 mask car | 3 |
| **Tổng tối đa** | | | | **100** |

Cả 9 ZIP qua `scripts/inspect_submissions.py` với kết quả **OK** (chỉ kiểm cấu trúc, không kiểm độ đúng của mask). Tôi không gặp lỗi export.

## 2. Một quyết định trước khi dùng gợi ý

- Ảnh, vị trí và object Medium đầu tiên tự vẽ: **chưa thực hiện**. Gợi ý YOLO được import vào `medium_instance` ngay từ đầu (65 mask), trước khi tôi tự vẽ object nào.
- Class và quy tắc tôi dùng để chọn biên: không có object Medium tự vẽ.
- Nếu dùng gợi ý sau đó: trước khi xem đáp án, tôi giữ nguyên 65 gợi ý của Medium. Sau khi xem kết quả scorer, tôi thêm 7 mask person (shape 66–72) ở `000000181542.jpg` cho những người nhỏ YOLO bỏ sót.
- Một quyết định gán nhãn tôi đã làm ở task khác: ở `hard_panoptic`, ảnh `000000460147.jpg`, tôi đổi mask shape 32 từ `truck` (YOLO đề xuất) thành `car`. Lý do: vì thân và đầu xe liền khối

## 3. Một lỗi tôi tìm thấy và sửa

- Task/ảnh/vùng: `cp5_occlusion`, ảnh `000000336232.jpg`. Lỗi nằm ở các xe nhỏ ở xa và một xe bị gán `truck`.
- Lỗi thuộc loại: **thiếu vật**, kèm **sai lớp**.
- Bằng chứng tôi nhìn thấy: gợi ý YOLO chỉ có 20 mask. Nhiều xe con nhỏ, mỗi xe khoảng 120–530 px, không có mask; mask shape 6 bị gán `truck`.
- Quy tắc và hành động sửa: mỗi vật đếm được là một instance, nên tôi vẽ thêm 17 mask `car` (shape 23 đến 39) và đổi shape 6 từ `truck` thành `car`. Sau sửa có 37 mask.
- Sau sửa đã Save và export lại chưa? **Đã Save** trong CVAT và **đã export lại**. `submissions/cp5_occlusion.zip` hiện có 37 annotation.

Các sửa khác cùng loại: `cp2_slice` (`000000017627.jpg`) thêm mask shape 15 là `bus`, vì YOLO bỏ sót xe buýt; `cp1_holes` (`000000144300.jpg`) đổi shape 3 và 4 từ `truck` thành `car`.

Kết quả tự đánh giá: tôi chạy `scoring/scorecard.py --group tiers` trên máy với đáp án ba tier `tiers_gt.zip` do lớp phát. File đáp án không được đưa lên fork.

| Task | Metric | Lần 1 (trước khi xem đáp án) | Lần 2 (sửa sau khi xem đáp án) |
| --- | --- | ---: | ---: |
| easy_semantic | mIoU | 0,793 → 17,5 / 20 | 0,793 → 17,5 / 20 |
| medium_instance | matched IoU × recall | 0,612 → 15,1 / 32 (recall 0,76) | 0,641 → 17,1 / 32 (recall 0,80) |
| hard_panoptic | PQ | 0,369 → 11,3 / 30 | 0,384 → 12,2 / 30 |
| **Tổng ba tier** | | **43,9 / 82** | **46,8 / 82** |

Đây là điểm tự đánh giá ba tier tối đa 82, không phải điểm chính thức /100. Sáu checkpoint không được chấm vì không có đáp án. Theo phân tích của scorer, điểm còn thấp chủ yếu vì sót vật nhỏ ở Medium và Hard (người ở xa), và vì mask sidewalk lệch so với đáp án (Easy sidewalk IoU 0,47; Hard sidewalk không khớp ở cả 2 ảnh).

## 4. Ba ca chưa chắc hoặc đã cân nhắc

| Ảnh/vị trí | Hai cách hiểu có thể | Quy tắc/chứng cứ | Quyết định hoặc câu hỏi cho coach |
| --- | --- | --- | --- |
| 1. `hard_panoptic` / `000000460147.jpg`, mask shape 32 | `truck` (YOLO đề xuất) hay `car` | Thân và đầu xe liền khối | Chọn `car` |
| 2. `cp1_holes` / `000000144300.jpg`, mask shape 3 và 4 | `truck` (YOLO đề xuất) hay `car` | Thân và đầu xe liền khối | Chọn `car` cho cả hai |
| 3. `cp6_coverage` / `7daa6479-67988f3f.jpg`, mask building | Giữ biên building SegFormer đề xuất hay sửa lại | Mask building đang bị lẫn với mask shape khác | Sửa lại biên building (diện tích giảm khoảng 13%); thêm mask car shape 7 |
