# Checklist kiểm thử — 19-menu-permission

Loại: **A** tự động (pytest) · **E** E2E (Playwright) · **O** Oracle qua VPN · **M** kiểm tay. Ca ưu tiên **Cao** phải đạt trước khi đóng task.

Tổng: **41 ca** · Cao 30

## 0. Dữ liệu

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T19-00-01 | Seed: ADMIN, TEMPLATE_OWNER, OPERATOR, VIEWER + 6 user (1 user 2 vai trò, 1 user đã tắt), 8 run của 4 người, 2 lần chạy bộ | fixture | Dùng cho mọi nhóm | A | Cao |

## 1. Migration

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T19-01-01 | Upgrade trên DB v4 có user 4 vai trò | db-migrate | Mỗi user có đúng menu tương đương bảng quyền v4 | A | Cao |
| ☐ | T19-01-02 | Chạy 2 lần; downgrade khi chỉ có vai trò seed | — | Không lỗi; ROLE cũ khôi phục | A | Cao |
| ☐ | T19-01-03 | Downgrade khi có vai trò tự tạo | — | Báo lỗi rõ, không mất dữ liệu | A | Trung bình |
| ☐ | T19-01-04 | Oracle RECON_APP_TEST | test-oracle | Upgrade/downgrade thành công | O | Trung bình |

## 2. Đồng bộ menu từ code

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T19-02-01 | Thêm menu mới trong menus.py, khởi động | menu_sync | Có trong RECON_MENU, IS_NEW=Y; không vai trò thường nào có; ADMIN thấy | A | Cao |
| ☐ | T19-02-02 | Code đổi label/path | — | SOURCE_* và PATH cập nhật; DISPLAY_* không đổi | A | Cao |
| ☐ | T19-02-03 | Bỏ menu khỏi code | — | IS_REMOVED=Y, ẩn với mọi người kể cả ADMIN; RECON_ROLE_MENU giữ nguyên | A | Cao |
| ☐ | T19-02-04 | Menu xuất hiện lại | — | IS_REMOVED=N, cấu hình cũ có hiệu lực | A | Trung bình |
| ☐ | T19-02-05 | 2 process khởi động cùng lúc | — | Không trùng dòng, không lỗi khóa | A | Cao |
| ☐ | T19-02-06 | Đồng bộ có thay đổi | — | PERM_REVISION tăng, audit actor system | A | Trung bình |

## 3. Tính quyền

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T19-03-01 | User 2 vai trò | effective_menus | Hợp các menu | A | Cao |
| ☐ | T19-03-02 | Vai trò bị tắt | — | Menu của vai trò đó không tính | A | Cao |
| ☐ | T19-03-03 | User đã tắt | — | Không có menu, không đăng nhập được | A | Cao |
| ☐ | T19-03-04 | ADMIN | — | Mọi menu không gỡ, kể cả menu mới và menu đang ẩn | A | Cao |
| ☐ | T19-03-05 | Registry | test quét page/service | Mọi page và service public có menu_code; thiếu → test đỏ | A | Cao |

## 4. Kiểm tra ở server

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T19-04-01 | Gọi service của menu không có quyền | ctx Operator gọi data_source.create | FORBIDDEN | A | Cao |
| ☐ | T19-04-02 | Mở URL page không có quyền | /data-sources | Chuyển /forbidden | E | Cao |
| ☐ | T19-04-03 | Gọi thẳng /_dash-update-component của màn không có quyền | POST với phiên Operator | Bị chặn | A | Cao |
| ☐ | T19-04-04 | Thao tác nhạy cảm với vai trò có menu | Operator có menu run chạy Data Source PROD; TO có menu history xóa hàng loạt; vai trò có menu data_source chuyển Oracle | Đều FORBIDDEN | A | Cao |

## 5. Phạm vi dữ liệu

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T19-05-01 | Danh sách run, lịch sử, dashboard | User B | Chỉ run của B; số đếm dashboard chỉ của B | A | Cao |
| ☐ | T19-05-02 | Mở run của A bằng ID ở: chi tiết, rows, row_detail, export, tải file gốc, chạy lại, đánh dấu kiểm tra, xóa dữ liệu tạm | User B | NOT_FOUND (không phải FORBIDDEN), không lộ tồn tại | A | Cao |
| ☐ | T19-05-03 | Lần chạy bộ của A: ma trận, .zip, chạy lại run lỗi, thay file | User B | NOT_FOUND | A | Cao |
| ☐ | T19-05-04 | Route Flask /download/* với ID của A | User B | 404 cùng thông báo như ID không tồn tại | A | Cao |
| ☐ | T19-05-05 | ADMIN | — | Thấy và thao tác mọi run | A | Cao |
| ☐ | T19-05-06 | Chạy lại run lỗi | B chạy lại lần chạy bộ của B | Run mới CREATED_BY = B | A | Trung bình |
| ☐ | T19-05-07 | Template, bộ đối soát, Data Source, danh mục | User có menu | Thấy toàn bộ, không lọc người tạo | A | Trung bình |

## 6. Vai trò

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T19-06-01 | Tạo vai trò: mã sai định dạng, mã trùng, tên trùng khác hoa thường | — | Lỗi dưới ô | E | Cao |
| ☐ | T19-06-02 | Sao chép menu từ vai trò khác, nhân bản | — | Menu giống nguồn | E | Trung bình |
| ☐ | T19-06-03 | Sửa/tắt/xóa ADMIN | service | ROLE_SYSTEM_LOCKED | A | Cao |
| ☐ | T19-06-04 | Xóa vai trò đang gán user | — | ROLE_IN_USE, gợi ý tắt | A | Cao |
| ☐ | T19-06-05 | Bỏ ADMIN khỏi user ADMIN cuối cùng / tắt user đó | — | LAST_ADMIN | A | Cao |
| ☐ | T19-06-06 | Hai Admin cùng sửa 1 vai trò | ROW_VERSION cũ | STALE_DATA | A | Trung bình |
| ☐ | T19-06-07 | Audit | tạo/sửa/xóa vai trò, gán user | Có menu trước/sau, rollback thì không có | A | Cao |

## 7. Hiệu lực và giao diện

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T19-07-01 | Admin tắt menu của vai trò khi user đang mở màn đó | 2 trình duyệt | ≤ 5 giây thanh bên đổi; thao tác kế tiếp chuyển /forbidden | E | Cao |
| ☐ | T19-07-02 | Thanh bên theo nhóm/thứ tự, ẩn nhóm rỗng | — | Đúng | E | Cao |
| ☐ | T19-07-03 | Màn vai trò: nhãn Mới, Đang ẩn; đánh dấu thay đổi; hỏi khi bỏ thay đổi | — | Đúng preview Screen14 | E | Trung bình |
| ☐ | T19-07-04 | Tab Quyền thực tế và Mô phỏng | — | Đúng hợp vai trò; mô phỏng lọc run đúng | E | Trung bình |
| ☐ | T19-07-05 | 4 trạng thái, bàn phím, 1366/375px | — | Đạt | E | Trung bình |

## 8. Oracle và hồi quy

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T19-08-01 | Chuyển metadata | Seed vai trò tự tạo | 4 bảng chép đúng thứ tự, user giữ quyền | O | Cao |
| ☐ | T19-08-02 | Test cũ các task 01–18 | Toàn bộ | Xanh sau khi thay require_role | A | Cao |

## Ghi nhận

| Ngày | Người | ID | Kết quả | Ghi chú |
|---|---|---|---|---|
|  |  |  |  |  |
