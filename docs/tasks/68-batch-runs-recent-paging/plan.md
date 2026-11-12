# Task 68 — Plan: phân trang card "Lần chạy gần đây của bộ"

## Bối cảnh

- Trang `/batch-runs` (landing, không `run_id`): `layout()` trong
  `app/ui/pages/batch_run_wizard.py` gọi `list_batch_runs(ctx, page=1,
  page_size=5)` rồi vẽ `render_recent_runs_card(recent)`.
- Mẫu có sẵn: task 59 (`report_admin.py`: Select cỡ trang 10/20/50/100,
  mặc định 10, đổi cỡ trang → về trang 1, giá trị ngoài danh sách → mặc
  định 10) và task 60 (`dashboard.py`: Pagination đặt NGOÀI vùng vẽ lại,
  callback chỉ trả dòng bảng + showing text + Pagination `total`, không
  `dcc.Loading`).

## Các bước

1. **UI** (`app/ui/pages/batch_run_wizard.py`):
   - Hằng số `BRW_RECENT_PAGE_SIZE_OPTIONS = [10, 20, 50, 100]`,
     `DEFAULT_BRW_RECENT_PAGE_SIZE = 10`.
   - `render_recent_runs_card(runs, total=None, page=1, page_size=10)`:
     thêm footer phân trang ở ngoài vùng thân bảng — dòng
     "Hiển thị x – y trong tổng số N lần chạy" (`id="brw-recent-showing"`),
     Select cỡ trang (`id="brw-recent-page-size"`, `w=130`, size xs),
     `dmc.Pagination` (`id="brw-recent-pagination"`, `total`, `value=page`,
     size xs). Thân bảng giữ `dmc.ScrollArea` tĩnh, bên trong là
     `html.Div(id="brw-recent-card-body")` chứa `render_recent_runs(runs)`.
     `total=None` thì dùng `len(runs)`; kẹp `page` vào khoảng hợp lệ.
   - `layout()` nhánh landing: gọi `list_batch_runs(ctx, page=1,
     page_size=DEFAULT_BRW_RECENT_PAGE_SIZE)` (đổi từ 5 → 10) và truyền
     `total` vào card.
   - Callback mới `_update_recent_runs`: Outputs = body children, showing
     text, Pagination `total`, Pagination `value`; Inputs = Pagination
     `value` + page-size Select `value`; `prevent_initial_call=True`.
     Lấy trang từ service `list_batch_runs` (server-side, không đổi
     service); đổi cỡ trang (trigger không phải Pagination) → trang 1;
     cỡ trang ngoài danh sách/không parse được → mặc định 10; trang vượt
     quá tổng số trang (sau khi tổng giảm) → gọi lại với trang cuối;
     service lỗi → thân bảng hiện `alert_box`, các output còn lại
     `no_update`; chưa đăng nhập → `no_update` toàn bộ.
2. **Tests-first** (`tests/unit/test_batch_recent_paging68.py` mới):
   render card trang 1/2 đúng dòng + showing text + Pagination total/value;
   rỗng; kẹp trang vượt; callback đổi cỡ trang về trang 1 + giá trị lạ về
   mặc định 10; callback bấm trang 2 lấy đúng trang từ service (mock
   `list_batch_runs`).
3. **Check live mới** `~/workspace/check-68-batch-recent-paging.py`
   (port 8117, DB/storage riêng `/run/pytest-tmp/check68.*`, seed 1 bộ +
   12 lần chạy): trang 1 hiện 10 dòng đầu, sang trang 2 đúng 2 dòng còn
   lại, đổi cỡ trang 20 → về trang 1 hiện đủ 12 dòng, không lỗi JS (quét
   CẢ console error VÀ pageerror, bỏ qua `ERR_TUNNEL_CONNECTION_FAILED`).
4. **Parent**: review diff → chạy lại targeted tests → chạy lại check live
   → typecheck + ruff → full suite → commit 1 commit
   `68-batch-runs-recent-paging: thêm phân trang card lần chạy gần đây của bộ`
   → export patch → verify `git am` sạch trên worktree ở `70674b5` →
   cập nhật MEMORY.md → giao patch (áp sau patch 66-followup, KHÔNG cần
   db-migrate, chỉ khởi động lại app).

## Quyết định

- D1: phân trang server-side qua `list_batch_runs` đã có — không đổi
  service (card hiện chỉ lấy 5 dòng đầu, không có list đầy đủ để cắt ở UI).
- D2: mặc định 10 dòng/trang, options 10/20/50/100, đổi cỡ trang → trang 1,
  giá trị lạ → mặc định 10 (mẫu task 59).
- D3: Pagination + Select ở footer tĩnh ngoài vùng thân bảng; callback chỉ
  trả thân bảng + showing + Pagination `total`/`value` (mẫu task 60).
- D4: KHÔNG import helper phân trang từ `dashboard.py` (các module trang
  Dash không được import lẫn nhau — bài học task 66); nhân bản phần tính
  toán nhỏ (tổng số trang + dòng hiển thị) ngay trong
  `batch_run_wizard.py`.
- D5: danh từ trong dòng hiển thị là "lần chạy":
  "Hiển thị 1 – 10 trong tổng số 12 lần chạy".
