# Spec 11 – Phân quyền theo menu, phạm vi dữ liệu và Danh sách menu

_Phiên bản 1.0, 05/11/2026. Bổ sung cho v4. Thay cơ chế 4 vai trò cố định (spec 06 mục 1) bằng vai trò do Admin tạo, cấu hình bật/tắt từng menu. Task 19 (phân quyền) và task 20 (Danh sách menu)._

## 1. Quyết định đã chốt

| # | Quyết định |
|---|---|
| D1 | **ADMIN** là vai trò đặc biệt duy nhất: luôn có mọi menu (kể cả menu mới), xem tất cả dữ liệu, làm được thao tác nhạy cảm. Không sửa, không xóa |
| D2 | Mọi vai trò khác **chỉ cấu hình bật/tắt từng menu**. Có menu = thấy menu và thao tác được trong màn đó |
| D3 | Phạm vi dữ liệu chạy đối soát: vai trò khác **chỉ thấy run, lần chạy bộ, lịch sử, dashboard do chính mình chạy**. Không có tùy chọn "xem tất cả" ngoài ADMIN |
| D4 | Thao tác nhạy cảm chỉ ADMIN, dù có menu: chạy trên Data Source PROD; xóa dữ liệu tạm hàng loạt; chuyển RECON_APP sang Oracle và xóa bản lưu SQLite cũ |
| D5 | Admin tự tạo vai trò; không gán quyền riêng từng người. Một người nhiều vai trò → hợp các menu |
| D6 | Danh sách menu do **code** khai báo và tự đồng bộ vào DB khi khởi động. Không có chức năng tạo menu trên giao diện |
| D7 | Admin chỉnh được cách hiển thị menu (tên, nhóm, thứ tự) và **tạm ẩn** menu khỏi mọi vai trò. Không tạo menu, không sửa đường dẫn |

## 2. Danh sách menu: nguồn và đồng bộ

### 2.1 Khai báo trong code (`app/ui/menus.py`)
```python
MENUS = [
  MenuDef(code="dashboard", label="Dashboard", group="DOI_SOAT", path="/", order=10, icon="lucide:layout-dashboard"),
  MenuDef(code="run", label="Chạy đối soát", group="DOI_SOAT", path="/runs/new", order=20, icon="lucide:play"),
  ...
  MenuDef(code="menu_admin", label="Danh sách menu", group="QUAN_TRI", path="/menus", order=30, icon="lucide:list"),
]
GROUPS = [GroupDef("DOI_SOAT","Đối soát",10), GroupDef("CAU_HINH","Cấu hình",20), GroupDef("QUAN_TRI","Quản trị",30)]
```
- `code` là khóa bất biến; mỗi page Dash và mỗi service khai báo `menu_code` mà nó thuộc về.
- Mã nhóm, mã menu: `^[a-z][a-z0-9_]{1,39}$`.

### 2.2 Đồng bộ khi khởi động (`services/menu_sync.py`)
Chạy một lần mỗi lần khởi động web (khóa bằng `RECON_APP_SETTING.MENU_SYNC_LOCK` để nhiều process không chạy chồng):

| Tình huống | Hành vi |
|---|---|
| Menu mới trong code | Thêm `RECON_MENU` (`SOURCE_*` = giá trị code, `DISPLAY_*` = NULL, `IS_NEW='Y'`). Không thêm vào vai trò nào (ADMIN tự có) |
| Code đổi label/nhóm/thứ tự/icon/path | Cập nhật cột `SOURCE_*` và `PATH`. **Không ghi đè** cột `DISPLAY_*` Admin đã chỉnh |
| Menu bị bỏ khỏi code | `IS_REMOVED='Y'`, ẩn khỏi mọi nơi; giữ `RECON_ROLE_MENU` để truy vết. Xuất hiện lại trong code → `IS_REMOVED='N'`, cấu hình cũ có hiệu lực lại |
| Nhóm mới / bỏ nhóm | Tương tự với `RECON_MENU_GROUP` |
- Đồng bộ tăng `PERM_REVISION` (mục 6) nếu có thay đổi; ghi audit actor `system`.

### 2.3 Giá trị hiển thị
`label = DISPLAY_LABEL ?? SOURCE_LABEL`, tương tự nhóm và thứ tự. "Khôi phục mặc định" = đặt `DISPLAY_*` về NULL.

## 3. Bảng dữ liệu
Chi tiết cột ở `11_menu_permission_tables.md`.

| Bảng | Vai trò |
|---|---|
| `RECON_MENU_GROUP` | Nhóm menu (seed từ code), tên/thứ tự hiển thị chỉnh được |
| `RECON_MENU` | Menu (seed từ code), tên/nhóm/thứ tự hiển thị, trạng thái ẩn |
| `RECON_ROLE` | Vai trò: mã, tên, mô tả, `IS_SYSTEM` (chỉ ADMIN), đang dùng |
| `RECON_ROLE_MENU` | Vai trò được bật menu nào |
| `RECON_USER_ROLE` | Đổi `ROLE STR(20)` cố định → `ROLE_ID` tham chiếu `RECON_ROLE` |

Migration: tạo vai trò `ADMIN` (system) và 3 vai trò thường `TEMPLATE_OWNER`, `OPERATOR`, `VIEWER` với menu tương ứng bảng quyền PRD v4 (để hành vi không đổi khi nâng cấp); chuyển `RECON_USER_ROLE.ROLE` sang `ROLE_ID`.

## 4. Quy tắc phân quyền

### 4.1 Tính quyền thực tế
```
effective_menus(user) =
  nếu user không hoạt động → ∅
  nếu user có vai trò ADMIN (đang dùng) → mọi menu IS_REMOVED='N' (kể cả đang ẩn, xem 4.3)
  ngược lại → ∪ menu của các vai trò đang dùng của user
             ∩ menu IS_REMOVED='N' AND IS_HIDDEN='N'
is_admin(user) = có vai trò ADMIN đang dùng
```

### 4.2 Kiểm tra
- **Service**: mọi hàm service khai báo `@requires_menu("batch_run")`; thiếu → `FORBIDDEN`. Hàm dùng chung nhiều màn khai báo danh sách (`any_of`).
- **Page Dash**: `dash.register_page(..., menu_code=...)`; không có menu → chuyển `/forbidden`.
- **Thanh bên**: chỉ hiện menu trong `effective_menus`, sắp theo thứ tự nhóm rồi thứ tự menu (giá trị hiển thị). Nhóm không còn menu nào thì ẩn.
- **Thao tác nhạy cảm** (D4): `require_admin(ctx)` trong service, bất kể menu.
- Có test tự động: mọi page và mọi hàm service public đều có `menu_code` (quét registry), tránh màn mới quên gắn quyền.

### 4.3 Menu bị tạm ẩn
- Ẩn khỏi thanh bên và chặn truy cập với mọi vai trò thường (page → trang "Chức năng tạm ngưng"; service → `MENU_HIDDEN`).
- **ADMIN vẫn truy cập được** (để kiểm tra khi bảo trì), thanh bên ADMIN hiện menu với nhãn "Đang ẩn".
- Cấu hình bật/tắt của vai trò giữ nguyên; bỏ ẩn thì có hiệu lực lại.
- Không cho ẩn các menu bắt buộc của quản trị: `menu_admin`, `role`, `user` (tránh tự khóa đường quản trị). Ẩn `dashboard` được phép; trang chủ khi đó chuyển tới menu đầu tiên người dùng có.

### 4.4 Rào chắn
- Vai trò ADMIN: không sửa menu, không tắt, không xóa, không đổi mã.
- Luôn còn ít nhất **một người dùng hoạt động có vai trò ADMIN** (`LAST_ADMIN`).
- Xóa vai trò đang gán cho người dùng: chặn (`ROLE_IN_USE`); gợi ý tắt vai trò.
- Mã vai trò `^[A-Z][A-Z0-9_]{1,29}$`, không đổi sau tạo; tên không trùng (không phân biệt hoa thường).

## 5. Phạm vi dữ liệu chạy đối soát (D3)
Lọc trong repo bằng `owner_filter(ctx)`; ADMIN không lọc.

| Đối tượng | Điều kiện với vai trò thường |
|---|---|
| `RECON_RUN` (danh sách, chi tiết, kết quả dòng, chi tiết dòng, export, tải file gốc, chạy lại, đánh dấu kiểm tra, xóa dữ liệu tạm của run) | `CREATED_BY = ctx.username` |
| `RECON_BATCH_RUN` và mục, file, .zip | `CREATED_BY = ctx.username`; run con theo batch |
| Lịch sử, Dashboard (đếm, biểu đồ) | Chỉ run của mình |
| Issue (task 14) | Theo run gốc (`FIRST_RUN_ID` của mình) |
| Template, bộ đối soát, Data Source, danh mục | Không lọc (dùng chung, theo menu) |

- Không thuộc phạm vi → `NOT_FOUND` (không phải `FORBIDDEN`) để không lộ run có tồn tại. Đường tải file Flask áp dụng cùng quy tắc.
- Chạy lại / chạy lại run lỗi tạo run mới với `CREATED_BY` = người bấm.
- Run của người dùng bị tắt: chỉ ADMIN còn xem được.
- Test bắt buộc: với mỗi đường truy cập trong bảng trên, user B gọi bằng ID run của user A → NOT_FOUND.

## 6. Hiệu lực ngay, không cần đăng xuất
- `RECON_APP_SETTING.PERM_REVISION` tăng trong cùng transaction với mọi thay đổi: vai trò, vai trò–menu, user–vai trò, trạng thái user, menu (ẩn, tên, nhóm, thứ tự), đồng bộ menu.
- Mỗi process cache `effective_menus(user_id)` theo `(user_id, PERM_REVISION)`; đọc revision tối đa 1 lần/giây.
- Thanh bên kiểm revision bằng `dcc.Interval` 5 giây; đổi revision thì dựng lại thanh bên. Người đang ở màn vừa bị tắt quyền: thao tác kế tiếp nhận `FORBIDDEN` và chuyển `/forbidden`.
- SLA: thay đổi có hiệu lực ≤ 5 giây với mọi phiên đang mở.

## 7. Màn hình

### 7.1 Vai trò và phân quyền (`/roles`, menu `role`) – task 19
Theo preview `Screen14-Permission` (đã duyệt), điều chỉnh:
- Bỏ bảng "Phạm vi dữ liệu và thao tác đặc biệt"; thay bằng một dòng ghi chú: "Vai trò thường: chỉ thấy run do mình chạy; thao tác nhạy cảm chỉ ADMIN."
- Checkbox menu lấy từ `RECON_MENU` (nhóm và thứ tự hiển thị). Menu `IS_NEW='Y'` có nhãn **"Mới"**; menu đang ẩn có nhãn **"Đang ẩn"** (vẫn bật/tắt được, có hiệu lực khi bỏ ẩn).
- Tab "Quyền thực tế của người dùng" và "Mô phỏng phạm vi dữ liệu" giữ nguyên.
- Lưu vai trò: hộp thoại liệt kê menu thêm/bỏ, số người ảnh hưởng.

### 7.2 Danh sách menu (`/menus`, menu `menu_admin`) – task 20
Theo preview `Screen15-MenuAdmin`:
- Bảng nhóm và menu (kéo-thả hoặc nút lên/xuống để đổi thứ tự trong nhóm; chọn nhóm từ danh sách nhóm).
- Mỗi menu: mã (chỉ đọc), đường dẫn (chỉ đọc), tên mặc định (từ code), tên hiển thị (sửa được), nhóm, thứ tự, số vai trò đang bật, trạng thái (Hiển thị / Đang ẩn / Mới / Đã gỡ khỏi code), lý do ẩn.
- Nhóm: đổi tên hiển thị, đổi thứ tự nhóm. Không tạo/xóa nhóm (do code).
- Tạm ẩn: hộp thoại nhập lý do (bắt buộc, hiển thị cho người dùng ở trang "Chức năng tạm ngưng"), cảnh báo số người dùng bị ảnh hưởng. Menu bắt buộc (`menu_admin`, `role`, `user`) không có nút ẩn, kèm lý do.
- "Khôi phục mặc định" cho từng menu và cho toàn bộ.
- Đánh dấu "Đã xem" menu mới (bỏ nhãn Mới) – tự động khi Admin lưu vai trò có tick menu đó, hoặc bấm tay.
- Xem trước thanh bên theo thứ tự đang chỉnh trước khi lưu.
- Lưu một lần cho mọi thay đổi (ROW_VERSION chống ghi đè).

## 8. Service

| Service | Hàm | Quyền |
|---|---|---|
| `perm` | `effective_menus(ctx)`, `is_admin(ctx)`, `requires_menu`, `require_admin`, `owner_filter(ctx)` | — |
| `role` | `list`, `get`, `create(code, name, desc, copy_from)`, `update(id, name, desc, active, menus, row_version)`, `delete(id)`, `users_of(id)`, `effective_of_user(user_id)` | menu `role` |
| `menu_admin` | `list_tree()`, `save(changes, row_version)` (tên, nhóm, thứ tự, ẩn/bỏ ẩn kèm lý do), `reset(menu_code \| ALL)`, `mark_seen(menu_code)`, `preview_sidebar(changes)` | menu `menu_admin` |
| `menu_sync` | `sync_from_code()` (khởi động) | system |

Mã lỗi mới: `ROLE_SYSTEM_LOCKED, ROLE_CODE_EXISTS, ROLE_NAME_EXISTS, ROLE_IN_USE, LAST_ADMIN, MENU_HIDDEN, MENU_NOT_HIDEABLE, MENU_REMOVED, MENU_GROUP_INVALID, MENU_HIDE_REASON_REQUIRED, STALE_DATA`.

## 9. Audit
Ghi `RECON_AUDIT_LOG` cùng transaction: tạo/sửa/tắt/xóa vai trò (kèm danh sách menu trước/sau); gán/gỡ vai trò người dùng; đổi tên/nhóm/thứ tự menu; ẩn/bỏ ẩn (kèm lý do); khôi phục mặc định; đồng bộ menu từ code (actor `system`).

## 10. Chuyển sang Oracle (spec 08)
Thứ tự chép: `RECON_MENU_GROUP`, `RECON_MENU`, `RECON_ROLE`, `RECON_ROLE_MENU` trước `RECON_USER_ROLE`. Thuộc phạm vi CONFIG_ONLY. Sau khi khởi động trên Oracle, `menu_sync` chạy lại bình thường.

## 11. Ảnh hưởng tới task đã có
- Task 01: `require_role` → `requires_menu` / `require_admin`; seed vai trò theo mục 3.
- Task 07, 11, 12, 14, 15, 18: thêm `owner_filter` và test NOT_FOUND chéo người dùng.
- Task 08: thanh bên đọc `effective_menus`; màn Người dùng chọn vai trò từ `RECON_ROLE`.
- Nên làm task 19 ngay sau task 01; task 20 sau task 19.
