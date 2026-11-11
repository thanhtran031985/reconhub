# Quyết định — Task 63

## D1 — Checklist real mode lưu ở cột mới CHECKLIST_JSON
Thay vì nhét vào REPORT_JSON (theo plan). Lý do: không đổi shape báo cáo cuối
(REPORT_JSON vẫn là `{bảng: {source_rows, target_rows, matched, checksum_matched}}`
như cũ); checklist cần cập nhật dần trong lúc chạy, báo cáo chỉ ghi lúc xong.
Cần migration 0008 + regen schema manifest (luật task 31).

## D2 — Fake mode không tạo bản ghi migration
Chỉ client-side (`dcc.Store`) + precheck thật. Theo plan.

## D3 — `start_migration` hiện bỏ qua kết quả precheck lỗi
`precheck()` đã qua decorator `@service` nên trả `ServiceResult`, nhưng
`start_migration` gọi mà không kiểm tra `.ok` — precheck lỗi thì migration
vẫn chạy tiếp (bật bảo trì, tạo phiên...). Đây là lỗi có sẵn, phát hiện khi
làm real mode (checklist bước 1 phải phản ánh đúng precheck). Fix trong
task 63: `start_migration` raise `ServiceError` khi precheck trả lỗi, trước
khi bật bảo trì/tạo phiên. Không đổi hành vi khi precheck OK (CLI đã gọi
precheck riêng trước nên không ảnh hưởng).

## D4 — Poll real mode theo `started_at`, không theo registry id
Modal poll tìm bản ghi migration mới nhất của đích có `CREATED_AT >= started_at`
(lúc bấm "Bắt đầu"), thay vì thread ghi id vào registry. Lý do: tránh state
chia sẻ giữa thread nền và callback. Registry chỉ dùng để báo lỗi khi thread
chết trước khi kịp tạo phiên (precheck trong thread lỗi) — trường hợp hiếm,
poll sau 30s không thấy phiên thì báo lỗi chung.

## D5 — Fake report không có DSN cụ thể trong "bước tiếp theo"
`next_steps` của fake dùng câu chung "Cập nhật biến môi trường RECON_DB_URL
trong file .env sang Oracle đích" (không có DSN user/host che *** như bản thật),
vì precheck không trả host/username. Bản thật giữ nguyên DSN như cũ.

## D6 — Fake luôn có dòng checklist "Nối lại liên kết RECON_RUN ↔ batch item"
Trong code thật, backfill chỉ chạy khi có liên kết vòng; fake mô phỏng luôn có
dòng này (đánh dấu xong) vì precheck không cho biết có liên kết hay không.
Bản thật: không có liên kết thì đánh dấu xong với ghi chú "Không có liên kết
vòng cần nối lại".

## D7 — Live check dùng launcher patch `create_engine_for_ds` (chỉ check script)
App thật không có Oracle trong VM nên precheck không thể pass với đích ORACLE.
Check-63 seed đích ORACLE_TEST (DB_TYPE='ORACLE' để hiện trong select) và chạy
app qua launcher riêng trong `~/workspace` (không nằm trong repo): launcher
patch `app.services.metadata_migration.create_engine_for_ds` để trả engine
SQLite tới file tạm khi tên DS là ORACLE_TEST, các DS khác giữ nguyên. Nhờ đó
fake chạy được precheck thật, và real mode chạy được migration thật
SQLite→SQLite để kiểm chứng luồng nền + checklist. Không đổi code product
cho việc test.

## D8 — Tick fake 400ms, mỗi tick xong 4 dòng checklist
Ước tính ~55 dòng checklist (NO_TEMP, DB seed nhỏ) → chạy fake hết khoảng
6–8 giây, đủ thấy tiến trình mà không chờ lâu.

## D9 — `start_migration` kiểm tra cả kết quả `set_maintenance_mode`
Cùng lỗi kiểu D3: `set_maintenance_mode` qua decorator trả ServiceResult
nhưng kết quả bị bỏ qua. Nay raise ServiceError nếu không ok, trước khi
tạo phiên. Hành vi khi thành công không đổi (CLI gọi precheck riêng trước).

## D10 — Báo cáo modal đọc đúng khóa source_rows/target_rows
Code cũ (`handle_migration_start`) đọc `info.get('src_rows')` / `tgt_rows`
trong khi REPORT_JSON ghi `source_rows` / `target_rows` — bảng đối chiếu
cũ luôn hiện 0. Renderer mới `_render_mig_report` đọc đúng khóa.
