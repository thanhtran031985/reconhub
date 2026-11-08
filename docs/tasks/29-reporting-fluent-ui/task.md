# 29-reporting-fluent-ui — Đồng bộ giao diện Báo cáo động theo thiết kế chuẩn Screen16 preview.html & Mẫu /batches

- Ngày tạo: 2026-11-08
- Giai đoạn: GĐ3
- Phụ thuộc: 27, 28
- Nhánh git: feat/29-reporting-fluent-ui

## Mục tiêu
1. Chuẩn hóa màn hình danh sách Quản trị báo cáo (`/report-admin`) theo đúng mẫu kiến trúc và trải nghiệm của màn hình Danh sách Bộ đối soát (`/batches`): đầy đủ tìm kiếm, lọc trạng thái/nhóm, bảng Fluent Compact, menu thao tác 3 chấm, modal xác nhận và thông báo toast.
2. Đồng bộ giao diện toàn bộ module Dynamic Reporting (Trung tâm báo cáo, Xem báo cáo, Wizard 6 bước và Lịch sử báo cáo) bám sát 100% bản thiết kế chuẩn Fluent Compact + Master–Detail trong `designs/components/Screen16-DynamicReporting/preview.html` và quy chuẩn `.agents/rules/ui-dash.md`.

## Phạm vi
- **Màn `/report-admin` (Danh sách Báo cáo đã đăng ký - tương tự `/batches`)**:
  - Header với nút Làm mới và nút `+ Báo cáo mới`.
  - Command bar: Tìm kiếm theo mã hoặc tên báo cáo, Select lọc trạng thái (ACTIVE / DRAFT / ARCHIVED), Select lọc nhóm danh mục (Tài chính, Kế toán, Vận hành), text đếm số lượng `N báo cáo`.
  - Bảng danh sách chuẩn Fluent Compact (`dmc.Table` + `dmc.TableScrollContainer`): Mã (mono, link mở sửa), Tên & Mô tả (Stack), Nhóm (Badge), Trạng thái (`status_chip`), Số template & Version, Chủ sở hữu, Menu thao tác 3 chấm (Sửa, Thêm template, Clone version, Lưu trữ, Xóa).
  - Trạng thái: Skeleton loading, Empty state, Error alert có nút Thử lại, Toast notifications, Modal xác nhận (`modal_confirm`).
- **Màn `/report-admin` (Wizard 6 bước cấu hình template)**:
  - Tái cấu trúc Bước 3 (Tham số & LOV) thành bố cục Master–Detail: Canvas trực quan layout 12 cột ở bên trái + Panel cấu hình LOV chuyên biệt bên phải.
  - Bổ sung dữ liệu mẫu thực tế vào bảng xem trước (preview) ở Bước 4.
  - Cố định thanh điều hướng (Sticky Footer) cho Wizard chứa nút "Quay lại" và "Tiếp theo".
- **Màn `/reports` (Trung tâm báo cáo)**: Chuyển từ lưới card sang bảng gom nhóm danh mục theo `preview.html`, cập nhật loading skeleton.
- **Màn `/reports/<report_id>` (Xem báo cáo)**: Bổ sung dòng Footer Total cho các cột có `is_total=True`, căn chỉnh độ rộng/lề số chuẩn.

## Ngoài phạm vi
- Không thay đổi schema DB hay logic nghiệp vụ của các service Task 21–26 (đã hoàn thiện và test xanh).
- Không phá vỡ các API contract hoặc quyền truy cập đã thiết lập ở Task 28.

## Thiết kế
- `designs/components/Screen16-DynamicReporting/preview.html` (Nguồn sự thật cho UI/UX Dynamic Reporting)
- Mẫu giao diện tham chiếu: `app/ui/pages/batch_defs.py` (`/batches`)
- `designs/reference/preview-fluent.html` (Mẫu đối chiếu Fluent Compact toàn hệ thống)
- `.agents/rules/ui-dash.md` (Quy tắc giao diện Dash Mantine)

## Spec liên quan
- `docs/specs/12_dynamic_reporting.md`
- `docs/specs/12_dynamic_reporting_tables.md`

## Quyết định kiến trúc
- Màn `/report-admin` danh sách: Tái dùng nguyên mẫu component và layout của `batch_defs.py`: `command_bar`, `status_chip`, `modal_confirm`, `TableScrollContainer`, menu 3 chấm.
- Màn `/reports`: Dùng `dmc.Table` có header nhóm phân loại (`<tr class="grp">` Tài chính, Kế toán, Vận hành) đúng thiết kế `.rlist` trong `preview.html`.
- Bước 3 Wizard: Chia 2 cột Master–Detail (Trái: Danh sách tham số + Canvas 12 cột; Phải: Panel cấu hình LOV). Giữ nguyên các hàm service xử lý backend.
- Wizard Navigation: Bọc nội dung bước trong container cuộn riêng (`flex: 1`, `overflow: auto`), cố định hàng nút điều hướng ở footer đáy panel (`.wfoot`).

## Các bước
### Bước 1 — Chuẩn hóa màn danh sách Quản trị báo cáo (`/report-admin`) tương tự `/batches`
- Làm: Dựng lại màn danh sách báo cáo trên `/report-admin` theo kiến trúc `batch_defs.py`:
  - Header: nút Làm mới (ActionIcon refresh) + nút `+ Báo cáo mới` (primary button).
  - Command bar: Search input + Filter status select + Filter category select + nhãn đếm `N báo cáo`.
  - Bảng Fluent Compact: Mã (mono link), Tên & Mô tả, Nhóm, Trạng thái (`status_chip`), Số template & Version, Chủ sở hữu, Cột thao tác (ActionIcon sửa + Menu dropdown 3 chấm: Sửa, Clone, Lưu trữ, Xóa).
  - Trạng thái Skeleton loading, Empty state, Error alert + Thử lại, Toast notifications, Modal xác nhận xóa/lưu trữ.
- Test viết trước: Cập nhật `tests/unit/test_page_report_admin.py` kiểm tra command bar, bộ lọc, bảng danh sách và menu thao tác.
- Kiểm tra: `uv run poe test` xanh.

### Bước 2 — Đồng bộ Trung tâm báo cáo (`/reports`) theo Fluent Compact
- Làm: Chuyển đổi hiển thị danh sách từ lưới Card sang Bảng gom nhóm theo danh mục (`.rlist`), mã font mono, nút xem báo cáo; chuyển loading spinner sang `dmc.Skeleton`.
- Test viết trước: Cập nhật `tests/unit/test_page_reports.py` kiểm tra cấu trúc bảng phân nhóm, tìm kiếm, lọc và toggle favorite.
- Kiểm tra: `uv run poe test` và Playwright test pass.

### Bước 3 — Tái cấu trúc Wizard Bước 3 (`/report-admin`): Master–Detail & Canvas layout 12 cột trực quan
- Làm: Bố cục Bước 3 thành 2 cột Master–Detail:
  - Cột trái: Bảng tham số nhỏ gọn + Canvas layout 12 cột hiển thị các khối span có tag Hợp lệ / Vượt cột (màu đỏ) + nút "Tự sắp xếp đẹp".
  - Cột phải: Panel cấu hình LOV (STATIC, SQL, LOOKUP) cho tham số đang chọn.
- Test viết trước: Cập nhật `tests/unit/test_page_report_admin.py` kiểm tra rendering Canvas và panel LOV.
- Kiểm tra: `uv run poe test`.

### Bước 4 — Cải thiện Xem báo cáo (`/reports/<id>`), Wizard Bước 4, Sticky Footer & Hoàn tất
- Làm:
  - Bổ sung dòng Footer Total cho các cột `is_total=True` trong `render_result_table` ([`app/ui/components/report_widgets.py`](file:///d:/reconhub/app/ui/components/report_widgets.py)).
  - Bổ sung dữ liệu mẫu vào xem trước layout cột ở Bước 4 Wizard.
  - Cố định thanh nút điều hướng (Sticky Footer) cho Wizard.
  - Dọn dẹp inline styles hardcode.
- Test viết trước: Bổ sung test kiểm tra footer total, sticky footer và preview cột có dữ liệu.
- Kiểm tra cuối cùng: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`, `uv run poe e2e`.

## Chấp nhận khi
- [ ] Màn danh sách `/report-admin` hiển thị đầy đủ bảng Fluent Compact, lọc tìm kiếm, menu thao tác 3 chấm, modal xác nhận tương tự `/batches`.
- [ ] Màn `/reports` hiển thị bảng gom nhóm danh mục chuẩn theo `preview.html`, không dùng lưới card.
- [ ] Bảng kết quả `/reports/<id>` có dòng tổng cho các cột `is_total=True`.
- [ ] Bước 3 Wizard có Canvas layout 12 cột trực quan và panel LOV Master–Detail bên phải.
- [ ] Bước 4 Wizard có bảng xem trước dữ liệu mẫu thực tế.
- [ ] Thanh điều hướng Wizard cố định ở chân trang, không trôi theo cuộn nội dung.
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test`, `uv run poe e2e` xanh.

## Câu hỏi mở
- Không. Bám sát thiết kế `preview.html` và mẫu giao diện `batch_defs.py`.
