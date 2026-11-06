# Spec 12b – Data Flow Dynamic Reporting

## A. Đăng ký CUSTOM_SQL
Admin → lưu DRAFT → chọn Data Source → nhập SQL → parser SELECT-only → detect bind variables → Oracle describe/fetch 0 rows → sinh candidates param/columns → cấu hình LOV + parameter layout → column grid → dry-run → snapshot → ACTIVE → Report Center.

## B. Đăng ký VIEW/TABLE
Admin → chọn Data Source → lấy danh sách owner/object account được SELECT → chọn object → ALL_TAB_COLUMNS → chọn field output → khai báo parameter filter bằng column/operator whitelist → cấu hình LOV/layout/columns → dry-run → ACTIVE. Runtime query builder chỉ dùng identifier đã discover; value luôn bind.

## C. Report Viewer
User → menu check → load active Report Master/templates → render params by row/order/span → resolve default/LOV → validate → create REPORT_RUN → execute count/data pages → map fields → format → return page → update run metrics/history.

## D. LOV
Load form → NONE/STATIC/LOOKUP trực tiếp; SQL → cache key(Data Source, SQL hash, dependency params) → cache hit hoặc execute read-only with binds → validate VALUE/LABEL → limit → cache → render control.

## E. Export
User → ownership check → enqueue export → worker loads exact version + params → cursor fetchmany → apply columns/format → split parts → zip if needed → store/hash → update export → user downloads through owner-checked endpoint.

## F. Version update
Edit ACTIVE → clone new DRAFT → change source/metadata → compare old/new columns/params → dry-run → transaction: old ACTIVE→ARCHIVED, new→ACTIVE, update ACTIVE_VERSION_ID → invalidate LOV/report metadata cache. Existing runs keep old VERSION_ID.

## G. Permission and ownership
Definitions shared by menu. User run/history/export/download filter CREATED_BY=username. ADMIN bypass. Cross-user ID returns NOT_FOUND. Audit in same transaction for metadata changes; run/download audit separately.
