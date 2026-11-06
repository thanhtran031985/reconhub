# Tiến độ – 26-reporting-export

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Queue/worker export | ✅ | 8923ebe |
| 2 | Streaming fetchmany và write-only XLSX | ✅ | d70c3ca |
| 3 | Split file/zip/hash/storage | ✅ | |
| 4 | Download/history/cache/security | ⬜ | |

## Ghi chú bước 3
- Split: xoay part khi đủ ngưỡng (xoay lười — chỉ khi còn dòng để ghi, không tạo part rỗng cuối); đúng 1.000.000 → 1 part.
- >1 part → ZIP (parts + `_summary.txt`: report code, run, export, format, tổng dòng, số file, danh sách file) rồi xóa part gốc; FORMAT='ZIP', PART_COUNT=n; 1 part giữ FORMAT request.
- FILE_SIZE + FILE_HASH (sha256 đọc theo chunk) tính trên file cuối (zip hoặc file đơn).
- Test: 5 pass mới (T26-06 split 250→3 part, đúng ngưỡng→1 part; T26-07 zip + summary + part đọc lại đủ 100 dòng; T26-08 hash/size/ROW_COUNT/FORMAT cho cả ZIP và file đơn). Tổng 17 pass (bước 1–3). Lint sạch, typecheck 21 lỗi = baseline.

## Ghi chú bước 2
- `_XlsxWriter` ghi theo type: STRING → write_string + num_format "@" (giữ leading zero), NUMBER → write_number + num_format từ FORMAT_MASK, DATE/DATETIME → write_datetime + mask (mặc định YYYY-MM-DD / YYYY-MM-DD HH:mm:ss); alignment từ metadata; WIDTH (px) đổi sang đơn vị ký tự Excel bằng /7.
- CSV: BOM UTF-8 + utf-8 (decode kiểm tra bằng utf-8-sig).
- Test: 5 pass mới (T26-02 tracemalloc 10k→100k peak < 3x; fetchmany đúng 5000/batch, fetchall chỉ 1 lần cho kiểm tra read-only; XLSX đọc lại bằng openpyxl; leading zero "00123" vẫn str; CSV BOM + tiếng Việt). Tổng 12 pass (bước 1+2). Lint sạch, typecheck 21 lỗi = baseline.
- Bẫy mock 2: fixture `run_env`/`operator_ctx` phải import trực tiếp vào file test mới (pytest chỉ đăng ký fixture trong module import nó).

## Ghi chú bước 1
- Migration 0005 thêm LOCKED_BY/LOCKED_AT/HEARTBEAT_AT vào RECON_RPT_EXPORT; metadata.py khớp; test migration lên/xuống.
- `report_run.py`: `_load_version_detail`/`_build_run_query`/`_stable_order_by`/`_map_oracle_error` đổi thành public (dùng chung cho export); `load_version_detail` mở rộng thêm label/format_mask/alignment/width/is_total cho cột.
- `claim_next_queued_export` trong dialect (SQLite RETURNING / Oracle SKIP LOCKED), bỏ qua user đã có ≥2 RUNNING (Q4).
- Service `report_export.py`: `request_export` (dedupe QUEUED/RUNNING/DONE + cache file còn tồn tại), `execute_export` (CSV + XLSX cơ bản, stream fetchmany).
- Worker `worker/export_runner.py` (claim/heartbeat 3s/reset stale 300s/poll); `worker/__main__.py` chạy cả 2 worker cùng tiến trình (Q3).
- Test: 8 pass (queue + migration). Lint sạch, typecheck 21 lỗi = baseline.
- Bẫy mock: MagicMock `fetchmany` trả cùng list mãi → vòng stream vô hạn, lấp đầy /tmp (tmpfs 512M) — mock stream phải đặt `fetchmany.side_effect = [rows, []]`. Đã dọn /tmp/pytest-of-root cũ.
