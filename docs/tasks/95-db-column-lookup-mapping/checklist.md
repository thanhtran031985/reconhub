# Checklist kiểm thử — Task 95: Đồng bộ nhãn cột từ lookup DB_COLUMN_MAPPING

Tài liệu kiểm thử chi tiết cho task `95-db-column-lookup-mapping`.

---

## 1. Migration dữ liệu `fact_bill` vào `DB_COLUMN_MAPPING`

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-MIG-01** | Kiểm tra tạo loại danh mục `DB_COLUMN_MAPPING` nếu chưa có | Bảng `RECON_LOOKUP_TYPE` có bản ghi `DB_COLUMN_MAPPING`, `IS_ACTIVE = 'Y'` | ✅ |
| **TC-MIG-02** | Migrate 119 cột của bảng `DATARAW.FACT_BILL` | Đủ 119 mã trong `RECON_LOOKUP_CODE` thuộc loại `DB_COLUMN_MAPPING` | ✅ |
| **TC-MIG-03** | Bảo toàn 7 mã đã tồn tại từ trước | 7 mã ban đầu (`CONFIRM_DATE`, `CONT_NO`, `CONT_SIZE`, `CONT_TYPE`, `INVOICE_DATE`, `INVOICE_NO`, `INV_CURRENCY`) không bị ghi đè nhãn | ✅ |
| **TC-MIG-04** | Kiểm tra tính Idempotent của migration | Chạy migration lần 2 trở đi không sinh lỗi, không tăng số lượng bản ghi (added = 0) | ✅ |
| **TC-MIG-05** | Kiểm tra các trường thuộc tính mặc định của code mới | `COLOR_BADGE = 'blue'`, `ICON_NAME = 'lucide:circle'`, `IS_ACTIVE = 'Y'`, `IS_SYSTEM = 'N'` | ✅ |

---

## 2. Ánh xạ nhãn lần đầu khi tạo Template mới (Initial Mapping)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-INIT-01** | Discover cột có mã khớp trong `DB_COLUMN_MAPPING` | Cột nhận nhãn mặc định từ `meaning` của lookup (vd: `CONT_NO` → `Số container`, `CONT_TYPE` → `Loại Cont`) | ✅ |
| **TC-INIT-02** | So sánh mã không phân biệt hoa thường | Tên cột DB `cont_no` hoặc `CONT_NO` đều match đúng mã lookup `CONT_NO` | ✅ |
| **TC-INIT-03** | Cột không tồn tại trong `DB_COLUMN_MAPPING` | Fallback về rule hiện tại: sinh nhãn dạng Title Case qua `prettify_column_label` (vd: `UNKNOWN_CUSTOM_COL` → `Unknown Custom Col`) | ✅ |
| **TC-INIT-04** | Lookup code bị vô hiệu hóa (`IS_ACTIVE = 'N'`) | Bỏ qua mã inactive, fallback về rule Title Case hiện tại | ✅ |
| **TC-INIT-05** | Nút "Làm mới cột" (`admin-col-refresh-btn`) khi phát hiện cột mới từ nguồn | Cột mới thêm nhận nhãn từ lookup mapping (nếu khớp) hoặc Title Case | ✅ |

---

## 3. Bảo toàn nhãn người dùng đã nhập khi mở lại / edit (Preserve User Input)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-EDIT-01** | Mở lại version DRAFT đã có nhãn lưu trong DB | Grid Tab 4 hiển thị đúng nhãn đã lưu trong `RECON_RPT_COLUMN.LABEL`, **không tự động lấy lại từ lookup** | ✅ |
| **TC-EDIT-02** | Chỉnh sửa nhãn thủ công trên grid Tab 4 và bấm "Lưu cột" | Hệ thống ghi nhận và lưu nhãn mới vào `RECON_RPT_COLUMN.LABEL`, thông báo thành công | ✅ |
| **TC-EDIT-03** | Tải lại trang sau khi đã lưu nhãn tùy biến | Nhãn hiển thị vẫn là nhãn tùy biến người dùng vừa lưu, không bị hoàn nguyên về lookup | ✅ |
| **TC-EDIT-04** | Thay đổi nhãn trong `/lookups` sau khi template đã tạo | Template đã lưu nhãn không bị ảnh hưởng, giữ nguyên nhãn của template | ✅ |

---

## 4. Hiển thị nhất quán trên các màn hình và chức năng liên quan

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Sub-tab "Xem trước layout" ở bước 4 | Hiển thị đúng nhãn tương ứng với grid cấu hình cột | ✅ |
| **TC-UI-02** | Màn hình chạy và xem kết quả báo cáo (`/report-viewer`) | Header bảng kết quả hiển thị đúng nhãn đã cấu hình | ✅ |
| **TC-UI-03** | Xuất kết quả báo cáo ra file Excel (.xlsx) | Dòng tiêu đề trong file Excel xuất ra hiển thị đúng nhãn của template | ✅ |
| **TC-UI-04** | Trang danh mục `/lookups` | Danh sách hiển thị đủ 119 mã của loại `DB_COLUMN_MAPPING`, tìm kiếm và lọc hoạt động tốt | ✅ |
| **TC-UI-05** | Chỉnh sửa mã code trên `/lookups` và bấm Lưu | Modal đóng mượt mà, bảng cập nhật giá trị mới, không bị vô hạn refresh callback, không treo trình duyệt (khắc phục lỗi Page Unresponsive) | ✅ |
| **TC-UI-06** | Remount pattern-matching buttons khi render bảng | Các callback `cb_edit_code_modal`, `cb_delete_code_modal`, `cb_delete_type_modal` raise `PreventUpdate` khi `value is None` thay vì trả `False` | ✅ |

---

## 5. Kiểm tra chất lượng và hồi quy kỹ thuật

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff (All checks passed) | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy (150 source files) | ✅ |
| **TC-REG-03** | `uv run pytest tests/unit/test_task95_lookup_mapping.py` | Toàn bộ 6/6 unit test mới viết pass 100% | ✅ |
| **TC-REG-04** | `uv run pytest tests/unit/test_column_label_format49.py` | Toàn bộ 18/18 test format nhãn cũ pass 100% | ✅ |
| **TC-REG-05** | `uv run pytest tests/unit/test_page_lookups.py` | Toàn bộ 35/35 test lookups pass 100% | ✅ |
| **TC-REG-06** | `uv run poe tasks-dashboard` | Dashboard cập nhật trạng thái đồng bộ | ✅ |
