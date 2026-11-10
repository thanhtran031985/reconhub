# 34-version-reopen — Mở lại version ACTIVE/DRY_RUN_OK về DRAFT + dry-run preview trên ACTIVE

- Ngày tạo: 2026-11-10
- Giai đoạn: GĐ3
- Phụ thuộc: 21, 25, 33
- Nhánh git: feat/34-version-reopen (rẽ từ `ac8386b`, đỉnh `feat/33-report-col-fix`)

## Mục tiêu

1. Cho phép mở lại version đã kích hoạt (ACTIVE) hoặc đã dry-run xong
   (DRY_RUN_OK) về DRAFT để sửa lại bảng cũ (cột, tham số, SQL), thay vì
   bắt buộc clone version mới.
2. Cho phép dry-run version ACTIVE dạng xem trước thuần túy (không đổi
   trạng thái), để xem dữ liệu của version đang chạy mà không phải gỡ
   kích hoạt.

## Vấn đề (phát hiện 10/11/2026, đã phân tích, chưa code)

Vòng đời version hiện tại là DRAFT → DRY_RUN_OK → ACTIVE, và ACTIVE là
trạng thái cuối: không sửa được cột (chỉ DRAFT mới sửa, `_load_version_draft`),
không dry-run được (`dry_run_version` chặn, báo "Chỉ dry-run được version
DRAFT hoặc chưa kích hoạt."), không lưu trữ được (`archive_version` chặn
ACTIVE). Muốn sửa bảng cũ chỉ còn cách clone sang DRAFT mới.

Hai điểm cụ thể:

1. `dry_run_version` (`app/services/report_run.py:540`): chỉ cho DRAFT và
   DRY_RUN_OK. Dry-run bản chất là xem trước chỉ đọc (chạy query, trả rows),
   nên với version ACTIVE việc chặn hẳn là quá tay — điều cần tránh chỉ là
   lật trạng thái ACTIVE → DRY_RUN_OK (sẽ gỡ kích hoạt version đang chạy).
   Nút "Chạy dry-run" ở bước 5 vẫn hiện với version ACTIVE, bấm vào chỉ
   nhận alert lỗi.
2. Chưa có service nào đưa version về DRAFT. Bước 6 với version ACTIVE chỉ
   hiện màn hình "Đã kích hoạt", không có đường nào mở lại để sửa.

## Phạm vi

- Service `reopen_version` mới trong `app/services/report_template.py`.
- `dry_run_version`: cho thêm ACTIVE, không đổi trạng thái khi preview.
- UI bước 6: nút "Mở lại để sửa" + modal xác nhận (màn hình ACTIVE và màn
  hình DRY_RUN_OK), callback cập nhật state về DRAFT và nhảy sang bước 4.
- Page dùng trạng thái version do service dry-run trả về thay vì gán cứng
  `DRY_RUN_OK` (`handle_dry_run`, `handle_dryrun_click`).
- Không đổi: vòng kích hoạt (DRY_RUN_OK → ACTIVE), clone, lưu trữ, các
  cổng khóa sửa cột (chỉ DRAFT).
