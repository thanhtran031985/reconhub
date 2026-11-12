# Quyết định — Task 65: Sửa modal migration (idle, bước 7 manual) + layout tab Lưu trữ

## D1 — "bước 5" user ghi được hiểu là bước 7
User viết "sau bước 6, thêm bước 5 với card bước manual" — đã có 6 bước nên "bước 5" là nhầm, hiểu là thêm **bước 7** "Các bước làm tay" sau bước 6. Nội dung bước 7 là 4 bước làm tay đã liệt kê ở task 63.

## D2 — Chạy xong 6 bước → tự chọn bước 7
Thay D4 task 64 (xong thì chọn bước 6 để thấy báo cáo): khi fake/real chạy xong, modal tự chọn bước 7 để thấy ngay 4 bước làm tay cần tick. Báo cáo đối chiếu vẫn nằm ở detail bước 6 (điều kiện vẽ báo cáo chuyển từ `idx == len(steps) - 1` sang kiểm tra key `finish`). Chạy lỗi vẫn chọn bước lỗi.

## D3 — Tick manual: thật lưu CHECKLIST_JSON, fake chỉ client-side
Chế độ thật: callback tick gọi `save_checklist` ghi vào `CHECKLIST_JSON` của phiên migration (qua service có quyền ADMIN); fake: chỉ đổi trong `ds-mig-state` (tải lại trang mất). Lưu lỗi thì vẽ lại từ state cũ để checkbox tự về trạng thái cũ.

## D4 — Mở modal khôi phục phiên DONE còn bước tay chưa tick
Mở modal không có phiên PROCESSING thì khôi phục phiên DONE gần nhất còn bước làm tay chưa tick hết (service mới `get_latest_migration` + chuẩn hóa `ensure_manual_step`), để tick đã lưu không bị mất khi đóng/mở lại modal. Summary ghi rõ "Phiên #N đã xong — còn X/4 bước làm tay chưa đánh dấu". Nếu phiên DONE đã tick hết thì mở modal với state trống như cũ (không có gì cần làm tiếp).

## D5 — `overall_status` loại trừ bước manual
Bước 7 không tính vào hoàn thành: 6 bước tự động xong là migration xong (status "done"), dù 4 việc tay còn chờ. Nếu không loại trừ, `advance_fake_checklist`/callback tick DONE không bao giờ nhận ra đã xong (manual luôn pending cho tới khi user tick).

## D6 — `advance_fake_checklist` bỏ qua manual, nạp item khi xong
Tick fake không tự "chạy" bước manual (không đánh dấu item tay là done); khi 6 bước tự động xong thì nạp item manual từ `next_steps` (qua `populate_manual_items`) để user tick. `ensure_manual_step` chỉ nạp item khi `overall_status == "done"` — trước đó bước 7 phải có 0 item để hiện "Chờ" (phát hiện khi test đỏ: fake state idle đã có `next_steps` nên nạp sớm sẽ hiện 4 item trước khi bước 6 xong).

## D7 — Hai card cùng hàng bằng SimpleGrid 2 cột
Dùng `dmc.SimpleGrid(cols={"base": 1, "md": 2}, spacing="md"})` thay vì flex tay: Mantine md = 992px, gần ngưỡng 900px của ui-dash (dưới đó xếp dọc). Code block SQL tự cuộn ngang trong card của nó.

## D8 — Nút "Xem trước" cùng hàng bằng flex row `align-items: flex-end`
Thay SimpleGrid 4 cột + Group riêng bằng một `html.Div` flex (`display: flex`, `gap: 12px`, `alignItems: flex-end`, `flexWrap: nowrap`): 4 ô lọc bọc trong div `flex: 1`, nút bọc trong div `flexShrink: 0`. `flex-end` căn nút thẳng hàng với ô nhập (không căn theo label). Không đổi id/filter/callback preview.

## D9 — Dòng phụ bước manual ghi "Tiếp theo:" thay vì "Đang:"
Bước manual không "chạy" mà chờ user làm tay nên stepper/detail ghi "Tiếp theo: <việc đầu chưa xong>" + badge "Cần làm tay" (khi có item) thay vì "Đang: …" / "Đang chạy". Detail gắn nhãn "Tiếp theo" cho việc đầu chưa xong.

## D10 — Guard callback tick chống vẽ lại tự kích hoạt
Vẽ lại detail (tick/poll) tạo lại checkbox có thể kích hoạt callback pattern-matching `mig-manual-check`: callback bỏ qua khi giá trị mới bằng đúng trạng thái đã lưu trong checklist (không có thay đổi thật thì trả `no_update`). Ngoài ra tick chỉ áp dụng cho item đúng `triggered_id`.

## D11 — Sửa test cũ theo hành vi mới (không phải regression)
- `test_running_step_index` (task 64): 6 bước xong → bước hiện tại giờ là manual (index 6, thay 5).
- `test_advance_fake_checklist_is_pure_and_completes` (task 63): fake xong còn 4 pending là 4 việc manual (chưa tick), không phải 0.
- `test_new_checklist_has_six_steps_all_pending` → đổi tên thành `..._seven_steps...` (7 bước).
- `test_start_migration_writes_checklist`: chỉ assert 6 bước tự động done; bước manual có 4 item pending.

## D12 — Lint: fixture import dùng chung qua `__all__`
`test_migration_fixes65.py` import fixture `mig63_env` từ `test_migration_stepper63` (không copy lại fixture) và khai báo `__all__ = ["mig63_env"]` theo pattern sẵn có của `test_export_concurrency57.py` — vừa hết F401 vừa hết F811 (redefinition khi dùng làm tham số test).

## D13 — Guard chống modal tự đóng khi tab vẽ lại (lỗi có sẵn từ task 63)
Sau migration thật DONE, `ds-mig-done-store` đổi → tab Lưu trữ vẽ lại → nút mở `ds-mig-start-btn` bị tạo lại, `n_clicks` về 0 và callback `toggle_mig_modal` kích hoạt giả với triggered = start-btn. Guard cũ chỉ chặn (0, 0); trường hợp user đã bấm Đóng 1 lần (close_clicks ≥ 1) vẫn lọt, đọc `target_ds_id=None` (select đích cũng bị tạo lại) rồi trả `opened=False` → modal tự đóng ~2,6s sau khi bấm Bắt đầu thật. Fix: lần kích hoạt mà nút vừa bấm có `n_clicks` falsy thì trả `no_update` (click thật luôn ≥ 1). Xác minh bằng bisect variant A (mở → đóng → mở lại → real): trước fix modal đóng sau 2,6s, sau fix vẫn mở sau 15s; check-65 4c2 xác nhận modal vẫn mở sau real DONE.

## D14 — SimpleGrid vô tình bọc 3 card (lỗi bố cục)
Thứ tự source trong `render_storage_tab` là migration → "Bản lưu SQLite cũ" → script; lúc bọc 2 card, thẻ đóng SimpleGrid đặt sau card script nên grid ôm cả 3 card — card SQLite chiếm cột 2 hàng 1, đẩy script xuống hàng 2 (check-65 1a FAIL live ở 1440×900: mig y=887, script y=1170). Fix: dời block Paper "Bản lưu SQLite cũ" ra sau thẻ đóng SimpleGrid (full width, đứng riêng dưới hàng 2 card). Test `test_storage_two_cards_share_row` siết thêm: grid có đúng 2 Paper con theo thứ tự [migration, script], không chứa "Bản lưu SQLite cũ".

## D15 — Mở lại modal không cần select đích (lỗi có sẵn từ task 63)
Sau real DONE, tab vẽ lại làm select đích reset về None; guard `if not target_ds_id` trong `toggle_mig_modal` đứng trước cả hai nhánh khôi phục phiên nên mở lại modal trả `opened=False` + alert "Vui lòng chọn Data Source Oracle đích" — user đóng modal rồi không mở lại được để tick bước tay (check-65 4i crash). Fix: dời guard xuống sau nhánh khôi phục PROCESSING và nhánh khôi phục DONE (cả hai dùng `TARGET_DS_ID` lưu trong DB, không cần select); chỉ mở mới (empty state) mới cần target để ghi tóm tắt. Lưu ý còn lại (ngoài phạm vi task 65): bấm "Bắt đầu" chạy mới vẫn cần chọn lại đích vì select đã reset — hành vi cũ, giữ nguyên.

## Ghi chú — lỗi lint có sẵn ngoài phạm vi task
`uv run poe lint` toàn repo còn 1 lỗi I001 ở `tests/unit/test_export_concurrency57.py` (import chưa sort, file task 57, không đụng trong task này) — để nguyên, báo parent. Ruff sạch trên cả 6 file task 65 đổi.

## Follow-up (12/11/2026, gộp vào task 65 — không tách task 66)
- F1: tiến độ tính theo số việc (items), không tính theo số bước — mượt hơn (57 việc vs 6 bước), khớp dòng phụ stepper.
- F2: bar đặt trên 2 card, hiện từ lúc bấm Bắt đầu; lúc idle không hiện (div trống) để modal gọn như cũ.
- F3: click handler vẽ lại stepper (thay vì thêm callback riêng theo dõi store) — ít callback hơn, khớp pattern manual tick.
- F4: bỏ khối next-steps khỏi `_render_mig_report` nhưng giữ nguồn dữ liệu `next_steps` trong state — vẫn là nguồn tạo item bước 7.

## Follow-up — ghi chú triển khai (subagent, 12/11/2026)
- F1 đã làm: helper `progress_counts(state)` trong `migration_checklist.py` cộng `step_counts` 6 bước tự động, bỏ key manual. Tổng việc phụ thuộc số bảng đích: fixture `_precheck_data` (4 bảng) = 20 việc; precheck thật trên DB seed (40 bảng) = 55 việc — test `test_mig_run_fake_path_uses_real_precheck` tính kỳ vọng từ `progress_counts(state)` thay vì hardcode 6/20.
- F2 đã làm: `html.Div(id="ds-mig-progress")` đặt ngay trên hàng 2 card (dưới `ds-mig-real-warning`); renderer `_render_mig_progress(state)` — idle/total 0 → div trống; running → `dmc.Progress` + label "Đang chạy bước X/6 · <tên> — d/t việc (NN%)"; done → 100% "Hoàn tất t/t việc"; error → bar đỏ + "Lỗi ở bước X/6". Output `ds-mig-progress` được thêm CUỐI danh sách Output của cả 4 callback (toggle_mig_modal 13→14, handle_mig_run 8→9, handle_mig_fake_tick 6→7, handle_mig_real_tick 8→9) để index các output cũ không đổi; mọi nhánh return đều cập nhật (kể cả no_update).
- F3 đã làm: `handle_mig_step_click` thêm Output thứ 3 `ds-mig-stepper` = `_render_mig_stepper(checklist, idx)`; guard no_update trả đủ 3 giá trị. Tick fake/real giữ `selected` từ store qua `_mig_selected_index` nên highlight sau click không bị tick đánh lại.
- F4 đã làm: `_render_mig_report` bỏ tham số `next_steps` + khối Divider/Text/Stack; chỉ còn bảng đối chiếu + tiêu đề. Caller duy nhất ở `_render_mig_detail` đã cập nhật.
- Test cũ phải sửa theo (hệ quả đổi số lượng output, không đổi hành vi): `test_detail_finish_step_shows_report_when_done` (layout64) bỏ assert "Dừng ứng dụng web ReconHub" ở detail bước 6; 4 test click ở layout64 unpack 3 giá trị; `test_mig_modal_open_guard_no_clicks` 13→14, `test_mig_run_guard_no_clicks` 8→9, `test_mig_run_fake_path_uses_real_precheck` unpack 9 giá trị; 2 test toggle ở fixes65 13→14.
- Lỗi sửa trong lúc làm: `toggle_mig_modal` còn sót 2 chỗ `return no_update_13` (guard remount) sau khi đổi tên biến thành `no_update_14` — bắt được nhờ test `test_toggle_modal_ignores_remount_spurious_fire` (NameError).
- Ruff format: chỉ format tay 2 dòng ternary mới trong `_render_mig_progress` (hunk 1828/1845); các hunk còn lại trong file đổi là drift có sẵn (checklist 98/121/229/281/477; data_sources 177/526/1919/2725/2770; test 63/65) — để nguyên theo quy tắc nhà.
