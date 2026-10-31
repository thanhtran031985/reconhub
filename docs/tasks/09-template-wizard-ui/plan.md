# Kế hoạch triển khai — 09-template-wizard-ui

## Mục tiêu
Cài đặt màn hình Wizard Đăng ký & Chỉnh sửa Template (Screen03-TemplateWizard) 5 bước và Màn hình Sơ đồ diễn giải Mermaid (Screen04-TemplateDiagram) theo đúng chuẩn thiết kế và tài liệu đặc tả PRD C3, C4, spec 03, spec 05.

---

## Phân chia các bước thực hiện

### Bước 1 — Khung giao diện, Quản lý State & Tự động lưu nháp
- **Tập tin tạo/sửa**:
  - `app/ui/pages/template_wizard.py`:
    - Đăng ký route: `/templates/new` (tạo mới) và `/templates/<template_id>/edit` (sửa bản nháp / tạo phiên bản mới).
    - Phân quyền: Chỉ `ADMIN` và `TEMPLATE_OWNER` được phép truy cập; các vai trò khác bị chặn và chuyển hướng `/forbidden`.
    - Tiêu đề màn hình H1: `Đăng ký template: {template_code}` hoặc `Đăng ký template mới`, phụ đề thông tin phiên bản, trạng thái lưu nháp, Data Source và bảng nguồn.
    - Bộ chuyển Tab đầu trang (SegmentedControl): `Cấu hình template` và `Sơ đồ diễn giải`.
    - Thanh tiến trình Stepper 5 bước: `1. File mẫu`, `2. Định nghĩa trường`, `3. Nguồn DB`, `4. Profile so sánh`, `5. Dry-run`.
    - Quản lý trạng thái bằng `dcc.Store`:
      - `wizard-config-store`: Chứa toàn bộ cấu trúc `TemplateConfig` (Pydantic v2).
      - `wizard-meta-store`: Chứa thông tin ngữ cảnh (`template_id`, `version`, `is_dirty`, `last_saved_at`, `current_step`).
    - Nút điều hướng chân trang: `Quay lại`, `Lưu nháp` (thủ công), `Tiếp` / `Lưu & kích hoạt v{N}`.
    - Cơ chế tự động lưu nháp: Kiểm tra dirty flag và tự động gọi `save_draft` định kỳ qua `dcc.Interval`.
    - Đầy đủ 4 trạng thái giao diện: Loading (Skeleton), Empty, Error (Alert có Thử lại), Normal.
- **Test viết trước**:
  - `tests/unit/test_page_template_wizard.py`: Kiểm tra khởi tạo state từ template mẫu DTP, hàm serialize/deserialize config ↔ form state, phân quyền RBAC và cơ chế lưu nháp.
- **Kiểm tra**:
  - `uv run pytest tests/unit/test_page_template_wizard.py`
  - `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`

---

### Bước 2 — Bước 1 & Bước 2 (File mẫu & Cấu trúc + Chuẩn hóa & Ánh xạ trường)
- **Tập tin tạo/sửa**:
  - `app/ui/pages/template_wizard.py`:
    - **Bước 1 — File mẫu & cấu trúc**:
      - Vùng tải lên `file_drop` / `dcc.Upload` (giới hạn 50MB, định dạng `.xlsx`).
      - Phân tích cấu trúc file: Chọn Sheet, Dòng header (`NumberInput`), Dòng bắt đầu dữ liệu (`NumberInput`), Số dòng chân trang cần bỏ qua.
      - Hệ thống phát hiện tự động: Thống kê số cột/dòng, nhận diện dòng tổng (footer total), cảnh báo mã lẫn chữ và số.
      - Hộp checkbox "Áp dụng các đề xuất".
      - Bảng xem trước 5 dòng đầu tiên từ file mẫu.
    - **Bước 2 — Định nghĩa & ánh xạ trường**:
      - Bảng ánh xạ: Cột Excel mẫu, Tên trường logic (mono), Nhãn hiển thị, Kiểu dữ liệu (`STRING`, `NUMBER`, `DATE`, `DATETIME`), Danh sách chuẩn hóa (TRIM, UPPER, REGEX, ABS, ROUND, DATE_FORMAT, VALUE_MAP), Giá trị mẫu.
      - Nút "Gợi ý tự động từ header".
      - Quản lý trường dẫn xuất (`derived_fields`): Định nghĩa trường mới từ biểu thức hàm (như `trunc_day(INV_DATETIME)`).
      - Hiển thị lỗi validation ngay dưới từng ô tương ứng nếu vi phạm (như trùng tên trường, sai cú pháp).
- **Test viết trước**:
  - Bổ sung test kiểm tra tải file mẫu `samples/dtp_sample_200.xlsx`, phát hiện dòng tổng, bảng ánh xạ trường và validation trường dẫn xuất.
- **Kiểm tra**:
  - `uv run pytest tests/unit/test_page_template_wizard.py`
  - `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`

---

### Bước 3 — Bước 3 (Nguồn dữ liệu DB & Điều kiện lọc)
- **Tập tin tạo/sửa**:
  - `app/ui/pages/template_wizard.py`:
    - Chọn Data Source (nguồn đối soát Oracle) từ danh sách cấu hình.
    - Chuyển đổi cách khai báo: `Bảng/View` hoặc `SQL tự viết`.
    - Checkbox "Đẩy phép gộp (SUM, COUNT) xuống DB" (`pushdown_aggregation`).
    - **Chế độ Bảng/View**:
      - Chọn Bảng/View nguồn kèm tìm kiếm nhanh; hiển thị chip các cột có sẵn kèm kiểu dữ liệu Oracle.
      - Bảng điều kiện lọc theo tham số (bắt buộc: `p_from` và `p_to` chỉ chọn cột DATE/TIMESTAMP; `p_org` tùy chọn).
      - Điều kiện lọc cố định (`fixed_filters`).
      - Khối xem trước câu `SELECT` sinh ra tự động (chỉ đọc) qua `code_block`.
    - **Chế độ SQL tự viết**:
      - Vùng nhập SQL có kiểm tra SQL Guard (chỉ cho phép SELECT/WITH, cấm DDL/DML), nút "Kiểm tra & lấy cột".
    - Bảng ánh xạ Cột DB → Trường logic, phát hiện trường chỉ có ở Excel hoặc chỉ có ở DB.
    - Cấu hình Lọc dữ liệu Excel theo cùng khoảng thời gian (`time_filter` trường ngày giờ Excel).
- **Test viết trước**:
  - Bổ sung test kiểm tra chuyển đổi chế độ khai báo DB, sinh SELECT tự động, chặn chọn cột sai kiểu cho `p_from`/`p_to`, chặn SQL nguy hiểm.
- **Kiểm tra**:
  - `uv run pytest tests/unit/test_page_template_wizard.py`
  - `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`

---

### Bước 4 — Bước 4 (Hồ sơ đối soát — Profile so sánh)
- **Tập tin tạo/sửa**:
  - `app/ui/pages/template_wizard.py`:
    - Quản lý danh sách Profiles qua Tabs (profile mặc định và các profile bổ sung, nút "Thêm profile").
    - Danh sách các trường có sẵn kèm nút thao tác nhanh: nút `Key` (thêm vào Group by), nút `Sigma Σ` (thêm Measure).
    - Vùng cấu hình Group by: Hiển thị các chip trường khóa so sánh, tự động tính độ hạt (Grain) và số nhóm ước tính.
    - Bảng Measures và quy tắc so sánh: Tên measure, Nhãn, Hàm gộp (`sum`, `count`, `first_distinct`, `value_exact`), Trường áp dụng, Kiểu so sánh (chính xác `exact`, sai số tuyệt đối `abs_tol`, sai số phần trăm `pct_tol`, chỉ hiển thị `display_only`), Sai số, Làm tròn.
    - Bộ lọc riêng cho Profile (Excel filter, DB filter) và lựa chọn Drill-down tới profile chi tiết.
    - Khối xem trước câu SQL gộp tự động sinh ra tương ứng (chỉ đọc) qua `code_block`.
- **Test viết trước**:
  - Bổ sung test kiểm tra thêm/xóa trường trong Group by, cấu hình Measures, cập nhật độ hạt và SQL gộp tự sinh.
- **Kiểm tra**:
  - `uv run pytest tests/unit/test_page_template_wizard.py`
  - `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`

---

### Bước 5 — Bước 5 (Dry-run Chạy thử & Kích hoạt phiên bản)
- **Tập tin tạo/sửa**:
  - `app/ui/pages/template_wizard.py`:
    - Form nhập tham số chạy thử: Từ ngày giờ (`p_from`), Đến ngày giờ (`p_to`), Đơn vị (`p_org`).
    - Nút "Chạy thử (Dry-run)": Gọi service `dry_run` với file mẫu và tham số đã chọn.
    - Hiển thị kết quả Dry-run:
      - 4 thẻ KPI: Control total (Khớp/Lệch), Nhóm Excel / DB, Số nhóm Khớp / Lệch, Thời gian thực thi tổng cộng.
      - Bảng phân tích chi tiết thời gian theo từng giai đoạn (Đọc Excel, Truy vấn DB, Chuẩn hóa, Gộp nhóm, So khớp).
      - Alert thông báo phạm vi dữ liệu đã sử dụng.
    - Nút "Lưu & Kích hoạt v{N}":
      - Tự động kiểm tra điều kiện (chỉ cho phép kích hoạt khi cấu hình hợp lệ và Dry-run thành công).
      - Gọi service `activate_version`, hiển thị thông báo thành công và chuyển hướng tới `/templates`.
- **Test viết trước**:
  - Bổ sung test kiểm tra luồng Dry-run, kiểm tra validation ngày bắt đầu > ngày kết thúc, và kích hoạt phiên bản thành công.
- **Kiểm tra**:
  - `uv run pytest tests/unit/test_page_template_wizard.py`
  - `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`

---

### Bước 6 — Tab Sơ đồ diễn giải (Screen04-TemplateDiagram)
- **Tập tin tạo/sửa**:
  - `app/ui/pages/template_wizard.py`:
    - Chuyển tab sang `Sơ đồ diễn giải`: Dựng 5 khối sơ đồ Mermaid đồng bộ với cấu hình hiện tại:
      1. Quy trình tổng thể (Pipeline)
      2. Chuẩn hóa & ánh xạ trường (Fields Normalization)
      3. Truy vấn & Lọc DB (DB Query & Filters)
      4. Cấu trúc Hồ sơ đối soát (Profiles Hierarchy)
      5. Kiểm soát tổng (Control Total)
    - Tích hợp render Mermaid cục bộ từ `app/ui/assets/mermaid.min.js`.
    - Nút "Sao chép mã Mermaid" cho từng sơ đồ kèm thông báo aria-live.
    - Cơ chế hiển thị mã nguồn kèm thông báo hỗ trợ khi thư viện đồ họa đang tải.
  - `tests/e2e/test_e2e_screens.py`:
    - Bổ sung kịch bản test E2E kiểm tra truy cập Wizard đăng ký template và tab Sơ đồ diễn giải.
- **Test viết trước**:
  - Bổ sung test kiểm tra sinh 5 sơ đồ Mermaid chuẩn cú pháp từ dữ liệu cấu hình wizard.
- **Kiểm tra**:
  - `uv run poe e2e`
  - `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`
  - Cập nhật `progress.md`, `README.md` (đánh dấu Task 09 hoàn thành `✅`), cập nhật `tasks-dashboard`.
