# Kế hoạch thực hiện — 100-multi-profile-run

## 1. Mục tiêu
Thực hiện chuyển đổi tính năng chọn profile trên trang `/runs/new` sang Multi Profile (cho phép chọn một hoặc nhiều profile cùng lúc), sinh ra N lượt chạy độc lập dùng chung file nạp tạm, hiển thị SQL preview dạng Tabs, và bổ sung bộ lọc Profile trên trang Lịch sử `/history`.

## 2. Kế hoạch từng bước

### Bước 1 — Service & Schema (`run.py`, `run_service.py`)
- Mở rộng `app/schemas/run.py`:
  - Thêm `CreateMultiRunParams(template_id, file_id, profile_codes: list[str], p_from, p_to, data_source_id, ...)`
  - Thêm `MultiRunResponse(run_ids: list[int], count: int)`
- Trong `app/services/run_service.py`:
  - Viết hàm `create_multi_run(ctx: Ctx, params: CreateMultiRunParams) -> dict[str, Any]`
  - Hàm thực hiện vòng lặp tạo các `RECON_RUN` độc lập trong cùng 1 connection transaction, validate toàn bộ `profile_codes`, đưa từng run vào `RECON_RUN_QUEUE`.
- Viết test unit `tests/unit/test_multi_profile_run.py`.

### Bước 2 — Cập nhật UI `/runs/new` (`new_run.py`)
- Thay thế `dmc.Select` của profile thành `dmc.MultiSelect(id="new-run-profile-select", ...)`
- Cập nhật Card 3 "Câu lệnh SQL đối soát DB":
  - Nếu chọn 1 profile: hiện code SQL như trước.
  - Nếu chọn nhiều profile: render `dmc.Tabs` gồm các tab ứng với từng profile đã chọn, bên trong mỗi tab là `code_block` câu lệnh SQL của profile đó.
- Cập nhật callback submit `submit_run_callback`:
  - Đọc `profile_codes` dạng `list[str]`.
  - Nếu có 1 profile: gọi `create_run` và redirect `/runs/<run_id>`.
  - Nếu có > 1 profile: gọi `create_multi_run`, redirect sang `/history` và thông báo toast thành công.
- Viết test unit / component test `tests/unit/test_new_run_multi_profile.py`.

### Bước 3 — Cập nhật UI `/history` (`history.py`)
- Thêm `dmc.Select(id="history-filter-profile", label="Profile", ...)` trên Filter bar.
- Thêm callback cập nhật danh sách profile khi `history-filter-template` thay đổi.
- Thêm `profile_code` vào `RunListFilter` và xử lý query filter `list_runs` trong `run_service.py`.
- Viết test unit `tests/unit/test_history_profile_filter.py`.

### Bước 4 — Kiểm thử tổng thể & hoàn tất
- Chạy `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`.
- Cập nhật `progress.md`, `checklist.md`, chạy `tasks-dashboard`.
