# Quyết định kỹ thuật — 100-multi-profile-run

## 1. Tạo N Run độc lập thay vì gom nhiều Profile vào 1 Run
- **Lý do**: Bảng `RECON_RUN` gắn liền với 1 `PROFILE_CODE`, và các bảng kết quả `RECON_RESULT_ROW`, `RECON_RUN_SUMMARY` đều chỉ có khóa ngoại `RUN_ID`. Mỗi profile có thể có cấu trúc Group By hoàn toàn khác nhau (ví dụ: một profile group theo Số HĐ, một profile group theo Chi nhánh + Ngày). Nếu nhồi nhiều profile vào 1 run sẽ làm xáo trộn kết quả và phá vỡ cấu trúc dữ liệu hiện tại.
- **Giải pháp**: Khi người dùng chọn $K$ profile, hệ thống sinh ra $K$ bản ghi `RECON_RUN` riêng biệt. Tất cả các run này cùng trỏ tới một file đã nạp (`FILE_ID` / `EXCEL_LOAD_ID`), giúp tái sử dụng hoàn toàn dữ liệu Excel tạm mà không phải đọc lại file.

## 2. Trải nghiệm điều hướng sau khi bấm Chạy
- **Khi chọn 1 profile**: Vẫn giữ nguyên hành vi quen thuộc là redirect trực tiếp vào trang kết quả `/runs/<run_id>`.
- **Khi chọn nhiều profile**: Không thể redirect đến 1 run đơn lẻ mà sẽ đưa người dùng về trang Lịch sử `/history` với thông báo thành công đưa $K$ run vào hàng đợi, nơi người dùng có thể theo dõi tiến độ của tất cả các run vừa tạo.
