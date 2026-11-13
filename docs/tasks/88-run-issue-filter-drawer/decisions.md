# Decisions — Task 88

## D1 — Giá trị filter "Chưa đối soát" là "OPEN"

Badge cột "Đối soát & Xử lý" coi cả "chưa có issue" (STATUS NULL do outerjoin)
và issue OPEN đều là "Chưa đối soát" (run_result.py:578-592). Filter dùng chung
ngữ nghĩa đó: chọn "Chưa đối soát" = `issue_status="OPEN"`, service dịch thành
`STATUS IS NULL OR STATUS = 'OPEN'`. Không sinh thêm giá trị đặc biệt nào khác.

## D2 — Options của filter lấy từ lookup ISSUE_STATUS (cùng mẫu task 85/87)

Dùng helper sẵn có của trang `run_result.py` là `_lookup_status_options(ctx)`
+ fallback `DEFAULT_ISSUE_STATUS_OPTIONS`. Không import từ `issues.py`:
các module trang không được import lẫn nhau (gây duplicate paths → mọi request 500).
Thêm 2 lựa chọn đầu: "Tất cả" (`ALL`) và "Chưa đối soát" (`OPEN`).

## D3 — Nút drawer: chỉ đổi tên + dời + thu nhỏ, hành vi lưu giữ nguyên

Người dùng chốt 14/11/2026 qua options widget: "Chỉ lưu như cũ (đổi tên + dời nút
thôi)". Nhãn mới "Chuyển xử lý chênh lệch" — hiểu là: bấm nút = chuyển nhóm chênh
lệch này sang luồng xử lý (tạo/cập nhật issue), vẫn ở lại drawer, không mở trang
/Xử lý chênh lệch. Giữ id `drawer-save-issue-btn`, icon `lucide:save`, size `"xs"`.
Callback lưu không đổi Outputs/Inputs.

## D4 — Drawer tra khóa theo mapping template, không hardcode tên cột

Nguyên nhân gốc (đã chứng minh bằng dữ liệu thật run #1040): `DATA_JSON` lưu theo
tên cột gốc trong file (vd `_COL_17`), còn drawer chỉ tra tên trường logic +
`TOTAL_AMOUNT`/`AMOUNT`/`INVOICE_NO`. Các template khác nhau có tên cột khác nhau
(BILL_VTOS dùng `_COL_n`, Catos dùng tên riêng, mẫu DTP dùng tên logic) nên mọi
tên cột đều phải suy từ mapping của template đang chạy (`config["fields"]`:
`field.name` → `field.excel` + `field.excel_aliases`).
Thứ tự khóa: tên cột gốc → tên trường logic → fallback cũ. Fallback cũ giữ cuối
để template mà `DATA_JSON` lưu theo tên logic vẫn chạy như trước.
Chỉ sửa phần "Dòng Excel gốc" của drawer; không sửa lưới, phần DB, hay
`header_row` của template (đổi `header_row` sẽ đổi mapping cho các lần chạy sau).

## D5 — Không db-migrate; chỉ khởi động lại app

Cả 3 việc đều là code UI + service, không đổi schema. Patch áp SAU patch 87.

## D6 — Filter về trang 1 khi đổi giá trị

Cùng hành vi với ô tìm kiếm và tab trạng thái trong `handle_filter_or_tab_change`:
đổi filter là tập kết quả khác nên phải về trang 1, tránh ở trang N mà kết quả
mới không đủ dòng.

## D7 — `render_result_grid` nhận options filter đã hoàn chỉnh, không bọc lại

Lúc triển khai, `layout()`/`handle_filter_or_tab_change` truyền
`_issue_filter_options(ctx)` (đã gồm Tất cả + Chưa đối soát) nhưng
`render_result_grid` lại gọi `_issue_filter_options_from(...)` thêm một lần
nữa → data có 2 lần "ALL" (trùng value) và Select không render ra DOM live
(trong khi unit test vẫn thấy component trong cây). Sửa: `render_result_grid`
chỉ dựng options từ fallback khi caller không truyền gì; caller truyền gì thì
dùng nguyên đó. Test hồi quy: `test_render_result_grid_issue_status_select_keeps_value`
assert không trùng value.

## D8 — Store filter giữ được `issue_status` sau F5

`run-res-filter-store` đã round-trip qua callback `handle_filter_or_tab_change`
(tab/page/page_size/search/only_diff) nên thêm `issue_status` vào đó là đủ;
không cần cơ chế giữ lựa chọn riêng. Sau F5, trang mở lại với filter
`issue_status` đã lưu (khác hành vi mặc định "ALL" chỉ khi store chưa có key).
