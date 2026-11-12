# Task 67 — Decisions

## Chẩn đoán (parent, 12/11/2026 — đã xác minh trong code)

- **A — upload lại báo "đã tồn tại"**: `ignore_file` (service) chỉ đặt
  `MATCH_STATE="IGNORED"` trên dòng `RECON_BATCH_RUN_FILE`, không xóa dòng.
  `_collect_uploads` lấy tập tên trùng từ MỌI dòng của run, không lọc
  `IGNORED`. Cả 2 nút ở bước 2 — "Bỏ qua" (`brw-ignore-btn`) và × gỡ file
  (`brw-remove-file-btn`) — đều đi qua `ignore_file` nên đều gặp lỗi này.
- **B — bấm "Tiếp tục" hiện "Đã đặt lại tham số về mặc định"**: callback
  `_reset_param` (Input pattern-matching `brw-param-reset-btn` ALL) không
  kiểm tra `n_clicks` — callback duy nhất trong wizard thiếu guard này (3
  callback anh em `_assign_file`, `_ignore_file`, `_toggle_skip` đều có
  `not any(c for c in (_n or []) if c)`). Sang bước 3, layout chèn các nút
  reset → Dash kích hoạt callback dù có `prevent_initial_call=True` (hành vi
  đã biết từ task 52) → handler chạy thật: đặt lại override tham số (mất dữ
  liệu user đã sửa) + hiện thông báo. Đây không chỉ là message sai mà là
  reset thật.
- **C1 — kiểm tra trước OK mà thực thi lỗi**: `_precheck_one_item` chỉ kiểm
  template Active, tham số resolve được, đọc/gộp file Excel, control total,
  dòng ngoài kỳ, dòng không hợp lệ, kết nối DS (chỉ mở connection). Nó KHÔNG
  build và KHÔNG chạy câu SQL DB → lỗi phía SQL/Oracle không thể bị precheck
  bắt. Lỗi thật của run #1033 đang nằm trong `RECON_RUN.ERROR_MSG` (executor
  ghi ở nhánh `except`), chỉ đọc được bằng SQL trực tiếp — UI không hiện ở
  đâu cả: `sync_batch_status` chỉ đồng bộ STATUS từ run con, không copy
  `ERROR_MSG` (mục lỗi chỉ hiện chữ chung "Lỗi khi chạy" ở bước 5); trang
  `/runs/<id>` không hề hiển thị `ERROR_MSG` (grep `run_result.py` = 0).
- **C2 — run #1033 không có SQL lưu**: `SOURCE_SQL` nằm ở
  `RECON_RUN_SUMMARY`, chỉ ghi khi chạy THÀNH CÔNG (executor ghi summary ở
  nhánh thành công; `summary.py` nhận `source_sql` từ `pipeline.py` sau
  `build_source_sql`). Nhánh lỗi xóa dòng summary dở dang và không lưu SQL →
  trang run hiện "-- Không có câu lệnh SQL nguồn...". Trả lời câu hỏi của
  user: câu SQL CÓ được build và truyền khi chạy (pipeline build rồi mới
  chạy), nhưng không được lưu lại khi thất bại nên trang run không thấy.
- **D — switch chạy ngầm**: `start()` chỉ tạo run con QUEUED + ghi
  `RECON_RUN_QUEUE` rồi trả về ngay; worker recon chạy thật; bước 5 poll
  tiến độ mỗi 2s. Chạy ngầm không cần cơ chế hàng đợi mới.

## Quyết định

- D1: file đã bỏ (IGNORED) được coi như chưa tồn tại khi kiểm trùng; giữ dòng
  IGNORED làm audit, không xóa cứng. **Bổ sung khi implement (12/11/2026)**:
  bảng `RECON_BATCH_RUN_FILE` có UNIQUE `(BATCH_RUN_ID, ORIGINAL_NAME)` nên
  không thể INSERT dòng mới cùng tên — upload lại TÁI DÙNG dòng IGNORED cũ
  bằng UPDATE tại chỗ (FILE_ID mới, MATCH_STATE ghép lại, UPDATED_BY/AT mới;
  lịch sử bỏ file vẫn còn trong audit log). Dòng REPLACED không tái dùng:
  thay file cùng tên vẫn bị bỏ qua như trùng (hành vi cũ, vấn đề riêng
  ngoài phạm vi task này).
- D2: guard `n_clicks` cho `_reset_param` theo mẫu 3 callback anh em; audit
  các callback ALL khác trong wizard.
- D3: lỗi chạy lấy từ `RECON_RUN.ERROR_MSG` của run con; `sync_batch_status`
  copy sang mục; hiện ở card lỗi bước 5 + trang /runs/<id>.
- D4: lưu `SOURCE_SQL` ngay sau khi build, nhánh lỗi giữ lại dòng summary tối
  thiểu chứa SQL — không migration. **Lệch khi implement (12/11/2026)**:
  plan nói ghi từ `pipeline.py` ngay sau `build_source_sql`, nhưng
  `run_pipeline` là hàm engine thuần, không biết run_id/engine — ghi
  `RECON_RUN_SUMMARY` từ đó phá tầng (AGENTS.md: nghiệp vụ ở services).
  Đổi thành: executor tách helper `resolve_profile` từ pipeline, build SQL
  best-effort trước khi gọi `run_pipeline` và ghi dòng summary tối thiểu
  ngay (chỉ khi `persist`), nhánh lỗi ghi lại sau khi dọn dẹp. Cùng kết
  quả, không đổi engine.
- D5: precheck probe SQL giới hạn 1 dòng trên Oracle (1 query nhẹ/mục).
  **Bổ sung khi implement (12/11/2026)**: probe dùng
  `open_source_connection` của module `batch_run` (Oracle, parse-only qua
  `describe_sql`) + `engine.raw_connection()` cho SQLite (bind thay bằng
  NULL), thay vì `open_checked_connection` (đi qua `source_conn` thật nên
  test cũ không mock được; probe cũng không cần assertion read-only vì chỉ
  parse/describe). Probe bỏ qua khi Oracle không kết nối được (tránh chờ
  timeout mỗi mục); riêng SQLite vẫn probe vì bước kiểm tra kết nối dùng
  helper chỉ hỗ trợ Oracle. Fixture `FakeConn` ở test_batch_precheck.py
  được bổ sung cursor `parse()` để probe chạy trong test cũ.
- D6: switch chạy ngầm chỉ đổi UX sau `start()` (hàng đợi + worker đã có
  sẵn); chạy ngầm → chuyển sang /batch-runs. **Bổ sung khi implement
  (12/11/2026)**: Switch đặt trong `brw-footer-warn-wrapper` cạnh checkbox
  "Chạy cả template có cảnh báo" (cùng hiện ở bước 5 DRAFT); cả `_navigate`
  và `_confirm_prod_start` đều đọc switch (xác nhận PROD cũng tôn trọng
  chế độ chạy ngầm). Thông báo chạy ngầm: "Đã bắt đầu chạy ngầm. Theo dõi
  tiến độ ở trang Lần chạy bộ." (mẫu `_save_draft`: notify + redirect).
- D7 (audit bước B, 12/11/2026): cùng lỗi thiếu guard như `_reset_param`
  còn ở `_replace_item_files` — khi layout bước 2 chèn các ô thay file,
  `contents` là list toàn None (truthy) nên callback chạy và hiện cảnh báo
  "Không có file nào." giả. Đã sửa: trả `no_update` khi file của ô được
  kích hoạt có `target_contents` None.
