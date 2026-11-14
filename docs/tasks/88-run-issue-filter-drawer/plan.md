# Plan — Task 88

Nhánh: `feat/88-run-issue-filter-drawer`, từ `bf2eafd` (task 87).
Không db-migrate. Chỉ khởi động lại app. Patch áp SAU patch 87.

## Bước 1 — Viết test đỏ trước (tests-first, theo AGENTS.md)

- Service (`tests/unit/test_run_service.py` hoặc file mới theo quy ước task 85/87):
  - `issue_status="OPEN"` → trả các dòng chưa có issue (STATUS NULL) + các dòng
    có issue OPEN, loại các dòng IN_PROGRESS/ACCEPTED/RESOLVED.
  - `issue_status="RESOLVED"` → chỉ các dòng có issue RESOLVED (hành vi cũ giữ nguyên).
  - `issue_status=None` → không lọc (hành vi cũ).
- Page (`tests/unit/test_page_run_result.py`):
  - Toolbar có Select `run-res-issue-status-select` với các lựa chọn "Tất cả",
    "Chưa đối soát" + các trạng thái lookup (kiểm tra cả đường fallback khi
    lookup rỗng/lỗi).
  - Callback `handle_filter_or_tab_change`: chọn giá trị khác "ALL" → gọi
    `get_run_rows` với `RunRowsFilter.issue_status` tương ứng và về trang 1.
  - Drawer: nút có nhãn "Chuyển xử lý chênh lệch", size xs, nằm trong Group tiêu
    đề (cùng hàng, bên phải); id `drawer-save-issue-btn` không đổi; callback lưu
    vẫn gọi `upsert_issue_for_row` như cũ (test hiện có cập nhật nhãn).
  - Drawer raw rows: với run có template map measure field → excel `_COL_17`
    và `DATA_JSON` dùng khóa `_COL_n`, Thành tiền hiển thị đúng số (không "—"),
    Số hóa đơn chỉ hiện số hóa đơn; với `DATA_JSON` dùng tên logic (mẫu DTP)
    vẫn hiển thị đúng; khi không lấy được config → fallback cũ.
- Chạy test mới, xác nhận ĐỎ trước khi sửa code.

## Bước 2 — (A) Filter "Đối soát & Xử lý" trên trang run

File: `app/ui/pages/run_result.py`, `app/services/run_service.py`.

1. Service: `get_run_rows` (`run_service.py:626-627`) — khi
   `filter.issue_status == "OPEN"` thì điều kiện là
   `STATUS IS NULL OR STATUS = 'OPEN'` (dòng chưa có issue có STATUS NULL do
   outerjoin). Các giá trị khác giữ `STATUS == value`. Xác nhận `recon_issue`
   đang được outerjoin (badge "Chưa đối soát" đã dựa vào NULL). Câu count dùng
   chung `base_query` nên tổng tự nhất quán.
2. UI: thêm `dmc.Select` id `run-res-issue-status-select` vào Group toolbar cạnh
   `run-res-search-input` và checkbox "Chỉ hiện cột lệch" (`run_result.py:734`),
   size xs, width ~200, value mặc định `"ALL"`, `aria-label="Đối soát & Xử lý"`.
   Options lấy từ helper sẵn có của trang `_lookup_status_options(ctx)` +
   fallback `DEFAULT_ISSUE_STATUS_OPTIONS`, thêm đầu danh sách
   `{"value": "ALL", "label": "Tất cả"}` và
   `{"value": "OPEN", "label": "Chưa đối soát"}`. Options nạp 1 lần lúc mở trang,
   cùng mẫu các Select khác của trang.
3. Callback `handle_filter_or_tab_change` (`run_result.py:1729`): thêm
   Input `run-res-issue-status-select` value; map `"ALL"`/rỗng → `None`,
   còn lại → đúng giá trị; khi `triggered_id` là select này thì về trang 1
   (như ô tìm kiếm/tab). Truyền `issue_status=...` vào `RunRowsFilter` lúc gọi
   `get_run_rows`.
4. **Bẫy đã biết**: toolbar nằm trong `render_result_grid` và được dựng lại mỗi
   lần callback chạy — phải truyền giá trị filter hiện tại vào
   `render_result_grid` như cách `search_query`/`only_diff_cols` đang làm, nếu
   không Select sẽ reset về "ALL" sau mỗi lần đổi. Kiểm tra cả `filter-store`
   (`run-res-filter-store`): nếu store đã giữ tab/page/page_size thì thêm
   `issue_status` vào đó để F5 giữ lại lựa chọn; nếu store không round-trip
   được thì ghi rõ trong decisions.md và giữ hành vi mặc định "ALL" sau F5.
5. Kiểm tra đường nạp ban đầu (~dòng 1586): giá trị mặc định phải là "ALL"
   (không lọc), không đổi hành vi khi mới mở trang.

## Bước 3 — (B) Nút drawer đổi tên + dời + thu nhỏ

File: `app/ui/pages/run_result.py` (hàm `render_detail_drawer`, ~dòng 1027-1075).

1. Title Group thành `dmc.Group(justify="space-between", align="center",
   children=[dmc.Group([icon, Text tiêu đề], gap="xs"), button])`.
2. Nút: `button_primary("Chuyển xử lý chênh lệch", id="drawer-save-issue-btn",
   icon="lucide:save", size="xs")`. Kiểm tra signature `button_primary` có nhận
   `size="xs"` không (các chỗ khác dùng size sm; nếu helper không hỗ trợ xs thì
   ghi decisions.md và dùng cách tương đương).
3. Group dưới cùng chỉ còn `html.Div(id="drawer-save-feedback")` (giữ nguyên id).
   Callback `handle_save_issue_from_drawer` (~1872) KHÔNG đổi Outputs/Inputs,
   chỉ đổi nhãn nút; hành vi lưu và thông báo giữ nguyên.
4. Cập nhật test cũ nào assert nhãn "Lưu trạng thái & ghi chú".

## Bước 4 — (C) Drawer tra khóa theo mapping template (không hardcode)

File: `app/ui/pages/run_result.py` (hàm `render_detail_drawer`, ~dòng 1137-1160).

1. Mở rộng `_profile_main_measure` (dòng 130) — hoặc thêm helper cạnh nó — để
   ngoài `{name, label, field, group_by}` còn trả về map trường logic →
   tên cột gốc trong file, lấy từ `config["fields"]`:
   `field.name` → `field.excel` (+ `field.excel_aliases`). Trả map rỗng khi
   không lấy được config (hàm này đã nuốt mọi exception → None; giữ nguyên
   tính chất đó, không raise).
2. Trong `render_detail_drawer`, dựng danh sách khóa:
   - Amount: `[excel/aliases của measure field] + [tên trường logic của measure]
     + ["TOTAL_AMOUNT", "AMOUNT"]` (bỏ các khóa None/rỗng, giữ thứ tự).
   - Invoice: `[excel/aliases của từng group_by field theo thứ tự] +
     [tên logic từng group_by field] + ["INVOICE_NO"]`.
   Dùng `_pick_value` như hiện tại (khớp khóa chính xác, 0 là giá trị thật).
3. Fallback `r.get("inv_no") or key_text` và `r.get("amount")` giữ nguyên.
4. Chỉ sửa phần "Dòng Excel gốc". Không sửa `_resolve_grid_measures`, phần DB,
   hay `header_row`/`data_start_row`.

## Bước 5 — Kiểm tra

1. Targeted tests xanh (service + page, gồm test mới bước 1).
2. `uv run poe typecheck` + `uv run poe lint` sạch (chỉ sửa dòng mình chạm;
   không chạy `poe format` toàn repo).
3. Live check bằng Playwright: script mới `~/workspace/check-88-run-issue-filter.py`
   (cổng 8145 — cổng trống tiếp theo; DB riêng dưới `/run/pytest-tmp/check88.*`,
   `RECON_DB_URL`/`RECON_STORAGE_DIR` riêng):
   - Seed theo mẫu check-85 (report + template + run có các dòng ở đủ trạng thái
     issue: chưa có issue, OPEN, IN_PROGRESS, RESOLVED; một nhóm có raw Excel
     với `DATA_JSON` khóa `_COL_n` và template map measure field → `_COL_17`).
   - S1: filter "Chưa đối soát" chỉ còn dòng chưa issue + OPEN; S2: filter
     "Đã xử lý xong" chỉ còn RESOLVED; S3: đổi filter về trang 1.
   - S4: mở drawer dòng MISSING_IN_DB → nút "Chuyển xử lý chênh lệch" nằm cùng
     hàng tiêu đề, bên phải, size xs; bấm lưu → issue lưu, feedback như cũ.
   - S5: drawer nhóm có raw `_COL_n` → Thành tiền hiện đúng số, Số hóa đơn chỉ
     hiện số hóa đơn.
   - Quét cả console error và pageerror; kiểm tra không cuộn trang ở 1366×768
     (quy tắc ui-dash).
4. Full suite: `TMPDIR=/run/pytest-tmp uv run poe test` xanh.
5. `uv run poe tasks-dashboard` sau mỗi bước rồi revert `docs/tasks/dashboard.html`
   trước khi commit (không đưa file sinh vào patch).

## Bước 6 — Bàn giao

- Parent review diff → commit `88-run-issue-filter-drawer: ...` (chỉ commit file
  task, KHÔNG `git add -A` vì cây còn 2 file progress.md đã sửa từ trước) →
  xuất patch `~/workspace/reconhub-task88.patch` → verify `git am` trên worktree
  sạch tại `bf2eafd` → cập nhật MEMORY.md → giao patch kèm lệnh áp + kiểm chứng.

## Follow-up (14/11/2026, người dùng duyệt) — fallback vị trí `_COL_n` + tra qua `f.db`

Nhánh: `feat/88-run-issue-filter-drawer-followup`, từ `f0edcc8`. Patch áp SAU
patch 88. Không db-migrate; chỉ khởi động lại app.

### F1 — Test đỏ trước

- `test_profile_main_measure_returns_field_maps`: `_profile_main_measure` trả
  thêm map vị trí (`field_pos_map`: tên logic → vị trí 1-based trong
  `config["fields"]`) và map DB (`field_db_map`: `f.db` → tên logic); các map
  rỗng khi không lấy được config.
- Drawer raw rows với `DATA_JSON` khóa `_COL_n` (template BILL_VTOS v4 thật:
  measure field `TONG_TIEN`, group-by `INVOICE_DATE`/`INVOICE_NO`, fields
  `TONG_TIEN`→`Tổng Tiền` vị trí 17, `SO_HD` (`db=INVOICE_NO`) vị trí 2,
  `NGAY_HD` (`db=INVOICE_DATE`) vị trí 3): Thành tiền hiện đúng số, Số hóa đơn
  chỉ hiện số hóa đơn.
- Không hồi quy: template tra tên được (DATA_JSON khóa tên logic hoặc tên cột
  gốc) vẫn hiển thị đúng như trước; dòng không có khóa `_COL_` nào thì KHÔNG
  dùng vị trí (test: xáo thứ tự fields mà không có `_COL_` → vẫn "—", không
  hiện sai số).

### F2 — Triển khai

File: `app/ui/pages/run_result.py` (hàm `_profile_main_measure`,
`render_detail_drawer`).
1. `_profile_main_measure` trả thêm `field_pos_map` và `field_db_map` (cùng
   tính chất nuốt exception → None như hiện tại; đặt tên/shape cuối do người
   triển khai chọn, ghi lại nếu khác plan).
2. `render_detail_drawer`: khi dựng khóa cho measure field và từng mục group-by,
   resolve field qua `f.name` rồi `f.db` (D9); thứ tự khóa theo D10, ứng viên
   vị trí chỉ thêm khi dòng `DATA_JSON` đang xét có khóa `_COL_`.
3. `handle_row_click_open_drawer` truyền các map mới vào drawer như cách đã
   truyền `field_excel_map`.
4. Không đụng filter (A), nút drawer (B), lưới, phần DB, `header_row`.

### F3 — Kiểm tra

Targeted tests xanh; typecheck/lint sạch; live check mở rộng script
`~/workspace/check-88-run-issue-filter.py` (cổng 8145, seed BILL_VTOS v4 thật
như F1): drawer nhóm `2026-04-29 11:00:45 | C26TBD0100011` hiện Thành tiền
493.500.000 / 131.000.000 và Số hóa đơn `C26TBD0100011`; template tra tên
được vẫn đúng; không cuộn trang, 0 lỗi JS. Full suite xanh.
Sau đó commit, xuất patch `~/workspace/reconhub-task88-followup.patch`, verify
`git am` tại `f0edcc8`, cập nhật MEMORY.md, giao patch.
