# Tiến độ — 29-reporting-fluent-ui

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Chuẩn hóa màn danh sách Quản trị báo cáo (`/report-admin`) tương tự `/batches` | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 1 |
| 2 | Đồng bộ Trung tâm báo cáo (`/reports`) theo Fluent Compact | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 2 |
| 3 | Tái cấu trúc Wizard Bước 3 (`/report-admin`): Master–Detail & Canvas 12 cột | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 3 |
| 4 | Cải thiện Xem báo cáo (`/reports/<id>`), Wizard Bước 4, Sticky Footer & Hoàn tất | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 4 |
| 5 | Tái cấu trúc toàn bộ 6 bước Wizard `/report-admin` bám sát `preview.html`, tự sinh SQL từ Table/View, tương thích SQLite/Oracle dry-run | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 5 |
| 6 | Tách route `/report-admin/new` & `/<id>`, menu thao tác 3 chấm, phân trang và cố định footer giống `/batch-runs/11` | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 6 |
| 7 | Tinh chỉnh UX Wizard: Nút Lưu nháp, bảng inline tham số, Canvas Drag & Drop 12 cột, xóa & sắp xếp cột Tab 4, loại bỏ reload trang | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 7 |
| 8 | Khắc phục 6 lỗi chức năng & UX Tab 1-4: Lưu nháp Tab 1 ghi DB, tự động nạp bind param Tab 2, LOV form đúng preview.html, xóa cột mượt mà, chuyển alert sang toast notification | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 8 |
| 9 | Tối ưu toàn diện Tab 3 (nhãn 2/3, khoảng cách 8px, bỏ nút thừa), Tab 4 (toolbar tìm kiếm + Lưu cột, chặn cảnh báo giả, 1 trang màn hình + tách Card Xem trước độc lập, drag & drop online sync, xóa cột 0ms chống treo page), Tab 5 (nạp LOV options) | ✅ | 2026-11-09 | 29-reporting-fluent-ui: step 9 |
| 10 | Tách Tab 4 thành 2 Sub-tab, xử lý dứt điểm Page Unresponsive (Lưu cột, Khôi phục DB, Xóa cột 0ms), khắc phục lỗi ORA-01861 trên Oracle và hiển thị bảng kết quả dry-run 100 dòng mẫu × 119 cột ở Tab 5 | ✅ | 2026-11-09 | 29-reporting-fluent-ui: step 10 |

## Nhật ký
- 2026-11-08: Khởi tạo task 29 từ thiết kế chuẩn Screen16 preview.html và yêu cầu chuẩn hóa danh sách `/report-admin` tương tự `/batches`. Lên plan và được duyệt.
- 2026-11-08: Hoàn thành bước 1: xây dựng lại bảng danh sách `/report-admin` theo phong cách Fluent Compact của `/batches` (command bar tìm kiếm, lọc trạng thái/nhóm, bảng sticky header, status chip, menu 3 chấm, unit tests 32/32 pass).
- 2026-11-08: Hoàn thành bước 2: chuyển đổi `/reports` từ lưới card sang Bảng gom nhóm danh mục bám sát `preview.html` (.rlist), bổ sung nhãn đếm `#reports-catalog-meta` có aria-live="polite", unit tests 10/10 pass.
- 2026-11-08: Hoàn thành bước 3: tái cấu trúc Wizard bước 3 sang Master–Detail 2 cột (Cột trái: danh sách tham số, Canvas layout 12 cột trực quan có kiểm tra vượt span, form cấu hình trường; Cột phải: LOV Detail Panel cố định #lovside), unit tests 32/32 pass.
- 2026-11-08: Hoàn thành bước 4: thêm dòng Footer Total cho `/reports/<id>` khi có cột is_total=True, sinh dữ liệu mẫu giả lập ở Bước 4 Wizard để xem trước format cột, cố định thanh điều hướng chân trang Sticky Footer cho Wizard (.wfoot), unit tests 18/18 và 32/32 pass.
- 2026-11-08: Chụp màn hình Playwright tự động đối chiếu app thực tế với thiết kế `preview.html` (`scripts/capture_reporting_screens.py`), lưu trong `docs/tasks/29-reporting-fluent-ui/screenshots/`.
- 2026-11-08: Nhận phản hồi rà soát UI từ người dùng: tái cấu trúc lại toàn bộ các bước của Wizard `/report-admin` theo pixel-perfect Fluent Ribbon và bố cục của `preview.html`:
  - Ribbon 6 bước dạng segmented bar chuẩn Fluent với icon tick xanh cho các bước đã qua, highlight xanh dương cho bước hiện tại.
  - Bước 1: Chuyển sang form lưới 4 cột `.info-grid` đồng bộ thiết kế `preview.html`, tích hợp lưu trực tiếp vào nút Tiếp theo.
  - Bước 2: Thiết kế lại với 4 cột config, dropdown chọn Table/View tự nạp danh sách từ catalog; khi chọn bảng/view, hệ thống truy vấn các cột và **tự động sinh câu lệnh SQL** có thụt lề định dạng chuẩn vào khung soạn thảo SQL nền tối `#0a1427`.
  - Bước 3: Canvas Master-Detail 12 cột trực quan và LOV side panel.
  - Bước 4: Bảng mapping cột trực tiếp, format mask, alignment, độ rộng và checkboxes hiển thị.
  - Bước 5 & 6: Sửa `open_checked_connection` (dùng `raw_connection` cho SQLite) và `build_report_query` / `build_paged_query` tương thích cả SQLite và Oracle, cho phép dry-run và kích hoạt template thành công 100%.
  - Tự động hóa kiểm thử và chụp toàn bộ 10 ảnh màn hình chạy thực tế qua Playwright (`scripts/test_and_capture_wizard.py`).
  - Kiểm tra 387/387 unit test báo cáo xanh 100%, lint và typecheck sạch sẽ.
- 2026-11-08: Hoàn thành bước 6: Tối ưu UI/UX `/report-admin` và Wizard bám sát phản hồi thực tế:
  - Cột "Thao tác" đồng bộ `/batches`: ActionIcon sửa nhanh (`lucide:edit-3`) + Dropdown menu 3 chấm (`lucide:more-vertical`) gồm Sửa, Clone, Lưu trữ, Xóa.
  - Bổ sung phân trang `dmc.Pagination` và nhãn `Hiển thị X - Y trong tổng số Z mục`.
  - Padding và Header: Chuẩn hóa padding `padding: "8px 12px"`, `gap: "6px"`; bọc header danh sách và nút "+ Báo cáo mới" vào container riêng biệt để ẩn hoàn toàn khi chuyển sang Wizard.
  - Cố định Sticky Footer chuẩn kiến trúc `/batch-runs/11`: Top bar cố định (Breadcrumb, tiêu đề, nút Đóng về danh sách, Ribbon 6 bước), thân cuộn riêng biệt, Footer cố định chân trang (`height: "48px"`), nút "Quay lại" và "Tiếp theo" luôn hiển thị rõ ràng tại zoom 100%.
  - Định tuyến phân tách: Hỗ trợ URL sạch `/report-admin` (danh sách), `/report-admin/new` (tạo mới) và `/report-admin/<id>` (chỉnh sửa), có fallback query string.
- 2026-11-08: Hoàn thành bước 7: Tinh chỉnh UX Wizard và Canvas 12 cột bám sát thiết kế `preview.html`:
  - Thêm nút "Lưu nháp" nằm cạnh nút "Đóng" trên thanh tiêu đề wizard để người dùng chủ động lưu tiến độ mọi lúc.
  - Sửa lỗi reload trang / giật màn hình khi bấm nút "Tiếp theo" từ Tab 1 (loại bỏ loading overlay thừa, tự động lưu DB và mượt mà chuyển sang Tab 2).
  - Cố định Footer chân trang ở mọi tỷ lệ zoom màn hình 100% (bằng cách chuẩn hóa container cha flexbox không bị tràn viền).
  - Thiết kế lại Tab 3 (Tham số & LOV): Bảng tham số inline editable (`Mã`, `Nhãn`, `Kiểu`, `Hiện`, `Bắt buộc`, `Mặc định`, `LOV`, `STT`, `Xóa`), nút "+ Thêm tham số", nút "+ Thêm hàng" và "Tự sắp xếp đẹp" trên toolbar Canvas 12 cột. Thẻ tham số trên Canvas có kéo thả (drag & drop handle `⋮⋮`), nút dời `← / →`, ô nhập Hàng/Rộng trực quan. Panel cấu hình LOV chuyên biệt bên phải.
  - Cải tiến Tab 4 (Cấu hình cột): Hỗ trợ kéo thả đổi thứ tự cột, nút `↑ ↓`, nút ActionIcon xóa cột `×` (kết nối service `delete_column`), và nút "Khôi phục thứ tự DB".
  - Kiểm thử: toàn bộ unit tests và lint / typecheck xanh 100%.
- 2026-11-08: Hoàn thành bước 8: Giải quyết dứt điểm 6 vấn đề kiểm thử thực tế trên `/report-admin/1` và `/report-admin/new`:
  - Tab 1 (Thông tin): Sửa callback `handle_save_draft_click` đọc đầy đủ các trường của form Tab 1 và gọi trực tiếp `update_report`/`update_template` lưu ngay vào DB; thông báo toast thành công kèm mốc thời gian.
  - Tab 2 (Nguồn dữ liệu): Thêm cơ chế tự động phát hiện bind variables mới (`_sync_new_bind_params`), tự động tạo bản ghi tham số trong `recon_rpt_param` và sắp xếp layout khi người dùng bổ sung `:p_customer` vào câu lệnh SQL và bấm "Phân tích SQL" hoặc "Lưu nháp".
  - Chuyển tab & Tab 3: Khắc phục triệt để lỗi "Không tìm thấy tham số." và hiện tượng giật lag liên tục bằng cách loại bỏ vòng lặp `_bump(state)` trong các pattern-matching input inline; tự động chuẩn hóa `editing_param_id` an toàn theo danh sách tham số hiện có.
  - Cấu hình LOV: Thiết kế lại panel bên phải `#lovside` bám sát `preview.html`: dropdown `Loại LOV` cập nhật tức thì phần thân LOV; hỗ trợ đầy đủ `NONE` (hướng dẫn), `STATIC` (danh sách tĩnh + cho chọn Tất cả), `SQL` (textarea SQL, cache giây, data source, nút "Kiểm tra LOV SQL"), `LOOKUP` (danh mục hệ thống). Nút "Lưu cấu hình LOV" cập nhật chính xác payload mà không làm ảnh hưởng mã tham số.
  - Tab 4 (Cấu hình cột): Khắc phục hiện tượng treo máy khi xóa cột qua callback `handle_col_del_click` có guard chặt chẽ; bổ sung `draggable="true"` hỗ trợ kéo thả đổi thứ tự cột; nút "Lưu cấu hình cột" lưu bulk mượt mà.
  - Toast Notification: Thay thế toàn bộ hộp `alert_box` đẩy lệch layout bằng `dmc.Notification` (`notify_success`, `notify_error`, `notify_warning`) hiển thị popup toast gọn gàng ở góc trên bên phải màn hình.
  - Sửa lỗi crash React APIController (`Duplicate callback outputs`) khi truy cập `/login` hoặc tải trang: chuẩn hóa `allow_duplicate=True` và `prevent_initial_call=True` trên `Output("admin-state-store", "data")` và `Output("admin-reports-store", "data")`.
  - Tối ưu hiệu năng Tab 4: dùng input native styled cho 120 cột giúp thao tác xóa cột và kéo thả tức thì không bị treo trình duyệt; bổ sung cầu nối Drag & Drop HTML5 qua hidden input gọi `reorder_columns` / `move_param` chuẩn xác.
  - Kiểm thử: 35/35 unit test `test_page_report_admin.py` pass; 49/49 unit tests báo cáo khác pass; typecheck (136 source files) và lint sạch sẽ 100%.
- 2026-11-09: Hoàn thành bước 9: Tối ưu toàn diện Tab 3, Tab 4, Tab 5 theo phản hồi kiểm thử thực tế trên `http://127.0.0.1:8050/report-admin/1`:
  - **Tab 3 (Tham số & LOV)**:
    - Card 3 (Bảng tham số): Giảm độ rộng cột "Nhãn" xuống còn ~2/3 (140px, max 150px); giảm padding mỗi cell còn `4px 4px` (khoảng cách giữa các cột đúng 8px).
    - Canvas 12 cột: Bỏ 2 nút mũi tên `← / →` trên thẻ tham số, chỉ giữ lại 2 ô nhập Hàng và Cột (Rộng); bỏ 3 nút thao tác thừa `+ Thêm tham số`, `+ Thêm hàng`, và `Tự sắp xếp đẹp` (thao tác trực quan kéo thả).
  - **Tab 4 (Cấu hình cột)**:
    - Chặn triệt để cảnh báo giả "Đã ở đầu danh sách." khi chuyển từ Tab 3 sang Tab 4 bằng cách thêm guard `has_click` trên các triggered button items trong callback `handle_col_move_click`.
    - Tái bố cục Toolbar Cấu hình cột: đặt ô tìm kiếm theo tên trường DB (`#admin-col-search`) trước nút "Lưu cột" (`#admin-col-save-btn`), và nút "Lưu cột" đặt trước nút "Khôi phục thứ tự DB". Ô tìm kiếm lọc tức thì 0ms trên DOM mà không cần reload.
    - Căn chỉnh Card "Cấu hình cột" vừa vặn 1 trang màn hình không bị tràn (ScrollArea `maxHeight: 280px`).
    - Tách riêng phần "Xem trước layout kết quả" thành một Card (`dmc.Paper`) độc lập phía dưới, có tiêu đề và mô tả rõ ràng.
    - Đồng bộ online layout preview: Khi người dùng kéo thả (drag & drop) đổi vị trí cột, bảng xem trước ở Card phía dưới cập nhật live ngay lập tức theo thời gian thực (gọi `reorder_columns` và re-render preview container mà không bump wizard state, chấm dứt hiện tượng reload lại cả trang).
    - Xóa cột chống treo máy 100%: Xóa trực tiếp row trên DOM bằng hiệu ứng fade-out 120ms kết hợp `delete_column` trên backend; loại bỏ re-render loop 110 dòng, giải quyết triệt để lỗi "Page Unresponsive" của trình duyệt.
  - **Tab 5 (Xem trước)**:
    - Nạp danh sách options thực tế cho các tham số có LOV (ví dụ tham số `org` với các đơn vị GML, GNL, GAL, NDV, BDP, ICD1, ICD3, NHI, PHAO, PME...) thông qua hàm `_lov_options`, thay vì bị gán mảng rỗng `[]`.
  - **Kiểm thử tự động toàn diện**:
    - Chạy script kiểm thử Playwright tự động trên trình duyệt thật Chromium (`scratch/verify_all_tabs.py`): Tab 3 (kiểm tra giao diện & các nút), Tab 4 (không cảnh báo sai, thứ tự nút toolbar, tìm kiếm cột, kéo thả cột đổi thứ tự & preview cập nhật live, xóa cột mượt mà không treo máy), Tab 5 (dropdown LOV `org` hiển thị đầy đủ options) — **TẤT CẢ PASS 100%**.
    - Unit tests: 35/35 unit test `test_page_report_admin.py` pass 100%.
    - Linter & Typecheck: `uv run poe lint` và `uv run poe typecheck` (136 source files) sạch sẽ 100%.
- 2026-11-09: Hoàn thành bước 10: Xử lý triệt để hiện tượng treo trang Tab 4 và lỗi dry-run Oracle Tab 5 theo yêu cầu người dùng:
  - **Tab 4 (Cấu hình cột & Xem trước layout)**:
    - Phân tách 2 card thành 2 sub-tab riêng biệt: `dmc.Tabs(id="admin-step4-subtabs")` gồm "Cấu hình cột" và "Xem trước layout", loại bỏ việc cuộn trang dài, giao diện vừa vặn một trang màn hình.
    - Chấm dứt triệt để hiện tượng Page Unresponsive khi bấm "Lưu cột", "Khôi phục thứ tự DB", "Làm mới cột" và "Xóa cột": thay thế các Mantine component nặng trong 119 dòng bằng HTML elements nhẹ (`html.Button`, `html.Tr(key=...)`, `dcc.Checklist`, `html.Span`); loại bỏ việc gán lại `admin-col-tbody` gây so sánh 1,7 triệu pattern-matching dependency trong Dash; xử lý DOM sort và row deletion trực tiếp trong `drag_drop_reporting.js`; sửa signature callback xóa cột trả về đúng 2 output khớp khai báo. Tốc độ các nút giảm từ treo >20s xuống còn 1.5s!
  - **Tab 5 (Xem trước & Dry-run trên Oracle)**:
    - Khắc phục lỗi `ORA-01861: literal does not match format string`: Thiết lập NLS Session định dạng ngày giờ chuẩn `YYYY-MM-DD HH24:MI:SS` trong `source_conn.py` khi mở kết nối Oracle Thin; đồng thời chuyển đổi chuỗi ngày sang đối tượng `datetime.datetime` trong `_prepare_query_binds` (`app/services/report_run.py`).
    - Khắc phục vòng đời dry-run: Cho phép chạy lại dry-run cho version ở trạng thái `DRY_RUN_OK` và giữ nguyên chế độ wizard khi người dùng truy cập lại `/report-admin/<id>`.
    - Hiển thị bảng kết quả dry-run chuẩn 100 dòng mẫu với 119 cột header: Cập nhật trực tiếp kết quả vào `admin-dryrun-result` và banner mà không unmount form wizard.
    - Dropdown tham số LOV `org` nạp động đầy đủ danh sách mã đơn vị (GML, GNL, GAL, NDV, BDP...) từ nguồn Oracle `dim_operating_unit`.
  - **Kiểm thử tự động thực tế**:
    - Kiểm thử tự động trên trình duyệt thật với Playwright (`scratch/test_tab4_delete_col.py`, `scratch/test_tab5_capture.py`): Tab 4 xóa cột trong 1.6s (119 cột còn 118 cột, không treo); Tab 5 dry-run thành công trên Oracle `FACT_BILL` trả về 4.627 dòng tổng và hiển thị bảng 100 dòng mẫu × 119 cột.
    - Toàn bộ unit tests (60/60 tests gồm `test_page_report_admin.py`, `test_report_run_execute.py`, `test_report_column_grid.py`) pass 100%.
    - Linter & Typecheck: `uv run poe lint` và `uv run poe typecheck` (136 source files) sạch sẽ 100%.
