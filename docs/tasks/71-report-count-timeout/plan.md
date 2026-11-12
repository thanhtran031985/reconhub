# Task 71 — Plan: timeout câu COUNT và câu dữ liệu cấu hình trên /settings

## Chẩn đoán (đã đọc code)

- Đường xem báo cáo: viewer → `get_report_page` →
  `_execute_count_page` (`app/services/report_run.py:350`). Hàm này chạy
  2 câu truy vấn:
  1. **COUNT**: `SELECT COUNT(*) AS total FROM (<SQL báo cáo>)` với
     `count_timeout = min(int(detail["timeout_sec"]), 30)  # Q3` — giới
     hạn câu đếm **cố định tối đa 30 giây**.
  2. **Trang dữ liệu**: `SELECT * FROM (<SQL báo cáo>) ORDER BY ...
     OFFSET ... FETCH NEXT 50 ROWS ONLY` với
     `data_timeout = int(detail["timeout_sec"])` — timeout của báo cáo,
     mặc định **300 giây** (migration 0004, `server_default="300"`).
- Thông báo lỗi "(30 giây)" khớp với `count_timeout` → câu **COUNT**
  là câu bị quá giờ, không phải câu lấy dữ liệu. Nâng `TIMEOUT_SEC` của
  báo cáo cũng không cứu được câu COUNT vì nó bị chặn cứng ở 30s.
- Vì sao COUNT chậm ở đây: nó bọc toàn bộ SQL báo cáo và bắt Oracle
  thực thi hết (lọc + gom ~11 tháng dữ liệu, App Catos, không lọc Org)
  chỉ để đếm số dòng. Câu lấy dữ liệu chỉ cần 50 dòng nên có thể nhanh,
  nhưng COUNT chạy TRƯỚC và chặn toàn bộ — COUNT lỗi thì không hiện gì
  cả, dù trang 1 có thể tải được.
- `TIMEOUT_SEC` của từng báo cáo (cột `RECON_RPT_VERSION.TIMEOUT_SEC`)
  **không sửa được trên giao diện** (không có trong `app/ui/pages/` hay
  `report_admin.py`) — chỉ có mặc định 300 trong DB. Vì vậy đưa timeout
  lên /settings không làm mất chức năng nào trên UI.

## Quyết định của user (12/11/2026)

Đưa cả 2 timeout lên trang /settings để tự chỉnh, mặc định 300s mỗi cái
(thay cho 3 hướng A/B/C trình trước đó).

## Thiết kế (theo mẫu settings sẵn có, task 52/57)

- 2 key mới trong `RECON_APP_SETTING`, theo mẫu `export_retention.py`
  (hàm get/set riêng, ADMIN-only):
  - `REPORT_COUNT_TIMEOUT_SEC` — timeout câu COUNT, mặc định 300.
  - `REPORT_DATA_TIMEOUT_SEC` — timeout câu dữ liệu (trang + xem trước),
    mặc định 300.
- Trang /settings thêm mục "Timeout truy vấn báo cáo" với 2
  `dmc.NumberInput` (giây), kẹp 1..3600, lưu qua service như các mục
  sẵn có.
- `report_run.py`: `_execute_count_page` bỏ chặn cứng `min(..., 30)` —
  `count_timeout` lấy từ setting, `data_timeout` lấy từ setting;
  `_execute_preview` (dry-run/xem trước 10 dòng) cũng dùng setting
  data timeout. Cột `TIMEOUT_SEC` của báo cáo vẫn giữ trong DB và vẫn
  dùng ở các đường describe/inspect (`report_source.py:475`,
  `report_param.py:921`) — không xóa.
- Không đổi SQL báo cáo, không migration (setting mới là dữ liệu, đọc
  với mặc định khi chưa có key).

## Các bước

1. Test đỏ trước: get/set 2 setting (mặc định 300, kẹp biên, chỉ ADMIN
   sửa được); `_execute_count_page` tôn trọng setting (count timeout 1s
   → lỗi "(1 giây)", không còn chặn 30s).
2. Service get/set + mục mới trên /settings + sửa `report_run.py`
   (count + data + preview).
3. Tests liên quan + check live (port 8121) + typecheck/ruff + full
   suite → commit → patch (áp sau patch 70, KHÔNG cần db-migrate, chỉ
   khởi động lại app).
