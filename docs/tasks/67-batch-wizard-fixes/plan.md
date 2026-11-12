# Task 67 — Plan: sửa lỗi wizard chạy bộ + switch chạy ngay/chạy ngầm

## Chẩn đoán (đã xác minh trong code, xem decisions.md)

- **A**: `ignore_file` chỉ đặt `MATCH_STATE="IGNORED"`, không xóa dòng
  `RECON_BATCH_RUN_FILE`; `_collect_uploads` lấy tập tên trùng từ MỌI dòng
  của run, không lọc `IGNORED` → upload lại cùng tên bị coi là trùng.
- **B**: callback `_reset_param` (Input pattern-matching
  `brw-param-reset-btn` ALL) là callback duy nhất trong wizard KHÔNG có
  guard kiểm tra `n_clicks` (3 callback anh em `_assign_file`,
  `_ignore_file`, `_toggle_skip` đều có). Sang bước 3, layout chèn các nút
  reset → Dash kích hoạt callback dù có `prevent_initial_call=True` (hành vi
  đã biết từ task 52) → đặt lại override thật + hiện thông báo.
- **C**: `_precheck_one_item` chỉ kiểm template/tham số/file/control total/
  dòng ngoài kỳ/dòng không hợp lệ/kết nối DS — KHÔNG build, KHÔNG chạy câu
  SQL. `sync_batch_status` chỉ đồng bộ STATUS từ run con, KHÔNG copy
  `ERROR_MSG` → mục lỗi chỉ hiện chữ chung "Lỗi khi chạy"; trang /runs/<id>
  cũng không hiện `ERROR_MSG`. `SOURCE_SQL` chỉ ghi vào `RECON_RUN_SUMMARY`
  khi chạy THÀNH CÔNG; nhánh lỗi xóa dòng summary và không lưu SQL.
- **D**: `start()` chỉ tạo run con QUEUED + ghi `RECON_RUN_QUEUE` rồi trả về
  ngay; worker recon chạy thật; bước 5 poll tiến độ mỗi 2s. Chạy ngầm không
  cần cơ chế mới, chỉ đổi UX sau `start()`.

## Các bước

1. **A — trùng tên khi upload lại** (`app/services/batch_run.py`,
   `_collect_uploads`): loại các dòng `MATCH_STATE="IGNORED"` khỏi
   `existing_names` / `seen_sha` / `current_count` (coi như chưa từng tải).
   Upload lại TÁI DÙNG dòng IGNORED cũ bằng UPDATE tại chỗ (UNIQUE
   `(BATCH_RUN_ID, ORIGINAL_NAME)` không cho INSERT dòng mới cùng tên);
   dòng IGNORED cũ giữ lại làm audit (lịch sử bỏ file còn trong audit log).
   Test: bỏ file rồi upload lại cùng tên → được nhận, không còn "đã tồn tại".
2. **B — reset tham số tự kích hoạt** (`app/ui/pages/batch_run_wizard.py`,
   `_reset_param`): thêm guard `not any(c for c in (_n or []) if c)` như 3
   callback anh em — chỉ chạy khi nút được bấm thật. Đồng thời rà soát các
   callback ALL khác trong wizard (`_replace_item_files` và các callback
   pattern-matching còn lại) xem có cùng lỗi thiếu guard không; sửa nếu có.
   Test: sang bước 3 không còn thông báo đặt lại, override tham số còn nguyên.
3. **C1 — lỗi thật lên UI**:
   - `sync_batch_status`: copy `ERROR_MSG` (kèm `ERROR_CODE` nếu item có chỗ
     chứa, nếu không thì chỉ message) từ run con (`RECON_RUN`) sang
     `RECON_BATCH_RUN_ITEM.ERROR_MSG` khi đồng bộ trạng thái FAILED.
   - Bước 5 (`render_step5`): trong mỗi AccordionPanel của mục, thêm card lỗi
     bên cạnh/bên dưới câu SQL, chỉ hiện khi mục FAILED (lấy `error_msg` của
     mục — nay đã là lỗi thật, không còn chữ chung "Lỗi khi chạy").
   - Trang `/runs/<id>` (`run_result.py`): thêm card lỗi khi run FAILED
     (lấy `ERROR_MSG` đã có trong `get_run`).
4. **C2 — lưu câu SQL khi chạy lỗi**: trong `pipeline.py`, ngay sau khi
   `build_source_sql` build xong thì lưu `SOURCE_SQL` (ghi dòng
   `RECON_RUN_SUMMARY` tối thiểu) trước khi chạy query; nhánh `except` trong
   `execute_run` giữ lại dòng summary chỉ chứa `SOURCE_SQL` (+ `DURATION_MS`)
   thay vì xóa hết. Không migration mới. Test: run lỗi vẫn xem được SQL đã
   thử ở tab SQL.
5. **C3 — precheck probe SQL**: `_precheck_one_item` thêm bước kiểm SQL — build
   câu SQL của mục và chạy probe giới hạn 1 dòng trên Oracle (1 query nhẹ mỗi
   mục); lỗi probe → check mức `error` như các check khác, mục về ERROR và
   không chạy ở bước 5. (Chi phí: thêm 1 query Oracle nhẹ mỗi mục lúc kiểm
   tra trước.)
6. **D — switch chạy ngay/chạy ngầm** (`render_step5` + `_confirm_prod_start`):
   thêm Switch ở bước 5 gần nút chạy ("Chạy ngay" mặc định / "Chạy ngầm");
   `_confirm_prod_start` đọc giá trị switch làm State. Chạy ngay: hành vi
   hiện tại (ở lại bước 5, poll tiến độ). Chạy ngầm: sau `start()` thành công
   thì chuyển trang sang `/batch-runs` kèm thông báo thành công + link theo
   dõi (như report chạy ngầm task 52); interval poll của wizard dừng theo
   chuyển trang.
7. **Tests-first + kiểm chứng**: unit test cho từng sửa (A, B, C1, C2, C3, D)
   + check live mới `~/workspace/check-67-batch-wizard-fixes.py` (port 8118,
   DB/storage riêng `/run/pytest-tmp/check67.*`): upload → bỏ → upload lại
   cùng tên được nhận; sang bước 3 không reset tham số; chạy 1 mục lỗi SQL →
   card lỗi hiện đúng lỗi + tab SQL của run vẫn có SQL; probe precheck bắt
   lỗi SQL; switch chạy ngầm chuyển sang /batch-runs. Quét CẢ console error
   VÀ pageerror.
8. **Parent**: review diff → chạy lại targeted tests → chạy lại check live →
   typecheck + ruff → full suite → commit 1 commit
   `67-batch-wizard-fixes: ...` → export patch
   `~/workspace/reconhub-task67.patch` → verify `git am` sạch trên worktree
   ở commit task 68 → cập nhật MEMORY.md → giao patch (áp sau patch 68,
   KHÔNG cần db-migrate, chỉ khởi động lại app).

## Quyết định

- D1: file đã bỏ (IGNORED) được coi như chưa tồn tại khi kiểm trùng; giữ dòng
  IGNORED làm audit, không xóa cứng.
- D2: guard `n_clicks` cho `_reset_param` theo mẫu 3 callback anh em; audit
  các callback ALL khác trong wizard.
- D3: lỗi chạy lấy từ `RECON_RUN.ERROR_MSG` của run con; `sync_batch_status`
  copy sang mục; hiện ở card lỗi bước 5 + trang /runs/<id>.
- D4: lưu `SOURCE_SQL` ngay sau khi build, nhánh lỗi giữ lại dòng summary tối
  thiểu chứa SQL — không migration.
- D5: precheck probe SQL giới hạn 1 dòng trên Oracle (1 query nhẹ/mục).
- D6: switch chạy ngầm chỉ đổi UX sau `start()` (hàng đợi + worker đã có
  sẵn); chạy ngầm → chuyển sang /batch-runs.
