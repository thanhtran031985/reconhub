# Quyết định – 22-reporting-source

Tham chiếu spec 12 và data flow. Ghi mọi khác biệt đã duyệt tại đây.

- 06/11/2026 (duyệt plan "làm theo đề xuất đến xong task"): Q0 — nhánh `feat/22-reporting-source` từ local `e9e649f` (đầu nhánh task 21); thứ tự áp patch bắt buộc: patch task 21 trước, patch task 22 sau. Q1 — validator mở rộng trong `app/engine/sql_guard.py`, discovery/query builder/diff trong service mới `app/services/report_source.py`, tái dùng `catalog.py` + `sql_builder.quote_identifier`. Q2 — validator report tái dùng lõi `sql_guard` (strip comments/literals + DISALLOWED_KEYWORDS) nhưng bỏ bắt buộc `:p_from`/`:p_to`. Q3 — `list_tables` thêm tham số `object_type` ("VIEW"/"TABLE"/None). Q4 — timeout discover/describe dùng `min(TIMEOUT_SEC của version, CALL_TIMEOUT_S của Data Source)`. Q5 — trước khi discover/describe, kiểm tra account Data Source là read-only, lỗi thì DS_NOT_READ_ONLY. Q6 — cột mất sau re-analyze: giữ dòng cột nhưng tắt WEB/EXCEL_VISIBLE để wizard/task 27 cho xem lại rồi xóa tay. Q7 — làm xong cả task rồi gửi xem (như task 19/20/21).
- T22-07 nhánh Oracle thật không chạy được trên máy ảo (không VPN) — kiểm chứng phía người dùng khi có VPN.
