# Progress — Task 66

- 12/11/2026: user gửi 3 ảnh (card sức khỏe kẹt #37/#38; bấm #37 lỗi ở /runs/37; /report-runs vẫn có #37) + yêu cầu tách card thành 1 tab và sửa lỗi link. Parent đọc code, xác minh nguyên nhân link sai bảng (run báo cáo RECON_REPORT_RUN gắn sang /runs/<id> chỉ đọc RECON_RUN), viết task.md + plan.md, trình plan chờ user duyệt.
- 12/11/2026: user duyệt plan, đặt tên task 66 → đã giao subagent làm theo plan.
- 12/11/2026: subagent làm xong theo plan (tests-first, đỏ → xanh):
  - Trang mới `app/ui/pages/queue_health.py` (/queue-health, MENU_CODE queue_health, nhóm DOI_SOAT order 90, icon lucide:activity); dời nguyên fetch/_health_card_body/render_health_card/callback từ dashboard.py; tiền tố id → queue-health-*; link run kẹt → /report-runs cho cả 2 kind.
  - dashboard.py bỏ card ở cả 2 nhánh + bỏ callback/import thừa (grep health = 0).
  - `get_queue_health` đổi @requires_menu sang queue_health; MenuDef + ROLE_MENUS_SEED cho cả 3 vai trò.
  - Migration 0009 (chỉ dữ liệu): chèn dòng RECON_MENU queue_health rồi cấp grant 3 vai trò, idempotent; downgrade chỉ gỡ grant SEED.
  - Cập nhật test cũ assert số lượng/tập menu: test_menu_sync (18→19), test_menu_admin_service (18→19), test_perm_effective (+queue_health 4 tập), test_perm_registry (page mapping), test_menu_display (sidebar +/queue-health), test_page_roles (19/19, 9/19, list OPERATOR +queue_health), test_perm_migration (RECON_MENU 13→14, grant 19→22), test_schema_inspector (manifest → 0009).
  - Manifest regenerate: `uv run poe schema-introspect` — diff chỉ version + generated_at, history không đổi; `--check` fresh.
  - LỆCH PLAN (D4): `format_short_dt` không import từ dashboard.py mà định nghĩa bản sao trong queue_health.py — import chéo trang làm Dash lỗi "duplicate paths", mọi request 500 (phát hiện nhờ check live; unit test không bắt được vì không làm HTTP request thật).
  - Check live ~/workspace/check-66-queue-health.py (port 8113): **11/11 pass** (dashboard 2 nhánh hết card; sidebar → /queue-health; link kẹt → /report-runs; Hủy → CANCELLED; đủ grant 3 vai trò; không lỗi JS).
  - Chưa commit — để uncommitted, chờ parent review + commit.
- Parent review 12/11/2026: check live chạy lại 10/11 (66-2 FAIL lặp lại) — chẩn đoán bằng probe: Dash Pages vẽ lại layout 2 lần khi điều hướng SPA, phần tử bị gỡ/gắn lại trong ~100ms; sửa check script chờ nội dung ổn định → 11/11. Không đổi app (hành vi đúng: tab hiện card sau ~200ms và ổn định). Probe đã xóa.
- Parent review 12/11/2026 (tiếp): full suite 3 failed ở tests/unit/test_role_service.py (list_roles_admin, clone_role, effective_of_user) — kỳ vọng hardcode danh sách menu OPERATOR chưa có queue_health (subagent sót); parent sửa 3 chỗ, thêm "queue_health" vào kỳ vọng (app đúng, chỉ test cũ). Chạy lại full suite sau fix.
- Follow-up 12/11/2026: user báo run #39 đang chạy không hiện trong danh sách (danh sách chỉ hiện mục kẹt) → yêu cầu thêm bảng Đang chạy/Đang chờ + badge phân biệt + filter. Parent viết followup-task.md + followup-plan.md, đã giao subagent làm theo plan.
- Follow-up 12/11/2026 (bảng Đang chạy/Đang chờ + badge + filter): bắt đầu làm theo followup-plan.md (F1–F5).
- Follow-up: service trả thêm key "active" (dùng lại exp_rows/run_rows, helper _queue_item chung shape với stuck); UI thêm bảng Đang chạy / Đang chờ + badge (QUEUED → "Đang chờ") + 2 Select filter ở header tĩnh + callback nhận thêm 2 Input filter; test mới 11 test (4 service + 6 UI + 1 guard filter) xanh; check live check-66followup-queue-active.py 9/9 (port 8114).
