# 08-app-shell-ui — Component Dash Mantine, AppShell, Templates, Data Sources, Người dùng

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ2
- Phụ thuộc: 01, 02, 03, 07
- Nhánh git: feat/08-app-shell-ui

## Mục tiêu
Có bộ component Dash Mantine theo designs/, khung ứng dụng, màn Templates, Data Sources (2 tab, gồm khối Dữ liệu tạm với xóa theo điều kiện) và Người dùng dùng service thật, đủ 4 trạng thái.

## Phạm vi
- app/ui/components/: 13 hàm component theo bảng ánh xạ designs/README.md
- app/ui/layout/shell.py: dmc.AppShell (navbar tối, header breadcrumb, nhãn ENV, menu người dùng Tài khoản/Đăng xuất), menu lọc theo vai trò; banner bảo trì và banner cảnh báo dữ liệu tạm (AD)
- pages/templates.py
- pages/data_sources.py: tab Nguồn đối soát (drawer thêm/sửa, kiểm tra); tab Lưu trữ RECON_APP: DB đang dùng, Dữ liệu tạm (KPI, ngưỡng cảnh báo, Xóa theo điều kiện → Xem trước → gõ XOA, Nhật ký xóa), Đích Oracle + script tạo user; chỗ trống có ghi chú cho khối Chuyển dữ liệu (task 13)
- pages/users.py (Screen11): bảng, lọc, drawer thêm/sửa (vai trò nhiều), đặt lại mật khẩu, mở khóa, tắt/bật, lịch sử đăng nhập
- Formatter số và ngày giờ VN; pages/dev_gallery.py (/dev/ui)

## Ngoài phạm vi
- Wizard (task 09)
- Chuyển dữ liệu (task 13)

## Thiết kế
- designs/components/AppShell, Button, Field, StatusChip, Alert, Tabs, Stepper, KpiCard, DataGrid, Drawer, FileDrop, EmptyState, CodeBlock, Gallery
- designs/components/Screen02-Templates, Screen08-DataSources, Screen11-Users

## Spec liên quan
- docs/PRD.md Phần B, C2, C8, C12
- docs/specs/05 mục 3

## Quyết định kiến trúc
- Màu/khoảng cách qua theme DMC; icon dash-iconify lucide; không emoji

## Các bước
### Bước 1 — Component + gallery
- Làm: Component + gallery
- Test viết trước: status_chip luôn có icon + chữ; field lỗi có aria-describedby; formatter
- Kiểm tra: `uv run poe test`; mở /dev/ui đối chiếu Gallery/preview.html

### Bước 2 — AppShell + banner
- Làm: AppShell + banner
- Test viết trước: menu theo vai trò; banner cảnh báo khi usage vượt ngưỡng
- Kiểm tra: `uv run poe test`

### Bước 3 — Màn Templates
- Làm: Màn Templates
- Test viết trước: e2e: tạo, clone, archive; 4 trạng thái
- Kiểm tra: `uv run poe e2e`

### Bước 4 — Màn Data Sources
- Làm: 2 tab, dữ liệu tạm, xóa theo điều kiện
- Test viết trước: e2e: tạo nguồn, kiểm tra (fetcher giả); xem trước rồi xóa theo điều kiện với XOA; Operator không thấy menu
- Kiểm tra: `uv run poe e2e`

### Bước 5 — Màn Người dùng
- Làm: Màn Người dùng
- Test viết trước: e2e spec 07 mục 4.1; không tắt được Admin cuối cùng
- Kiểm tra: `uv run poe e2e`

## Chấp nhận khi
- [ ] Ba màn khớp preview.html về bố cục, chữ trên nút
- [ ] Đủ 4 trạng thái
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh, e2e xanh

## Câu hỏi mở
- —
