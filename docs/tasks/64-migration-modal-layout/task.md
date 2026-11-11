# Task 64 — Sửa layout modal chuyển Oracle: 2 card + stepper hiện item đang chạy

## Yêu cầu gốc (user, 11/11/2026 22:37)
> "chỉnh lại modal cho vừa trang, hiện tại đang scroll"
> "chỉnh lại stepper theo ui-dash.md và gần giống hình mình gửi"
> "chia 2 card làm 2 phần: 1 phần stepper, phần kia là detail (check list của stepper), list nào chạy xong thì check đã chạy để biết trong stepper đó làm những việc gì"
> "hãy vẽ layout cái bạn đang hiểu mình đã nói"

## Yêu cầu bổ sung (user, 11/11/2026 22:42)
> "mỗi bước trong stepper có thể thấy đang chạy được không? vd tạo table A -> done, table B ..."

## Layout đã duyệt (mockup HTML parent vẽ, user "làm đi bạn" 22:44)
- Modal rộng hơn (kiểu `xl`), cao cố định vừa khung nhìn ở 1366×768 — **không scroll cả modal**. Header một dòng, footer cố định (Đóng / Bắt đầu). Chỉ card chi tiết được cuộn riêng khi danh sách dài.
- **Card trái "Tiến trình" (~320–340px):** stepper dọc 6 bước, vòng tròn đánh số nối bằng đường kẻ (giống hình user gửi): xong ✓ xanh, đang chạy tô xanh dương đầy (số trắng), chưa chạy vòng xám. Bấm vào bước nào thì chọn bước đó.
- **Card phải "Chi tiết bước" (flex 1):** checklist của bước đang chọn — dòng chạy xong ✓ xanh kèm số liệu (vd "Đích: 393 dòng"), dòng chưa chạy ○ xám, item đang làm tô riêng (chấm xanh + nhãn "Đang chạy"). Khi chạy xong, chọn bước 6 "Hoàn tất" thì card phải hiện thêm bảng đối chiếu từng bảng + 4 bước làm tay tiếp theo.
- **Mỗi bước trong stepper hiện item đang chạy:**
  - Bước đang chạy: dòng xanh "Đang: <tên item đang làm>" + "n/m bảng xong" ngay dưới tên bước (vd: table A xong → dòng tự nhảy sang table B).
  - Bước đã xong: dòng xanh "✓ n/n việc xong".
  - Bước chưa chạy: "Chờ • 0/m việc".
- Item đang làm được **suy ra từ dòng chờ đầu tiên trong bước** (bảng chép theo đúng thứ tự) — không đổi data model, không thêm cột.
- Phong cách Fluent Compact theo `.agents/rules/ui-dash.md`: mật độ gọn (size xs/sm, gap xs, p sm), Paper withBorder radius sm, không gradient/bo góc lớn/hiệu ứng; Master–Detail (trái danh sách, phải panel chi tiết cuộn độc lập).

## Ngoài phạm vi
- Không đổi logic chạy fake/real, switch, precheck, checklist, migration 0008 (task 63). Chỉ sửa cách vẽ modal + stepper + detail.
