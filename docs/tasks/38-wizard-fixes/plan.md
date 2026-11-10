# Plan — 38-wizard-fixes

## Câu hỏi chốt

- **Q0 — Footer thu còn bao nhiêu?** 20px (nút 18px, chữ 10px, icon 12px,
  capsule p=1, đệm ngang 12px). Nhỏ hơn nữa (16px) thì nút khó bấm.
- **Q1 — Lưu nháp bước 3 lưu những gì?** Toàn bộ bảng tham số bước 3
  (Nhãn, Kiểu, Hiện, Bắt buộc, Mặc định, LOV, STT), chỉ ghi các dòng có
  đổi so với DB (tránh audit thừa + tránh lỗi validation ở dòng không đụng).
  LOV chỉ ghi khi loại LOV đổi: giữ nguyên cấu hình LOV đã lưu (SQL/static/
  lookup) mà chỉ đổi `lov_type`, đồng thời đổi `control_type` theo cùng
  luật `handle_p_save_lov` (có LOV → SELECT, về NONE → TEXT nếu đang SELECT).
  Lỗi từng dòng không chặn dòng khác; cuối cùng toast tổng kết số dòng đã lưu
  + mã tham số lỗi (nếu có).
- **Q2 — Ghép dòng bảng với DB thế nào?** Các State ALL trả về theo đúng
  thứ tự DOM = thứ tự `version["params"]` lúc render bảng; zip theo thứ tự,
  lệch độ dài thì báo lỗi, không ghi gì.
- **Q3 — Nút tăng/giảm Canvas rộng bao nhiêu?** Ô 34 → 46px (controls chiếm
  ~20px bên phải, còn ~26px cho 1–2 chữ số), giữ căn giữa + nowrap.

## Các bước

| Bước | Nội dung | Kiểm chứng |
| --- | --- | --- |
| 0 | Task + nhánh `feat/38-wizard-fixes` từ `7ae6f43` | — |
| 1 | Test đỏ cho 3 lỗi | Test fail đúng chỗ |
| 2 | Sửa 3 mục (footer 20px, Lưu nháp bước 3 lưu bảng, Canvas trả controls) | Test unit xanh |
| 3 | Kiểm chứng cuối (typecheck, lint, full suite, Playwright 1366x768 + 1440x900) + xuất patch | Patch `git am` sạch |
