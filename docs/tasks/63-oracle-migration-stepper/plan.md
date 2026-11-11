# Plan — Task 63: Modal stepper chuyển Oracle + switch thật/fake

## Bối cảnh
- Trang `/data-sources`, tab "Lưu trữ RECON_APP", khối "Chuyển dữ liệu sang Oracle" (`app/ui/pages/data_sources.py`, hàm `render_storage_tab` + callback `handle_migration_start`).
- Service migration: `app/services/metadata_migration.py` — `precheck()`, `start_migration()` (đồng bộ, chạy trong một callback; ghi tiến độ STAGE/PROGRESS_PCT vào `RECON_METADATA_MIGRATION`), `clean_target_schema()`, `delete_old_sqlite()`, `set_maintenance_mode()`.
- Nút "Chuyển sang Oracle" hiện tại gọi `start_migration` đồng bộ rồi hiện bảng đối chiếu. Không có tiến trình trực tiếp.
- Branch hiện tại: `feat/58-history-cancel-filter`, HEAD `88ea6e9` (task 62). Task 63 xếp chồng lên trên (như task 58–62).

## Bước 1 — Modal + stepper UI
- Bấm "Chuyển sang Oracle" mở `dmc.Modal` (render qua portal — test/check Playwright phải assert theo text trên `document.body`, không query theo id modal).
- Trong modal: tóm tắt đích + chế độ (đọc từ `ds-mig-target-select` / `ds-mig-mode-select` trên trang), `dmc.Switch` id `ds-mig-real-switch` "Migration thật" (mặc định OFF = fake), nút "Bắt đầu" id `ds-mig-run-btn`, stepper dọc 6 bước tái dùng kiểu visual của wizard stepper (vòng tròn đánh số nối bằng đường kẻ, bước đang chạy tô xanh), mỗi bước có checklist bước con (trạng thái chờ/đang chạy/xong/lỗi).
- Khi switch BẬT: hiện cảnh báo (ghi dữ liệu thật sang Oracle + bật chế độ bảo trì).
- Nút "Kiểm tra trước" và "Xóa schema đích" trên trang giữ nguyên.

## Bước 2 — Fake mode (mặc định)
- Bấm "Bắt đầu" với switch OFF: gọi `precheck()` thật (chỉ đọc). Precheck lỗi → dừng ở bước 1 với đúng thông báo lỗi.
- Precheck OK → xây fake checklist từ ước tính (số bảng/dòng theo chế độ NO_TEMP/FULL/CONFIG_ONLY), chạy mô phỏng bằng `dcc.Interval` + `dcc.Store` (mỗi tick hoàn thành một vài dòng checklist; logic tick viết thành helper thuần để test được).
- Xong 6 bước: hiện báo cáo đối chiếu giả + 4 bước làm tay tiếp theo (dừng app/worker → đổi RECON_DB_URL → db-migrate → khởi động lại).
- Fake mode KHÔNG ghi gì sang Oracle, KHÔNG bật bảo trì, KHÔNG tạo bản ghi migration.

## Bước 3 — Real mode (switch BẬT)
- Bấm "Bắt đầu" với switch ON: chạy `start_migration` trong luồng nền (`threading.Thread`), chặn chạy 2 migration cùng lúc (từ chối nếu đã có phiên PROCESSING).
- Service ghi tiến độ checklist theo từng bước con vào bản ghi migration: thêm cột `CHECKLIST_JSON` vào `RECON_METADATA_MIGRATION` (migration 0008; theo luật task 31, chạy `uv run poe schema-introspect` để regen schema manifest).
- Modal poll bằng `dcc.Interval` (1–2s) đọc checklist từ bản ghi migration và cập nhật stepper trực tiếp.
- Lỗi ở bước nào: dừng ở đó, hiện lỗi + hướng xử lý (thường "Xóa schema đích" rồi chạy lại).
- Đóng modal giữa chừng: migration vẫn chạy tiếp; mở lại modal/trang thì thấy đúng tiến độ hiện tại của phiên PROCESSING.

## Bước 4 — Kiểm chứng
- Tests-first: test unit cho fake runner (xây checklist từ precheck, tick advance, hoàn thành), trạng thái switch, và checklist writer của real mode (ghi/đọc CHECKLIST_JSON). Theo luật repo: `progress.md` + `uv run poe tasks-dashboard` sau mỗi bước, rồi REVERT `docs/tasks/dashboard.html` (không đưa vào patch); KHÔNG chạy `uv run poe format` toàn repo, chỉ format tay dòng mình sửa; typecheck + lint + test xanh trước khi báo xong.
- Check live Playwright `~/workspace/check-63-migration-stepper.py` (port 8109, DB/storage riêng `/run/pytest-tmp/check63.*`, seed theo mẫu check-39): modal mở; chạy fake hết 6 bước; checklist đủ dòng; switch BẬT hiện cảnh báo; quét cả console error VÀ pageerror.
- Full suite xanh, commit một commit `63-oracle-migration-stepper: ...`, export patch, verify `git am` sạch trên worktree ở `88ea6e9`.

## Quyết định chờ ghi
- D1: checklist real mode lưu ở cột mới CHECKLIST_JSON (thay vì nhét vào REPORT_JSON) để không đổi shape báo cáo cuối.
- D2: fake mode không tạo bản ghi migration (chỉ client-side + precheck thật).
