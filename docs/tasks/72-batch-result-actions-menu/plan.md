# Task 72 — Plan: nút tải + cột Thao tác thành menu

## Chẩn đoán (đã đọc code)

- **Cả 2 nút tải ĐÃ có code** ở tầng callback + service:
  - "Tải tất cả": callback `_download_zip`
    (`batch_run_result.py:613`) → service `build_zip`
    (`batch_run.py:2530`, đầy đủ: cache theo hash danh sách run,
    file `00_TONG_HOP_<YYYYMM>.xlsx` + file riêng từng mục DONE qua
    `export_run`, lưu `ZIP_PATH`/`ZIP_RUN_SET_HASH`) → `dcc.send_file`.
  - "Tải file" từng dòng: callback `_download_one`
    (`batch_run_result.py:589`, pattern-matching
    `brr-download-btn`) → `export_run(ctx, run_id)` → `dcc.send_file`.
  - Vì vậy nghi ngờ "chưa code" của user cần kiểm chứng live: có thể
    nút đã nối dây nhưng bấm không tải được (lỗi service lặng, file
    không sinh ra, hoặc download không về tới trình duyệt).
- **Cột Thao tác hiện tại**: 3 nút xếp chồng trong ô
  (`render_matrix_table`, dòng ~233–256): "Mở run" (Anchor
  `/runs/<id>`), "Tải file" (`brr-download-btn`), "Chạy lại"
  (`brr-rerun-btn`, chỉ khi DONE/FAILED/NOT_RUN).

## Thiết kế

- Cột Thao tác → 1 nút (vd "⋯" / "Thao tác") mở `dmc.Menu` với 3 mục:
  Mở run / Tải file / Chạy lại. Các mục menu giữ NGUYÊN id hiện tại
  (`brr-download-btn`, `brr-rerun-btn` dạng pattern-matching;
  Mở run giữ Anchor href) để 2 callback tải/chạy-lại không đổi.
- Nếu check live phát hiện nút tải bấm không ra file → sửa đúng chỗ
  lỗi (service hoặc callback), không viết lại phần đã chạy.

## Các bước

1. Check live trước (port 8122): mở trang kết quả có 2 mục DONE,
   bấm "Tải tất cả" → xác nhận file .zip tải về (đúng tên, chứa tổng
   hợp + 2 file riêng); bấm "Tải file" từng dòng → xác nhận file
   .xlsx tải về. Ghi rõ nút nào hỏng (nếu có) và lỗi gì.
2. Test đỏ trước cho menu (render: mỗi dòng có 1 menu với đủ 3 mục,
   id giữ nguyên; callback tải/chạy-lại vẫn nối dây).
3. Đổi cột Thao tác sang `dmc.Menu` (+ sửa lỗi tải nếu bước 1 tìm ra).
4. Tests liên quan + check live lại (menu mở được, từng mục chạy đúng:
   Tải file tải về, Chạy lại chạy lại mục, Mở run chuyển trang) + quét
   console error + pageerror + typecheck/ruff + full suite (parent
   chạy chung sau task 71) → commit → patch (áp sau patch 71, không
   db-migrate, chỉ khởi động lại app).
