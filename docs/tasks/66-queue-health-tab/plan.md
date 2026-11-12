# Plan — Task 66: Tách card sức khỏe thành tab riêng + sửa link run kẹt

## Bối cảnh
- Task 62 (commit `88ea6e9`): thẻ "Sức khỏe hàng đợi & worker" trên dashboard (`app/ui/pages/dashboard.py`: `_health_card_body` ~471, `render_health_card` ~619, callback `handle_health_actions` ~934, card vẽ ở 2 nhánh layout ~794 và ~866); service `app/services/worker_health.py::get_queue_health` (`@requires_menu("dashboard")`).
- Branch hiện tại: `feat/58-history-cancel-filter`, HEAD `b8c0666` (task 65 follow-up). Task 66 xếp chồng lên trên. (User duyệt 12/11/2026, đặt tên task này là 66 — follow-up modal trước đó gộp vào task 65.)

## Phân tích lỗi bấm run #37 (đã xác minh trong code)
- Danh sách kẹt của `get_queue_health` lấy run từ bảng `recon_report_run` (RECON_REPORT_RUN — run báo cáo), `run_id` = ID run báo cáo (worker_health.py ~175-210).
- `dashboard.py:535` gắn link: `href = f"/runs/{item['run_id']}"` khi `kind == "run"`.
- Nhưng `/runs/<run_id>` (`app/ui/pages/run_result.py`, Screen06-RunResult) gọi `get_run` (`app/services/run_service.py:291`) — chỉ đọc run đối soát theo lô ở bảng RECON_RUN. ID #37 là run báo cáo, không có trong RECON_RUN → "Không tìm thấy dữ liệu lần chạy #37."
- `/report-runs` (`MENU_CODE report_history`) liệt kê RECON_REPORT_RUN nên #37 có ở đó.
- Fix: run báo cáo trong danh sách kẹt link sang `/report-runs` (giống kind export đã làm); không có trang chi tiết riêng cho từng run báo cáo, các thao tác (Xóa / Xuất lại / Chạy lại) đều ở /report-runs.
- Vì sao #37/#38 kẹt 12h+ (phân tích, không thuộc phạm vi sửa): worker export chỉ nhận hàng RECON_RPT_EXPORT; run QUEUED chỉ được chạy khi có export (hoặc bấm Xem ở viewer) kéo nó đi — xem `report_export.py:801-808` (chốt run DONE trong lúc chạy export). Export của #37/#38 đã "Đã hủy" nên run QUEUED trơ trọi, không worker nào nhận — đúng mẫu #32/#33. Cách dọn: bấm Hủy trên card (cancel_report_run: ADMIN hoặc chủ).

## Bước 1 — Trang mới "Hàng đợi & worker"
- File mới `app/ui/pages/queue_health.py`: `dash.register_page(__name__, path="/queue-health", title="Hàng đợi & worker – ReconHub")`, `MENU_CODE = "queue_health"`, `layout()` có `page_gate` + tiêu đề trang + card sức khỏe (rộng hết trang, không còn là card trong dashboard).
- Dời nguyên bộ ba từ dashboard.py sang trang mới: `fetch_queue_health`, `_health_card_body`, `render_health_card`, callback `handle_health_actions` (Làm mới bằng tay + Hủy theo đúng luật service cũ). Đổi tiền tố id `dashboard-health-*` → `queue-health-*` cho đúng chỗ mới; cập nhật test + check script nhắc tới id cũ.
- Dashboard bỏ card ở cả 2 nhánh layout (~794 nhánh có dữ liệu, ~866 nhánh trống) và bỏ callback + import không còn dùng (`WORKER_KIND_LABELS`, `get_queue_health` nếu không còn chỗ nào dùng).
- Service `get_queue_health`: đổi `@requires_menu("dashboard")` → `@requires_menu("queue_health")` (sau khi dời, chỉ trang mới gọi service này — kiểm tra không còn nơi nào khác gọi).
- Menu: thêm `MenuDef("queue_health", "Hàng đợi & worker", "DOI_SOAT", "/queue-health", 90, "lucide:activity")` vào `app/ui/menus.py` (nhóm Đối soát, sau report_history 80) + thêm code vào cả 3 danh sách `ROLE_MENUS_SEED` (TEMPLATE_OWNER, OPERATOR, VIEWER — khớp "ai cũng xem được" như card cũ; ADMIN thấy qua IS_SYSTEM).
- Quyền trên DB thật: `menu_sync` chỉ đồng bộ định nghĩa menu (RECON_MENU), KHÔNG cấp quyền vai trò — nên thêm migration 0009 (chỉ dữ liệu, không đổi schema): INSERT vào RECON_ROLE_MENU cho 3 vai trò (theo mẫu `migrations/versions/0003_menu_permission.py:208`, viết idempotent — chỉ thêm khi chưa có). User chạy `uv run poe db-migrate` sau khi áp patch. Kiểm tra `uv run poe schema-introspect` sau migration để chắc không drift (migration không có DDL nên manifest không đổi).

## Bước 2 — Sửa link run kẹt (làm cùng lúc dời card)
- Trong render danh sách kẹt (dời sang trang mới): `href = "/report-runs"` cho cả kind run lẫn export (bỏ nhánh `/runs/{run_id}`).
- Kiểm tra không còn link nào khác trong card trỏ sang `/runs/<id>` (grep `/runs/` trong file mới + dashboard).

## Bước 3 — Kiểm chứng
- Tests-first: test unit cho (1) render trang mới chứa card (badge, 4 con số hàng đợi, danh sách kẹt) và dashboard hết card; (2) link run kẹt → /report-runs (cả 2 kind), không còn `/runs/` trong render card; (3) migration 0009 cấp đủ 3 vai trò (chạy migrate trên DB tạm rồi query RECON_ROLE_MENU); (4) service decorator đổi sang queue_health (gọi thiếu quyền → từ chối).
- Check live Playwright `~/workspace/check-66-queue-health.py` (port 8113, DB/storage riêng `/run/pytest-tmp/check67.*`, seed như check-62 + 1 run QUEUED kẹt): dashboard không còn card sức khỏe; sidebar có mục "Hàng đợi & worker" → mở /queue-health thấy card + nút Làm mới; bấm link run kẹt → sang /report-runs (không lỗi "Không tìm thấy"); bấm Hủy run kẹt → run chuyển CANCELLED, biến khỏi danh sách; quét cả console error VÀ pageerror.
- Full suite xanh (parent chạy sau review), commit một commit `66-queue-health-tab: ...`, export patch, verify `git am` sạch trên worktree ở `b8c0666`.

## Quyết định chờ ghi
- D1: "1 tab" được hiểu là 1 mục menu riêng trong sidebar (trang /queue-health), card rời khỏi dashboard hẳn — không phải tab con trong trang dashboard.
- D2: link run kẹt → /report-runs (nơi run tồn tại + có đủ thao tác), không tạo trang chi tiết riêng cho run báo cáo.
- D3: cấp quyền bằng migration 0009 (dữ liệu) thay vì để ADMIN gán tay trên /roles — user chỉ cần db-migrate sau khi áp patch.
