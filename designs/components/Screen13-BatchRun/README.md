# Screen13-BatchRun

Prototype: `preview.html` (độc lập, mở bằng trình duyệt, dữ liệu minh họa trong bộ nhớ). Spec: docs/specs/10_batch_run.md mục 9.

## Màn Bộ đối soát (`/batches/<id>`)
- Thông tin bộ (mã, tên, số run song song mỗi Data Source), bảng công thức theo kỳ, ô kỳ thử.
- Cảnh báo template Archived trong bộ.
- Bảng mục: #, template đã đăng ký (tên, mã, profile, chip Archived/Mới thêm), Version, Mẫu tên file, Gộp, Bắt buộc, Data Source, Tham số ghi đè (trống = mặc định template; tên lạ báo lỗi), Giá trị với kỳ thử, Gỡ.
- Hộp thoại **Thêm template vào bộ**: tìm kiếm; lọc "Chỉ template thêm được / Tất cả"; danh sách template đã đăng ký (Active/Draft/Archived, version, Data Source, lý do không thêm được); chi tiết cấu hình template đang chọn (chỉ đọc); khối "Cách chạy trong bộ" cho các template đã chọn (mẫu tên file gợi ý sẵn, bắt buộc; Gộp; Bắt buộc); nút "Thêm n template".
- Thanh dưới: trạng thái thay đổi, Lưu bộ đối soát.

## Màn Chạy bộ đối soát (5 bước)
1. Chọn bộ + kỳ + tên lần chạy; lần chạy gần đây; cảnh báo kỳ đã chạy; cảnh báo template Archived.
2. Vùng kéo thả nhiều file/.zip; khối file khớp nhiều template, khối file không khớp (chọn tay / bỏ file); bảng ghép (file chip có nút bỏ, trạng thái: Đã ghép, Gộp n file, Thiếu file bắt buộc + Bỏ qua tháng này, Chỉ nhận 1 file, Tùy chọn sẽ bỏ qua).
3. Bảng tham số: p_from, p_to, tham số khác; ô có biểu thức và giá trị đã tính; ô đã sửa tô tím; Về mặc định.
4. KPI Sẵn sàng/Cảnh báo/Lỗi/Bỏ qua; bảng precheck; Thay file; tùy chọn chạy cả mục cảnh báo; nút "Chạy n template".
5. KPI Xếp hàng/Đang chạy/Xong/Lỗi; tiến độ tổng; bảng tiến độ từng mục.
Thanh điều hướng dưới: Quay lại, lý do khóa, nút chính.

## Màn Kết quả lần chạy bộ (`/batch-runs/<id>/result`)
KPI (Khớp hết, Có lệch + tổng chênh, Lỗi/chưa chạy, Bỏ qua); tìm, lọc; ma trận (chọn, template, trạng thái, Tổng Excel, Tổng DB, Chênh lệch, Khớp, Lệch, Thiếu DB, Thiếu Excel, So tháng trước, Kiểm tra, Mở run, Tải file); thao tác chọn nhiều (Đánh dấu đã kiểm tra, Xóa dữ liệu tạm – gõ XOA); Chạy lại run lỗi; Tải tất cả (.zip) với danh sách file trong zip.

## Chuyển sang Dash
Bảng lớn dùng dag.AgGrid; hộp thoại dmc.Modal; upload dcc.Upload(multiple=True); wizard lưu DB (batch run DRAFT); tiến độ dcc.Interval 2 giây. Theo rule ui-dash và token v4.
