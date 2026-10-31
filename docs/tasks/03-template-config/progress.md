# Tiến độ — 03-template-config

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Pydantic model | ✅ | 2026-10-31 |  |
| 2 | Validator có kết nối | 🔄 |  |  |
| 3 | Repo/service version | ⬜ |  |  |
| 4 | Export/import + diagram + seed | ⬜ |  |  |

## Nhật ký
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
