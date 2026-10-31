# 15-dashboard-compare — Dashboard đầy đủ và so sánh hai run

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ3
- Phụ thuộc: 12
- Nhánh git: feat/15-dashboard-compare

## Mục tiêu
Dashboard có thẻ chỉ số, tỉ lệ lệch theo template, việc cần làm; so sánh hai run cùng template/profile.

## Phạm vi
- Service dashboard.summary, compare_runs
- UI Dashboard đủ PRD C1; nút So với run trước

## Ngoài phạm vi
- —

## Thiết kế
- designs/components/Screen01-Dashboard, Screen06-RunResult

## Spec liên quan
- docs/PRD.md C1, C6

## Quyết định kiến trúc
- Theo AGENTS.md và spec 01.

## Các bước
### Bước 1 — Service
- Làm: Service
- Test viết trước: integration SQLite
- Kiểm tra: `uv run poe test`

### Bước 2 — UI Dashboard
- Làm: UI Dashboard
- Test viết trước: e2e
- Kiểm tra: `uv run poe e2e`

### Bước 3 — So sánh run
- Làm: So sánh run
- Test viết trước: 2 run khác dữ liệu → đếm đúng 3 nhóm
- Kiểm tra: `uv run poe test`

## Chấp nhận khi
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- —
