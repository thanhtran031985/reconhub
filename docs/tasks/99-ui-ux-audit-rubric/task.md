# 99-ui-ux-audit-rubric — Chuẩn hóa tiêu chí rà soát UI/UX (Astryx Rubric) và tinh chỉnh giao diện Mail Template Studio

- Ngày tạo: 2026-11-19
- Giai đoạn: GĐ3
- Phụ thuộc: 98
- Nhánh git: feat/99-ui-ux-audit-rubric

## Mục tiêu
1. Chuẩn hóa quy trình rà soát giao diện trong skill `.agents/skills/ra-soat-ui/SKILL.md` bằng bộ tiêu chuẩn kiểm toán UI/UX 6 tiêu chí (ReconHub Audit Rubric) chắt lọc từ Meta Astryx và chuẩn Fluent Compact.
2. Thực nghiệm rà soát và tinh chỉnh giao diện trang Mail Template Studio (`/mail-template-studio`), ghi lại ảnh chụp đối chiếu Trước vs. Sau ở 2 kích thước chuẩn (1440×900 và 1366×768) trên cả 2 chế độ Sáng (Light) và Tối (Dark).

## Phạm vi
- Cập nhật tài liệu skill `.agents/skills/ra-soat-ui/SKILL.md` với bảng rubric 6 tiêu chuẩn chi tiết: Token Integrity, Frame-First & No-Scroll, Information Density, State Completeness, Micro-interactions & A11y, Dark Mode Consistency.
- Chụp ảnh trạng thái ban đầu (Before) của `/mail-template-studio` ở 1440×900 và 1366×768 (Sáng & Tối).
- Tinh chỉnh giao diện trang `app/ui/pages/mail_template_studio.py` và CSS liên quan:
  - Thêm `EmptyState` chuẩn cho Panel Thuộc tính khi chưa click chọn component trên Canvas.
  - Tinh gọn mật độ form fields Panel Phải (giảm padding dư thừa, đồng nhất `size="xs"`, hỗ trợ cuộn êm).
  - Tinh chỉnh khung Email Canvas với viền mô phỏng hộp thư sắc nét, phân tách rõ Header và Body.
  - Đảm bảo 100% tuân thủ nguyên tắc không cuộn trang ở $\ge$ 1366px (`scrollHeight <= innerHeight`).
- Chụp ảnh trạng thái sau khi sửa (After), lập bảng đối chiếu Trước vs. Sau.

## Ngoài phạm vi
- Không cài đặt các thư viện React hay NPM của Meta Astryx (giữ nguyên stack Python Dash + Mantine DMC 2.x).
- Không thay đổi nghiệp vụ backend, event registry hoặc schema DB của Mail Template Studio đã hoàn thành ở Task 98.

## Thiết kế
- `designs/components/Screen-MailTemplateStudio/preview.html`
- `designs/reference/preview-fluent.html`

## Spec liên quan
- `.agents/rules/ui-dash.md`
- `docs/DESIGN_SYSTEM.md`

## Quyết định kiến trúc
- Ghi nhận trong `decisions.md`.

## Các bước
### Bước 1 — Cập nhật skill ra-soat-ui với ReconHub Audit Rubric 6 tiêu chí
- Làm: Soạn thảo và cập nhật bảng tiêu chuẩn kiểm toán vào `.agents/skills/ra-soat-ui/SKILL.md`.
- Kiểm tra: File markdown chuẩn format, có đầy đủ thang điểm và hướng dẫn đánh giá.

### Bước 2 — Chụp ảnh đối chiếu trạng thái ban đầu (Before)
- Làm: Chạy server dev, dùng trình duyệt tự động chụp toàn cảnh `/mail-template-studio` ở 1440×900 và 1366×768 (Light/Dark).
- Lưu ảnh vào: `tests/e2e/__screens__/99-mail-studio-before-*.png`.
- Kiểm tra: Ảnh chụp rõ nét, bao quát đủ 3 panel.

### Bước 3 — Tinh chỉnh giao diện trang Mail Template Studio theo Rubric
- Làm: Thêm EmptyState cho panel thuộc tính, chuẩn hóa mật độ controls, viền canvas và no-scroll.
- Test viết trước: Bổ sung test kiểm tra render EmptyState và không lỗi callbacks trong `tests/unit/test_page_mail_template_studio.py`.
- Kiểm tra: `uv run poe test` và `uv run poe typecheck` xanh.

### Bước 4 — Chụp ảnh trạng thái hoàn thiện (After) và Báo cáo đối chiếu
- Làm: Chụp ảnh màn hình mới (After) tại cùng các góc nhìn và kích thước.
- Lập bảng so sánh Trước vs. Sau và báo cáo nghiệm thu.

## Chấp nhận khi
- [ ] Bảng tiêu chuẩn kiểm toán 6 tiêu chí được cập nhật vào `.agents/skills/ra-soat-ui/SKILL.md`.
- [ ] Có đầy đủ ảnh chụp Before và After đối chiếu trực quan.
- [ ] Trang `/mail-template-studio` có EmptyState panel thuộc tính và tuân thủ chuẩn No-Scroll ở 1366×768.
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh 100%.

### Data Model Impact
- [x] Task không thay đổi database schema.
