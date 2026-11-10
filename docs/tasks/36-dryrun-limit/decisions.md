# Decisions — 36-dryrun-limit

- **Q0 (2026-11-10):** Gốc chậm là COUNT toàn bộ. Bỏ COUNT, chỉ chạy
  1 query lấy trang xem trước.
- **Q1 (2026-11-10):** Không còn tổng: `total=None`; audit ghi
  `preview_rows`.
- **Q2 (2026-11-10):** Lấy `min(10, preview_max_rows)` dòng.
- **Q3 (2026-11-10):** Bỏ cả ba: alert cam bước 5, banner "Dry-run OK",
  banner "Xem trước ACTIVE". Toast vẫn báo thành công.
