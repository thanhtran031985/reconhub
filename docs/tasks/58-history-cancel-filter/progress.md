# Task 58 — progress

## Bước 1 — Docs + nhánh (xong, 11/11/2026)
- Nhánh `feat/58-history-cancel-filter` từ `4cdafb3` (task 57).
- User duyệt plan 3 mục ("làm đi bạn" 17:46) sau khi xem phân tích
  nguyên nhân gốc (chốt DONE không điều kiện ghi đè CANCELLED;
  checkpoint hủy mỗi 10 batch; nút flex trái; service đã có `status`).

## Bước 2 — Fix 1/2/3 (xong)
- Fix 1 (`app/services/report_export.py`): checkpoint hủy mỗi batch;
  kiểm tra hủy lần nữa trước khi chốt; UPDATE chốt DONE và
  `_fail_export` chỉ áp dụng khi export còn QUEUED/RUNNING
  (QUEUED vì gọi trực tiếp vẫn có thể là QUEUED — phát hiện khi rà
  caller: chỉ worker gọi sau claim, nhưng nhiều test + đường gọi
  đồng bộ cũ gọi trực tiếp trên export QUEUED).
- Fix 2 (`app/ui/assets/dashAgGridFunctions.js`): 4 vị trí cố định,
  nút không phù hợp vẽ ẩn cùng kích thước (visibility:hidden +
  disabled). Lưu ý: nhãn "Thử lại" rộng hơn "Hủy" nên vị trí 1 hơi
  rộng hơn ở dòng FAILED — chỉ khác giữa các dòng, không nhảy khi bấm.
- Fix 3 (`app/ui/pages/report_runs.py`): Select lọc trạng thái +
  `aria-label="Lọc theo trạng thái"`, `_filters_to_kwargs` thêm
  `status`, callback thêm Output/Input + reset ở "Xóa lọc". Cập nhật
  test cũ: `test_history_refresh53.py` (12 output, fingerprint ở
  index 10), `test_console_cleanup45.py` (thêm status vào lời gọi
  vị trí + assert reset về "all").

## Bước 3 — Test (xong)
- Mới `tests/unit/test_history_cancel_filter58.py` (6 test): hủy ở
  batch đầu → CANCELLED + xóa file; hủy đúng lúc chốt (pct=90) →
  vẫn CANCELLED, run không bị chốt DONE; `_fail_export` không ghi đè
  CANCELLED; `_filters_to_kwargs` status; lọc service; JS có nút giữ
  chỗ. Typecheck + ruff sạch, `node --check` JS OK.
- Playwright `~/workspace/check-58.py` 14/14: hủy RUNNING →
  CANCELLED (transitions RUNNING→CANCELLED, không qua DONE), file dở
  bị xóa, export chờ được nhận ngay; x nút Xuất lại/Chạy lại không
  đổi sau khi Xóa (1207.625 / 1280.078); lọc Lỗi/Đang chờ/Tất cả +
  "Xóa lọc" reset; /settings canh giữa (header/card/nút cùng tâm
  820.0 — tâm nội dung sau sidebar); không lỗi JS.
- Bài học check: check-58 dùng DB/storage riêng
  (/run/pytest-tmp/check58.db) vì check-59 chạy song song cùng
  /tmp/check39.db; seed() gọi service qua get_recon_engine() (đọc
  env) nên phải set cả env; nút giữ chỗ mang text nên chờ nút theo
  text sẽ bắt nhầm placeholder — chờ nút `:visible`.

## Bước 4 — /settings canh giữa (xong, subagent)
- Chỉ `app/ui/pages/settings.py` (+20/-5): Box ngoài
  `alignItems: center`, header `width: fit-content`, 2 card `w=100%`
  (giữ maw=640), Group nút `justify=center` + `w=100%` + maw=640,
  alert cùng chiều rộng cột. Ruff + import OK; kiểm chứng live
  trong check-58 (58-4). Gộp vào patch 58 (mục 4).
