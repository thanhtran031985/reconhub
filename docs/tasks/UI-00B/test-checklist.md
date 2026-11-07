# TEST CHECKLIST — TASK UI-00B: Fluent Foundation

## 1. Functional Regression
- [ ] Ứng dụng khởi động bình thường không báo lỗi import.
- [ ] Đăng nhập tại `/login` vẫn hoạt động tốt, redirect về `/`.
- [ ] Sidebar mở rộng (200px) và thu gọn về rail (48px) khi click nút toggle.
- [ ] Breadcrumb hiển thị chính xác theo đường dẫn hiện tại.
- [ ] Công tắc đổi giao diện Sáng / Tối (`ColorSchemeToggle`) chuyển đổi bình thường.
- [ ] Menu người dùng (Tài khoản, Đăng xuất) hoạt động bình thường.
- [ ] Cơ chế cập nhật quyền theo `PERM_REVISION` trong sidebar tiếp tục hoạt động.

## 2. Component API & Defaults
- [ ] `DataGrid`:
  - [ ] Nhận `rowModelType="clientSide"` hoặc `"infinite"`.
  - [ ] Áp dụng đúng `rowHeight=32`, `headerHeight=34`.
  - [ ] Áp dụng đúng theme và CSS class `rh-diff`.
- [ ] `PageHeader`:
  - [ ] Render Title order=4, size 18px.
  - [ ] Subtitle hiển thị font 12px c="dimmed" cùng hàng.
  - [ ] Action buttons căn phải cùng hàng ngang.
- [ ] `CommandBar`:
  - [ ] Render `dmc.Paper` withBorder.
  - [ ] Search input cao 28px, icon search lucide.
  - [ ] Phân cách separator hiển thị đúng token.
- [ ] `MasterDetailLayout`:
  - [ ] Phân chia Master chiếm `flex: 1` và Detail cố định 380px.
  - [ ] Trên desktop (≥900px): nằm ngang song song.
  - [ ] Trên mobile (<900px): xếp chồng dọc (stack).
- [ ] `WizardShell`:
  - [ ] Stepper compact 1 hàng ở đỉnh.
  - [ ] Body chiếm `flex: 1`, cuộn độc lập.
  - [ ] Footer Back / Next cố định ở chân trang.
- [ ] `SkeletonGrid`:
  - [ ] Render đúng số dòng/cột skeleton với chiều cao 32px.
- [ ] `ErrorState`:
  - [ ] Hiển thị thông điệp lỗi kèm nút "Thử lại".

## 3. Layout & Scroll (1366×768 & 1440×900)
- [ ] Khung `AppShell` không làm phát sinh page-scroll toàn trang (`document.documentElement.scrollHeight <= innerHeight`).
- [ ] Không có horizontal scroll ở khung nhìn desktop.
- [ ] Header chiếm đúng 44px chiều cao.
- [ ] Navbar chiếm đúng 200px (khi mở) và 48px (khi đóng).

## 4. Code Quality & Safety
- [ ] `uv run poe lint` không có lỗi.
- [ ] `uv run poe typecheck` không có lỗi.
- [ ] `uv run poe test` xanh toàn bộ suite.
- [ ] Không có duplicate component ID nào được sinh ra.
- [ ] Không có source code trang nào trong `app/ui/pages/` bị sửa.

