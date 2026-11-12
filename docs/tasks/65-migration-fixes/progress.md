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
