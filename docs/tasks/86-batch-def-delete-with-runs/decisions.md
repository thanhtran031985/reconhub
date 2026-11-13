# Decisions — Task 86

- D1: không chỉ xóa dòng chặn — phải xóa xếp tầng đúng thứ tự FK, nếu không delete sẽ lỗi IntegrityError thay cho message CONFLICT cũ.
- D2: các run đối soát con (RECON_RUN) được GIỮ LẠI trong Lịch sử, chỉ NULL liên kết batch (BATCH_RUN_ID/BATCH_RUN_ITEM_ID) — xóa cả run đối soát sẽ xóa luôn kết quả đối soát, không phải điều user yêu cầu.
- D3: chặn duy nhất còn lại là lần chạy bộ đang RUNNING (worker đang chạy mà xóa thì lỗi giữa chừng); các trạng thái khác (DONE/PARTIAL/CANCELLED/DRAFT) xóa được.
- D4: audit DELETE_BATCH_DEF giữ nguyên, kèm số lần chạy đã xóa.
- D5 (ZIP_PATH / file trên disk): file zip của lần chạy bộ nằm ở `storage/batch/<run_id>/` (do `build_zip` ghi, đường dẫn lưu ở RECON_BATCH_RUN.ZIP_PATH). Khi xóa bộ, sau khi transaction DB commit thì dọn kèm các thư mục đó bằng `shutil.rmtree(ignore_errors=True)` (helper `_remove_batch_run_storage`, theo tiền lệ `temp_data.py` dọn `storage/runs/<run_id>`); dọn disk best-effort, không chặn xóa nếu lỗi. File gốc đã tải lên (RECON_FILE, `storage/files/`) là dữ liệu dùng chung nên KHÔNG đụng tới. ZIP_PATH của lần chạy đã xóa không còn ý nghĩa vì bản ghi RECON_BATCH_RUN đã bị xóa cùng.
