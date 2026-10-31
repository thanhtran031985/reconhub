# Tiến độ — 11-run-result-ui

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Header + KPI + tabs | ✅ | 2026-11-01 | pending |
| 2 | Grid động | ✅ | 2026-11-01 | pending |
| 3 | Drawer + invalid + export | ✅ | 2026-11-01 | pending |
| 4 | Đã kiểm tra xong | ✅ | 2026-11-01 | pending |

## Nhật ký
### Bước 1-4 — 2026-11-01 03:30
- Đã làm:
  - Cài đặt toàn bộ màn hình kết quả run tại `app/ui/pages/run_result.py` (`/runs/<run_id>`).
  - Header với badge trạng thái run, trạng thái kiểm tra, trạng thái dữ liệu tạm; các nút hành động "Đã kiểm tra xong", "Xóa dữ liệu tạm", "Chạy lại", "Export Excel".
  - 4 KpiCards: Control total file, Tổng tiền Excel trong khoảng, Tổng tiền DB, Chênh lệch.
  - Stacked ratio bar thể hiện tỷ lệ kết quả; 8 tabs trạng thái có badge số lượng.
  - Bộ lọc từ khóa key và checkbox "Chỉ hiện cột lệch".
  - Bảng kết quả AgGrid động 2 tầng (Key, Trạng thái, Measure Excel/DB/Chênh) với CSS highlight `rh-diff`.
  - Drawer chi tiết dòng raw Excel và bản ghi DB khi click dòng kết quả.
  - Modal xác nhận "Đã kiểm tra xong" có checkbox purge temp data.
  - Modal xác nhận "Xóa dữ liệu tạm".
  - Viết bộ unit test `tests/unit/test_page_run_result.py` và bổ sung E2E test `test_e2e_run_result_page_accessible`.
- Kiểm tra:
  - `uv run poe lint`: Không có lỗi.
  - `uv run poe typecheck`: Không có lỗi.
  - `uv run poe test`: 271 passed, 4 skipped (Oracle tests skip do không có biến môi trường VPN).
- Suy ra (nếu có): Tuân thủ strictly Design Tokens, tiếng Việt có dấu, không emoji, xử lý an toàn dữ liệu tạm đã xóa.
