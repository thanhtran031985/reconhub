---
name: dong-task
description: Rà soát và đóng một task: kiểm từng mục "Chấp nhận khi", chạy toàn bộ kiểm tra, đổi trạng thái ✅. Dùng khi người dùng nói "đóng task", "kiểm tra hoàn thành" hoặc gọi /dong-task.
---

# Đóng task

1. Đọc mục "Chấp nhận khi" trong `docs/tasks/NN-slug/task.md`.
2. Chạy `uv run poe typecheck`, `uv run poe lint`, `uv run poe test`; task có giao diện chạy `uv run poe e2e`; task có phần Oracle nhắc người dùng chạy `uv run poe test-oracle` qua VPN và dán kết quả.
3. Báo bảng: Mục | Đạt/Chưa đạt | Bằng chứng.
4. Tất cả đạt và người dùng đồng ý: đổi ✅ trong README và progress, chạy `uv run poe tasks-dashboard`, đề xuất commit `NN-slug: done`, nhắc merge nhánh.
5. Chưa đạt: liệt kê việc còn thiếu, không đổi trạng thái.
