# Task 52 — export-background (xuất Excel chạy ngầm)

## Yêu cầu (user, 11/11/2026, báo cáo 5 — /reports/5)
Phần xuất ra Excel, bổ sung thêm phần xuất chạy ngầm. Ví dụ: dữ liệu
nhiều, tầm 1.000.000 record, nếu để user bấm và chờ sẽ rất lâu. Khi
user chọn mode chạy ngầm, hệ thống sẽ tự chạy, sau đó user sẽ vào lịch
sử báo cáo để download khi dữ liệu chạy xong. Giống Oracle EBS in báo
cáo đó bạn.

## Quyết định của user (11:08 11/11/2026, trả lời 4 câu hỏi)
- Không thông báo chủ động khi xong — user tự vào lịch sử xem.
- Xuất lại sẽ chạy lại, sinh ra run mới vì dữ liệu có thể có update mới.
- Thêm chức năng cho ADMIN tự setup dọn file export: manual hoặc
  scheduler xóa (sau xxx ngày), mặc định manual.
- Xếp hàng giống EBS (FIFO, chạy tuần tự).
