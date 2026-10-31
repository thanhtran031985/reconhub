# Tiến độ — 04-excel-reader

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Reader | ✅ | 2026-11-01 |  |
| 2 | Mapping + detect | 🔄 |  |  |
| 3 | Normalize + derive + invalid | ⬜ |  |  |
| 4 | Control total + filters | ⬜ |  |  |
| 5 | Inspect | ⬜ |  |  |
| 6 | Service file + nạp dữ liệu tạm | ⬜ |  |  |

## Nhật ký
### Bước 1 — 2026-11-01 00:07
- Đã làm:
  - Cài đặt `app/engine/reader.py`:
    - `list_sheets(path)`: trích xuất danh sách sheet qua `fastexcel` (trả `["Sheet1"]` cho file CSV).
    - `read_sheet(path, file_spec)`: đọc dữ liệu thô qua `calamine` (Excel) hoặc `polars.read_csv` (hỗ trợ phân cách `,`, `;`, `\t` và UTF-8 BOM `\ufeff`).
    - Cắt dòng theo `header_row`, `data_start_row`, `skip_footer_rows`.
    - Sinh cột `__row_no` phản ánh chính xác số dòng thực tế trong file Excel (1-based index).
    - Giữ mọi ô dữ liệu ở kiểu chuỗi (`pl.Utf8`), bảo toàn số 0 ở đầu (e.g. `"0334"`), loại bỏ BOM và tự động gắn hậu tố `__2`, `__3` khi phát hiện header trùng lặp kèm cảnh báo.
  - Viết test `tests/unit/test_excel_reader.py` kiểm tra danh sách sheet, đọc file mẫu `dtp_sample_200.xlsx` 201 dòng thô, header trùng lặp và CSV phân cách `;` kèm UTF-8 BOM.
- Kiểm tra:
  - `uv run pytest tests/unit/test_excel_reader.py -v`: 4/4 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 44 source files.
  - `uv run poe test-engine`: 104 passed.
- Suy ra (nếu có): Loại bỏ BOM `\ufeff` ở dòng header CSV là bắt buộc để tránh Polars nhận diện sai tên cột đầu tiên khi file được lưu dưới dạng UTF-8-SIG từ Excel.
<!-- ### Bước N — YYYY-MM-DD HH:mm
- Đã làm:
- Kiểm tra: lệnh + kết quả (ghi rõ test Oracle bị skip hay đã chạy qua VPN)
- Suy ra (nếu có):
- Việc cần người làm thủ công:
-->
