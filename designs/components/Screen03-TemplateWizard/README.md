# Screen03-TemplateWizard

PRD C3, task 09. Preview bấm chuyển được 5 bước; bước 3 chuyển được Bảng/View ↔ SQL tự viết.
- Khung: H1, dòng phụ (nháp, tự lưu, Data Source, bảng); tab nút Cấu hình | Sơ đồ diễn giải; Stepper (todo/current/done/warn); Quay lại · Lưu nháp · Tiếp ("Lưu & kích hoạt vN" ở bước 5, khóa kèm lý do nếu dry-run chưa đạt).
- Bước 1: FileDrop, Sheet, Dòng header, Dữ liệu từ dòng, header nhận diện; Hệ thống phát hiện (Alert); Xem trước 5 dòng.
- Bước 2: bảng Dùng · Cột Excel · Trường logic · Nhãn · Kiểu · Chuẩn hóa · Giá trị mẫu; Gợi ý lại; Trường dẫn xuất; lỗi dưới ô.
- Bước 3: Data Source, Cách khai báo, Đẩy phép gộp. **Bảng/View**: ô bảng có tìm kiếm + chip cột; **Điều kiện lọc theo tham số** (p_from, p_to chỉ cột kiểu ngày; p_org; Thêm tham số lọc); Điều kiện cố định; **Câu SELECT sinh ra**. SQL tự viết: textarea + Kiểm tra & lấy cột. Cột DB → Trường logic; Lọc Excel theo cùng khoảng.
- Bước 4: tab profile; trường có sẵn (nút Key, Sigma có aria-label); Group by + grain; Measures; bộ lọc profile; drill-down; SQL gộp.
- Bước 5: Từ/Đến ngày giờ (giây), tham số, Chạy thử; KPI (control total, nhóm, khớp, thời gian theo stage); phạm vi đã dùng.
- 4 trạng thái (trống = chưa có file mẫu).
