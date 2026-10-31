# Spec 00 – Tổng quan, thuật ngữ, phạm vi

## 1. Mục tiêu
Tự động hóa đối soát giữa file Excel xuất từ hệ thống tác nghiệp và dữ liệu Oracle (DWH/ODS), cấu hình bằng template, không cần viết code cho mỗi loại file mới.

## 2. Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| RECON_APP | Kho dữ liệu của ứng dụng: người dùng, Data Source, template, run, kết quả, dữ liệu tạm. Mặc định SQLite, chuyển được sang Oracle |
| Data Source | Kết nối Oracle: nguồn đối soát (user chỉ đọc) hoặc đích lưu RECON_APP |
| Template | Cấu hình cho một loại file: nhận diện file, trường logic, nguồn DB (bảng/view + cột lọc), profile |
| Version | Bản cấu hình bất biến của template; run ghi version đã dùng |
| Trường logic | Tên chung `UPPER_SNAKE`, map tới cột Excel và cột DB |
| Trường dẫn xuất | Trường tính từ trường khác (vd `INV_DATE = trunc_day(INV_DATETIME)`) |
| Profile | Cách so sánh: Group by, Measures, bộ lọc, drill-down |
| Measure | Hàm gộp + trường + quy tắc so sánh |
| Control total | Dòng tổng trong file dùng kiểm tra đã đọc đủ dữ liệu |
| Run | Một lần đối soát: file + template version + profile + tham số |
| Dữ liệu tạm | Dòng Excel đã nạp, file gốc, cache của run. Người dùng chủ động xóa |
| Dry-run | Chạy thử khi đăng ký template |
| Issue | Xử lý một dòng chênh lệch [GĐ3] |

## 3. Trạng thái kết quả

| Mã | Nhãn | Ý nghĩa |
|---|---|---|
| MATCHED | Khớp | Có cả hai phía, mọi measure trong sai số |
| MISMATCH | Lệch giá trị | Có cả hai phía, ít nhất một measure vượt sai số |
| MISSING_IN_DB | Thiếu trong DB | Khóa chỉ có ở Excel |
| MISSING_IN_EXCEL | Thiếu trong Excel | Khóa chỉ có ở DB |
| INCONSISTENT | Không nhất quán | Measure `first_distinct` có ≥ 2 giá trị trong một nhóm |
| DUPLICATE | Trùng khóa | Profile không gộp mà khóa lặp ở một phía |
| INVALID | Không hợp lệ | Dòng Excel lỗi parse hoặc thiếu khóa |

## 4. Phạm vi MVP (GĐ0–GĐ2)
Đăng nhập bằng người dùng của ứng dụng, 4 vai trò, Data Source, template có version, engine đủ trạng thái, run qua hàng đợi, wizard + chạy + kết quả + lịch sử, export Excel, xóa dữ liệu tạm theo yêu cầu.

## 5. Ngoài phạm vi
Entra ID/SSO, pushdown mode (đẩy Excel vào staging), nguồn không phải Oracle, theo dõi thư mục, lịch chạy, đối soát DB–DB, sửa dữ liệu nguồn, tự động xóa dữ liệu tạm, Docker.

## 6. Ví dụ chuẩn: file DTP
- Sheet "BÁO CÁO DTP", 19 cột, header dòng 1, dòng cuối là dòng tổng (Dịch vụ = "Tổng tiền"). File thật tháng 02/2026: 12.445 dòng, 12.221 hóa đơn, tổng 24.114.547.250.
- Một hóa đơn có nhiều dòng (nhiều container/dịch vụ). Mã giao dịch lẫn số và chuỗi (`PAYMENTGW-...`). Ngày lập là chuỗi `dd/MM/yyyy HH:mm:ss`.
- `samples/dtp_sample_200.xlsx` là dữ liệu tổng hợp cùng cấu trúc: 200 dòng, 190 hóa đơn, ngày 01–05/02/2026, tổng Số lượng 220, Thành tiền 366.732.000.
