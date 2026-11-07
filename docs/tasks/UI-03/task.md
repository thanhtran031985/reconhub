# TASK UI-03 — Admin Master–Detail

## Status

TODO

## Dependencies

- UI-00B (Fluent Foundation)
- UI-01 (Compact Lists)

## Objective

Chuyển đổi 4 màn hình quản trị hệ thống (`/lookups`, `/users`, `/roles`, `/menus`) sang pattern **MASTER_DETAIL** chuẩn Fluent: `PageHeader` + `CommandBar` + `MasterDetailLayout` (Master bên trái chiếm `flex: 1` | Detail panel bên phải rộng 380–420px, viền trái, cuộn độc lập).
Xử lý triệt để lỗi **tràn ngang desktop** hiện có ở `/roles` (1410px) và `/menus` (1460px), chấm dứt việc cuộn dọc hàng nghìn pixel (`menus` cuộn 3017px, `roles` cuộn 1496px). Loại bỏ các Modal/Drawer dài để đưa trực tiếp form thao tác sang Detail Panel.

> [!IMPORTANT]
> **EXECUTION POLICY**:
> AI chỉ được thực hiện task này khi người dùng chỉ định chính xác: `"Làm UI-03"`.
> Sau khi hoàn thành task này: **STOP**. Không tự động bắt đầu task tiếp theo.

## Pages

| Route | Page Module | Task Gốc Sinh Ra | Spec Liên Quan | Màn Thiết Kế Gốc |
|---|---|---|---|---|
| `/lookups` | `app/ui/pages/lookups.py` | [17-lookup-codes](../17-lookup-codes/task.md) | Task 17 (Lookup codes & types) | `designs/components/Screen12-Lookups` |
| `/users` | `app/ui/pages/users.py` | [01-auth-users](../01-auth-users/task.md), [08-app-shell-ui](../08-app-shell-ui/task.md) | [01_architecture_adr.md](../../specs/01_architecture_adr.md), [05_services_pages.md](../../specs/05_services_pages.md) | `designs/components/Screen11-Users` |
| `/roles` | `app/ui/pages/roles.py` | [19-menu-permission](../19-menu-permission/task.md) | [11_menu_permission.md](../../specs/11_menu_permission.md), [11_menu_permission_tables.md](../../specs/11_menu_permission_tables.md) | `designs/components/Screen14-Permission` |
| `/menus` | `app/ui/pages/menus.py` | [20-menu-admin](../20-menu-admin/task.md) | [11_menu_permission.md](../../specs/11_menu_permission.md) | `designs/components/Screen15-MenuAdmin` |

## Target Pattern

**MASTER_DETAIL**:
- Master: Danh sách bên trái (DataGrid hoặc Compact List co giãn `flex: 1`, internal scroll).
- Detail: Panel thuộc tính cố định bên phải (rộng 380–420px theo token, nền `surface-2`, viền trái `line`, internal scroll).
- Thao tác: Click chọn 1 dòng ở Master → Thông tin chi tiết hiện ngay ở Detail bên phải. Không mở Modal để chỉnh sửa.

## Read First

1. `AGENTS.md`
2. `.agents/rules/ui-dash.md`
3. `docs/ui-migration.md` (mục 3, 4, 5, 8 cho UI-03)
4. Yêu cầu & nghiệp vụ gốc:
   - [01-auth-users/task.md](../01-auth-users/task.md) (Người dùng, mật khẩu argon2, LAST_ADMIN protection)
   - [17-lookup-codes/task.md](../17-lookup-codes/task.md) (Danh mục Lookup Types & Codes)
   - [19-menu-permission/task.md](../19-menu-permission/task.md) (Phân quyền vai trò theo menu, PERM_REVISION)
   - [20-menu-admin/task.md](../20-menu-admin/task.md) (Danh sách cây menu, chức năng tạm ẩn/hiện)
5. Baseline screenshots: `artifacts/ui-inventory/roles-before-1366x768.png`, `menus-before-1366x768.png`, `users-before-1366x768.png`, `lookups-before-1366x768.png`
6. Foundation components từ UI-00B (`MasterDetailLayout`, `PageHeader`, `CommandBar`, `DataGrid`)

## Allowed Scope

- `/roles` (Vai trò và phân quyền):
  - **Khắc phục lỗi tràn ngang 1410px**: Bỏ bảng ma trận HTML tĩnh khổng lồ.
  - Master (Trái): Danh sách vai trò (Mã, Tên vai trò, Loại hệ thống, Trạng thái).
  - Detail (Phải): Cây phân quyền menu gán cho vai trò đang chọn (dạng checklist các nhóm menu và chức năng, nút Lưu quyền).
  - Thêm vai trò mới: Mở form tạo ngay tại panel Detail (hoặc modal ngắn).
- `/menus` (Quản trị menu):
  - **Khắc phục lỗi tràn ngang 1460px và cuộn 3017px**:
  - Master (Trái): Danh sách/Cây phân cấp menu (Group, Tên menu, Đường dẫn, Icon, Trạng thái Ẩn/Hiện).
  - Detail (Phải): Panel thuộc tính menu đang chọn (Tên hiển thị, Icon lucide picker, vị trí thứ tự order, switch tạm ẩn/hiện, nút Lưu).
  - Bỏ `menus-hide-modal` và `menus-save-modal` dài, chuyển sang cập nhật trực tiếp tại Detail Panel.
- `/users` (Quản lý người dùng):
  - Master (Trái): `DataGrid` danh sách người dùng (Username, Họ tên, Email, Vai trò, Trạng thái).
  - Detail (Phải): Panel thông tin người dùng được chọn + Form chỉnh sửa họ tên, email, gán vai trò checkbox (thay thế cho Drawer trượt ra che khuất màn hình).
  - Giữ Modal xác nhận đặt lại mật khẩu (`users-reset-modal`) và Modal xác nhận khóa người dùng.
- `/lookups` (Danh mục):
  - Master (Trái): Danh sách Lookup Type (`flex: 1`).
  - Detail (Phải): Danh sách Lookup Codes của Type đang chọn kèm form thêm/sửa code nhanh.
- Tự động chuyển thành xếp chồng dọc (stack) trên mobile (<900px).

## Forbidden Scope

- **KHÔNG thay đổi permission semantics**: Logic kiểm tra quyền `effective_menus`, `is_admin`, `page_gate` trong `app/services/perm.py` phải giữ nguyên 100%.
- **KHÔNG đổi component IDs** quan trọng (ví dụ: `users-search-input`, `roles-create-code`, `menus-table`...).
- **KHÔNG xóa các modal xác nhận ngắn hợp lệ**: Modal xác nhận xóa, modal xác nhận reset mật khẩu.
- **KHÔNG sửa dữ liệu người dùng seed** (`admin`, `owner`, `operator`, `viewer`).

## Preserve Contracts

- Bảng `RECON_USER`, `RECON_ROLE`, `RECON_ROLE_MENU`, `RECON_MENU` và schema DB không thay đổi.
- Quy tắc bảo vệ Admin cuối cùng (`LAST_ADMIN`) không được phép vô hiệu hóa.
- Audit log ghi nhận hành động quản trị phải được gọi đầy đủ từ service.

## Preflight

1. `git status --short`
2. `git branch --show-current`
3. Xem ảnh baseline tại `artifacts/ui-inventory/` của `roles`, `menus`, `users`, `lookups`.
4. Chạy `uv run poe test` và `pytest tests/e2e/test_menus.py` kiểm tra phân quyền.

## Implementation Steps

1. **Step 1 — Lookups Master–Detail (`/lookups`)**:
   - Tích hợp `MasterDetailLayout`.
   - Trái: Lookup Types list. Phải: Lookup Codes management.
   - Thử nghiệm chọn type, nạp codes và thêm mới code.
2. **Step 2 — Users Master–Detail (`/users`)**:
   - Trái: `DataGrid` danh sách người dùng.
   - Phải: Form chi tiết người dùng và phân vai trò.
   - Chuyển thao tác tạo mới / chỉnh sửa từ Drawer vào Detail panel.
3. **Step 3 — Roles & Permissions Matrix (`/roles`)**:
   - Thay thế ma trận bảng tĩnh bằng layout Master (Role) — Detail (Menu permissions checklist).
   - Kiểm tra: Triệt tiêu hoàn toàn tràn ngang 1410px và cuộn dọc 1496px.
   - Kiểm tra lưu quyền và cập nhật `PERM_REVISION`.
4. **Step 4 — Menus Administration (`/menus`)**:
   - Tái cấu trúc sang Master (Danh sách cây menu) — Detail (Thuộc tính & cấu hình hiển thị).
   - Kiểm tra: Triệt tiêu hoàn toàn tràn ngang 1460px và cuộn dọc 3017px.
   - Kiểm tra thao tác tạm ẩn menu và cập nhật navbar đồng bộ.
5. **Step 5 — Chụp ảnh AFTER & Verification**:
   - Chụp 4 trang ở 1366×768, 1440×900, 390×844 lưu vào `artifacts/ui-migration/UI-03/`.
   - Kiểm tra không còn horizontal scroll trên desktop.

## Bug Safety Rules

Mọi lỗi gặp phải phân loại:
- `A. PRE-EXISTING UNRELATED`: Ghi nhận, không sửa.
- `B. PRE-EXISTING BLOCKER`: Sửa tối thiểu nếu chặn quản trị.
- `C. INTRODUCED BY CURRENT TASK`: Bắt buộc sửa và kèm regression test.
- `D. DISCOVERED RELATED BUG`: Chỉ sửa nếu thuộc phạm vi 4 trang trên và không đổi contract.
- `E. UNKNOWN`: DỪNG và hỏi người dùng.

## Tests

- Chạy `uv run poe lint`
- Chạy `uv run poe typecheck`
- Chạy `uv run poe test`
- Chạy `pytest tests/e2e/test_menus.py`
- Đo đạc tự động Playwright:
  - Cả 4 trang `document.documentElement.scrollWidth <= innerWidth` tại 1366×768.
  - Cả 4 trang `document.documentElement.scrollHeight <= innerHeight` tại 1366×768.

## Visual Checks

- Màn hình `/roles` hiển thị danh sách vai trò bên trái, khi bấm vào một vai trò thì danh sách quyền/menu bên phải cập nhật tức thì. Không bị cuộn tràn ra ngoài màn hình.
- Màn hình `/menus` cây menu gọn gàng, panel bên phải cho phép sửa thuộc tính mà không mở modal che khuất bảng.
- Không còn thanh cuộn ngang của toàn bộ trang web trên desktop.

## Acceptance Criteria

- [ ] `/lookups`, `/users`, `/roles`, `/menus` chuyển thành công sang pattern MASTER_DETAIL.
- [ ] Hết hoàn toàn horizontal overflow trên desktop 1366×768 (`roles` từ 1410px về <= 1366px; `menus` từ 1460px về <= 1366px).
- [ ] Hết hoàn toàn page-scroll dọc (`menus` từ 3017px về <= 768px; `roles` từ 1496px về <= 768px).
- [ ] Không dùng Modal dài để sửa quyền, sửa menu hoặc sửa user.
- [ ] Cơ chế phân quyền và gán vai trò hoạt động chính xác 100%.
- [ ] Ảnh AFTER đã lưu tại `artifacts/ui-migration/UI-03/`.
- [ ] Toàn bộ test suite PASS.

## Files Expected To Change

- `app/ui/pages/lookups.py`
- `app/ui/pages/users.py`
- `app/ui/pages/roles.py`
- `app/ui/pages/menus.py`

## Files Must Not Change

- `app/services/perm.py`
- `app/services/user.py`
- `app/core/auth.py`
- `app/db/metadata.py`

## Completion Report Format

```markdown
## UI-03 Completed

Pages migrated to Admin Master–Detail:
- /lookups (Master: Types | Detail: Codes)
- /users (Master: DataGrid | Detail: User form & Roles)
- /roles (Master: Roles | Detail: Permissions checklist; Overflow eliminated: 1410px -> 1366px, Scroll: 1496px -> 768px)
- /menus (Master: Menu tree | Detail: Properties & Visibility; Overflow eliminated: 1460px -> 1366px, Scroll: 3017px -> 768px)

Screenshots:
- artifacts/ui-migration/UI-03/<page>-after-1366x768.png

Tests run:
- lint: PASS
- typecheck: PASS
- tests: PASS
- e2e: PASS

STOP. Chờ người dùng chỉ định task tiếp theo.
```

## STOP Condition

Sau khi hoàn thành và test xong: **STOP**.
Chờ người dùng review và chỉ định task tiếp theo.

