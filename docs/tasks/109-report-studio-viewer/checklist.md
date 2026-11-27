# Checklist kiểm thử — 109-report-studio-viewer

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task `109-report-studio-viewer` (Report Studio UI, Persistence & Viewer / Per-Visual Export Integration).

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Migration `0019_report_studio` & `schema-introspect` | Thêm `RECON_RPT_VISUAL`, `RECON_RPT_VISUAL_FIELD`, mở rộng `RECON_RPT_TPL_VER` & `RECON_REPORT_RUN`; drift = 0; report cũ giữ nguyên | ✅ |
| **TC-FN-02** | Report Studio Center (`/report-studio`): Create / Open / Clone / Archive | Chỉ cho chọn `RECON_RPT_MODEL_VER` đang `ACTIVE` (chặn `DRAFT`); Clone không xuất bản tự động; Archive không xóa dữ liệu DB | ✅ |
| **TC-FN-03** | Fields & Measures Panel: Search, Checkbox, Drag/Drop, Invalid Drop | Search metadata không query DB và tự expand nhóm; ẩn field `HIDDEN`; invalid drop từ chối kèm lý do và giữ nguyên visual | ✅ |
| **TC-FN-04** | Multi-visual 12-col Canvas: Add / Select / Move / Resize (`GRID_SPAN`) / Duplicate / Delete | Đổi width 3/4/6/8/12 cột và thứ tự không gây chồng lấn; Duplicate giữ bindings nhưng không nhân bản report-level filter; Delete chỉ xóa trên Draft | ✅ |
| **TC-FN-05** | 5 loại Visual V1 (`Table`, `Matrix`, `KPI`, `Bar`, `Line`) & Đổi loại visual | Render đúng dữ liệu; Matrix tổng hợp phía server; đổi sang loại không tương thích hiện preview field bị loại và hỏi xác nhận | ✅ |
| **TC-FN-06** | Data Wells, Aggregation Dropdown & Format Panel | Dropdown Aggregation đổi đúng theo datatype/policy measure; đổi tiêu đề/format cập nhật preview tức thì; không lưu Plotly figure JSON vào DB | ✅ |
| **TC-FN-07** | Report/Visual Filters & Filter Preview trên Canvas | Tái sử dụng `RECON_RPT_PARAM`/LOV; đổi filter preview trên canvas không ghi đè default đã lưu; debounce + `request_seq` bỏ qua response cũ | ✅ |
| **TC-FN-08** | Preview, Validate Report, Save Draft & Publish | Validate focus đúng visual lỗi; Save Draft chống ghi đè `ROW_VERSION`; Publish pin cứng `MODEL_VERSION_ID`, yêu cầu Change Note & ghi audit | ✅ (service + UI) |
| **TC-FN-09** | Impact Analysis nối ngược sang Model Studio | Sửa/ẩn field đang dùng trong `RECON_RPT_VISUAL` → Model Studio Impact Analysis liệt kê đúng report & visual bị ảnh hưởng | ✅ |
| **TC-FN-10** | Report Viewer (`/reports/<id>`) & Xuất từng visual (Per-Visual Export) | Hiển thị đủ thanh tham số/preset + đa visual; bấm Xuất XLSX/CSV trên một visual tạo `RECON_REPORT_RUN` gắn `VISUAL_ID` và worker xuất file đúng dữ liệu | ✅ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Layout Desktop `1366×768` & `1440×900` (Light & Dark mode) | `scrollHeight <= innerHeight`, `scrollWidth <= innerWidth`; 3 panel cuộn nội bộ; biểu đồ Plotly & `dag.AgGrid` khớp theme `tokens.css` | ✅ |
| **TC-UI-02** | 4 trạng thái dữ liệu trên Report Studio & Viewer | Đủ Loading skeleton, Empty report/Empty visual guidance, No data, Query Error (safe message + Thử lại + giữ cấu hình visual) | ✅ |
| **TC-UI-03** | Mobile (`390×844`) | `/reports/<id>` xem & lọc đa visual xếp dọc không tràn ngang; `/report-studio/<id>/edit` hiển thị chế độ giới hạn rõ ràng | ✅ |
| **TC-UI-04** | Accessibility & Console sạch | Kéo thả có nút/keyboard fallback (`+ Thêm trường`); mọi nút icon có tooltip + `aria-label`; zero lỗi JS console & duplicate callback ID | ✅ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy strict | ✅ |
| **TC-REG-03** | `uv run poe schema-introspect --check` | Manifest và history đồng bộ 100% | ✅ |
| **TC-REG-04** | `uv run poe test-engine` | Toàn bộ unit/integration test mới và Reporting Core cũ (`CUSTOM_SQL`/`VIEW`/`TABLE`) xanh | ✅ |
| **TC-REG-05** | `uv run poe e2e` | Toàn bộ E2E Playwright (kể cả `test_report_studio_e2e.py`) xanh, kèm ảnh chụp kiểm chứng | ✅ |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | `uv run poe security-check` | Toàn bộ kiểm tra bảo mật tự động đạt | ✅ |
| **TC-SEC-02** | Không arbitrary SQL / Không lộ bí mật | Trình duyệt chỉ gửi intent metadata; lỗi SQL không lộ raw stacktrace/credential; tab `SQL thực hiện` chỉ `ADMIN` thấy | ✅ |
| **TC-SEC-03** | Phân quyền Viewer & Export | Chưa login → `/login`; không có menu `report_studio` → `/forbidden`; export kiểm tra `owner_filter` (`CREATED_BY`) | ✅ |
