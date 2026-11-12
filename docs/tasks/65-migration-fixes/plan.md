# Plan — Task 65: Sửa modal migration (idle, bước 7 manual) + layout tab Lưu trữ

## Bối cảnh
- Task 63 (commit `2219105`) + task 64 (commit `3fa3b10`): modal stepper 6 bước, 2 card Master–Detail, file chính `app/ui/pages/data_sources.py` (`_render_mig_stepper`, `_render_mig_detail`, `_empty_mig_state`, các callback `handle_mig_modal`, `handle_mig_run`, `handle_mig_fake_tick`, `handle_mig_real_tick`); helper checklist `app/services/migration_checklist.py` (6 bước `MIGRATION_STEP_KEYS`/`MIGRATION_STEP_LABELS`, `new_checklist`, `save_checklist`/`load_checklist`); service `app/services/metadata_migration.py` (`start_migration` ghi `next_steps` vào checklist lúc DONE, fake dùng `fake_next_steps()`).
- Branch hiện tại: `feat/58-history-cancel-filter`, HEAD `3fa3b10` (task 64). Task 65 xếp chồng lên trên.

## Bước 1 — Sửa lỗi idle "Đang chạy…"
- Nguyên nhân đã xác minh: `_render_mig_stepper` tìm "bước hiện tại" bằng cách lấy bước running/error, không có thì lấy bước pending đầu tiên — lúc modal mới mở state `idle` (6 bước, 0 dòng con) nên bước 1 rơi vào nhánh `is_current` → tô xanh + `running_item` None → ghi "Đang chạy…".
- Fix: chỉ coi một bước là "hiện tại/đang chạy" khi state tổng đang `running` (hoặc bước đó running/error); lúc `idle` thì `current_idx = -1`, cả 6 bước vẽ nhánh chờ ("Chờ" khi 0 item, "Chờ • 0/m việc" khi có item). Kiểm tra cả `_mig_selected_index`/`running_step_index` không đổi lựa chọn mặc định sai lúc idle (mở modal vẫn chọn bước 1).

## Bước 2 — Bước 7 "Các bước làm tay"
- Mở rộng khung checklist lên 7 bước: thêm key `manual` + label "Các bước làm tay" vào `MIGRATION_STEP_KEYS`/`MIGRATION_STEP_LABELS` (cẩn thận các nơi duyệt đúng 6 bước — grep `MIGRATION_STEP_KEYS`, `len(steps)`, `_render_mig_report` gọi khi `idx == 5` phải chuyển thành kiểm tra theo key, không theo số thứ tự cứng).
- Nội dung bước 7 lấy từ `next_steps` (thật: từ `start_migration` lúc DONE; fake: từ `fake_next_steps()` lúc fake xong): mỗi dòng là một item checklist (label là câu bước tay, bỏ số thứ tự đầu dòng hoặc giữ nguyên câu). Trước khi bước 6 xong, bước 7 có 0 item → hiện "Chờ" + ghi chú "Chạy xong 6 bước thì mới làm các bước này" trong detail.
- Tick: mỗi item bước 7 có `dmc.Checkbox` (checked = status done); bấm tick → đổi status item → lưu lại. Thật: ghi vào `CHECKLIST_JSON` của phiên migration (dùng `save_checklist`, qua service/callback có quyền ADMIN); fake: chỉ đổi trong `ds-mig-state` (client-side, tải lại mất). Cả 4 done → bước 7 hiện ✓.
- Chạy xong 6 bước → tự chọn bước 7 (thay vì bước 6 như D4 task 64) để thấy ngay 4 bước tay; báo cáo đối chiếu vẫn ở detail bước 6. Chạy lỗi → vẫn chọn bước lỗi. Mở modal giữa chừng có phiên PROCESSING → bước 7 chưa có item (hiện "Chờ").
- Fake tick/poll không được reset tick manual khi vẽ lại (tick chỉ đổi khi user bấm hoặc khi bước 7 mới được tạo).

## Bước 3 — Hai card migration + script cùng hàng
- Trong `render_storage_tab`, bọc Paper "Chuyển dữ liệu sang Oracle" và Paper "Script khởi tạo schema đích Oracle" vào một hàng flex (mỗi card flex 1, gap md); dưới 900px xếp dọc (theo ui-dash: panel chia đôi chuyển thành xếp dọc). Không đổi id/select/nút/callback bên trong hai card. Code block SQL cuộn ngang riêng trong card của nó nếu dài.

## Bước 4 — Nút "Xem trước" cùng hàng với ô lọc
- Trong Paper "Xóa dữ liệu tạm theo điều kiện": đưa nút "Xem trước" vào cùng hàng với 4 ô lọc (Template, Trạng thái kiểm tra, Chạy trước, Người chạy), căn thẳng hàng với ô nhập (không căn theo label). Cách làm do implementer chọn (vd grid 5 cột + ô nút canh cuối, hoặc Group flex align flex-end); yêu cầu: ở 1440×900 và 1366×768 nút nằm cùng hàng, không rớt dòng, không vỡ layout khi resize nhẹ. Không đổi id/filter/callback preview.

## Bước 5 — Kiểm chứng
- Tests-first: test unit cho (1) render stepper lúc idle (không bước nào "Đang chạy…", cả 6 "Chờ"); (2) helper bước 7 (tạo item từ next_steps, tick đổi status, cả 4 done → bước done); (3) render 2 card cùng hàng + nút Xem trước cùng hàng (assert cấu trúc component/id, không assert pixel).
- Check live Playwright `~/workspace/check-65-migration-fixes.py` (port 8111, DB/storage riêng `/run/pytest-tmp/check65.*`, seed + launcher như check-63/64): mở modal chưa bấm Bắt đầu → bước 1 "Chờ" (không "Đang chạy…"); fake xong → tự chọn bước 7, tick 1 bước tay → tải lại modal vẫn còn tick (fake: chỉ cần còn trong cùng phiên trang; thật: kiểm tra CHECKLIST_JSON đã lưu tick); 2 card migration + script cùng hàng ở 1440×900 (so vị trí top tương đương, không xếp dọc); nút Xem trước cùng hàng với ô lọc ở 1366×768; quét cả console error VÀ pageerror.
- Full suite xanh (parent chạy sau review), commit một commit `65-migration-fixes: ...`, export patch, verify `git am` sạch trên worktree ở `3fa3b10`.

## Quyết định chờ ghi
- D1: "bước 5" user ghi được hiểu là bước 7 (đã có 6 bước).
- D2: chạy xong 6 bước → tự chọn bước 7 (thay D4 task 64 chọn bước 6).
- D3: tick manual chế độ thật lưu vào CHECKLIST_JSON; fake chỉ lưu tạm client-side.
