# Task 52 — plan (chờ duyệt, chưa code)

## Hiểu đúng vấn đề
- Hiện tại bấm "Xuất Excel" ở viewer là phải ngồi chờ: trình duyệt poll
  mỗi 2s, tới DONE mới tự tải file. Dữ liệu ~1.000.000 dòng thì viết
  file mất nhiều phút; đóng tab/rớt mạng là mất dấu (Lịch sử hiện chỉ
  hiện link tải khi DONE, đang chạy thì hiện "—").
- Engine kiểu EBS đã có sẵn: bảng `RECON_RPT_EXPORT` (QUEUED → RUNNING
  → DONE / FAILED / CANCELLED, % thật, file, số dòng), `request_export`
  (chống trùng cùng run+format), worker export (nhận 1 export QUEUED,
  chạy tuần tự, heartbeat, tự reset export kẹt), Lịch sử báo cáo đã có
  link tải khi DONE + kiểm quyền owner/ADMIN + audit, đã có sẵn
  retry/cancel export. Hàng đợi đã FIFO theo CREATED_AT, tối đa 2
  export RUNNING mỗi user.
- `execute_export` đọc kết quả ĐÃ LƯU của run (không query lại dữ liệu
  live) → xuất lại cùng run sẽ ra file cũ. Vì vậy "xuất lại" phải sinh
  run mới (chạy lại báo cáo với cùng tham số) rồi mới xuất.

## Các bước
1. Docs + nhánh `feat/52-export-background` từ `973a431` (xong).
2. Viewer — chế độ xuất: thêm Select "Xuất ngay / Chạy ngầm" cạnh nút
   "Xuất Excel" (mặc định "Xuất ngay", giữ nguyên hành vi cũ). Chọn
   "Chạy ngầm": gọi `request_export` như cũ → hiện thông báo "Đã đưa
   vào hàng đợi chạy ngầm — xem tiến trình và tải file trong Lịch sử
   báo cáo" kèm link tới /report-runs → không bật poll, không tự tải.
   Nếu `request_export` trả về export đang QUEUED/RUNNING thì báo đang
   chạy + %; nếu đã DONE sẵn thì hiện link tải file đó.
3. Lịch sử báo cáo (/report-runs) — cột File hiện trạng thái export mới
   nhất theo run: QUEUED "Đang chờ", RUNNING "Đang xuất NN%",
   DONE icon tải (như cũ), FAILED "Lỗi" + nút "Thử lại"
   (`retry_export`), CANCELLED "Đã hủy"; nút "Hủy" cho QUEUED/RUNNING
   (`cancel_export`). Bảng tự làm mới mỗi 10s khi còn export chưa xong
   (dcc.Interval) + nút "Làm mới".
4. "Xuất lại" — service mới `rerun_and_export(ctx, run_id)`: tạo run
   mới từ run gốc (cùng report/template/tham số, chủ sở hữu là user bấm)
   rồi chạy ngay (execute_report_run, đồng bộ như viewer) → DONE thì
   gọi `request_export` (định dạng theo export mới nhất của run gốc,
   mặc định XLSX). Run mới + export mới hiện trong Lịch sử. Không cần
   cột cờ hay migration: run của viewer vốn chạy đồng bộ trong web
   process (chỉ count + 1 trang), nên tạo → chạy → xuất làm liền trong
   một lần gọi; version theo ACTIVE như "Chạy lại" (task 43).
5. Dọn file export — setting trong `RECON_APP_SETTING` (không cần
   migration cho setting): `EXPORT_RETENTION_MODE` (manual|scheduler,
   mặc định manual), `EXPORT_RETENTION_DAYS` (mặc định 30). Trang "Cài
   đặt hệ thống" mới, chỉ ADMIN (khai báo menu theo luật task 19), gồm
   2 trường này + nút Lưu (service get/set setting, ADMIN-only). Worker
   export sweep định kỳ (tối đa 1 lần/giờ) khi mode=scheduler: xóa file
   + dòng export DONE/FAILED/CANCELLED quá N ngày (không động tới
   QUEUED/RUNNING, không xóa run), ghi audit. Chế độ manual: không tự
   xóa + nút "Xóa" (ADMIN) trên từng export DONE/FAILED trong Lịch sử
   (service `delete_export` mới: xóa file + dòng + audit).
6. Typecheck + lint + full suite + Playwright (chạy ngầm → Lịch sử hiện
   "Đang chờ" → worker xong → icon tải xuất hiện; Xuất lại sinh run
   mới + export mới; sweep scheduler xóa file quá hạn) + xuất patch
   (không kèm dashboard.html). Không cần db-migrate (không migration).
   Áp patch xong khởi động lại app và worker.

## Ngoài phạm vi
- Không thông báo chủ động khi export xong (user tự vào lịch sử xem).
- Không tăng song song worker (xếp hàng FIFO như hiện tại).
- Không dọn run, chỉ dọn file + dòng export.
