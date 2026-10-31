# 14-issue-handling — Xử lý chênh lệch

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ3
- Phụ thuộc: 12
- Nhánh git: feat/14-issue-handling

## Mục tiêu
Gán nguyên nhân, người xử lý (người dùng của ứng dụng), trạng thái cho dòng chênh lệch, từng dòng hoặc hàng loạt; run sau nhận diện dòng đã chấp nhận lệch.

## Phạm vi
- Revision Alembic bảng ISSUE + seed lý do
- Service issue, audit
- Executor ghép issue theo (template, profile, KEY_HASH)
- UI: khối xử lý trong Drawer, chọn nhiều dòng, page /issues

## Ngoài phạm vi
- —

## Thiết kế
- designs/components/Screen09-Issues, Screen06-RunResult (Drawer)

## Spec liên quan
- docs/PRD.md C9
- docs/specs/02 mục 6

## Quyết định kiến trúc
- Issue tách khỏi run

## Các bước
### Bước 1 — DB + service
- Làm: DB + service
- Test viết trước: integration SQLite + quyền
- Kiểm tra: `uv run poe test`

### Bước 2 — Liên kết run
- Làm: Liên kết run
- Test viết trước: G01 chạy 2 lần, lần 2 nhận ACCEPTED
- Kiểm tra: `uv run poe test`

### Bước 3 — UI
- Làm: UI
- Test viết trước: e2e
- Kiểm tra: `uv run poe e2e`

## Chấp nhận khi
- [ ] Xử lý hàng loạt 100 dòng < 2 giây
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- Danh mục nguyên nhân chuẩn do ai quản lý?
