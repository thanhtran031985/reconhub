# 10-new-run-ui — Màn Chạy đối soát

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ2
- Phụ thuộc: 07, 08
- Nhánh git: feat/10-new-run-ui

## Mục tiêu
Operator upload file, nhận diện template, nhập khoảng ngày giờ (bắt buộc) và tham số theo template, xem precheck, xác nhận PROD, chạy và theo dõi tiến độ.

## Phạm vi
- pages/new_run.py theo PRD C5: dcc.Upload, detect, profile, DateTimePicker Từ/Đến + chọn nhanh, ô tham số sinh động theo params, áp khoảng cho Excel, Data Source, measures
- precheck (debounce), số dòng ngoài khoảng, control total, cảnh báo trùng
- Modal PROD; tiến độ bằng dcc.Interval; xong chuyển /runs/<id>

## Ngoài phạm vi
- Lên lịch chạy

## Thiết kế
- designs/components/Screen05-NewRun, FileDrop, Field, Alert

## Spec liên quan
- docs/PRD.md C5
- docs/specs/05 mục 2–3

## Quyết định kiến trúc
- Ngày giờ giờ VN, truyền service datetime naive

## Các bước
### Bước 1 — Upload + nhận diện
- Làm: Upload + nhận diện
- Test viết trước: e2e upload sample → DTP
- Kiểm tra: `uv run poe e2e`

### Bước 2 — Tham số + precheck
- Làm: Tham số + precheck
- Test viết trước: chọn nhanh 'Tháng trước' với ngày giả lập; từ > đến → nút Chạy tắt
- Kiểm tra: `uv run poe e2e`

### Bước 3 — Chạy + tiến độ
- Làm: Chạy + tiến độ
- Test viết trước: e2e chạy sample → màn kết quả
- Kiểm tra: `uv run poe e2e`

## Chấp nhận khi
- [ ] Không chạy được khi thiếu/sai khoảng thời gian
- [ ] Số dòng ngoài khoảng hiện trước khi chạy
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh, e2e xanh

## Câu hỏi mở
- —
