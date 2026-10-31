# Đưa ReconHub vào Google Antigravity (máy Windows)

Bộ khởi động giữ khuôn dự án TMS (PRD, DESIGN_SYSTEM, specs, tasks có task.md / progress.md / plan.md / decisions.md / _archive), hướng dẫn agent theo định dạng Antigravity.

## 1. Trong thư mục có gì
- `AGENTS.md`: hướng dẫn luôn nạp (dự án, môi trường, stack, cấu trúc, quy trình task, quy tắc, lệnh).
- `.agents/rules/`: `database.md`, `engine.md`, `ui-dash.md` (tự nạp theo vùng code), `security.md` (agent tự quyết khi nào đọc).
- `.agents/skills/`: `khoi-tao`, `lam-task`, `dong-task`, `tao-task`, `ra-soat-ui`.
- `docs/PRD.md`, `docs/specs/00–08`, `docs/DESIGN_SYSTEM.md`, `docs/tasks/` (17 task, 00 → 16).
- `designs/`: token, 13 thành phần, Gallery, 11 màn `preview.html` (mở bằng trình duyệt; thanh dưới đổi 4 trạng thái và Sáng/Tối).
- `samples/`: file mẫu `dtp_sample_200.xlsx` (dữ liệu tổng hợp theo đúng cấu trúc file DTP: 200 dòng, 190 hóa đơn, có dòng "Tổng tiền") và template mẫu. Đặt file thật vào `samples/private/` (không commit).
- `scripts/`: `tasks_dashboard.py`, `design_system.py`, `gen_dmc_theme.py` (chỉ cần Python); `scripts/oracle/*.sql` (bạn chạy tay).

## 2. Chuẩn bị máy Windows
- Python 3.12 và uv: `winget install astral-sh.uv` (hoặc `pip install uv`), Git.
- VPN tới Oracle server. Không cần Docker, không cần Oracle Client.
- Kiểm tra nhanh: `uv --version`, `git --version`.

## 3. Chuẩn bị Oracle test (làm tay, một lần)
Chạy theo thứ tự bằng SQL Developer/SQL*Plus, sửa mật khẩu và tablespace trong script:
1. `scripts/oracle/01_create_src_test.sql` (user DBA): tạo schema `RECON_SRC` + bảng `SRC_FACT_INVOICE_DTP`, user chỉ đọc `RECON_SRC_RO`.
2. `scripts/oracle/02_seed_src_test.sql` (user RECON_SRC): nạp dữ liệu khớp với `samples/dtp_sample_200.xlsx`, có sẵn các dòng lệch để kiểm tra.
3. `scripts/oracle/03_create_recon_app.sql` (user DBA): tạo schema `RECON_APP_TEST` làm đích thử chuyển RECON_APP từ SQLite. Dùng lại script này (đổi tên) khi tạo schema RECON_APP thật.
4. `scripts/oracle/99_drop_test.sql`: xóa toàn bộ đối tượng test khi không cần nữa.

Sau đó điền các biến `ORACLE_TEST_*` trong `.env` (copy từ `.env.example`).

## 4. Mở dự án trong Antigravity
```powershell
cd D:\reconhub
git init
git add . ; git commit -m "init: bộ khởi động ReconHub"
```
Mở thư mục bằng Antigravity. Vào **Customizations** kiểm tra thấy AGENTS.md, 4 rule, 5 skill. Chọn chế độ agent **Planning**; đặt duyệt lệnh terminal ở mức yêu cầu bạn xác nhận.

## 5. Làm từng task
- Task đầu: gõ `Chạy skill khoi-tao` (hoặc `/khoi-tao`).
- Task sau: `Làm task 04-excel-reader theo skill lam-task`.
- Agent tạo Implementation Plan → bạn góp ý, duyệt → agent chép vào `plan.md`, tạo nhánh `feat/NN-slug`.
- Sau mỗi bước agent chạy Kiểm tra, cập nhật `progress.md`, báo cáo, đề xuất commit rồi DỪNG. Bạn xem, đồng ý, gõ `continue`.
- Bước có test Oracle: bật VPN rồi chạy `uv run poe test-oracle`, dán kết quả cho agent.
- Mở phiên mới: `Tiếp tục task NN-slug từ progress.md`. Kết thúc: `Đóng task NN-slug`, rồi merge nhánh.
- Xem tổng thể: `python scripts/tasks_dashboard.py` (hoặc `uv run poe tasks-dashboard` sau task 00) rồi mở `docs/tasks/dashboard.html`.

## 6. Sau task 01: tạo tài khoản Admin đầu tiên
`uv run python -m app.cli create-admin` → nhập username, họ tên, mật khẩu. Đăng nhập rồi tạo người dùng khác ở màn Người dùng.

## 7. Khi thiết kế thay đổi
Sửa `designs/tokens.json` hoặc preview.html, chạy `python scripts/design_system.py` và `python scripts/gen_dmc_theme.py`.
