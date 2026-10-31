# DataGrid

Bảng dữ liệu. Bảng đơn giản `rh-table`; grid kết quả `dash-ag-grid`.

## Props và quy tắc

- `build_column_defs(meta)` từ `run.columns`: khóa ghim trái (mono), Trạng thái, mỗi measure nhóm Excel | DB | Chênh.
- Ô lệch `rh-diff`; số căn phải vi-VN; infinite row model 200 dòng.
- Chọn nhiều dòng (Lịch sử, Issues): cột checkbox, thanh hành động hiện khi có lựa chọn.
- 4 trạng thái.

## Kiểu dáng
Lớp `rh-…` trong `../bundle.css`; xem `../Gallery/preview.html`.

## Chuyển sang Dash
Hàm trong `app/ui/components/` theo bảng "Ánh xạ sang Dash Mantine" ở `designs/README.md`. Không dùng hex/px.
