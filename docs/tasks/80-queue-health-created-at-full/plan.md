# Task 80 — Plan

## Thay đổi

1. `app/ui/pages/queue_health.py`: thêm `format_full_dt(iso_str)`
   ("%d/%m/%Y %H:%M:%S", None → "—", lỗi parse → giữ nguyên chuỗi);
   `_health_item_row` dùng `format_full_dt` cho ô "Tạo lúc"
   (thay `format_short_dt`). `format_short_dt` giữ nguyên cho dòng
   "Worker ... thấy lần cuối".
2. Test mới trong `tests/unit/test_queue_health66.py`:
   - `format_full_dt` (None → "—", đủ ngày/giờ/phút/giây,
     chuỗi lỗi giữ nguyên).
   - `_health_item_row` vẽ ô "Tạo lúc" dạng đầy đủ (render row
     rồi đọc text ô thứ 4).
3. Check live: mở rộng `~/workspace/probe-queue-health-layout.py`
   (seed 1 run QUEUED 10h trước) assert ô "Tạo lúc" khớp regex
   `^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$` ở cả 2 bảng.
4. Ruff + typecheck (file đổi) → full suite → commit → patch
   (áp sau patch 79, không cần db-migrate, chỉ khởi động lại app).

## Lưu ý

- Ô "Tạo lúc" đã có `whiteSpace: nowrap` + font mono (rh-code)
  nên chuỗi dài hơn không vỡ dòng; bảng có TableScrollContainer
  minWidth 520 nên tràn ngang (nếu có) cuộn trong bảng.
