# Task 72 — Decisions

- D1: cả 2 nút tải ĐÃ có code (callback `_download_zip` →
  `build_zip` đầy đủ cache/tổng hợp/file riêng; callback
  `_download_one` → `export_run`). Nghi ngờ "chưa code" cần kiểm chứng
  live trước khi kết luận.
- D2: cột Thao tác → `dmc.Menu` 1 nút mở menu; các mục giữ nguyên id
  hiện tại (`brr-download-btn`, `brr-rerun-btn`, Mở run là Anchor)
  để callback tải/chạy-lại không đổi.
- D3: nếu check live tìm ra lỗi tải → sửa đúng chỗ lỗi, không viết lại
  phần đã chạy.
- D4: check live trước (port 8122, 2 mục DONE) phát hiện cả 2 nút tải
  HỎNG THẬT, cùng một gốc: "Tải tất cả" tải được .zip nhưng chỉ có
  00_TONG_HOP (thiếu 2 file riêng, build_zip lặng lẽ bỏ qua export lỗi);
  "Tải file" bấm không tải gì (callback trả notify_error). Gốc:
  `export_run` crash `AttributeError: 'NoneType' object has no attribute
  'get'` ở `app/engine/export.py:121` — `STATUS_AMOUNTS_JSON` trong DB
  là NULL. Chuỗi: `build_summary` trả `{}` khi profile không có
  `main_measure` (`summary.py:160-175`) → executor lưu
  `_get_sum(...) or summary_dict.get("status_amounts")` — `{}` falsy nên
  rơi sang `None` → cột NULL (`run_executor.py:540`) →
  `export.py:116` dùng `summary.get("STATUS_AMOUNTS_JSON", {})` trả
  `None` (key có sẵn với giá trị None) → `.get` crash. Fix 2 chỗ:
  export.py dùng `or {}` (chữa cả các run đã lưu NULL, gồm batch #17
  thật) + executor lưu `{}` thay vì NULL cho run mới.
- D5: lỗi tải thứ hai, ở tầng callback (phát hiện sau khi sửa D4, khi
  check live lại): `_download_one` đọc `res.data["path"]` nhưng
  `export_run` chỉ trả `{"run_id", "export_path", "file_name"}` — không
  có key `"path"` → `KeyError` → callback 500, bấm "Tải file" không tải
  gì. Hai caller còn lại (`run_result.py:1905`,
  `file_routes.py:86`) đều dùng đúng `"export_path"`; chỉ chỗ này sai
  nên nút "Tải file" chưa từng chạy được. Fix: đọc `"export_path"`.
- D6: giới hạn check live: worker không chạy được run có DS SQLITE
  (`open_source_connection` chỉ hỗ trợ ORACLE, `source_conn.py:30`) —
  có sẵn, không phải do task 72. Vì vậy check "Chạy lại" chỉ chứng minh
  menu gọi được `rerun_item` (tạo run con mới trong hàng đợi), không chờ
  worker chạy xong; trên app thật (DS Oracle) worker chạy bình thường.
