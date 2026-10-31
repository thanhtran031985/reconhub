# 12-export-history — Lịch sử run (xóa nhiều run), Dashboard tối thiểu, hoàn thiện MVP

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ2
- Phụ thuộc: 10, 11
- Nhánh git: feat/12-export-history

## Mục tiêu
Màn Lịch sử có lọc theo trạng thái kiểm tra và dữ liệu tạm, chọn nhiều run để xóa dữ liệu tạm (Admin); Dashboard tối thiểu; rà soát 4 trạng thái. Hết task: đưa lên UAT.

## Phạm vi
- pages/history.py theo PRD C7: cột Kiểm tra, Dữ liệu tạm; lọc; chọn nhiều + 'Xóa dữ liệu tạm' (Modal tổng hợp, gõ XOA)
- pages/dashboard.py: run gần đây + Chạy đối soát
- Rà soát 4 trạng thái, bàn phím, aria, 1366px
- docs/USER_GUIDE.md (tiếng Việt): đăng nhập, đăng ký template, chạy, xem, kiểm tra xong, xóa dữ liệu tạm

## Ngoài phạm vi
- Thẻ chỉ số, biểu đồ (15)

## Thiết kế
- designs/components/Screen07-History, Screen01-Dashboard

## Spec liên quan
- docs/PRD.md C1, C7

## Quyết định kiến trúc
- Theo AGENTS.md và spec 01.

## Các bước
### Bước 1 — Lịch sử + xóa nhiều run
- Làm: Lịch sử + xóa nhiều run
- Test viết trước: e2e lọc 'chưa kiểm tra'; chọn 2 run, xóa, cột Dữ liệu tạm thành Đã xóa; Operator không thấy nút xóa hàng loạt
- Kiểm tra: `uv run poe e2e`

### Bước 2 — Dashboard tối thiểu
- Làm: Dashboard tối thiểu
- Test viết trước: e2e
- Kiểm tra: `uv run poe e2e`

### Bước 3 — Rà soát chất lượng
- Làm: axe-core (hỏi trước khi cài), 1366px
- Test viết trước: e2e
- Kiểm tra: `uv run poe e2e`

### Bước 4 — Hướng dẫn sử dụng
- Làm: USER_GUIDE.md
- Test viết trước: —
- Kiểm tra: Đọc lại

## Chấp nhận khi
- [ ] Luồng e2e spec 07 mục 4 xanh
- [ ] Sẵn sàng UAT
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- —
