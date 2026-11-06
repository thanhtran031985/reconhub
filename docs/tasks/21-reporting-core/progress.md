# Tiến độ – 21-reporting-core

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Schema/migration cho 10 bảng | ✅ | |
| 2 | Services Report Master, Template, Version clone/activate/archive | ✅ | |
| 3 | Seed menu report_center/report_history/report_admin | ✅ | |
| 4 | Audit và Oracle metadata migration | ✅ | |

Hồi quy cuối (06/11/2026): test đầy đủ **670 pass, 5 skip, 0 fail** (617 ở cuối task 20 + 53 test mới task 21); e2e **12 pass**; typecheck **21 lỗi = baseline task 19, 0 mới**; lint sạch. T21-01: nhánh SQLite đạt (upgrade head 2 lần + downgrade base + upgrade head, downgrade từ chối khi có dữ liệu); nhánh Oracle chưa chạy được (không VPN) — kiểm chứng phía người dùng.
