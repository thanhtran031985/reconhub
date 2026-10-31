# Screen06-RunResult

PRD C6, task 11. Preview: bấm "Đã kiểm tra xong" → hộp thoại (bỏ chọn "Xóa luôn dữ liệu tạm" để chỉ đánh dấu); bấm một dòng để mở chi tiết.
1. Header: H1, dòng phụ (profile, khoảng, tham số, Data Source, version, người chạy); chip Kiểm tra (Chưa / Đã · người · lúc) và chip Dữ liệu tạm (Còn · dung lượng / Đã xóa lúc …; dùng chung: "Dùng chung với run #…"). Nút: **Đã kiểm tra xong** (ẩn khi đã kiểm tra), Chạy lại, So với run trước (GĐ3), **Export Excel**.
2. Hộp thoại Đã kiểm tra xong: checkbox "Xóa luôn dữ liệu tạm của run này" (mặc định bật), Sẽ xóa / Giữ lại, cảnh báo. Run đã kiểm tra nhưng còn dữ liệu tạm: hiện nút "Xóa dữ liệu tạm" (danger).
3. 4 KpiCard; thanh tỉ lệ; tabs trạng thái (đếm); tìm khóa; chỉ cột lệch; grid nhóm Excel | DB | Chênh, ô lệch `rh-diff`.
4. Drawer: dòng Excel gốc (hoặc "Dữ liệu Excel gốc đã xóa lúc …"), dòng DB truy vấn lại theo khóa.
4 trạng thái; run đang chạy thay KPI bằng tiến độ; FAILED hiện Alert mã lỗi.
