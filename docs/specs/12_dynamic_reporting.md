# Spec 12 – Dynamic Reporting / Trung tâm báo cáo

## 1. Mục tiêu
Module báo cáo động cho FIN, kế toán và đơn vị nghiệp vụ. Thêm báo cáo chủ yếu bằng metadata, không viết page Dash riêng. Một Report Master có 1..N Report Template. Mỗi template có version, Data Source Oracle, nguồn dữ liệu, tham số, LOV, layout tìm kiếm, mapping cột, layout kết quả và giới hạn thực thi.

## 2. Quyết định đã chốt
- Ba loại nguồn triển khai ngay: `CUSTOM_SQL`, `VIEW`, `TABLE`.
- Template Active không sửa trực tiếp. Sửa bằng clone version mới: DRAFT → DRY_RUN_OK → ACTIVE; version cũ ARCHIVED.
- Parameter hỗ trợ LOV `NONE`, `STATIC`, `SQL`, `LOOKUP`.
- Layout parameter dùng grid 12 cột: `DISPLAY_ROW`, `DISPLAY_ORDER`, `GRID_SPAN` từ 1..12; tổng GRID_SPAN mỗi hàng ≤ 12. Vượt thì cảnh báo và chặn qua bước.
- Layout cột cấu hình trên grid; kéo thả để đổi vị trí; nhập đồng thời header, format, width, web/excel visibility và total.
- Account Oracle chạy report phải read-only. Không dùng account ứng dụng có quyền ghi.
- Web dùng server-side pagination. Export chạy background; mỗi file Excel tối đa 1.000.000 data rows, vượt thì chia file và đóng zip.
- User thường chỉ xem Report Run/Export do mình tạo; ADMIN thấy tất cả. Report definitions dùng chung theo menu.

## 3. Màn hình
1. `/reports`: Trung tâm báo cáo, tìm/lọc nhóm/yêu thích, card Report Master Active.
2. `/reports/<report_id>`: template dạng tab, form tham số động, bảng kết quả server-side, export.
3. `/report-runs`: lịch sử, tải file, chạy lại với tham số cũ.
4. `/report-admin`: danh sách Report Master/Template và wizard 6 bước.

## 4. Wizard
### Bước 1 – Thông tin chung
Report code/name/category/owner/description/default favorite/visible; template code/name/order/status/version.

### Bước 2 – Nguồn dữ liệu
Chung: Data Source, `SOURCE_TYPE`, timeout 1..600 giây, preview max rows, export max rows.

#### CUSTOM_SQL
- Nhập SQL SELECT hoặc WITH...SELECT.
- Phân tích bind variables và column metadata.
- Chặn DML, DDL, PL/SQL, nhiều statement, comment nguy hiểm, dynamic SQL.
- Thực thi bằng bind parameters, không nối chuỗi.

#### VIEW
- Chọn `OWNER` và `VIEW_NAME` từ `ALL_VIEWS` mà account có quyền SELECT.
- Discover columns từ `ALL_TAB_COLUMNS`.
- Filter/sort chỉ từ metadata đã whitelist. Backend sinh SQL `SELECT <whitelisted columns> FROM <validated owner.view> WHERE ...`.
- Không cho nhập tùy ý owner/view hoặc expression.

#### TABLE
- Chọn `OWNER` và `TABLE_NAME` từ `ALL_TABLES` mà account có quyền SELECT.
- Discover cột từ `ALL_TAB_COLUMNS`.
- Cùng whitelist filter/sort như VIEW.
- Cảnh báo dùng TABLE trực tiếp có thể phụ thuộc schema; ưu tiên VIEW cho báo cáo nghiệp vụ ổn định.

Với VIEW/TABLE, parameter filter có thêm: `FILTER_COLUMN`, `FILTER_OPERATOR` (`=`, `>=`, `<=`, `BETWEEN`, `IN`, `LIKE_PREFIX`, `IS_NULL`), không cho operator tùy ý. Cột sort và direction cũng whitelist.

### Bước 3 – Parameter, LOV, layout
Parameter: code, label, data/control type, required, default, display row/order, grid span, visible.
- NONE: input theo data type.
- STATIC: grid Value/Label; Value không trùng; optional ALL.
- SQL: LOV SQL SELECT-only, aliases VALUE/LABEL, Data Source, cache seconds 0..3600, max 5.000 rows, test.
- LOOKUP: chọn lookup type, chỉ active khi tạo mới.
Layout review: kéo thả, thay row, GRID_SPAN 1..12; tổng mỗi row ≤12; auto-layout; preview khớp Report Viewer.

### Bước 4 – Column mapping
Grid: order, DB field readonly, display label, data type, format, alignment, web/excel visible, total, width. Kéo thả hoặc grid row drag. Preview cập nhật ngay. Detect cột mới/mất/đổi type sau re-analyze.

### Bước 5 – Dry-run
Nhập parameter thử, thực thi tối đa preview rows; hiển thị query plan summary, thời gian, row count, sample, cảnh báo timeout/type/format. Không cho activate khi lỗi.

### Bước 6 – Activate
Snapshot source, SQL/source object, parameters, LOV, parameter layout, columns, limits. Chỉ một ACTIVE version/template.

## 5. Thực thi
- Tạo REPORT_RUN với snapshot template version + resolved params.
- Chuẩn hóa/validate param rồi bind.
- CUSTOM_SQL dùng SQL snapshot. VIEW/TABLE dùng query builder whitelist.
- Web: count query có timeout riêng, data query dùng offset/fetch hoặc row_number theo Oracle version; stable sort bắt buộc.
- Column formatter dùng metadata; không render HTML từ DB.
- Cancel đánh dấu CANCEL_REQUESTED; worker hủy ở checkpoint/Oracle cancel nếu driver hỗ trợ.

## 6. Export
Export job snapshot run/version/params/columns. Cursor fetchmany (5.000–20.000 rows), không load toàn bộ RAM. XLSX dùng write-only mode; mã, invoice, container, leading-zero giữ Text. CSV UTF-8 BOM tùy config. Chia file khi vượt giới hạn, zip, hash và lưu lịch sử.

## 7. Security
- `report_center`, `report_history`, `report_admin` là menu codes.
- `requires_menu`; activate/source SQL management chỉ ADMIN hoặc menu report_admin theo chính sách hiện tại; Data Source PROD vẫn ADMIN-only nếu task 19 quy định.
- owner_filter cho run/export/file download.
- Identifier owner/table/view/column phải tồn tại trong whitelist metadata; không bind identifier.
- SQL parser + account read-only + timeout là các lớp độc lập.
- Audit create/update/version/dry-run/activate/run/export/download/cancel.

## 8. Giới hạn mặc định
Preview 100 dòng UI wizard; web page 50, max 200; SQL timeout 300s; count timeout 60s; LOV 5.000 rows, cache 300s; max export 5.000.000 rows/job; 1.000.000 rows/file; 2 export jobs/user chạy đồng thời.
