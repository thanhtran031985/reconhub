# Kế hoạch thực hiện TASK UI-02 — Reports & Analytics

## Mục tiêu
Chuyển đổi 5 màn hình báo cáo và phân tích (`/` Dashboard, `/runs/<id>`, `/batch-runs/<id>/result`, `/issues`, `/reports/<id>`) sang pattern REPORT chuẩn Fluent Compact: `PageHeader` + `FilterBar` (compact 1 hàng) + Vùng kết quả/DataGrid (`flex: 1`, internal scroll).
Triệt tiêu hoàn toàn page-scroll desktop 1366×768 (Dashboard: 1065px -> <= 768px; Run Result: 2644px -> <= 768px), giữ nguyên quy chuẩn highlight ô lệch `rh-diff`, format số tiền `24.114.547.250`, metadata-driven columnDefs và 100% callback contract.

## Kế hoạch từng bước

### Bước 1: Dashboard (`app/ui/pages/dashboard.py`)
- Thay H1 tiêu đề bằng `page_header` (Title order=4, subtitle, bộ chọn tháng/năm ở right actions).
- Co gọn 4 thẻ KPI (`kpi_card`): padding `xs/sm`, height cố định ~72px, icon 16px.
- Gom 2 bảng tổng hợp (Tỷ lệ lệch, 10 run gần nhất) vào 2 card flex có internal scroll (`dmc.TableScrollContainer`), giúp toàn bộ Dashboard vừa khít viewport 1366×768 mà không sinh scrollbar trang.
- Chạy `pytest tests/unit/test_page_dashboard.py`.

### Bước 2: Run Result (`app/ui/pages/run_result.py`)
- Thay header hiện tại bằng `page_header` tích hợp nút "Xuất Excel" và "Đã kiểm tra xong".
- Thu gọn bộ lọc trạng thái dòng (MISMATCH, MATCHED...) thành `filter_bar` compact 1 hàng.
- Chuyển 2 bảng kết quả đối soát sang `dmc.TableScrollContainer` / AgGrid với sticky headers và scroll nội bộ `flex: 1` `dmc.Paper`.
- Bảo toàn class `rh-diff` cho các ô số liệu chênh lệch, bảo toàn Drawer chi tiết dòng (`run-res-row-drawer`).
- Chạy `pytest tests/unit/test_page_run_result.py`.

### Bước 3: Batch Run Result (`app/ui/pages/batch_run_result.py`)
- Sử dụng `page_header` và KPI summary compact.
- Chuyển bảng tiến độ các template con sang table compact có sticky header và scroll nội bộ.
- Chạy `pytest tests/unit/test_batch_run_pages.py`.

### Bước 4: Issues Resolution (`app/ui/pages/issues.py`)
- Tích hợp bộ lọc lý do chênh lệch vào `filter_bar` compact 1 hàng.
- Chuyển bảng xử lý chênh lệch sang compact table trong flex paper với sticky header.
- Bảo toàn các callback cập nhật lý do chênh lệch (đơn lẻ và hàng loạt).
- Chạy `pytest tests/unit/test_page_issues.py`.

### Bước 5: Report Viewer (`app/ui/pages/report_viewer.py`)
- Tối ưu Tab "Tham số": form tham số động co giãn compact 12 cột.
- Tab "Kết quả": `render_result_table` nhận metadata-driven columnDefs, bao bọc trong flex-1 container có internal scroll.
- Chạy `pytest tests/unit/test_page_report_viewer.py`.

### Bước 6: Verification & Complete
- Chạy toàn bộ 74 tests của 5 trang.
- Kiểm tra lint (`ruff check`).
- Cập nhật tài liệu UI-02, tasks-dashboard, commit và push lên `feat/UI-02`.

