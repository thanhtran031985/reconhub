# Checklist kiểm thử — 107-model-studio-ui

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task `107-model-studio-ui` (Model Center & Semantic Model Studio UI).

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Truy cập `/report-models` theo phân quyền | Chưa login → `/login`; không có menu `report_model` → `/forbidden`; ADMIN/TEMPLATE_OWNER vào bình thường | ✅ |
| **TC-FN-02** | Model Center: Create / Open / Clone / Archive / Impact Analysis | Tạo mới mở Draft; Clone sinh Draft độc lập; Impact Analysis mở Drawer liệt kê dependency; Archive hiện confirm & không xóa physical data | ✅ |
| **TC-FN-03** | Model Explorer: Search & `+ Thêm bảng` | Search khớp column tự mở bảng và highlight; Drawer `+ Thêm bảng` lọc schema/TABLE/VIEW và khóa bảng đã có trong model | ✅ |
| **TC-FN-04** | Canvas: Zoom In/Out, Fit, Auto Layout (Star Schema), Drag Card | Pan/zoom mượt không làm cuộn cả trang; Auto Layout đặt Fact trung tâm + có Undo; Drag card lưu tọa độ vào Draft | ✅ |
| **TC-FN-05** | Tạo & Sửa quan hệ (Drag column-to-column & nút `+ Tạo quan hệ`) | Mở Relationship Properties tạm, chạy Kiểm tra quan hệ (Tầng 1 & Tầng 2), `Áp dụng thay đổi` vẽ lại SVG và đánh dấu dirty; Xóa qua confirm | ✅ |
| **TC-FN-06** | Table & Field Properties & Measure Studio | Bắt buộc Grain cho Fact; khóa `SUM` trên Text/Date; bật Virtual Date Hierarchy; tạo Simple & AST Calculated Measure thành công | ✅ |
| **TC-FN-07** | Validation Issue Navigation, Save Draft Concurrency & Publish | Click issue từ `Kiểm tra model` focus đúng đối tượng; xung đột `ROW_VERSION` hiện cảnh báo không ghi đè; Publish yêu cầu Change Note & hiển thị Diff | ✅ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Tuân thủ `dmc.AppShell` & Fluent Compact (`1366×768`, `1440×900`) | Đủ 3 panel cuộn nội bộ; `document.documentElement.scrollHeight <= innerHeight` và `scrollWidth <= innerWidth`; không dùng top-tabbar thay AppShell | ✅ |
| **TC-UI-02** | Chế độ Sáng / Tối & Token CSS | Card, đường nối SVG, chip `PK`/`FK` dùng biến CSS trong `tokens.css`; `PK`/`FK` phân biệt bằng cả text badge lẫn icon/màu | ✅ |
| **TC-UI-03** | 4 trạng thái dữ liệu (Loading, Empty, Error+Retry, Data) | Đủ `dmc.Skeleton`, `empty_state` (+ Thêm bảng / Xóa bộ lọc), `dmc.Alert` giữ dữ liệu cũ + Thử lại | ✅ |
| **TC-UI-04** | Responsive Mobile (`390×844`) | Không tràn ngang (`scrollWidth <= innerWidth`); Model Studio hiển thị chế độ xem + thông báo chỉnh sửa trên desktop | ✅ |
| **TC-UI-05** | Accessibility & Console sạch | Mọi icon button có tooltip + `aria-label`; `aria-live="polite"` cho validation; không lỗi JS console hay duplicate callback ID | ✅ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy strict | ✅ |
| **TC-REG-03** | `uv run poe test-engine` | Toàn bộ test liên quan xanh (`37/37` unit Model Studio / Semantic Model, `40/40` E2E; toàn bộ `test-engine`: `2261 passed`, `18 failed` có sẵn ngoài phạm vi task 107) | ✅ |
| **TC-REG-04** | `uv run pytest tests/e2e/test_model_studio_e2e.py -v` | Toàn bộ kịch bản E2E Playwright xanh kèm ảnh chụp màn hình 3 viewport | ✅ |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | `uv run poe security-check` | Toàn bộ kiểm tra bảo mật tự động đạt | ✅ |
| **TC-SEC-02** | Bảo vệ credential & metadata | Không lộ mật khẩu Data Source trong `dcc.Store`, HTML DOM hay console log | ✅ |
| **TC-SEC-03** | Read-only trên DB nguồn | Mọi thao tác trên Model Studio không chạy DDL/DML tới Oracle nguồn | ✅ |
