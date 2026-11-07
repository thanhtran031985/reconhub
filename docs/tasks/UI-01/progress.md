# Tiến độ TASK UI-01 — Compact Lists

| Bước | Nội dung | Trạng thái |
|---|---|:---:|
| Preflight | Kiểm tra lint, typecheck, test baseline | ✅ |
| Step 1 | Templates List (`app/ui/pages/templates.py`) | ✅ |
| Step 2 | Run History (`app/ui/pages/history.py`) | ✅ |
| Step 3 | Batch Definitions (`app/ui/pages/batch_defs.py`) | ✅ |
| Step 4 | Report Runs (`app/ui/pages/report_runs.py`) | ✅ |
| Step 5 | Reports Center (`app/ui/pages/reports.py`) | ✅ |
| Step 6 | Regression Tests & Verification | ✅ |

## Nhật ký thực hiện

### 2026-11-07 — Triển khai hoàn tất UI-01
- Tạo nhánh `feat/UI-01` tách từ `feat/UI-00B`.
- Lập Implementation Plan chi tiết cho 5 trang danh sách (`/templates`, `/history`, `/batches`, `/report-runs`, `/reports`).
- **Step 1 (`/templates`)**: Di chuyển sang `page_header` + `command_bar`, chuyển bảng sang sticky header `34px`, scroll nội bộ `flex: 1` `dmc.Paper`, giữ 100% pattern-matching callbacks. Test `test_page_templates.py`: 9/9 passed.
- **Step 2 (`/history`)**: Sử dụng `page_header` (giữ `id="history-title"` cho callback cập nhật title), chuyển bảng sang sticky header `34px` trong flex paper, triệt tiêu scroll trang (trước đây 2181px). Test `test_page_history.py`: 11/11 passed.
- **Step 3 (`/batches`)**: Sử dụng `page_header` + `command_bar`, bảng compact sticky header `34px`. Test `test_batch_def_pages.py`: 5/5 passed.
- **Step 4 (`/report-runs`)**: Sử dụng `page_header`, chuyển bảng sang sticky header `34px` trong flex paper, pagination gọn `mt="xs"`. Test `test_page_report_runs.py`: 8/8 passed.
- **Step 5 (`/reports`)**: Sử dụng `page_header` + `command_bar` (search, category select, fav checkbox), render cards compact trong scroll area flex `minHeight: 0`. Test `test_page_reports.py`: 9/9 passed.
- **Step 6**: Chạy ruff lint (All checks passed) và chạy toàn bộ test suite UI-01: 42/42 tests passed.
