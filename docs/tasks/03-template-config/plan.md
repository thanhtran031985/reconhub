# Kế hoạch thực hiện — Task 03: TemplateConfig, version và service template

## Mục tiêu
Cung cấp schema Pydantic v2 `TemplateConfig` đầy đủ theo Spec 03 với validator tĩnh bắt lỗi theo đường dẫn chi tiết (>= 18 test cases); validator kết nối catalog kiểm tra bảng/cột và kiểu ngày; quản lý vòng đời template và phiên bản (`RECON_TEMPLATE`, `RECON_TEMPLATE_VERSION`) với kiểm soát xung đột đồng thời (`STALE_DATA`); tính năng export/import JSON, sinh 5 sơ đồ Mermaid trực quan, và nạp seed template DTP.

## Các bước thực hiện

### Bước 1 — Pydantic model (`app/schemas/template_config.py`)
- Định nghĩa các schema Pydantic v2:
  - `FileSpec`, `RowFilter`, `FieldSpec`, `DerivedSpec`
  - `DbSourceSpec`, `SourceFilter`, `StaticFilter`, `ParamSpec`
  - `TimeFilterSpec`, `ProfileSpec`, `MeasureSpec`, `ControlTotalSpec`
  - `TemplateConfig` (gồm `schema_version: int = 1`, ...)
- Bộ validator tĩnh (`@model_validator(mode="after")`):
  1. Định danh `FieldSpec.name` và `DerivedSpec.name` tuân thủ regex `^[A-Z][A-Z0-9_]{0,29}$`, không trùng nhau.
  2. Bắt buộc có đúng 1 profile `is_default=True`.
  3. Mọi trường trong `group_by` phải tồn tại trong `fields` hoặc `derived` và có mặt ở cả hai nguồn (Excel & DB).
  4. Các trường trong `measures` phải tồn tại; `agg="sum"` chỉ áp dụng cho trường kiểu `number`; `agg="value"` chỉ cho phép khi `aggregate=False`.
  5. Cấu trúc drilldown giữa các profile không bị chu trình vòng lặp (cycle).
  6. `main_measure` phải nằm trong danh sách `measures` của chính profile đó.
  7. `DbSourceSpec`: nếu `kind="table"`, bắt buộc có `table`; phải có tham số `p_from` và `p_to` (kiểu date/datetime, `source="user"`); và phải có bộ lọc tương ứng cho `p_from`, `p_to`.
  8. Lỗi validate trả về đường dẫn chính xác (e.g. `profiles[0].measures[1].field`, `db_source.filters[0].column`).
- Test viết trước (`tests/unit/test_template_config_static.py`):
  - Kiểm tra nạp thành công template mẫu `samples/templates/DTP_HOA_DON_TAC_NGHIEP.json`.
  - Kiểm tra >= 18 trường hợp lỗi sai cấu hình, assert đúng error type và path.

### Bước 2 — Validator có kết nối (`app/services/template_validate.py`)
- Cài đặt `validate_template_connected(config: TemplateConfig, ds_id: int)`:
  - Nếu kết nối tới data source thành công:
    - Bảng `db_source.table` phải tồn tại trong catalog (schema + table).
    - Mọi cột DB được tham chiếu (`fields[].db`, `filters[].column`, `static_where[].column`) phải tồn tại trong bảng.
    - Cột lọc `p_from` và `p_to` phải có kiểu ngày/giờ (`DATE`, `TIMESTAMP`).
    - Báo lỗi chi tiết với mã `COLUMN_NOT_FOUND`, `TABLE_NOT_FOUND` kèm đường dẫn cấu hình (path).
  - Nếu không kết nối được qua VPN/mạng: sinh cảnh báo (warning) chứ không chặn việc lưu nháp.
- Test viết trước (`tests/unit/test_template_config_connected.py`):
  - Kiểm tra với catalog mock và test integration nếu có VPN Oracle.

### Bước 3 — Repo/service version (`app/services/template.py`)
- Các hàm service với phân quyền:
  - `list_templates(ctx, q, status)`: người dùng đã đăng nhập đều xem được.
  - `get_template(ctx, template_id, version=None)`: lấy thông tin chi tiết template + config JSON.
  - `save_draft_template(ctx, code, name, description, config, data_source_id, row_version)`:
    - Nếu template mới: tạo `RECON_TEMPLATE` (DRAFT, v1) + `RECON_TEMPLATE_VERSION` (v1, DRAFT).
    - Nếu template đã có: kiểm tra `row_version` (nếu không khớp trả lỗi `STALE_DATA`); nếu version mới nhất đang là DRAFT và chưa có run thì cập nhật; nếu đã có run hoặc đã activate thì tạo version mới = max(version) + 1.
  - `clone_template(ctx, template_id, new_code, new_name)`: nhân bản template sang mã mới ở trạng thái DRAFT v1.
  - `archive_template(ctx, template_id)`: chuyển trạng thái sang ARCHIVED.
  - `activate_version(ctx, template_id, version)`: kích hoạt version thành ACTIVE (cần `DRY_RUN_OK='Y'`, các version ACTIVE cũ chuyển sang RETIRED).
  - Phân quyền: `ADMIN` hoặc `TEMPLATE_OWNER` được phép sửa đổi/lưu/kích hoạt/lưu trữ.
  - Ghi `RECON_AUDIT_LOG` cho mọi thao tác thay đổi template/version.
- Test viết trước (`tests/unit/test_template_service.py`):
  - Phân quyền, lưu nháp, tạo phiên bản mới, kiểm tra STALE_DATA, clone, archive.

### Bước 4 — Export/import + diagram + seed
- `app/services/template_export_import.py`:
  - `export_template(ctx, template_id, version=None)` -> JSON dictionary hoàn chỉnh.
  - `import_template(ctx, data: dict, overwrite: bool = False)`: nạp template từ file JSON, kiểm tra tính hợp lệ.
- `app/services/diagram.py`:
  - Hàm sinh 5 sơ đồ Mermaid từ `TemplateConfig`:
    1. Sơ đồ luồng đối soát tổng quan (`flowchart LR`)
    2. Sơ đồ chuẩn hóa dữ liệu từng trường
    3. Sơ đồ truy vấn DB và bộ lọc
    4. Sơ đồ cây Profile đối soát và quan hệ drilldown
    5. Sơ đồ kiểm tra Control Total
- Cập nhật CLI `seed_cmd`: nạp tự động template mẫu `DTP_HOA_DON_TAC_NGHIEP` (gắn kết nối `ORACLE_TEST` nếu có).
- Test viết trước (`tests/unit/test_template_diagram.py`, `tests/unit/test_template_seed_export_import.py`).
