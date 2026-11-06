# Checklist kiểm thử – 21-reporting-core

| ✓ | ID | Ca kiểm thử | Loại | Ưu tiên |
|---|---|---|---|---|
| ☐ | T21-01 | Upgrade/downgrade SQLite và Oracle | Oracle | Cao |
| ☑ | T21-02 | PK/FK/UQ/check constraints | pytest | Cao |
| ☑ | T21-03 | Clone Active tạo DRAFT mới | pytest | Cao |
| ☑ | T21-04 | Chỉ một ACTIVE version khi concurrent activate | pytest | Cao |
| ☑ | T21-05 | Run cũ giữ VERSION_ID cũ | pytest | Cao |
| ☑ | T21-06 | Audit và rollback transaction | pytest | Cao |

Ghi chú: T21-01 nhánh SQLite đạt (migration lifecycle + downgrade từ chối khi có dữ liệu); nhánh Oracle chưa chạy được trên máy ảo (không VPN) — kiểm chứng phía người dùng khi có VPN.
