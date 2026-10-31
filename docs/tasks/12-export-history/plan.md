# Kế hoạch thực hiện — 12-export-history

## Mục tiêu
Hoàn thành màn Lịch sử run (`/history`, Screen07) với bộ lọc đa tiêu chí, chọn nhiều run để xóa dữ liệu tạm (phân quyền Admin, yêu cầu gõ XOA); hoàn thành màn Dashboard tối thiểu (`/`, Screen01) hiển thị KPI và run gần đây; rà soát chất lượng 4 trạng thái, ARIA, bàn phím, kích thước 1366px; và biên soạn hướng dẫn sử dụng `docs/USER_GUIDE.md` sẵn sàng cho UAT.

---

## Các bước triển khai

### Bước 1 — Lịch sử run + Xóa nhiều run (Screen07)
- **Cập nhật Service & Schema:**
  - Bổ sung `is_temp_purged: bool | None` và `filename: str | None` vào `RunListFilter` (`app/schemas/run.py`).
  - Cập nhật `list_runs` (`app/services/run_service.py`) join `recon_file` và `recon_run_summary` để trả thêm `filename`, `file_size`, `p_from`, `p_to`, `checked_by`, `match_pct`.
- **Giao diện `app/ui/pages/history.py` (Screen07):**
  - Tiêu đề H1: "Lịch sử: ... run trong kỳ", phụ đề "Truy vết file gốc, version, khoảng tìm kiếm, người chạy. Chọn nhiều run để xóa dữ liệu tạm (Admin)."
  - Bộ lọc: Template, Kiểm tra (Tất cả, Chưa kiểm tra, Đã kiểm tra), Dữ liệu tạm (Tất cả, Còn, Đã xóa), Người chạy, Tên file.
  - 4 trạng thái: Loading (skeleton rows), Empty ("Chưa có run nào"), Error (Alert lỗi + Thử lại), Normal (bảng lịch sử).
  - Bảng lịch sử:
    - Checkbox từng dòng: chỉ Admin được tích, disabled nếu run đã xóa dữ liệu tạm. Checkbox "Chọn tất cả" trên header.
    - Operator/Viewer: ẩn cột checkbox và thanh xóa hàng loạt.
    - Cột thông tin: Run ID, Thời gian chạy, Template (ver), Profile, Khoảng tìm kiếm, File gốc, Người chạy, Trạng thái (chip có icon), % Khớp, Kiểm tra, Dữ liệu tạm (Còn / Đã xóa ngày), Thao tác (Xem, Tải file gốc nếu còn, Chạy lại).
  - Thanh chọn hàng loạt: "Đã chọn N run" kèm nút "Xóa dữ liệu tạm" (màu đỏ).
  - Modal xác nhận xóa hàng loạt: Tổng hợp số run, dung lượng ước tính giải phóng, danh sách "Sẽ xóa / Giữ lại", cảnh báo về run chưa kiểm tra, ô nhập xác nhận bắt buộc "XOA", gọi `purge_runs(ctx, selected_run_ids)`.
- **Test:** Viết `tests/unit/test_page_history.py` và cập nhật E2E test.

### Bước 2 — Dashboard tối thiểu (Screen01)
- **Giao diện `app/ui/pages/dashboard.py` (thay thế placeholder `home.py`):**
  - Tiêu đề H1: "Tháng MM/YYYY: N run, M chưa kiểm tra", phụ đề "Tổng quan đối soát. Run gần nhất lúc ...", Nút "Chạy đối soát" (dẫn sang `/runs/new`).
  - Banner cảnh báo dữ liệu tạm (chỉ Admin khi vượt ngưỡng dung lượng hoặc có run quá hạn): "Dữ liệu tạm X GB, Y run giữ quá Z ngày. [Xem và xóa](/data-sources?tab=storage)".
  - 4 thẻ KPI:
    1. Run trong kỳ (tổng số run, chi tiết hoàn thành / lỗi / đang chạy)
    2. Tỉ lệ khớp trung bình (% khớp theo nhóm)
    3. Chưa kiểm tra (số run chưa kiểm tra, dung lượng tạm)
    4. Việc của tôi (số run của người dùng hiện tại đang chờ kiểm tra hoặc lỗi)
  - Thẻ "Run gần đây": Danh sách run mới nhất kèm trạng thái, tỷ lệ khớp, trạng thái kiểm tra, link "Xem", nút "Xem lịch sử" dẫn sang `/history`.
  - 4 trạng thái: Loading, Empty, Error, Normal.
- **Test:** Viết `tests/unit/test_page_dashboard.py`.

### Bước 3 — Rà soát chất lượng & E2E spec 07 mục 4
- Rà soát bàn phím (tabindex, focus visible), ARIA attributes (`aria-label`, `aria-busy`, `role="alert"`, `aria-modal`), font mono cho mã/ngày giờ, bố cục responsive 1366px.
- Đảm bảo toàn bộ luồng E2E spec 07 mục 4 xanh:
  - Đăng nhập, Data Source, Template, New Run, Run Result, History, Bulk Purge, Dashboard.
- Kiểm tra `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`.

### Bước 4 — Hướng dẫn sử dụng (`docs/USER_GUIDE.md`)
- Soạn thảo tài liệu hướng dẫn sử dụng hoàn chỉnh bằng tiếng Việt có dấu:
  1. Giới thiệu tổng quan hệ thống ReconHub
  2. Đăng nhập và quản lý tài khoản
  3. Cấu hình Data Source kết nối Oracle
  4. Đăng ký Template đối soát (5 bước Wizard)
  5. Thực hiện Chạy đối soát (Upload Excel, chọn tham số, kiểm tra trước)
  6. Xem kết quả đối soát, tra cứu dòng lệch qua Drawer
  7. Xác nhận "Đã kiểm tra xong" và tải báo cáo Excel
  8. Lịch sử run và quản lý / xóa dữ liệu tạm
  9. Phân quyền và vai trò người dùng (Admin, Template Owner, Operator, Viewer)
