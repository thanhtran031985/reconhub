# 36-dryrun-limit — Dry-run chỉ fetch 10 dòng, bỏ alert/info bước 5

- Ngày tạo: 2026-11-10
- Giai đoạn: GĐ3 (fix, theo mẫu task 33 — không thêm dòng dashboard)
- Phụ thuộc: 25, 33, 34
- Nhánh git: feat/36-dryrun-limit (rẽ từ `dbcbf17`, đỉnh `feat/35-report-aggrid`)

## Vấn đề (người dùng báo 10/11/2026, kèm ảnh bước 5)

Dry-run trên app thật: "Tổng 5509 dòng · 10312 ms" — chạy rất chậm.

Gốc: `dry_run_version` gọi `_execute_count_page`, chạy HAI query —
COUNT toàn bộ (`SELECT COUNT(*) FROM (<SQL>)`, quét hết) rồi mới lấy
1 trang (tối đa 100 dòng). COUNT là phần "load hết" gây chậm trên Oracle.

## Phạm vi

- Service: dry-run chỉ chạy 1 query lấy tối đa 10 dòng (`_execute_preview`
  mới), KHÔNG chạy COUNT nữa; `total` trả về `None` (không còn biết tổng);
  audit ghi `preview_rows` thay cho `total`. `get_report_page` (xem báo
  cáo, cần tổng để phân trang) giữ nguyên `_execute_count_page`.
- Page bước 5: bỏ alert cam ("Preview dùng tối đa 100 dòng..."), bỏ banner
  "Dry-run OK" / "Xem trước ACTIVE", bỏ dòng info "Tổng ... dòng · ... ms ·
  hiển thị tối đa ... dòng mẫu". Chỉ còn form tham số + nút "Chạy dry-run"
  + bảng kết quả 10 dòng. Toast báo thành công dạng "xem trước N dòng
  (... ms)" thay cho "tổng ... dòng".
- Không đổi: điều kiện vào DRY_RUN_OK / xem trước ACTIVE (task 34), nút
  kích hoạt bước 6, preview_max_rows của version (chỉ lấy
  `min(10, preview_max_rows)`).
