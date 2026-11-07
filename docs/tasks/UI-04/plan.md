# Kế hoạch thực hiện TASK UI-04 — Configuration Master–Detail

## Mục tiêu
Chuyển đổi 4 màn hình cấu hình chuyên sâu (`/data-sources`, `/batches/<def_id>`, `/report-admin`, `/templates/<id>/diagram`) sang pattern **MASTER_DETAIL**.
Loại bỏ 65 inline styles lặp lại trong `data-sources`, khắc phục hiện tượng sơ đồ Mermaid bung chiều cao 4132px trong `template-diagram` bằng container có bounded viewport (pan/zoom), và đảm bảo trang `/report-admin` mượt mà, bảo toàn 26 callbacks hiện có.

## Các bước thực hiện:

### Bước 1: Data Sources & Storage Master–Detail (`app/ui/pages/data_sources.py`)
- Chuyển tab Nguồn dữ liệu sang Master–Detail:
  - Master (Trái ~340px): Danh sách Data Sources Oracle với trạng thái, nút "+ Thêm nguồn".
  - Detail (Phải flex: 1): Form thông tin kết nối (host, port, service, username, password fernet, nút Test kết nối, Lưu).
- Dọn dẹp triệt để các inline styles lặp lại, thay bằng DMC classes/tokens chuẩn.
- Bọc container với `height: calc(100vh - 48px)`, `overflow: hidden`, triệt tiêu page-scroll dọc.
- Kiểm tra `pytest tests/unit/test_page_data_sources.py`.

### Bước 2: Batch Definition Detail (`app/ui/pages/batch_def_edit.py`)
- Master (Trái): Danh sách các template con trong bộ đối soát.
- Detail (Phải): Panel cấu hình thứ tự chạy và mapping tham số cho template con đang chọn.
- Bọc container khống chế chiều cao, table scroll nội bộ.
- Kiểm tra `pytest tests/unit/test_batch_def_pages.py`.

### Bước 3: Bounded Template Diagram (`app/ui/pages/template_diagram.py`)
- Bọc container sơ đồ Mermaid bằng khung bounded viewport `style={"flex": 1, "minHeight": 0, "overflow": "hidden"}`.
- Tích hợp controls thu phóng / di chuyển (Zoom in, Zoom out, Reset) và xuất SVG.
- Triệt tiêu hoàn toàn độ dài bung 4132px về `<= 768px` mà không làm vỡ sơ đồ.
- Kiểm tra `pytest tests/unit/test_page_template_diagram.py`.

### Bước 4: Report Admin Substeps (`app/ui/pages/report_admin.py`)
- Master (Trái ~320px): Danh sách các cấu hình báo cáo với tìm kiếm và nút "+ Thêm báo cáo".
- Detail (Phải flex: 1): 4 Tab cấu hình:
  - UI-04.1: Shell, Header & Master List
  - UI-04.2: General Info & Source (TABLE/VIEW/CUSTOM_SQL)
  - UI-04.3: Dynamic Parameters & LOV
  - UI-04.4: Column Mapping & Export
- Giữ nguyên 100% 26 callbacks và các component ID liên quan.
- Bọc container có giới hạn chiều cao `calc(100vh - 48px)`.
- Kiểm tra `pytest tests/unit/test_page_report_admin.py`.

### Bước 5: Verification & Complete
- Chạy toàn bộ 43 unit tests của UI-04.
- Chạy `ruff check` kiểm tra linting.
- Cập nhật tiến độ `docs/tasks/UI-04/progress.md`, `task.md` (DONE), `docs/tasks/UI-MIGRATION-INDEX.md` (DONE), `tasks-dashboard`.
- Commit và push branch `feat/UI-04` lên GitHub.
