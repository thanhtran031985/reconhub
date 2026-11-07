# TASK UI-07 — System & Auth

## Status

DONE

## Dependencies

- UI-00B (Fluent Foundation)

## Objective

Đồng bộ thiết kế, typography, spacing và token màu Fluent cho 5 màn hình hệ thống và xác thực (`/login`, `/account`, `/forbidden`, `/suspended`, `/dev/ui`).
Loại bỏ các style hardcoded (ví dụ: `backgroundColor: var(--color-bg, #f8fafc)` trong login), chuẩn hóa kích thước controls về `size="sm"` / `size="xs"` và đảm bảo hiển thị hoàn hảo trên cả desktop và mobile mà tuyệt đối không can thiệp vào logic xác thực, phiên làm việc hay quyền hạn.

> [!IMPORTANT]
> **EXECUTION POLICY**:
> AI chỉ được thực hiện task này khi người dùng chỉ định chính xác: `"Làm UI-07"`.
> Sau khi hoàn thành task này: **STOP**. Không tự động bắt đầu task tiếp theo.

## Pages

| Route | Page Module | Task Gốc Sinh Ra | Spec Liên Quan | Màn Thiết Kế Gốc |
|---|---|---|---|---|
| `/login` | `app/ui/pages/login.py` | [01-auth-users](../01-auth-users/task.md) & [08-app-shell-ui](../08-app-shell-ui/task.md) | [01_architecture_adr.md](../../specs/01_architecture_adr.md), [06_security_ops.md](../../specs/06_security_ops.md) | `designs/components/Screen10-Login` |
| `/account` | `app/ui/pages/account.py` | [01-auth-users](../01-auth-users/task.md) | [01_architecture_adr.md](../../specs/01_architecture_adr.md), [06_security_ops.md](../../specs/06_security_ops.md) | `designs/components/Screen10-Login` |
| `/forbidden` | `app/ui/pages/forbidden.py` | [01-auth-users](../01-auth-users/task.md) & [19-menu-permission](../19-menu-permission/task.md) | [05_services_pages.md](../../specs/05_services_pages.md) | — |
| `/suspended` | `app/ui/pages/suspended.py` | [19-menu-permission](../19-menu-permission/task.md) & [20-menu-admin](../20-menu-admin/task.md) | [11_menu_permission.md](../../specs/11_menu_permission.md) | — |
| `/dev/ui` | `app/ui/pages/dev_gallery.py` | [08-app-shell-ui](../08-app-shell-ui/task.md) | — | `designs/components/Gallery` |

## Target Pattern

**FORM**:
- Layout form gọn gàng, thẻ Paper `withBorder=True`, viền mảnh `line`, nền `surface`.
- Typography chuẩn Segoe UI / Inter, nhãn trường 12px fw=600, input `size="sm"`.
- Nút chính màu xanh Fluent `primary` (`#0F6CBD`), nút phụ viền mảnh.
- Không áp dụng máy móc quy chuẩn Data 4-state cho các trang tĩnh (`login`, `forbidden`, `suspended`).

## Read First

1. `AGENTS.md`
2. `.agents/rules/ui-dash.md`
3. `designs/tokens.json`
4. `docs/ui-migration.md` (mục 3, 4, 10 cho UI-07)
5. Yêu cầu & nghiệp vụ gốc:
   - [01-auth-users/task.md](../01-auth-users/task.md) (Xác thực, phiên làm việc, đổi mật khẩu bắt buộc)
   - [19-menu-permission/task.md](../19-menu-permission/task.md) & [20-menu-admin/task.md](../20-menu-admin/task.md) (Quyền hạn 403 Forbidden và chức năng 503 Suspended)
6. Baseline screenshots: `artifacts/ui-inventory/login-before-1366x768.png`, `account-before-1366x768.png`, `forbidden-before-1366x768.png`, `suspended-before-1366x768.png`

## Allowed Scope

- `/login`:
  - Thay màu nền thẻ cứng `#f8fafc` bằng biến token `var(--bg)` (`#F5F5F5`).
  - Thẻ đăng nhập dùng `dmc.Paper(withBorder=True, radius="md", p="lg")`, tối đa 400px.
  - Chuẩn hóa form đổi mật khẩu bắt buộc (`step=change`) đồng bộ style.
- `/account`:
  - Chuẩn hóa 2 khối: Khối thông tin người dùng (Username, Họ tên, Email, Các vai trò được gán) và Khối form đổi mật khẩu tự nguyện.
  - Loại bỏ các inline style thừa `style={"flex": 1}`.
- `/forbidden` & `/suspended`:
  - Căn giữa màn hình gọn gàng với icon lucide nét mảnh (`shield-alert` cho 403, `pause-circle` cho suspended).
  - Tiêu đề order=3 (18px), thông báo nguyên nhân rõ ràng và nút "Quay lại trang chủ".
- `/dev/ui`:
  - Đồng bộ các component demo theo đúng foundation UI-00B.

## Forbidden Scope

- **TUYỆT ĐỐI KHÔNG SỬA**:
  - Cơ chế tạo phiên Flask `session["user_id"]`, `session["session_version"]`, cookie HttpOnly / SameSite.
  - Cờ bắt buộc đổi mật khẩu `MUST_CHANGE_PW` và logic ép đổi mật khẩu tại login.
  - Thuật toán băm mật khẩu Argon2 trong `app/core/auth.py`.
  - Logic kiểm tra quyền truy cập route trong `app/ui/app.py`.
  - Component IDs của form đăng nhập (`login-username`, `login-password`, `login-submit-btn`...).

## Preserve Contracts

- Đăng nhập thành công phải redirect về đúng trang trước đó hoặc trang chủ `/`.
- Đăng xuất phải xóa sạch phiên và redirect về `/login`.
- Đổi mật khẩu thành công phải cập nhật `SESSION_VERSION` để hủy các phiên cũ.

## Preflight

1. `git status --short`
2. `git branch --show-current`
3. Xem ảnh baseline của 5 trang.
4. Chạy `pytest tests/unit/test_auth.py` ghi nhận baseline test xác thực.

## Implementation Steps

1. **Step 1 — Login & Mandatory Password Change Modernization (`/login`)**:
   - Thay `backgroundColor: var(--color-bg, #f8fafc)` bằng token `var(--bg)`.
   - Chuẩn hóa kích thước input `size="sm"`, nút Đăng nhập màu primary.
   - Kiểm tra hiển thị cả 2 trạng thái: Form đăng nhập và Form đổi mật khẩu bắt buộc (`/login?step=change`).
2. **Step 2 — Account Page Refactoring (`/account`)**:
   - Tích hợp `PageHeader`.
   - Phân chia khối thông tin tài khoản và form đổi mật khẩu thành 2 panel rõ ràng.
3. **Step 3 — System Static Pages (`/forbidden`, `/suspended`)**:
   - Dựng giao diện thông báo lỗi/tạm ngưng tối giản, biểu tượng rõ ràng, nút điều hướng về trang chủ.
4. **Step 4 — Dev Component Gallery (`/dev/ui`)**:
   - Cập nhật showcase hiển thị đầy đủ các component Fluent Foundation mới từ UI-00B.
5. **Step 5 — Chụp ảnh AFTER & Verification**:
   - Chụp cả 5 trang ở 1366×768, 1440×900, 390×844 lưu vào `artifacts/ui-migration/UI-07/`.
   - Chạy test auth regression.

## Bug Safety Rules

Mọi lỗi gặp phải phân loại:
- `A. PRE-EXISTING UNRELATED`: Ghi nhận, không sửa.
- `B. PRE-EXISTING BLOCKER`: Sửa tối thiểu nếu chặn đăng nhập.
- `C. INTRODUCED BY CURRENT TASK`: Bắt buộc sửa và kèm regression test.
- `D. DISCOVERED RELATED BUG`: Chỉ sửa nếu thuộc phạm vi 5 trang trên và không đổi contract.
- `E. UNKNOWN`: DỪNG và hỏi người dùng.

## Tests

- Chạy `uv run poe lint`
- Chạy `uv run poe typecheck`
- Chạy `uv run poe test`
- Chạy `pytest tests/unit/test_auth.py`
- Đo đạc tự động Playwright: Cả 5 trang đều `document.documentElement.scrollHeight <= innerHeight` ở 1366×768 (riêng `/dev/ui` chấp nhận cuộn dọc nếu danh sách demo dài).

## Visual Checks

- Thẻ đăng nhập hiển thị trang nhã, bóng mờ nhẹ (`shadow="sm"`), viền mảnh, căn giữa hoàn hảo.
- Trang 403 và Suspended không bị lệch khung, chữ tiếng Việt có dấu rõ ràng.
- Giao diện tài khoản hiển thị đúng font mono cho Username và các badge vai trò màu sắc chuẩn.

## Acceptance Criteria

- [ ] `/login`, `/account`, `/forbidden`, `/suspended`, `/dev/ui` được đồng bộ thiết kế chuẩn Fluent.
- [ ] Không còn màu hex hoặc style cứng trong `login.py`.
- [ ] Logic đăng nhập, đăng xuất, đổi mật khẩu và bảo mật phiên hoạt động 100% nguyên vẹn.
- [ ] Hiển thị hoàn hảo trên cả desktop 1366×768 và mobile 390×844.
- [ ] Ảnh AFTER đã lưu tại `artifacts/ui-migration/UI-07/`.
- [ ] Toàn bộ test suite PASS.

## Files Expected To Change

- `app/ui/pages/login.py`
- `app/ui/pages/account.py`
- `app/ui/pages/forbidden.py`
- `app/ui/pages/suspended.py`
- `app/ui/pages/dev_gallery.py`

## Files Must Not Change

- `app/core/auth.py`
- `app/core/session.py`
- `app/routes/auth_routes.py`

## Completion Report Format

```markdown
## UI-07 Completed

Pages migrated to System & Auth Pattern:
- /login (Token styling, clean card, mandatory pw change harmonized)
- /account (Profile info & voluntary password change)
- /forbidden (Minimalist 403 error page)
- /suspended (Minimalist feature suspended page)
- /dev/ui (Showcase updated with Fluent Foundation components)

Screenshots:
- artifacts/ui-migration/UI-07/<page>-after-1366x768.png

Tests run:
- lint: PASS
- typecheck: PASS
- tests: PASS

STOP. Chờ người dùng chỉ định task tiếp theo.
```

## STOP Condition

Sau khi hoàn thành và test xong: **STOP**.
Chờ người dùng review và chỉ định task tiếp theo.

