# Field

Nhãn + ô nhập + gợi ý/lỗi: input, password, select, multiselect, textarea mono, datetime, checkbox.

## Props và quy tắc

| Prop | Kiểu |
|---|---|
| label, hint, error, required, mono | |

Ngày giờ: `dmc.DateTimePicker(withSeconds=True, valueFormat="DD/MM/YYYY HH:mm:ss")`. Mật khẩu: `dmc.PasswordInput` (nút hiện/ẩn). Lỗi: viền và nền crit, `aria-describedby`.

## Kiểu dáng
Lớp `rh-…` trong `../bundle.css`; xem `../Gallery/preview.html`.

## Chuyển sang Dash
Hàm trong `app/ui/components/` theo bảng "Ánh xạ sang Dash Mantine" ở `designs/README.md`. Không dùng hex/px.
