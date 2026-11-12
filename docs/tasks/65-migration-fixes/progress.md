# Tiến độ — Task 65: Sửa modal migration (idle, bước 7 manual) + layout tab Lưu trữ

## Bước 1 — Sửa lỗi idle "Đang chạy…"
- [x] Test đỏ: render stepper lúc idle (không bước nào "Đang chạy…")
- [x] Fix `_render_mig_stepper` (chỉ coi bước là hiện tại khi state `running`)
- [x] Kiểm tra `_mig_selected_index`/`running_step_index` lúc idle (mở modal vẫn chọn bước 1)
- [x] Phát hiện thêm khi rà: detail bước 7 lúc idle hiện badge "Đang chạy" (do `is_current` dùng `running_step_index` trả về bước cuối) — đã guard `overall != "idle"` trong `_render_mig_detail`

## Bước 2 — Bước 7 "Các bước làm tay"
- [x] Test đỏ: helper bước 7 (tạo item từ next_steps, tick, overall loại manual)
- [x] Checklist 7 bước + `manual_items`/`populate_manual_items`/`set_item_status`/`ensure_manual_step`
- [x] `start_migration` ghi manual items lúc DONE; `get_latest_migration` + khôi phục phiên DONE ở modal mở
- [x] Callback tick manual (fake: ds-mig-state; thật: CHECKLIST_JSON); chạy xong tự chọn bước 7; báo cáo vẫn ở detail bước 6
- [x] Sửa 2 test cũ theo hành vi mới: `test_running_step_index` (6 bước xong → bước hiện tại là manual, index 6), `test_advance_fake_checklist_is_pure_and_completes` (xong fake còn 4 pending manual)

## Bước 3 — Hai card migration + script cùng hàng
- [x] Test đỏ: cấu trúc SimpleGrid 2 cột
- [x] Bọc 2 Paper vào SimpleGrid cols {"base": 1, "md": 2}

## Bước 4 — Nút "Xem trước" cùng hàng với ô lọc
- [x] Test đỏ: nút trong cùng hàng flex với 4 ô lọc
- [x] Flex row align-items flex-end, không rớt dòng ở 1440×900 / 1366×768

## Bước 5 — Kiểm chứng
- [x] Typecheck + lint + test targeted xanh (51 passed: test_migration_fixes65 16 + test_migration_stepper63 + test_migration_modal_layout64; ruff sạch 6 file đổi; mypy sạch 145 file)
- [x] Check live `check-65-migration-fixes.py`: **28/28 PASS** (port 8111) — 1a 2 card cùng hàng 1440×900; 1b nút Xem trước cùng hàng 1366×768; 2a–2e idle; 3a–3h fake + tick bền; 4a–4j real DONE + tick lưu CHECKLIST_JSON + mở lại khôi phục 3/4 bước tay; 5a không console error / pageerror
- [x] Sửa thêm 2 lỗi có sẵn phát hiện khi check live (ngoài plan nhưng cùng modal migration, ghi D13/D15): guard chống modal tự đóng khi tab vẽ lại; mở lại modal không cần select đích
- [ ] Chưa chạy full suite (parent chạy sau review)

## Trạng thái
- ✅ xong (chờ parent review + full suite + commit + xuất patch)
- 12/11/2026: follow-up sau khi user áp patch 65 và gửi ảnh modal (fake xong, bước 7 đã chọn): bỏ next-steps ở bước 6, click bước đổi indicator, thêm progress bar. User bảo gộp vào task 65 luôn ("nhiều task quá rồi"), không tách task 66 — docs 66 đã dời thành followup-task.md / followup-plan.md trong thư mục task 65; đã giao subagent làm.

## Follow-up — triển khai (subagent, 12/11/2026)
- [x] Tests-first: `tests/unit/test_migration_followup65.py` mới (11 test) — đỏ toàn bộ trước khi code (report còn next-steps, click 2 output, chưa có progress_counts/_render_mig_progress)
- [x] Bước 1: `_render_mig_report` bỏ tham số `next_steps` + khối Divider/Text/Stack; chỉ còn bảng đối chiếu + tiêu đề; caller `_render_mig_detail` cập nhật
- [x] Bước 2: `handle_mig_step_click` thêm Output thứ 3 `ds-mig-stepper` vẽ lại theo bước vừa bấm; guard trả đủ 3 no_update
- [x] Bước 3: helper `progress_counts` (migration_checklist.py) + renderer `_render_mig_progress` + `html.Div(id="ds-mig-progress")` trên 2 card; Output progress thêm cuối 4 callback (toggle 13→14, run 8→9, fake tick 6→7, real tick 8→9), mọi nhánh return cập nhật
- [x] Test cũ sửa theo: layout64 (4 test click unpack 3 + bỏ assert next-steps ở detail bước 6), stepper63 (len 13→14, 8→9, unpack run 9 giá trị, kỳ vọng progress tính từ state), fixes65 (2 test toggle 13→14)
- [x] Typecheck + lint: mypy sạch (145 file); ruff check sạch 6 file đổi; format tay 2 dòng ternary mới trong `_render_mig_progress` (drift có sẵn để nguyên)
- [x] Test targeted xanh: 83 passed (followup65 11 + fixes65 + stepper63 + modal_layout64 + page_data_sources + metadata_migration)
- [x] Check live `check-65followup-migration-progress.py`: **18/18 PASS** (port 8112) — 1a idle không bar; 1b–1d fake bar hiện, % tăng 18→40, label "Đang chạy bước 4/6 · Sao chép dữ liệu — 14/55 việc (25%)"; 1e–1f xong 100% "Hoàn tất"; 2a–2c detail bước 6 còn báo cáo + bảng, hết "Các bước tiếp theo"; 2d–2f click bước 6 highlight sang đúng bước 6 (bg rgb(231,245,255)), click bước 7 về đúng bước 7; 3a–3e real bar cập nhật qua tick thật (12%, bước 2/6), DB DONE, UI sang bước 7, bar 100%, modal vẫn mở; 4a không console error / pageerror. Lưu ý: lần chạy đầu 3a FAIL do lấy mẫu ở 5s thì real đã DONE (DB seed nhỏ, xong < 5s) — sửa script lấy mẫu mỗi 300ms, không sửa app. Tổng việc real lúc đầu 52 (verify chưa có item, top-3 chỉ biết sau khi chép) rồi lên 55 khi DONE — hành vi đúng, % tính trên tổng hiện tại.
- [ ] Chưa chạy full suite (parent chạy sau review)
