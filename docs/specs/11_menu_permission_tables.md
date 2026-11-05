# Spec 11a – Thiết kế bảng: Menu, vai trò, phân quyền

Kiểu trung lập theo spec 02 mục 0. Bảng sửa được có `CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION`. Một Alembic revision mới cho task 19 (`xxxx_menu_permission`), một revision nhỏ cho task 20 nếu cần thêm cột (dự kiến không cần: task 20 dùng cột đã tạo ở task 19).

## 1. RECON_MENU_GROUP

| Cột | Kiểu | Null | Ràng buộc / mặc định | Ghi chú |
|---|---|---|---|---|
| CODE | STR(40) | N | PK, `^[a-z][a-z0-9_]{1,39}$` | Từ code |
| SOURCE_LABEL | STR(100) | N | | Tên từ code, đồng bộ |
| SOURCE_ORDER | INT | N | | |
| DISPLAY_LABEL | STR(100) | Y | | Admin chỉnh; NULL = dùng SOURCE |
| DISPLAY_ORDER | INT | Y | | |
| IS_REMOVED | FLAG | N | `N` | Code không còn khai báo |
| SYNCED_AT | TS | N | | |
| UPDATED_BY, UPDATED_AT, ROW_VERSION | | | | |

## 2. RECON_MENU

| Cột | Kiểu | Null | Ràng buộc / mặc định | Ghi chú |
|---|---|---|---|---|
| CODE | STR(40) | N | PK | Khóa bất biến, page/service tham chiếu |
| PATH | STR(200) | N | | Từ code, Admin không sửa |
| ICON | STR(60) | Y | | Từ code (lucide) |
| SOURCE_LABEL | STR(100) | N | | |
| SOURCE_GROUP | STR(40) | N | FK RECON_MENU_GROUP(CODE) | |
| SOURCE_ORDER | INT | N | | |
| DISPLAY_LABEL | STR(100) | Y | | |
| DISPLAY_GROUP | STR(40) | Y | FK RECON_MENU_GROUP(CODE) | |
| DISPLAY_ORDER | INT | Y | | |
| IS_HIDEABLE | FLAG | N | `Y` | `N` cho `menu_admin`, `role`, `user` (khai báo trong code) |
| IS_HIDDEN | FLAG | N | `N` | Admin tạm ẩn |
| HIDDEN_REASON | STR(300) | Y | bắt buộc khi IS_HIDDEN='Y' (CK) | Hiện ở trang "Chức năng tạm ngưng" |
| HIDDEN_BY | STR(60) | Y | | |
| HIDDEN_AT | TS | Y | | |
| IS_NEW | FLAG | N | `Y` khi đồng bộ thêm mới | Bỏ khi Admin đánh dấu đã xem |
| IS_REMOVED | FLAG | N | `N` | |
| SYNCED_AT | TS | N | | |
| UPDATED_BY, UPDATED_AT, ROW_VERSION | | | | |

CK: `IS_HIDDEN='N' OR IS_HIDEABLE='Y'`; `IS_HIDDEN='N' OR HIDDEN_REASON IS NOT NULL`.
Index: `IX_MENU_GROUP (COALESCE(DISPLAY_GROUP, SOURCE_GROUP))` không dùng được trên mọi dialect → sắp xếp trong Python (số menu < 50).

## 3. RECON_ROLE

| Cột | Kiểu | Null | Ràng buộc / mặc định | Ghi chú |
|---|---|---|---|---|
| ID | ID | N | PK | |
| CODE | STR(30) | N | UQ, `^[A-Z][A-Z0-9_]{1,29}$` | Không đổi sau tạo |
| NAME | STR(100) | N | UQ theo chữ thường (kiểm ở service; Oracle thêm index trên `LOWER(NAME)`) | |
| DESCRIPTION | STR(300) | Y | | |
| IS_SYSTEM | FLAG | N | `N` | `Y` duy nhất cho `ADMIN` (seed) |
| IS_ACTIVE | FLAG | N | `Y` | |
| CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION | | | | |

## 4. RECON_ROLE_MENU

| Cột | Kiểu | Null | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| ROLE_ID | ID | N | FK RECON_ROLE(ID) ON DELETE CASCADE | Xóa vai trò (chỉ khi không có user) xóa luôn cấu hình |
| MENU_CODE | STR(40) | N | FK RECON_MENU(CODE) | |
| GRANTED_BY | STR(60) | N | | |
| GRANTED_AT | TS | N | | |
PK `(ROLE_ID, MENU_CODE)`. ADMIN **không có dòng** ở bảng này (quyền tính theo `IS_SYSTEM`).

## 5. RECON_USER_ROLE (thay đổi)

| Trước | Sau |
|---|---|
| `USER_ID, ROLE STR(20)`, PK `(USER_ID, ROLE)`, CK ROLE in 4 giá trị | `USER_ID FK RECON_USER, ROLE_ID FK RECON_ROLE(ID)`, PK `(USER_ID, ROLE_ID)`, + `ASSIGNED_BY`, `ASSIGNED_AT` |

Migration (batch mode SQLite):
1. Tạo 4 bảng mới; seed nhóm và menu từ `app/ui/menus.py` (gọi `menu_sync` trong revision).
2. Seed `RECON_ROLE`: `ADMIN` (system), `TEMPLATE_OWNER`, `OPERATOR`, `VIEWER`; seed `RECON_ROLE_MENU` theo bảng quyền PRD v4.
3. Thêm cột `ROLE_ID`, điền từ `ROLE` theo mã; kiểm không còn NULL; bỏ cột `ROLE`, đổi PK.
4. Downgrade: điền lại `ROLE` từ mã vai trò; vai trò tự tạo không có mã cũ → downgrade báo lỗi rõ (không mất dữ liệu ngầm).

## 6. RECON_APP_SETTING (khóa mới)
| KEY | Ý nghĩa |
|---|---|
| `PERM_REVISION` | Số nguyên tăng mỗi thay đổi phân quyền/menu |
| `MENU_SYNC_LOCK` | Khóa chống đồng bộ chồng khi nhiều process khởi động |

## 7. Seed menu (khớp v4 + gói bổ sung)

| Nhóm | Mã menu | Tên | Đường dẫn | Ẩn được | TEMPLATE_OWNER | OPERATOR | VIEWER |
|---|---|---|---|---|---|---|---|
| Đối soát | dashboard | Dashboard | / | Có | ✓ | ✓ | ✓ |
| | run | Chạy đối soát | /runs/new | Có | ✓ | ✓ | |
| | result | Kết quả run | /runs/<id> | Có | ✓ | ✓ | ✓ |
| | batch_run | Chạy bộ đối soát | /batch-runs | Có | ✓ | ✓ | |
| | history | Lịch sử | /runs | Có | ✓ | ✓ | ✓ |
| | issue | Xử lý chênh lệch | /issues | Có | ✓ | ✓ | |
| Cấu hình | template | Templates | /templates | Có | ✓ | | ✓ |
| | batch_def | Bộ đối soát | /batches | Có | ✓ | | ✓ |
| | data_source | Data Sources | /data-sources | Có | | | |
| | lookup | Danh mục hệ thống | /lookups | Có | | | |
| Quản trị | user | Người dùng | /users | **Không** | | | |
| | role | Vai trò và phân quyền | /roles | **Không** | | | |
| | menu_admin | Danh sách menu | /menus | **Không** | | | |

Ghi chú: Viewer có menu dashboard/history/result nhưng theo D3 chỉ thấy run của chính mình (thường là không có). Giữ để hành vi menu tương đương v4; Admin có thể tắt sau.
