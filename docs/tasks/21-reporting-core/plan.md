# Implementation Plan — 21-reporting-core (Reporting Core và versioning)

## Bối cảnh
- Phụ thuộc task 19, 20 — đã xong, remote `feat/20-menu-admin` ở `c18ba8c`.
- Tài liệu đã có trên nhánh `docs/dynamic-reporting` (`e5eb466`): spec 12, 12a (bảng), 12b (data flow), Screen16 preview, `docs/tasks/21-reporting-core/` (task/progress/decisions/plan/test-checklist), `samples/reporting/fin_revenue_sample.json`.
- Không có UI trong task này (UI ở task 27); không migration nào khác đang chờ; không thêm package mới.

## Nhánh và tài liệu
- Nhánh mới `feat/21-reporting-core` từ `c18ba8c` (đầu nhánh 20).
- Chép `docs/tasks/21-reporting-core/` từ nhánh docs vào nhánh mới khi tạo nhánh (task/progress/decisions/test-checklist; plan.md chép nguyên văn plan này sau khi duyệt).
- Spec 12/12a/12b + Screen16 + samples ở lại nhánh `docs/dynamic-reporting` làm tài liệu tham chiếu, không đưa vào patch task 21.
- Thêm 8 dòng task 21–28 vào `docs/tasks/README.md` trong nhánh task 21 (theo hướng dẫn trong README-DYNAMIC-REPORTING.md).

## Các bước (theo progress.md)

### Bước 1 — Schema/migration cho 10 bảng
- Thêm 10 bảng vào `app/db/metadata.py` theo spec 12a: RECON_REPORT, RECON_REPORT_TEMPLATE, RECON_RPT_TPL_VER, RECON_RPT_PARAM, RECON_RPT_PARAM_LOV, RECON_RPT_COLUMN, RECON_REPORT_RUN, RECON_RPT_EXPORT, RECON_RPT_FAVORITE, RECON_RPT_PRESET, RECON_RPT_LOV_CACHE (thực tế 11 bảng theo bảng liệt kê; xem Q8).
- Migration `migrations/versions/0004_reporting_core.py` (down_revision `0003_menu_permission`), chạy được SQLite (batch mode) và Oracle; downgrade xóa các bảng mới (từ chối nếu đã có dữ liệu report? xem Q9).
- Ràng buộc: SOURCE_TYPE in (CUSTOM_SQL, VIEW, TABLE); version STATUS in (DRAFT, DRY_RUN_OK, ACTIVE, ARCHIVED); UQ(TEMPLATE_ID, VERSION_NO); GRID_SPAN 1..12, DISPLAY_ROW >= 1; LOV_TYPE in (NONE, STATIC, SQL, LOOKUP); FORMAT in (XLSX, CSV, ZIP); các CHECK ở mức DB theo dialect (SQLite/Oracle).
- Test trước: `tests/unit/test_reporting_schema.py` — tạo bảng, PK/FK/UQ/check vi phạm bị chặn (T21-02), upgrade/downgrade SQLite (T21-01 phía SQLite).
- Kiểm tra: `uv run poe test`.

### Bước 2 — Services Report Master, Template, Version clone/activate/archive
- Module mới `app/services/report.py` (Report Master CRUD) và `app/services/report_template.py` (Template CRUD + version clone/activate/archive).
- Theo quy ước service hiện có: nhận `ctx`, `@service` + `@requires_menu` (report_admin cho ghi metadata, report_center cho đọc), trả `ServiceResult`, lỗi tiếng Việt từ `app/schemas/errors.py` (thêm mã mới nếu cần: REPORT_NOT_FOUND dùng NOT_FOUND sẵn có; VERSION_CONFLICT/STALE_DATA đã có).
- Report Master: create/get/list/update/archive (CODE duy nhất, IS_VISIBLE/IS_ACTIVE).
- Template: create/get/list (theo REPORT_ID), update (chỉ khi chưa có version ACTIVE? — template đổi tên/thứ tự không ảnh hưởng version), archive.
- Version: create DRAFT (VERSION_NO = max+1), clone (sao chép sâu source + params + LOV + columns từ version bất kỳ, version mới DRAFT, VERSION_NO = max+1 — T21-03), activate (transaction: version cũ ACTIVE → ARCHIVED, version mới → ACTIVE, cập nhật ACTIVE_VERSION_ID của template; chỉ một ACTIVE — khóa bằng dòng `REPORT_ACTIVATE_LOCK` trong RECON_APP_SETTING theo mẫu MENU_SYNC_LOCK — T21-04), archive (không archive version ACTIVE; archive version DRAFT/DRY_RUN_OK).
- Validation ở service: GRID_SPAN 1..12 và tổng GRID_SPAN mỗi DISPLAY_ROW ≤ 12; SOURCE_OWNER/SOURCE_OBJECT bắt buộc với VIEW/TABLE; SQL_TEXT bắt buộc với CUSTOM_SQL; STATIC JSON values không trùng; SQL LOV có aliases VALUE/LABEL (kiểm tra cú pháp nông — parser sâu ở task 22/23).
- Run cũ giữ VERSION_ID cũ: REPORT_RUN.VERSION_ID là FK tới version, không đổi khi activate version mới (T21-05 — chỉ kiểm tra ở mức schema/service, thực thi run ở task 25).
- Test trước: `tests/unit/test_reporting_services.py` — CRUD, clone, activate đồng thời (2 lần activate liên tiếp, chỉ một ACTIVE), lỗi validation, run giữ version cũ.
- Kiểm tra: `uv run poe test`, `uv run poe typecheck`, `uv run poe lint`.

### Bước 3 — Seed menu report_center/report_history/report_admin
- Thêm 3 menu vào `app/ui/menus.py` (MENUS + ROLE_MENUS_SEED): report_center + report_history cho cả 4 vai trò, report_admin chỉ ADMIN (xem Q1); nhóm DOI_SOAT sau issue (70/80), report_admin nhóm QUAN_TRI sau menu_admin (xem Q2).
- Không cần migration mới: `menu_sync.sync_from_code` tự thêm menu mới (IS_NEW='Y'); role seed gán theo ROLE_MENUS_SEED.
- Trang `/reports`, `/report-runs`, `/report-admin` chưa có (task 27) nên 3 menu tạm thời chưa có trang đích — sidebar sẽ có mục nhưng bấm vào chưa có page (ghi chú trong decisions.md; giống batch_run/batch_def ở task 18/19).
- Test trước: `tests/unit/test_reporting_menus.py` — sync xong có đủ 3 menu, role seed đúng, effective_menus đúng.
- Kiểm tra: `uv run poe test`.

### Bước 4 — Audit và Oracle metadata migration
- Audit (cùng transaction) cho: report create/update/archive, template create/update/archive, version clone/activate/archive — dùng `write_audit_log` có sẵn.
- Thêm 11 bảng report vào thứ tự chuyển Oracle trong `app/services/metadata_migration.py` (sau các bảng menu/role).
- T21-01 phía Oracle: không chạy được trên máy ảo (không VPN) — ghi rõ trong decisions.md, kiểm chứng phía người dùng khi có VPN hoặc để task tích hợp Oracle sau.
- Test trước: `tests/unit/test_reporting_audit.py` — mỗi thao tác ghi đúng 1 dòng audit, rollback transaction thì audit cũng rollback (T21-06).
- Kiểm tra: `uv run poe test`, `uv run poe typecheck`, `uv run poe lint`, `uv run poe e2e` (không có UI mới nên e2e chỉ hồi quy).

## Kiểm tra cuối (ở cuối bước 4)
- `uv run poe test` (617 pass hiện tại + test mới), `uv run poe e2e`, `uv run poe typecheck` (21 lỗi baseline, 0 mới), `uv run poe lint`.
- Không phá golden/reconcile/batch/permission hiện có; không dùng dữ liệu giả trong production path.

## Câu hỏi chốt (Q0–Q9)
- Q0: Nhánh `feat/21-reporting-core` từ `c18ba8c`; chép thư mục task 21 từ nhánh docs; thêm 8 dòng 21–28 vào README.md trong nhánh task 21. Đồng ý?
- Q1: Seed menu — report_center + report_history cho cả 4 vai trò (VIEWER xem được báo cáo), report_admin chỉ ADMIN. Đồng ý?
- Q2: Vị trí menu — report_center/report_history nhóm DOI_SOAT sau issue (thứ tự 70/80), report_admin nhóm QUAN_TRI sau menu_admin (thứ tự 40); nhãn "Trung tâm báo cáo" / "Lịch sử báo cáo" / "Quản trị báo cáo". Đồng ý?
- Q3: Làm theo đề xuất (làm xong cả task rồi gửi xem như task 19/20) hay dừng sau mỗi bước chờ "continue"?
- Q8: Spec 12a liệt kê 11 bảng nhưng task.md ghi "10 bảng" — làm đủ 11 bảng theo spec 12a (thêm RECON_RPT_LOV_CACHE). Đồng ý?
- Q9: Downgrade migration 0004: xóa các bảng report mới. Nếu đã có dữ liệu report thì từ chối downgrade (an toàn) hay vẫn xóa? Đề xuất: từ chối khi có dòng dữ liệu trong RECON_REPORT/RECON_REPORT_RUN (giống mẫu downgrade 0003 từ chối khi có custom role được gán).
