# TEST CHECKLIST — TASK UI-00B: Fluent Foundation

## 1. Functional Regression
- [x] Ứng dụng khởi động bình thường không báo lỗi import.
- [x] Đăng nhập tại `/login` vẫn hoạt động tốt, redirect về `/`.
- [x] Sidebar mở rộng (200px) và thu gọn về rail (48px) khi click nút toggle.
- [x] Breadcrumb hiển thị chính xác theo đường dẫn hiện tại.
- [x] Công tắc đổi giao diện Sáng / Tối (`ColorSchemeToggle`) chuyển đổi bình thường.
- [x] Menu người dùng (Tài khoản, Đăng xuất) hoạt động bình thường.
- [x] Cơ chế cập nhật quyền theo `PERM_REVISION` trong sidebar tiếp tục hoạt động.

## 2. Component API & Defaults
- [x] `DataGrid`:
  - [x] Nhận `rowModelType="clientSide"` hoặc `"infinite"`.
  - [x] Áp dụng đúng `rowHeight=32`, `headerHeight=34`.
  - [x] Áp dụng đúng theme và CSS class `rh-diff`.
- [x] `PageHeader`:
  - [x] Render Title order=4, size 18px.
  - [x] Subtitle hiển thị font 12px c="dimmed" cùng hàng.
  - [x] Action buttons căn phải cùng hàng ngang.
- [x] `CommandBar`:
  - [x] Render `dmc.Paper` withBorder.
  - [x] Search input cao 28px, icon search lucide.
  - [x] Phân cách separator hiển thị đúng token.
- [x] `MasterDetailLayout`:
  - [x] Phân chia Master chiếm `flex: 1` và Detail cố định 380px.
  - [x] Trên desktop (≥900px): nằm ngang song song.
  - [x] Trên mobile (<900px): xếp chồng dọc (stack).
- [x] `WizardShell`:
  - [x] Stepper compact 1 hàng ở đỉnh.
  - [x] Body chiếm `flex: 1`, cuộn độc lập.
  - [x] Footer Back / Next cố định ở chân trang.
- [x] `SkeletonGrid`:
  - [x] Render đúng số dòng/cột skeleton với chiều cao 32px.
- [x] `ErrorState`:
  - [x] Hiển thị thông điệp lỗi kèm nút "Thử lại".

## 3. Layout & Scroll (1366×768 & 1440×900)
- [x] Khung `AppShell` không làm phát sinh page-scroll toàn trang (`document.documentElement.scrollHeight <= innerHeight`).
- [x] Không có horizontal scroll ở khung nhìn desktop.
- [x] Header chiếm đúng 44px chiều cao.
- [x] Navbar chiếm đúng 200px (khi mở) và 48px (khi đóng).

## 4. Code Quality & Safety
- [x] `uv run poe lint` không có lỗi.
- [x] `uv run poe typecheck` không có lỗi.
- [x] `uv run poe test` xanh toàn bộ suite.
- [x] Không có duplicate component ID nào được sinh ra.
- [x] Không có source code trang nào trong `app/ui/pages/` bị sửa.

