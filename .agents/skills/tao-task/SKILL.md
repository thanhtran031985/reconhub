---
name: tao-task
description: Tạo task mới trong docs/tasks từ mẫu _template. Dùng khi người dùng nói "tạo task mới" hoặc gọi /tao-task.
---

# Tạo task mới

1. Đọc `docs/tasks/README.md`, lấy số lớn nhất + 1 làm NN.
2. Đề xuất slug (kebab-case, tiếng Anh, ngắn); hỏi xác nhận nếu chưa rõ.
3. Copy `docs/tasks/_template/` sang `docs/tasks/NN-slug/`, điền tiêu đề, ngày, giai đoạn, phụ thuộc.
4. Có nội dung thì ghi vào task.md theo khung; chưa có thì để khung trống.
5. Task có giao diện: liệt kê `designs/components/*` liên quan.
6. Thêm dòng vào bảng README (⬜), chạy `uv run poe tasks-dashboard`.
7. Không bắt đầu làm khi chưa được yêu cầu.
