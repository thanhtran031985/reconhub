# Task 71 — Decisions

- D1: giới hạn 30s là của **câu COUNT** (`count_timeout =
  min(timeout_sec, 30)`, `app/services/report_run.py:370`), chặn cứng
  bất kể `TIMEOUT_SEC` của báo cáo (mặc định 300s, migration 0004).
- D2: COUNT chạy TRƯỚC câu dữ liệu và chặn toàn bộ lượt xem — COUNT lỗi
  thì không hiện gì, dù trang 1 (50 dòng) có thể tải nhanh.
- D3: không tìm thấy lý do giữ mức 30s trong spec/docs (chỉ comment
  `# Q3` trong code) — mức này là lựa chọn lúc viết code.
- D4: hướng sửa user đã chọn (12/11/2026): đưa cả 2 timeout lên trang
  /settings để tự chỉnh, mặc định 300s mỗi cái (thay cho 3 hướng A/B/C).
- D5: 2 key `REPORT_COUNT_TIMEOUT_SEC` / `REPORT_DATA_TIMEOUT_SEC`
  trong `RECON_APP_SETTING` (mẫu `export_retention.py`, ADMIN-only),
  kẹp 1..3600, mặc định 300. `_execute_count_page` bỏ chặn cứng
  `min(..., 30)`; `_execute_preview` cũng dùng setting data timeout.
  Cột `TIMEOUT_SEC` của báo cáo vẫn giữ trong DB, vẫn dùng ở các đường
  describe/inspect — không xóa. Không migration (setting đọc với mặc
  định khi chưa có key).
- D6: get/set timeout đặt ở module service mới
  `app/services/report_timeouts.py` (không nhét vào `report_run.py`):
  theo đúng mẫu `export_retention.py`, `report_run.py` chỉ import
  `get_report_timeouts` — tránh vòng import và để `run_env` fixture
  monkeypatch được qua danh sách module như các service setting khác.
