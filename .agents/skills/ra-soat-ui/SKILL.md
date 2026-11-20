---
name: ra-soat-ui
description: So sánh các màn đã code với designs/components ở 2 kích thước, 4 trạng thái và chế độ tối theo Rubric chuẩn. Dùng khi người dùng nói "rà soát giao diện", "so với thiết kế" hoặc gọi /ra-soat-ui.
---

# Rà soát giao diện (ReconHub UI/UX Audit)

> [!NOTE]
> **Ghi chú nguồn gốc:** Bộ tiêu chuẩn kiểm toán giao diện (Audit Rubric) bên dưới được nghiên cứu, học tập và chắt lọc từ hệ sinh thái thiết kế **Meta Astryx** ([github.com/meta/astryx](https://github.com/meta/astryx)), sau đó được bản địa hóa và chuẩn hóa theo phong cách **Fluent Compact + Master–Detail** trên nền tảng Dash Mantine Components của ReconHub.

---

## 1. Quy trình thực hiện rà soát

1. Khởi động môi trường kiểm thử: `uv run poe dev`, đăng nhập bằng user quản trị hoặc tài khoản kiểm thử từ `uv run poe db-seed`.
2. Mở màn hình cần rà soát bằng trình duyệt tự động (Playwright hoặc Antigravity Browser) tại 2 kích thước chuẩn:
   - **1440×900** (Desktop chuẩn rộng).
   - **1366×768** (Laptop văn phòng, giới hạn chiều cao tối thiểu).
3. Kiểm tra lần lượt cả 2 giao diện: **Chế độ Sáng (Light Theme)** và **Chế độ Tối (Dark Theme)**.
4. Kiểm tra đầy đủ 4 trạng thái dữ liệu (Bình thường, Đang tải, Trống, Lỗi).
5. Mở tệp thiết kế tham chiếu `designs/components/<ScreenNN>/preview.html` (hoặc `preview-fluent.html`) để đối chiếu mật độ và bố cục.
6. Chụp ảnh màn hình lưu vào `tests/e2e/__screens__/` (đặt tên dạng `<NN>-<page>-<trạng_thái>-<kích_thước>.png`).
7. Đánh giá chất lượng màn hình dựa trên **Bảng kiểm định 6 tiêu chuẩn (Audit Rubric)** bên dưới.
8. Lập bảng tổng hợp kết quả (Màn | Tiêu chí | Hiện trạng | Mức độ | Đề xuất sửa). **Không tự ý sửa code giao diện khi người dùng chưa xác nhận mục cần sửa.**

---

## 2. Bảng kiểm định 6 tiêu chuẩn UI/UX (ReconHub Audit Rubric)

Mọi màn hình trong ReconHub khi được rà soát phải được chấm điểm theo 6 tiêu chuẩn cốt lõi sau:

| Tiêu chuẩn | Nội dung kiểm tra bắt buộc | Tiêu chí Đạt |
|---|---|---|
| **1. Token Integrity (Tính toàn vẹn Token)** | Tuyệt đối không hardcode mã màu hex (`#...`) hay kích thước pixel cứng (`px`) trong trang/component. Toàn bộ màu sắc, padding, border-radius phải dùng semantic token từ `designs/tokens.json` (biến CSS `designs/tokens.css` hoặc `app/ui/theme.py`). | 100% sử dụng token (`primary`, `surface`, `line`, `ink`, `p="sm"`, `radius="sm"`). |
| **2. Frame-First & No-Scroll (Khung màn hình không cuộn)** | Ở màn hình máy tính $\ge$ 1366×768, trang tuyệt đối **KHÔNG cuộn toàn cục** (`document.documentElement.scrollHeight <= innerHeight`). Chỉ cho phép cuộn nội bộ trong bảng (`dag.AgGrid`) hoặc panel thuộc tính (`dmc.ScrollArea`). Vùng chính dùng flex 1 và `min-height: 0`. | Không xuất hiện thanh cuộn trình duyệt của cả trang web. |
| **3. Information Density (Mật độ thông tin Fluent Compact)** | Các controls (TextInput, Select, Button, DatePicker) thống nhất dùng `size="xs"` hoặc `"sm"`. Khoảng cách `gap="xs"`, padding `p="sm"`. Dữ liệu nhiều dòng phải hiển thị dạng bảng có vạch ngăn (table/grid), không dàn trải card; số tiền/định lượng căn phải và dùng font `tabular-nums`. | Giao diện gọn gàng, chứa nhiều thông tin hữu ích mà không gây rối mắt. |
| **4. State Completeness (Đầy đủ 4 trạng thái)** | Mọi khối dữ liệu phải xử lý đầy đủ 4 trạng thái: (1) Bình thường, (2) Đang tải (`dmc.Skeleton` đúng kích thước), (3) Trống (`EmptyState` nêu rõ lý do + 1 hành động điều hướng), (4) Lỗi (`dmc.Alert` thông báo sự cố, giữ lại dữ liệu cũ nếu có + nút "Thử lại"). | Không có trạng thái trống trơn hoặc trang bị sập/đơ khi API lỗi. |
| **5. Micro-interactions & A11y (Tương tác & Tiếp cận)** | Độ tương phản chữ/nền đạt chuẩn WCAG AA ($\ge$ 4.5:1). Viền Focus hiển thị rõ ràng khi duyệt bằng phím Tab. Các nút chỉ có icon bắt buộc có `aria-label` và bọc `dmc.Tooltip`. Hover mượt mà, không làm giật khung layout. | Thao tác bằng phím thuận tiện, chỉ dẫn trực quan rõ ràng. |
| **6. Dark Mode Consistency (Đồng nhất chế độ tối)** | Khi chuyển sang chế độ tối (Dark Theme): màu nền không bị đen tuyệt đối (`#000000`), phân tầng rõ rệt giữa `surface` và `surface-2`, viền `line` mảnh nhẹ, chữ không bị chìm hoặc lóa mắt. | Trải nghiệm dễ chịu, dịu mắt trong điều kiện thiếu sáng. |

---

## 3. Mẫu bảng báo cáo rà soát (Audit Report Template)

Khi hoàn thành rà soát, xuất báo cáo cho người dùng theo mẫu sau:

```markdown
### Báo cáo rà soát giao diện: <Tên màn hình> (<Đường dẫn URL>)

- **Kích thước kiểm thử:** 1440×900 và 1366×768
- **Chế độ hiển thị:** Sáng (Light) & Tối (Dark)
- **Ảnh chụp bằng chứng:** `tests/e2e/__screens__/...`

| Tiêu chuẩn | Hiện trạng thực tế | Đánh giá | Đề xuất cải tiến |
|---|---|:---:|---|
| 1. Token Integrity | | ✅ Đạt / ⚠️ Cần sửa | |
| 2. Frame-First & No-Scroll | | ✅ Đạt / ⚠️ Cần sửa | |
| 3. Information Density | | ✅ Đạt / ⚠️ Cần sửa | |
| 4. State Completeness | | ✅ Đạt / ⚠️ Cần sửa | |
| 5. Micro-interactions & A11y | | ✅ Đạt / ⚠️ Cần sửa | |
| 6. Dark Mode Consistency | | ✅ Đạt / ⚠️ Cần sửa | |

**Kết luận chung:** (Đạt chuẩn / Cần tinh chỉnh theo danh sách trên)
```
