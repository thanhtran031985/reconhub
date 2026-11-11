# Task 53 — decisions

- D1: Giữ interval 10s chạy liên tục, chỉ chặn VẼ LẠI khi dữ liệu không
  đổi (fingerprint). Không tắt interval khi "không có gì chạy": user có
  thể nộp export từ tab viewer khác trong lúc tab Lịch sử đang mở, tắt
  interval sẽ làm Lịch sử không thấy export mới cho tới khi user tương
  tác. Chi phí mỗi tick chỉ là 1 query danh sách + export theo run.
- D2: Chỉ gate khi trigger đúng là `report-runs-auto-refresh`. Mọi
  trigger khác (lọc, phân trang, "Làm mới", refresh-store sau hành động
  export) luôn vẽ lại như cũ — đơn giản, không sợ nút "Làm mới" bị coi
  là không đổi.
- D3: Fingerprint chỉ gồm những gì bảng đang hiện: tổng số run, trang,
  mỗi run `id:status:row_count:finished_at`, mỗi export
  `id:status:progress_pct`. Tên/nhóm/tham số của run không đổi sau khi
  tạo nên không cần đưa vào.
