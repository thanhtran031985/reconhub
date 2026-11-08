# Implementation Plan — 29-reporting-fluent-ui
**Đồng bộ giao diện Báo cáo động theo thiết kế chuẩn Screen16 preview.html & Mẫu /batches**

## Bối cảnh & Mục tiêu
- Phụ thuộc: Task 27, 28 (đã hoàn thành logic và backend).
- Mục tiêu chính:
  1. Chuẩn hóa màn hình danh sách Quản trị báo cáo (`/report-admin`) theo đúng mẫu kiến trúc và trải nghiệm của màn hình Danh sách Bộ đối soát ([`/batches`](file:///d:/reconhub/app/ui/pages/batch_defs.py)): có đầy đủ tìm kiếm, lọc trạng thái, lọc nhóm, bảng Fluent Compact, menu thao tác 3 chấm, modal xác nhận lưu trữ/xóa, toast notifications và loading skeleton.
  2. Đồng bộ giao diện Trung tâm báo cáo (`/reports`) sang bảng gom nhóm danh mục bám sát [`designs/components/Screen16-DynamicReporting/preview.html`](file:///d:/reconhub/designs/components/Screen16-DynamicReporting/preview.html).
  3. Bổ sung dòng Footer Total cho màn Xem báo cáo (`/reports/<id>`).
  4. Tái cấu trúc Wizard Bước 3 (Master–Detail 2 cột, Canvas layout 12 cột trực quan), bổ sung dữ liệu mẫu ở Bước 4, và cố định thanh điều hướng Sticky Footer cho Wizard (`/report-admin`).

## Nhánh & Tài liệu tham chiếu
- **Nhánh**: `feat/29-reporting-fluent-ui`
- **Mẫu màn hình danh sách tham chiếu**: `app/ui/pages/batch_defs.py` (`/batches`)
- **File thiết kế chuẩn**: `designs/components/Screen16-DynamicReporting/preview.html`
- **Quy tắc thiết kế**: `.agents/rules/ui-dash.md` (Fluent Compact + Master–Detail)

---

## Các bước triển khai

### Bước 1 — Chuẩn hóa màn danh sách Quản trị báo cáo (`/report-admin`) tương tự `/batches`
* **Mục tiêu**: Xây dựng lại màn hình danh sách Report Master / Template trên `/report-admin` theo đúng mẫu kiến trúc và trải nghiệm của [`/batches`](file:///d:/reconhub/app/ui/pages/batch_defs.py).
* **Tệp chỉnh sửa**:
  * [`app/ui/pages/report_admin.py`](file:///d:/reconhub/app/ui/pages/report_admin.py)
* **Nội dung thực hiện**:
  1. **Header một dòng**:
     * Title: "Quản trị báo cáo", Subtitle: "Danh sách báo cáo đã đăng ký và cấu hình template".
     * Actions: Nút Làm mới (ActionIcon `lucide:refresh-cw`), Nút `+ Báo cáo mới` (primary button dẫn sang Wizard mới).
  2. **Command bar**:
     * Search input: "Tìm theo mã hoặc tên báo cáo..."
     * Filter select trạng thái: Tất cả trạng thái, Hoạt động (`ACTIVE`), Bản nháp (`DRAFT`), Đã lưu trữ (`ARCHIVED`).
     * Filter select nhóm: Tất cả nhóm, Tài chính, Kế toán, Vận hành.
     * Text đếm ở bên phải: `N báo cáo` (font 11px, màu nhạt).
  3. **Bảng danh sách chuẩn Fluent Compact (`dmc.Table` + `TableScrollContainer`)**:
     * Header cố định (sticky top=0, height=34px, font 11px fw=600).
     * Cột **Mã**: font monospace (`className="rh-code"`), in đậm, link mở wizard sửa.
     * Cột **Tên báo cáo & Mô tả**: Stack gồm tên (fw=600, size=sm) + mô tả nhỏ bên dưới (c=dimmed, size=xs).
     * Cột **Nhóm**: Badge danh mục (Tài chính, Kế toán, Vận hành).
     * Cột **Trạng thái**: `status_chip(status)` căn giữa.
     * Cột **Số template & Version**: Hiển thị số lượng template và version đang active (Badge xanh lá `vX ACTIVE`).
     * Cột **Chủ sở hữu**: FIN, ACC, v.v.
     * Cột **Thao tác**:
       * Nút ActionIcon sửa (`lucide:edit-3`).
       * Menu dropdown 3 chấm (`lucide:more-vertical`) gồm:
         * *Sửa báo cáo & template* (mở Wizard)
         * *Thêm template mới*
         * *Clone version mới*
         * *Lưu trữ* (mở modal xác nhận)
         * *Xóa báo cáo* (mở modal xác nhận)
  4. **Các trạng thái & Modals**:
     * Loading: 5 dòng `dmc.Skeleton(height=40, radius="sm")`.
     * Empty state: Tiêu đề, mô tả và nút tạo mới.
     * Error alert: Giữ dữ liệu cũ + nút Thử lại.
     * Toast notifications: `notify_success`, `notify_error` khi thao tác.
     * Modals xác nhận: `modal_confirm` cho Lưu trữ và Xóa báo cáo.
* **Test viết trước**: Cập nhật [`tests/unit/test_page_report_admin.py`](file:///d:/reconhub/tests/unit/test_page_report_admin.py) kiểm tra rendering danh sách, lọc trạng thái, tìm kiếm và menu thao tác.
* **Kiểm tra**: `uv run poe test` xanh.

---

### Bước 2 — Đồng bộ Trung tâm báo cáo (`/reports`) theo Fluent Compact
* **Mục tiêu**: Chuyển đổi hiển thị danh sách từ lưới Card sang **Bảng gom nhóm danh mục** đúng thiết kế `.rlist` trong `preview.html`.
* **Tệp chỉnh sửa**:
  * [`app/ui/pages/reports.py`](file:///d:/reconhub/app/ui/pages/reports.py)
* **Nội dung thực hiện**:
  1. Thay thế `render_reports_sections` và `render_report_card` (lưới Card cũ) bằng Bảng gom nhóm theo danh mục (`dmc.Table`):
     * Dòng header nhóm phân cách: `Tài chính · N báo cáo`, `Kế toán · N báo cáo`, `Vận hành · N báo cáo`.
     * Cột bảng: **Mã báo cáo** (font monospace, click mở báo cáo), **Tên báo cáo**, **Mô tả**, **Số template** (`Badge`), **Nút "Xem báo cáo"**.
  2. Bổ sung nhãn đếm `#catalog-meta` hiển thị `N báo cáo` có thuộc tính `aria-live="polite"`.
  3. Đổi loading spinner tròn sang `dmc.Skeleton` dạng dòng bảng mượt mà.
  4. Giữ nguyên toàn bộ logic tìm kiếm, lọc danh mục, toggle sao yêu thích và phân quyền nút `+ Đăng ký báo cáo`.
* **Test viết trước**: Cập nhật [`tests/unit/test_page_reports.py`](file:///d:/reconhub/tests/unit/test_page_reports.py) kiểm tra cấu trúc bảng phân nhóm, tương tác tìm kiếm và favorite.
* **Kiểm tra**: `uv run poe test` và Playwright test pass.

---

### Bước 3 — Tái cấu trúc Wizard Bước 3 (`/report-admin`): Master–Detail & Canvas layout 12 cột trực quan
* **Mục tiêu**: Xóa bỏ form cuộn dọc 1 cột dài dằng dặc; đưa về đúng chuẩn Master–Detail 2 cột có Canvas 12 cột trực quan như trong `preview.html`.
* **Tệp chỉnh sửa**:
  * [`app/ui/pages/report_admin.py`](file:///d:/reconhub/app/ui/pages/report_admin.py)
* **Nội dung thực hiện**:
  1. Tái cấu trúc `render_step3` thành bố cục 2 cột Master–Detail:
     * **Cột trái (Master & Canvas)**:
       * Bảng danh sách tham số dạng table nhỏ gọn (Mã, Nhãn, Kiểu, Bắt buộc, LOV, Nút chọn để sửa, Nút xóa).
       * **Canvas layout trực quan (`#param-canvas`)**: Render trực quan các hàng tìm kiếm (ví dụ: `Hàng 1: [Từ ngày (3/12)] [Đến ngày (3/12)] [Đơn vị (6/12)]`) với thẻ xanh `Hợp lệ` hoặc thẻ đỏ `Vượt X cột` khi tổng span > 12.
       * Nút `Tự sắp xếp đẹp` (`auto_layout`) điều chỉnh vị trí và span tự động.
     * **Cột phải (Detail Panel)**:
       * Panel độc lập cố định cấu hình LOV cho tham số đang chọn (`Setup LOV: <mã>`):
         * `STATIC`: Grid danh sách Value/Label, nút `+ Thêm giá trị`, checkbox cho chọn "Tất cả".
         * `SQL`: Textarea câu lệnh SQL, input cache seconds, nút kiểm tra LOV.
         * `LOOKUP`: Dropdown chọn danh mục hệ thống.
* **Test viết trước**: Cập nhật [`tests/unit/test_page_report_admin.py`](file:///d:/reconhub/tests/unit/test_page_report_admin.py) assert bố cục 2 cột, Canvas layout và panel LOV.
* **Kiểm tra**: `uv run poe test` xanh.

---

### Bước 4 — Cải thiện Xem báo cáo (`/reports/<id>`), Wizard Bước 4, Sticky Footer & Hoàn tất
* **Mục tiêu**: Bổ sung dòng Footer Total cho `/reports/<id>`, thêm dữ liệu mẫu xem trước cho Bước 4, cố định thanh điều hướng chân trang (Sticky Footer) và dọn dẹp CSS inline.
* **Tệp chỉnh sửa**:
  * [`app/ui/components/report_widgets.py`](file:///d:/reconhub/app/ui/components/report_widgets.py)
  * [`app/ui/pages/report_viewer.py`](file:///d:/reconhub/app/ui/pages/report_viewer.py)
  * [`app/ui/pages/report_admin.py`](file:///d:/reconhub/app/ui/pages/report_admin.py)
* **Nội dung thực hiện**:
  1. **Màn `/reports/<report_id>`**: Trong hàm `render_result_table`, thêm dòng chân bảng `dmc.TableTfoot` cho `Tổng cộng`: tính tổng trang hiện tại cho các cột có cờ `is_total=True`, áp dụng đúng định dạng số tiền `#,##0` và căn phải.
  2. **Bước 4 Wizard (Cấu hình cột)**: Bổ sung 2–3 dòng dữ liệu mẫu giả lập vào bảng xem trước (`_render_columns_preview`) để người dùng kiểm chứng trực tiếp format tiền tệ `#,##0`, ngày tháng `DD/MM/YYYY`, căn lề và độ rộng cột.
  3. **Thanh điều hướng Sticky Footer**: Tách nội dung bước vào khung cuộn riêng (`flex: 1`, `overflow: auto`), cố định hàng nút "Quay lại" và "Tiếp theo" ở đáy màn hình (`.wfoot`) theo quy tắc 41.
  4. **Dọn dẹp code**: Loại bỏ các style inline hardcoded, chuyển sang sử dụng tokens chuẩn.
* **Test viết trước**: Bổ sung test kiểm tra footer total, sticky footer và xem trước cột có dữ liệu.
* **Kiểm tra cuối cùng**: Chạy toàn bộ `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`, `uv run poe e2e`.

---

## Tiêu chí nghiệm thu (Chấp nhận khi)
- [ ] Màn danh sách `/report-admin` hiển thị đầy đủ bảng Fluent Compact, lọc tìm kiếm, menu thao tác 3 chấm, modal xác nhận tương tự `/batches`.
- [ ] Màn `/reports` hiển thị bảng gom nhóm danh mục theo `preview.html`, không dùng lưới card.
- [ ] Bảng kết quả `/reports/<id>` có dòng tổng cho các cột `is_total=True`.
- [ ] Bước 3 Wizard có Canvas layout 12 cột trực quan và panel LOV Master–Detail bên phải.
- [ ] Bước 4 Wizard có bảng xem trước dữ liệu mẫu thực tế.
- [ ] Thanh điều hướng Wizard cố định ở chân trang, không trôi theo cuộn nội dung.
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test`, `uv run poe e2e` xanh 100%.
