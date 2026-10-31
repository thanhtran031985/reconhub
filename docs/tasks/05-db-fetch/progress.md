# Tiến độ — 05-db-fetch

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Builder kind=table | ✅ | 2026-11-01 |  |
| 2 | SQL gộp theo profile | 🔄 |  |  |
| 3 | SQL guard | ⬜ |  |  |
| 4 | Fetch + describe | ⬜ |  |  |

## Nhật ký
### Bước 1 — 2026-11-01 00:35
- Đã làm:
  - Cài đặt `app/engine/sql_dialect.py`:
    - `quote_identifier(ident)`: quote định danh theo chuẩn Oracle (`"SCHEMA"."TABLE"`, `"COLUMN"`), bóc tách và chuẩn hóa tên bảng/view/cột.
    - Cài đặt các biểu thức chuẩn Oracle: `trunc_day` (`TRUNC(expr)`), `trunc_month` (`TRUNC(expr, 'MM')`), `concat` (`expr1 || expr2`), `substr`, `coalesce`.
  - Cài đặt `app/engine/sql_builder.py`:
    - `build_source_sql(config, profile=None, params=None)` cho chế độ `kind="table"`:
      - Thu thập danh sách cột trong whitelist từ các trường có mapping cơ sở dữ liệu (`f.db`), không dùng `SELECT *`.
      - Sinh câu lệnh `SELECT <columns> FROM "SCHEMA"."TABLE"`.
      - Sinh mệnh đề `WHERE` an toàn:
        - Xử lý các filters động liên kết với tham số (`p_from`, `p_to`,...), hỗ trợ ép kiểu `cast="trunc_day"`, bind parameter `:param`.
        - Hỗ trợ cờ `skip_if_empty`: tự động bỏ qua điều kiện lọc nếu tham số rỗng/None.
        - Xử lý các filters tĩnh (`static_where`: `=`, `!=`, `in`, `is null`, `is not null`).
  - Viết test `tests/unit/test_sql_builder_table.py` xác thực:
    - Sinh SQL mẫu DTP từ bảng `RECON_SRC.SRC_FACT_INVOICE_DTP` với đầy đủ các cột mapped và mệnh đề WHERE có bind.
    - Kiểm tra `skip_if_empty` khi có và không có giá trị tham số.
    - Kiểm tra các biểu thức `static_where` (IN list, IS NOT NULL, chuỗi ký tự).
- Kiểm tra:
  - `uv run pytest tests/unit/test_sql_builder_table.py -v`: 3/3 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 54 source files.
- Suy ra (nếu có): Quá trình quote định danh bảng trên Oracle cần tách theo dấu chấm `.` để quote riêng biệt từng thành phần `"SCHEMA"."TABLE"`, tránh để nguyên chuỗi `"SCHEMA.TABLE"` khiến Oracle hiểu nhầm là tên bảng có chứa ký tự chấm.
<!-- ### Bước N — YYYY-MM-DD HH:mm
- Đã làm:
- Kiểm tra: lệnh + kết quả (ghi rõ test Oracle bị skip hay đã chạy qua VPN)
- Suy ra (nếu có):
- Việc cần người làm thủ công:
-->
