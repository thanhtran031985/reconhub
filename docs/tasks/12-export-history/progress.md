# Tiến độ — 12-export-history

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Lịch sử + xóa nhiều run | ✅ | 2026-11-01 | pending |
| 2 | Dashboard tối thiểu | ✅ | 2026-11-01 | pending |
| 3 | Rà soát chất lượng | ✅ | 2026-11-01 | pending |
| 4 | Hướng dẫn sử dụng | ✅ | 2026-11-01 | pending |

## Nhật ký
### Bước 1-4 — 2026-11-01
- Đã làm:
  - Cập nhật service `list_runs` (`app/services/run_service.py`) và schema `RunListFilter` (`app/schemas/run.py`): hỗ trợ lọc theo trạng thái kiểm tra (`is_checked`), trạng thái xóa dữ liệu tạm (`is_temp_purged`), tên file (`filename`), trả về đầy đủ metadata % khớp, dung lượng và ngày xóa.
  - Xây dựng màn hình Lịch sử run (`app/ui/pages/history.py`, Screen07) tại `/history` với 5 bộ lọc tiêu chí, bảng lịch sử chi tiết, phân quyền Admin thấy cột checkbox chọn run và nút "Xóa dữ liệu tạm" hàng loạt; modal xác nhận gõ "XOA".
  - Xây dựng màn hình Dashboard tối thiểu (`app/ui/pages/dashboard.py`, Screen01) tại `/` với 4 thẻ KPI chỉ số, bảng Run gần đây, nút "Chạy đối soát" và banner cảnh báo dung lượng tạm. Thay thế placeholder `home.py`.
  - Viết bộ unit test `tests/unit/test_page_history.py` (8 tests) và `tests/unit/test_page_dashboard.py` (6 tests).
  - Bổ sung test E2E cho `/history` và `/` trong `tests/e2e/test_e2e_screens.py`.
  - Viết test luồng nghiệp vụ E2E toàn diện `tests/e2e/test_e2e_workflow.py` kiểm tra trọn vẹn đặc tả spec 07 mục 4.
  - Soạn thảo tài liệu hướng dẫn sử dụng tiếng Việt hoàn chỉnh `docs/USER_GUIDE.md` sẵn sàng cho UAT.
- Kiểm tra:
  - `uv run poe lint`: Không có lỗi.
  - `uv run poe typecheck`: Không có lỗi (88 source files).
  - `uv run poe test`: 288 passed, 4 skipped (Oracle tests skip do không có biến môi trường VPN).
  - `uv run poe e2e`: 9/9 passed.
