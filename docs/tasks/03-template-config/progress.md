# Tiến độ — 03-template-config

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Pydantic model | ✅ | 2026-10-31 | 9be5c68 |
| 2 | Validator có kết nối | ✅ | 2026-10-31 | f48a33d |
| 3 | Repo/service version | ✅ | 2026-10-31 | 7c36c51 |
| 4 | Export/import + diagram + seed | ✅ | 2026-11-01 |  |

## Nhật ký
### Bước 4 — 2026-11-01 00:01
- Đã làm:
  - Cài đặt `app/services/diagram.py`: sinh 5 sơ đồ Mermaid hợp lệ từ cấu hình `TemplateConfig`:
    1. `generate_pipeline_diagram`: sơ đồ luồng dữ liệu đối soát tổng quan (`flowchart LR`) từ Excel qua lọc & chuẩn hóa, phái sinh, profile đối chiếu với dữ liệu Oracle DB.
    2. `generate_fields_normalization_diagram`: sơ đồ các bước chuẩn hóa từng trường dữ liệu.
    3. `generate_db_query_diagram`: sơ đồ câu lệnh truy vấn CSDL kèm điều kiện lọc WHERE và danh sách cột SELECT.
    4. `generate_profiles_hierarchy_diagram`: sơ đồ quan hệ cây profile đối soát và liên kết drilldown.
    5. `generate_control_total_diagram`: sơ đồ kiểm tra đối chiếu tổng kiểm soát file với tổng cộng dồn dữ liệu chi tiết.
  - Cài đặt `app/services/template_export_import.py`:
    - `export_template(ctx, template_id, version)`: trích xuất toàn bộ thông tin metadata và cấu hình JSON của template.
    - `import_template(ctx, data, overwrite)`: nạp template từ file JSON, kiểm tra tính hợp lệ qua Pydantic schema, bảo vệ chống ghi đè vô tình khi `overwrite=False`.
  - Cập nhật lệnh CLI `seed_cmd` trong `app/cli.py` để tự động nạp template mẫu `DTP_HOA_DON_TAC_NGHIEP` (tự động liên kết Data Source `ORACLE_TEST` nếu có sẵn) đảm bảo tính idempotent.
  - Viết test `tests/unit/test_template_diagram.py` (kiểm tra đầy đủ cả 5 sơ đồ Mermaid) và `tests/unit/test_template_seed_export_import.py` (kiểm tra export, import mới, chặn trùng mã, ghi đè và nạp seed qua CLI).
- Kiểm tra:
  - `uv run pytest tests/unit/test_template_diagram.py tests/unit/test_template_seed_export_import.py -v`: 8/8 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 43 source files.
  - `uv run poe test`: 100 passed, 3 skipped.
- Suy ra (nếu có): Trích xuất sơ đồ Mermaid trực tiếp từ cấu hình Pydantic giúp tài liệu hóa và trực quan hóa trực tiếp luồng đối soát trên giao diện mà không cần duy trì sơ đồ thủ công riêng biệt.
### Bước 3 — 2026-10-31 23:57
- Đã làm:
  - Cài đặt `app/services/template.py` gồm các dịch vụ quản lý vòng đời template và phiên bản theo Spec 03:
    - `list_templates(ctx, q, status)`: liệt kê danh sách template kèm trạng thái và phiên bản hiện hành.
    - `get_template(ctx, template_id, version)`: lấy chi tiết template kèm cấu hình `CONFIG_JSON` của phiên bản chỉ định.
    - `save_draft_template(...)`: tạo mới template hoặc ghi đè phiên bản nháp khi chưa có run; tự động tăng số hiệu phiên bản mới (`max + 1`) nếu phiên bản hiện tại đã có run ghi nhận; bảo vệ kiểm soát xung đột đồng thời qua `row_version` (trả `STALE_DATA`).
    - `activate_version(...)`: kích hoạt phiên bản thành `ACTIVE`, chuyển các phiên bản `ACTIVE` trước đó thành `RETIRED`, yêu cầu kết quả `DRY_RUN_OK='Y'`.
    - `clone_template(...)`: nhân bản template sang mã mới ở trạng thái `DRAFT` v1, chặn trùng mã (`TEMPLATE_CODE_EXISTS`).
    - `archive_template(...)`: chuyển trạng thái sang `ARCHIVED` (không thể chạy đối soát mới).
    - Phân quyền: các thao tác tạo/sửa/kích hoạt/lưu trữ yêu cầu vai trò `ADMIN` hoặc `TEMPLATE_OWNER`.
    - Ghi nhận `RECON_AUDIT_LOG` trong cùng transaction cho mọi thay đổi.
  - Viết test `tests/unit/test_template_service.py` với 7 test case kiểm tra lưu nháp mới, ghi đè nháp, tạo phiên bản mới khi đã có run, kiểm soát `STALE_DATA`, kích hoạt version, clone và archive.
- Kiểm tra:
  - `uv run pytest tests/unit/test_template_service.py -v`: 7/7 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 41 source files.
  - `uv run poe test`: 92 passed, 3 skipped.
- Suy ra (nếu có): Kiểm tra số lượng lượt chạy trong `RECON_RUN` của phiên bản hiện tại trước khi quyết định ghi đè hay sinh phiên bản mới giúp bảo toàn tính bất biến (immutability) của các kết quả đối soát trong quá khứ.
### Bước 2 — 2026-10-31 23:53
- Đã làm:
  - Cài đặt `app/services/template_validate.py`: hàm `validate_template_connected(ctx, config, data_source_id)` xác thực cấu hình `DbSourceSpec` với catalog CSDL Oracle thực tế:
    - Kiểm tra bảng/view tồn tại trong schema (báo lỗi `TABLE_NOT_FOUND` kèm đường dẫn `db_source.table`).
    - Kiểm tra mọi cột DB được tham chiếu trong `fields[].db`, `filters[].column`, `static_where[].column` tồn tại trong bảng (báo lỗi `COLUMN_NOT_FOUND` kèm đường dẫn chính xác).
    - Kiểm tra các cột lọc dùng cho `p_from`, `p_to` bắt buộc có kiểu `DATE` hoặc `TIMESTAMP` (báo lỗi nếu là chuỗi/số).
    - Xử lý mất kết nối hoặc không truy cập được Data Source thành cảnh báo (warnings) an toàn, không chặn việc lưu nháp template.
  - Viết test `tests/unit/test_template_config_connected.py` với 6 test case bao quát bảng không tồn tại, cột không tồn tại, cột ngày sai kiểu, mất kết nối mạng và không chọn data source.
  - Bổ sung test integration `test_validate_template_connected_oracle` trong `tests/integration/test_oracle_smoke.py` (tự động skip khi thiếu VPN/môi trường).
- Kiểm tra:
  - `uv run pytest tests/unit/test_template_config_connected.py -v`: 6/6 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 40 source files.
  - `uv run poe test`: 85 passed, 3 skipped.
- Suy ra (nếu có): Tách biệt rõ hai cấp độ xác thực (tĩnh qua Pydantic schema validation và động qua kết nối catalog Data Source) giúp giao diện người dùng lưu nháp linh hoạt ngay cả khi đang offline hoặc chưa kết nối VPN, đồng thời cảnh báo rõ ràng trước khi kích hoạt.
### Bước 1 — 2026-10-31 23:50
- Đã làm:
  - Cài đặt `app/schemas/template_config.py` gồm toàn bộ các model Pydantic v2 theo Spec 03: `FileSpec`, `RowFilter`, `RowFilters`, `FieldSpec`, `DerivedSpec`, `DerivedExpr`, `DbSourceSpec`, `SourceFilter`, `StaticFilter`, `ParamSpec`, `TimeFilterSpec`, `MeasureSpec`, `ProfileSpec`, `ControlTotalSpec`, `TemplateConfig`.
  - Cài đặt bộ kiểm tra chéo (`_validate_cross_rules`) sử dụng `ValidationError.from_exception_data` của `pydantic_core` để chỉ định chính xác đường dẫn (`loc`) của mọi trường lỗi cấu hình: trùng tên trường giữa fields và derived, bắt buộc đúng 1 profile mặc định, group_by phải đủ nguồn 2 phía và tồn tại, kiểm tra ràng buộc kiểu dữ liệu cho sum/value, main_measure, và phát hiện chu trình drilldown vòng lặp.
  - Viết bộ test `tests/unit/test_template_config_static.py` với 23 test case kiểm tra mẫu DTP hợp lệ và 22 trường hợp sai cấu hình với assert vị trí lỗi chính xác.
- Kiểm tra:
  - `uv run pytest tests/unit/test_template_config_static.py -v`: 23/23 passed.
  - `uv run poe test-engine`: 79 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 39 source files.
- Suy ra (nếu có): Dùng `pydantic_core.ValidationError.from_exception_data` với danh sách `InitErrorDetails` cho phép gắn đường dẫn lỗi (`loc`) dạng tuple động tùy biến (`("profiles", p_idx, "measures", m_idx, "agg")`) chuẩn xác hơn rất nhiều so với raise ValueError thông thường trong model_validator.
<!-- ### Bước N — YYYY-MM-DD HH:mm
- Đã làm:
- Kiểm tra: lệnh + kết quả (ghi rõ test Oracle bị skip hay đã chạy qua VPN)
- Suy ra (nếu có):
- Việc cần người làm thủ công:
-->
