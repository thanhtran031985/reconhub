# AppShell

Khung ứng dụng: thanh bên tối, thanh trên, banner, vùng nội dung.

## Props và quy tắc

| Prop | Kiểu | Ghi chú |
|---|---|---|
| user | `{username, full_name, roles[]}` | Menu người dùng góc phải: Tài khoản, Đăng xuất |
| env | DEV/UAT/PROD | Nhãn màu |
| breadcrumb | `{label, href?}[]` | |
| banners | `{tone, text, link?}[]` | Bảo trì; cảnh báo dữ liệu tạm (chỉ Admin) |

Menu theo vai trò: **Đối soát** (Dashboard, Chạy đối soát, Kết quả run, Lịch sử); **Cấu hình** (Templates, Đăng ký template, Data Sources – AD, Người dùng – AD).

## Kiểu dáng
Lớp `rh-…` trong `../bundle.css`; xem `../Gallery/preview.html`.

## Chuyển sang Dash
Hàm trong `app/ui/components/` theo bảng "Ánh xạ sang Dash Mantine" ở `designs/README.md`. Không dùng hex/px.
