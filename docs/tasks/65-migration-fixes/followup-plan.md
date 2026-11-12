# Plan — Follow-up task 65: Modal migration (bỏ next-steps bước 6, click đổi indicator, progress bar)

## Bối cảnh
- Task 63 (commit `2219105`) + task 64 (commit `3fa3b10`) + task 65 (commit `958ba32`): modal stepper 7 bước, 2 card Master–Detail, file chính `app/ui/pages/data_sources.py` (`_render_mig_stepper`, `_render_mig_detail`, `_render_mig_report`, `_empty_mig_state`, các callback `toggle_mig_modal`, `handle_mig_run`, `handle_mig_fake_tick`, `handle_mig_real_tick`, `handle_mig_step_click`, `handle_mig_manual_tick`); helper checklist `app/services/migration_checklist.py` (`step_counts`, `running_step_index`, `overall_status`, `MANUAL_STEP_KEY`).
- Branch hiện tại: `feat/58-history-cancel-filter`, HEAD `958ba32` (task 65). Follow-up này xếp chồng lên trên.

## Bước 1 — Bỏ khối next-steps khỏi detail bước 6
- Nguyên nhân trùng lặp: `_render_mig_report` (data_sources.py ~1971) vẽ bảng đối chiếu + khối "Các bước tiếp theo cần thực hiện:" (Divider + Text + Stack các dòng `next_steps`); từ task 65, 4 dòng đó đã là item tick được của bước 7 nên hiện 2 lần.
- Fix: bỏ khối Divider + Text + Stack(steps_list) khỏi `_render_mig_report`, giữ bảng đối chiếu + tiêu đề "Chuyển dữ liệu thành công!". Bỏ tham số `next_steps` của helper (chỉ có 1 nơi gọi, ở `_render_mig_detail` ~1949) và cập nhật docstring. Không xóa `state.get("next_steps")` — vẫn là nguồn tạo item bước 7 (`populate_manual_items`).

## Bước 2 — Click bước đổi indicator
- Nguyên nhân đã xác minh trong code: `handle_mig_step_click` (~2600) chỉ có 2 Output (`ds-mig-selected-step`, `ds-mig-detail`), không trả `ds-mig-stepper` — nên bấm bước chỉ vẽ lại card detail bên phải, stepper bên trái giữ highlight cũ (bước 7 sau khi xong). Lỗi có từ task 64: check-64 chỉ assert detail đổi, không assert highlight.
- Fix: thêm Output thứ 3 `ds-mig-stepper` children = `_render_mig_stepper(checklist, idx)`; các nhánh no_update trả thêm `dash.no_update`. Guard chống re-fire đã có sẵn (vẽ lại stepper tạo lại div với n_clicks=0 → callback chạy lại nhưng `not any(clicks)` → no_update). Tick fake/real giữ `selected` từ store qua `_mig_selected_index` nên highlight sau click không bị tick đánh lại; khi DONE tick fake/real ép về `_MIG_MANUAL_IDX` và tắt interval — chỉ xảy ra đúng lúc chạy vừa xong, không ảnh hưởng click sau đó.

## Bước 3 — Progress bar
- Thêm `html.Div(id="ds-mig-progress")` trong modal, đặt ngay trên hàng 2 card (dưới switch/warning, trên flex stepper+detail).
- Helper mới trong `migration_checklist.py`: `progress_counts(state) -> (done, total)` = cộng `step_counts` của 6 bước tự động, bỏ key manual (khớp `overall_status` không tính bước 7). Ví dụ trường hợp user: 6+3+1+42+3+2 = 57 việc.
- Renderer mới `_render_mig_progress(state)`: idle → div trống (không hiện bar, modal gọn như cũ); running → `dmc.Progress` value = done/total*100 + label "Đang chạy bước X/6 · <tên bước> — done/total việc (NN%)" (bước đang chạy lấy từ `running_step_index`, bỏ qua bước manual); done → 100% "Hoàn tất total/total việc"; error → bar đỏ + "Lỗi ở bước X".
- Callbacks thêm Output `ds-mig-progress` children (cập nhật mọi nhánh return, kể cả no_update): `toggle_mig_modal` (mở modal → vẽ theo state khôi phục), `handle_mig_run` (bấm Bắt đầu → 0% hoặc trạng thái precheck lỗi), `handle_mig_fake_tick`, `handle_mig_real_tick` (cập nhật mỗi tick/poll). Click bước + tick manual KHÔNG cần output này (tiến độ không đổi). Không đổi interval 400ms/1,5s.

## Bước 4 — Kiểm chứng
- Tests-first: test unit cho (1) `_render_mig_report` không còn chữ "Các bước tiếp theo" nhưng vẫn có bảng đối chiếu; (2) click handler trả 3 output, stepper vẽ lại với idx được chọn làm selected; (3) `progress_counts` (idle 0/57, giữa chừng, done 57/57, không tính manual); (4) `_render_mig_progress` idle → trống, running → value đúng.
- Check live Playwright `~/workspace/check-65followup-migration-progress.py` (port 8112, DB/storage riêng `/run/pytest-tmp/check66.*`, seed + launcher như check-63/64/65): fake chạy → bar hiện, % tăng theo tick, label đổi tên bước; xong → 100% + tự chọn bước 7; detail bước 6 không còn "Các bước tiếp theo" nhưng còn bảng đối chiếu; click bước 6 sau khi xong → highlight stepper sang bước 6 (assert style/background của block bước 6) + detail bước 6; click bước 7 → highlight về bước 7; quét cả console error VÀ pageerror.
- Full suite xanh (parent chạy sau review), commit một commit `65-migration-fixes-followup: ...`, export patch, verify `git am` sạch trên worktree ở `958ba32`.

## Quyết định chờ ghi
- D1: tiến độ tính theo số việc (items), không tính theo số bước — mượt hơn (57 việc vs 6 bước), khớp dòng phụ stepper.
- D2: bar đặt trên 2 card, hiện từ lúc bấm Bắt đầu; lúc idle không hiện (div trống) để modal gọn như cũ.
- D3: click handler vẽ lại stepper (thay vì thêm callback riêng theo dõi store) — ít callback hơn, khớp pattern manual tick.
