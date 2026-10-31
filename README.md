# ReconHub

Ứng dụng đối soát dữ liệu giữa file Excel và Oracle: template (mapping cột, bảng/view + cột lọc, Group by, SUM/COUNT, sai số), chạy theo khoảng ngày giờ người dùng nhập. Toàn Python (Dash Mantine + Polars), chạy trực tiếp trên Windows/Linux (không Docker). RECON_APP trên SQLite (có người dùng và phân quyền riêng), chuyển được sang Oracle. Dữ liệu Excel là dữ liệu tạm, người dùng chủ động xóa.

- Bắt đầu: **HUONG-DAN.md**. Hướng dẫn agent: **AGENTS.md**, `.agents/`.
- Đặc tả: docs/PRD.md, docs/specs/. Thiết kế: mở `designs/components/Screen01-Dashboard/preview.html`.
- Task: docs/tasks/README.md, tiến độ docs/tasks/dashboard.html.
