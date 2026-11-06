# Sổ tay Hướng dẫn Sử dụng Hệ thống ReconHub

ReconHub là ứng dụng nội bộ phục vụ công tác đối soát dữ liệu giữa file báo cáo Excel và cơ sở dữ liệu Oracle. Tài liệu này hướng dẫn chi tiết quy trình thao tác dành cho các vai trò: **Quản trị viên (Admin)**, **Chủ sở hữu mẫu đối soát (Template Owner)**, **Chuyên viên vận hành (Operator)** và **Người xem (Viewer)**.

---

## Mục lục
1. [Tổng quan hệ thống và Vai trò người dùng](#1-tổng-quan-hệ-thống-và-vai-trò-người-dùng)
2. [Đăng nhập và Quản lý tài khoản](#2-đăng-nhập-và-quản-lý-tài-khoản)
3. [Quản lý Nguồn dữ liệu (Data Sources) & Lưu trữ](#3-quản-lý-nguồn-dữ-liệu-data-sources--lưu-trữ)
4. [Đăng ký & Quản trị Mẫu đối soát (Templates)](#4-đăng-ký--quản-trị-mẫu-đối-soát-templates)
5. [Quy trình Chạy đối soát (New Run)](#5-quy-trình-chạy-đối-soát-new-run)
6. [Xem và Phân tích Kết quả đối soát (Run Result)](#6-xem-và-phân-tích-kết-quả-đối-soát-run-result)
7. [Xác nhận "Đã kiểm tra xong" & Xuất báo cáo Excel](#7-xác-nhận-đã-kiểm-tra-xong--xuất-báo-cáo-excel)
8. [Lịch sử đối soát & Xóa dữ liệu tạm hàng loạt (History)](#8-lịch-sử-đối-soát--xóa-dữ-liệu-tạm-hàng-loạt-history)
9. [Bảng điều khiển Tổng quan (Dashboard)](#9-bảng-điều-khiển-tổng-quan-dashboard)
10. [Vai trò và phân quyền (`/roles`, chỉ Admin)](#10-vai-trò-và-phân-quyền-roles-chỉ-admin)
11. [Chạy đối soát theo bộ (Batch Run)](#11-chạy-đối-soát-theo-bộ-batch-run)

---

## 1. Tổng quan hệ thống và Vai trò người dùng

ReconHub hỗ trợ giải quyết bài toán so lệch dữ liệu quy mô lớn với tốc độ cao, xử lý dung lượng file từ hàng chục ngàn đến hàng triệu dòng.

### Phân quyền người dùng
Quyền được tính theo menu: vai trò có menu nào thì người dùng thấy menu đó ở thanh bên và thao tác được trong màn đó. Admin tự tạo thêm vai trò và bật/tắt menu cho từng vai trò ở màn **Vai trò và phân quyền** (`/roles`, xem mục 10).

| Vai trò | Ký hiệu | Quyền hạn chính |
|---|---|---|
| **Admin** | `ADMIN` | Toàn quyền hệ thống: quản lý tài khoản người dùng, vai trò và phân quyền, cấu hình nguồn Oracle, giám sát dung lượng và xóa dữ liệu tạm hàng loạt. |
| **Template Owner** | `TEMPLATE_OWNER` | Tạo mới, cấu hình, kiểm thử (dry-run) và kích hoạt các mẫu đối soát (Templates). |
| **Operator** | `OPERATOR` | Tải file Excel lên, chọn khoảng thời gian tìm kiếm, chạy đối soát, tra cứu dòng lệch, xuất file kết quả và xác nhận hoàn thành kiểm tra. |
| **Viewer** | `VIEWER` | Xem danh sách templates, theo dõi dashboard, xem lịch sử và kết quả đối soát ở chế độ chỉ đọc. |

> **Phạm vi dữ liệu:** Admin xem tất cả run. Vai trò thường chỉ thấy run do mình chạy ở Dashboard, Lịch sử và Kết quả; mở link run của người khác sẽ báo không tìm thấy. File Excel gốc chỉ tải được khi do mình tải lên, thuộc run của mình, hoặc là file mẫu của template mình có quyền xem.

---

## 2. Đăng nhập và Quản lý tài khoản

### Đăng nhập hệ thống
1. Truy cập đường dẫn ứng dụng ReconHub (mặc định cổng `8050`).
2. Nhập **Tên đăng nhập** và **Mật khẩu**.
3. Nhấn **Đăng nhập**.
> **Lưu ý:** Nếu nhập sai mật khẩu quá 5 lần liên tiếp, tài khoản sẽ tự động bị tạm khóa để bảo vệ an toàn hệ thống. Hãy liên hệ Admin để được mở khóa.

### Đổi mật khẩu lần đầu
- Với tài khoản mới do Admin cấp, hệ thống yêu cầu đổi mật khẩu ở lần đăng nhập đầu tiên.
- Nhập mật khẩu mới, xác nhận lại mật khẩu và nhấn **Lưu mật khẩu mới**.

### Quản lý thông tin cá nhân
- Nhấp vào tên tài khoản ở góc trên bên phải màn hình → chọn **Tài khoản**.
- Tại đây bạn có thể xem họ tên, vai trò hiện tại và chủ động thay đổi mật khẩu định kỳ.

---

## 3. Quản lý Nguồn dữ liệu (Data Sources) & Lưu trữ

Chỉ tài khoản có vai trò **Admin** mới có quyền truy cập menu **Data Sources** (`/data-sources`).

### Tab 1: Nguồn đối soát (Oracle)
1. Nhấn **Thêm nguồn dữ liệu**.
2. Nhập thông tin kết nối:
   - **Tên nguồn**: Ví dụ `ORCL_BILLING_PROD`
   - **Môi trường**: Chọn `DEV`, `TEST`, `UAT`, hoặc `PROD`
   - **Host & Cổng**: Ví dụ `10.0.1.50:1521`
   - **Service Name**: Tên service Oracle Database
   - **Tài khoản & Mật khẩu**: Tài khoản người dùng có quyền **chỉ đọc (SELECT)** trên schema nghiệp vụ.
3. Nhấn **Kiểm tra kết nối** để kiểm tra tính thông suốt qua mạng VPN.
4. Nhấn **Lưu nguồn dữ liệu**.

### Tab 2: Lưu trữ RECON_APP & Dữ liệu tạm
- Xem thông số dung lượng lưu trữ hiện tại của hệ thống.
- Cấu hình ngưỡng cảnh báo dung lượng (mặc định `5.0 GB`) và số ngày lưu trữ dữ liệu tạm (mặc định `30 ngày`).
- Thực hiện xóa dữ liệu tạm theo điều kiện lọc (theo Template, trước ngày chỉ định, người chạy).

---

## 4. Đăng ký & Quản trị Mẫu đối soát (Templates)

Mẫu đối soát (Template) định nghĩa quy tắc ghép nối, chuẩn hóa dữ liệu giữa các cột trong file Excel và các trường dữ liệu trong bảng/view của Oracle.

### Đăng ký Template mới qua Wizard 5 bước (`/templates/new`)
1. **Bước 1 — Thông tin chung**:
   - Nhập Mã template (viết hoa không dấu, ví dụ: `DTP_HOA_DON`), Tên mô tả, Chọn Nguồn dữ liệu Oracle.
2. **Bước 2 — Cấu trúc file Excel**:
   - Khai báo dòng tiêu đề (Header row), dòng bắt đầu dữ liệu (Data row), Tên Sheet cần đọc.
   - Định danh nhận diện file qua các cột tiêu đề bắt buộc.
3. **Bước 3 — Nguồn DB & Lọc thời gian**:
   - Chọn bảng hoặc view nguồn từ danh mục schema Oracle.
   - Chọn cột áp dụng khoảng tìm kiếm Từ ngày (`p_from`) và Đến ngày (`p_to`).
   - Cấu hình điều kiện lọc đơn vị nếu có (`p_org`).
4. **Bước 4 — Ghép cột (Mapping) & Khóa chính**:
   - Ghép từng trường logic với cột Excel tương ứng và cột trong bảng DB.
   - Đánh dấu ít nhất một trường làm **Khóa chính (Key)** dùng để so khớp.
   - Khai báo kiểu dữ liệu: `Text`, `Number`, `DateTime`, `Date`.
5. **Bước 5 — Hồ sơ đối soát (Profiles) & Chỉ tiêu đo (Measures)**:
   - Thiết lập nhóm gộp dữ liệu (Group By), ví dụ: Gộp theo Số hóa đơn, hoặc Gộp theo Ngày × Điểm thu.
   - Cấu hình các chỉ tiêu tính toán: `SUM(Tiền)`, `COUNT(Số dòng)`.
   - Thiết lập ngưỡng sai số cho phép (Tolerance), ví dụ: `0.01` VNĐ hoặc `0` (so khớp tuyệt đối).

### Kiểm thử (Dry-run) và Kích hoạt
- Tại bước cuối của Wizard, nhấn **Kiểm tra sơ bộ (Dry-run)** để hệ thống đọc thử dữ liệu mẫu và phát hiện lỗi cú pháp.
- Sau khi kiểm thử thành công, nhấn **Kích hoạt Template** để chuyển trạng thái sang `ACTIVE`, sẵn sàng cho vận hành.

---

## 5. Quy trình Chạy đối soát (New Run)

Menu **Chạy đối soát** (`/runs/new`) dành cho vai trò **Operator**, **Template Owner** và **Admin**.

### Các bước thực hiện
1. **Chọn mẫu đối soát**: Chọn Template cần thực hiện từ danh sách đang hoạt động.
2. **Chọn Hồ sơ (Profile)**: Chọn cấu hình nhóm gộp và chỉ tiêu cần so khớp.
3. **Tải file Excel lên**:
   - Kéo thả file Excel hoặc nhấn vào khung tải file để chọn từ máy tính.
   - Hệ thống tự động kiểm tra định dạng file `.xlsx` / `.xls` và tính mã băm SHA-256 chống trùng lặp.
4. **Nhập khoảng thời gian tìm kiếm**:
   - Chọn **Từ ngày giờ** (`p_from`) và **Đến ngày giờ** (`p_to`).
   - *Lưu ý quan trọng:* Khoảng ngày giờ này được áp dụng đồng thời cho cả dữ liệu truy vấn từ Oracle và dữ liệu dòng trong file Excel. Các dòng Excel nằm ngoài khoảng này sẽ được ghi nhận và phân loại riêng.
5. **Kiểm tra sơ bộ (Pre-check)**:
   - Nhấn nút **Kiểm tra trước**. Hệ thống kiểm tra kết nối Oracle, kiểm tra cấu trúc sheet Excel và cảnh báo nếu chạy trên môi trường PROD.
6. **Khởi chạy đối soát**:
   - Nhấn **Bắt đầu đối soát**. Run được đưa vào hàng đợi xử lý ngầm (Worker). Màn hình sẽ tự động chuyển sang trang Kết quả run.

---

## 6. Xem và Phân tích Kết quả đối soát (Run Result)

Màn hình Kết quả run (`/runs/<run_id>`) cung cấp góc nhìn toàn diện về tính chính xác của dữ liệu:

### 1. Thẻ chỉ số tổng quan (KPI Cards)
- **Tổng kiểm soát file (Control Total)**: Giá trị tổng tiền ghi nhận trên file gốc so với giá trị tính toán lại.
- **Tổng tiền Excel trong khoảng**: Tổng tiền các dòng dữ liệu hợp lệ nằm trong khoảng thời gian đối soát.
- **Tổng tiền DB**: Tổng tiền truy vấn tương ứng từ Oracle Database.
- **Chênh lệch**: Khoản tiền lệch giữa hai bên (màu đỏ nếu có chênh lệch).

### 2. Phân loại trạng thái kết quả (8 Tabs)
Dữ liệu kết quả được gom nhóm theo các tab chi tiết:
- **Tất cả chênh lệch**: Tổng hợp mọi dòng phát hiện có vấn đề cần xử lý.
- **Khớp (MATCHED)**: Các nhóm có khóa trùng khớp và sai số chỉ tiêu nằm trong ngưỡng cho phép.
- **Lệch giá trị (MISMATCH)**: Tìm thấy cả ở hai bên nhưng giá trị tiền hoặc số lượng sai lệch vượt ngưỡng.
- **Thiếu trong DB (MISSING_IN_DB)**: Có trong Excel nhưng không tìm thấy dữ liệu tương ứng trong Oracle.
- **Thiếu trong Excel (MISSING_IN_EXCEL)**: Có trong Oracle nhưng không xuất hiện trong file Excel.
- **Không nhất quán (INCONSISTENT)**: Khác biệt về thuộc tính mô tả.
- **Trùng khóa (DUPLICATE)**: Khóa chính xuất hiện nhiều lần không hợp lệ trong cùng nguồn.
- **Không hợp lệ (INVALID)**: Dòng dữ liệu thiếu thông tin bắt buộc, sai định dạng ngày hoặc sai kiểu số.

### 3. Bảng lưới động & Tra cứu dòng lệch
- Bảng hiển thị tiêu đề hai tầng: Cột Khóa chính, Cột Trạng thái, và các nhóm cột Giá trị Excel / DB / Chênh lệch.
- Các ô có phát sinh chênh lệch được đánh dấu màu nổi bật (`rh-diff`).
- Sử dụng ô **Tìm kiếm** để tra nhanh theo số hóa đơn / mã giao dịch.
- Tích chọn **Chỉ hiện cột lệch** để ẩn bớt các cột giá trị đã khớp hoàn toàn.
- **Nhấp vào một dòng bất kỳ** trên bảng để mở **Ngăn chi tiết (Drawer)** bên phải màn hình:
  - Xem danh sách các dòng Excel thô tương ứng (Raw Excel rows).
  - Xem bản ghi chi tiết truy vấn từ DB.
  - Trường hợp dữ liệu tạm đã được xóa, hệ thống sẽ hiển thị thông báo rõ ràng: *"Dữ liệu Excel gốc đã xóa lúc DD/MM/YYYY HH:mm"*.

---

## 7. Xác nhận "Đã kiểm tra xong" & Xuất báo cáo Excel

### Xác nhận đã kiểm tra (Mark Checked)
1. Khi đã rà soát xong kết quả, Operator nhấn nút **Đã kiểm tra xong** ở thanh tiêu đề.
2. Hộp thoại xác nhận xuất hiện:
   - Người dùng có thể tích chọn **"Xóa dữ liệu tạm của run này để tiết kiệm dung lượng"** (khuyến nghị khi đối soát xong xuôi).
3. Nhấn **Xác nhận**.
   - Trạng thái kiểm tra chuyển thành: `Đã kiểm tra · <tên_user>`.
   - Kết quả đối soát, tổng hợp và thông số run vẫn được lưu vĩnh viễn để phục vụ báo cáo.

### Xuất báo cáo đối soát ra Excel
1. Nhấn nút **Export Excel**.
2. Hệ thống tạo file Excel báo cáo gồm nhiều sheet:
   - **Tổng hợp**: Thông tin tham số run, thời gian, người chạy, tỷ lệ khớp và 4 chỉ số KPI.
   - **Chi tiết kết quả**: Bảng chi tiết toàn bộ các dòng theo cấu hình Profile.
   - **Dòng lỗi (nếu có)**: Danh sách các dòng dữ liệu không hợp lệ kèm lý do chi tiết.
3. Trình duyệt sẽ tự động tải file `.xlsx` về máy. Ngay cả khi dữ liệu tạm đã bị xóa, tính năng xuất báo cáo vẫn hoạt động bình thường dựa trên kho kết quả đã lưu.

---

## 8. Lịch sử đối soát & Xóa dữ liệu tạm hàng loạt (History)

Truy cập menu **Lịch sử** (`/history`) để quản lý toàn bộ các lần chạy đối soát trong quá khứ.

### Bộ lọc tìm kiếm đa tiêu chí
- **Template**: Lọc theo mẫu đối soát cụ thể.
- **Kiểm tra**: Lọc theo trạng thái `Chưa kiểm tra` hoặc `Đã kiểm tra`.
- **Dữ liệu tạm**: Lọc theo trạng thái `Còn` hoặc `Đã xóa`.
- **Người chạy**: Lọc theo tài khoản thực hiện.
- **Tên file**: Tìm kiếm theo tên file gốc tải lên.

### Thao tác trên từng dòng run
- **Xem**: Nhấn để mở lại chi tiết màn hình Kết quả run.
- **Tải**: Tải lại file Excel gốc (chỉ khả dụng khi dữ liệu tạm chưa bị xóa).
- **Chạy lại**: Tự động chuyển sang màn hình Chạy đối soát với các tham số cũ được điền sẵn.

### Xóa dữ liệu tạm hàng loạt (Chỉ dành cho Admin)
> Xóa 1 run của mình thì không cần Admin; xóa nhiều run cùng lúc mới cần Admin.
Theo quy tắc nghiệp vụ cốt lõi của ReconHub, **dữ liệu tạm chỉ bị xóa khi người dùng chủ động yêu cầu**:
1. Tài khoản Admin tích chọn các ô checkbox ở đầu các dòng run cần xóa (hoặc tích ô **Chọn tất cả** trên tiêu đề cột).
2. Thanh thông báo xuất hiện: `Đã chọn N run.` kèm nút màu đỏ **Xóa dữ liệu tạm**.
3. Nhấn **Xóa dữ liệu tạm** để mở hộp thoại xác nhận an toàn:
   - Xem tổng số run và dung lượng ước tính giải phóng.
   - Đọc danh sách những gì sẽ xóa (dòng nạp tạm, file gốc, cache) và những gì được giữ lại (kết quả, tổng hợp, export).
   - Nhập chính xác từ khóa **`XOA`** vào ô xác nhận.
4. Nhấn nút **Xóa dữ liệu tạm**. Hệ thống sẽ thu hồi dung lượng ổ đĩa ngay lập tức và cập nhật trạng thái cột Dữ liệu tạm thành `Đã xóa DD/MM`.

---

## 9. Bảng điều khiển Tổng quan (Dashboard)

Truy cập biểu tượng trang chủ hoặc đường dẫn `/` để theo dõi tình hình vận hành:

- **Thẻ Run trong kỳ**: Tổng số run đã chạy trong tháng hiện tại, kèm phân loại hoàn thành / lỗi / đang chạy. Vai trò thường chỉ tính run do mình chạy.
- **Tỉ lệ khớp trung bình**: Tỷ lệ phần trăm khớp dữ liệu chung của toàn đơn vị.
- **Chưa kiểm tra**: Số lượng run đối soát xong nhưng chưa được chuyên viên xác nhận hoàn thành, kèm dung lượng dữ liệu tạm tương ứng.
- **Việc của tôi**: Tổng hợp số run của chính bạn đang chờ xử lý hoặc bị lỗi cần kiểm tra lại.
- **Bảng Run gần đây**: Liệt kê 5-10 lượt đối soát mới nhất kèm đường dẫn nhanh đến màn hình kết quả và nút **Xem lịch sử**.
- **Cảnh báo dung lượng (Admin)**: Hiển thị thanh banner cảnh báo màu vàng khi tổng dung lượng dữ liệu tạm vượt quá ngưỡng cho phép hoặc có run giữ tạm quá số ngày quy định.

---

## 10. Vai trò và phân quyền (`/roles`, chỉ Admin)

### Tab Vai trò
- Danh sách vai trò bên trái, chi tiết bên phải: tên, mã, mô tả, trạng thái đang dùng.
- **Thêm vai trò**: nhập mã (chữ hoa, số, gạch dưới) và tên; có thể sao chép menu từ một vai trò có sẵn.
- **Menu được truy cập**: tick menu theo nhóm (Đối soát / Cấu hình / Quản trị). Menu gắn nhãn **Mới** là menu vừa thêm vào hệ thống; menu **Đang ẩn** vẫn gán được và có hiệu lực khi Admin bỏ ẩn ở màn Danh sách menu.
- **Lưu vai trò**: hộp thoại liệt kê menu thêm/bỏ và số người dùng bị ảnh hưởng. Quyền mới có hiệu lực trong tối đa 5 giây, người đang mở app không cần đăng xuất.
- Vai trò hệ thống **Admin** luôn có toàn bộ menu, không sửa, không tắt, không xóa được. Không xóa vai trò đang gán cho người dùng (gỡ vai trò khỏi họ ở màn Người dùng trước).

### Tab Quyền thực tế của người dùng
- Chọn một người dùng để xem menu thực tế của họ (hợp các vai trò đang mang), vai trò nào cấp menu nào, và thanh bên họ sẽ thấy.

### Tab Mô phỏng phạm vi dữ liệu
- Chọn một người dùng để xem họ thấy những run nào ở màn Lịch sử: Admin thấy tất cả, vai trò thường chỉ thấy run do mình chạy.

---

## 11. Chạy đối soát theo bộ (Batch Run)

Chạy đối soát theo bộ dùng khi cuối kỳ phải đối soát nhiều template cùng lúc: khai báo bộ một lần (nhóm template, mẫu tên file, tham số theo kỳ), mỗi kỳ chỉ cần tải tất cả file một lần rồi chạy song song.

### 11.1. Khai báo bộ đối soát (`/batches`)

Chỉ Admin và Template Owner sửa được bộ; Operator chỉ chạy, Viewer chỉ xem bộ.

1. Mở **Bộ đối soát** (`/batches`), nhấn **Tạo bộ đối soát**, nhập mã (chữ hoa, số, gạch dưới), tên, mô tả và số template chạy song song trên một Data Source (1–4, mặc định 2).
2. Mở bộ, nhấn **Thêm template**: chọn template đã kích hoạt (template nháp hoặc đã lưu trữ không thêm được), nhập **mẫu tên file** (ví dụ `*DTP*`, nhiều mẫu cách nhau bằng `|`), tick **Gộp** nếu một mục nhận nhiều file, tick **Bắt buộc** nếu thiếu file thì mục đó không được chạy, đặt **Ưu tiên** (số nhỏ chạy trước).
3. **Tham số ghi đè**: mỗi mục có thể ghi đè tham số của template bằng công thức theo kỳ, ví dụ `p_ky` = `{ky.thang}` (tháng dạng `202610`), `p_from` = `{ky.tu}`, `p_to` = `{ky.den}`. Công thức hỗ trợ cộng/trừ ngày (`{ky.tu-1d}`, `{ky.den+3d}`) và `{ky.nam}`.
4. Nhấn **Kích hoạt** khi bộ đã có ít nhất một mục đang hoạt động, mọi mục đều có mẫu tên file và tham số giải được với kỳ hiện tại. Bộ đã lưu trữ không sửa được.

> Hệ thống có sẵn bộ mẫu `DOANH_THU_CUOI_THANG` (template DTP mẫu, mẫu tên `*DTP*`, gộp nhiều file) để tham khảo; các template khác do người dùng đăng ký thật.

### 11.2. Chạy một kỳ (`/batch-runs`)

1. Mở **Chạy bộ đối soát** (`/batch-runs`), chọn bộ, chọn kỳ (tháng dạng `YYYY-MM`, mặc định tháng hiện tại), đặt tên lần chạy nếu cần rồi nhấn **Tạo lần chạy**.
2. **Bước 1 – Tải file**: kéo thả hoặc chọn các file Excel/CSV (tối đa 200 file, mỗi file tối đa 50MB) hoặc một file `.zip` (tối đa 200MB). File trùng tên hoặc trùng nội dung sẽ được báo và bỏ qua.
3. **Bước 2 – Ghép file**: hệ thống tự ghép file vào mục theo mẫu tên; file không khớp hoặc khớp nhiều mục cần chọn tay hoặc bỏ qua. Mục có template đã lưu trữ sẽ bị bỏ qua. Mục bắt buộc thiếu file thì không sang được bước sau.
4. **Bước 3 – Tham số**: xem tham số đã giải theo kỳ cho từng mục, sửa ghi đè khi cần (để trống hoặc nhấn **Về mặc định** để dùng giá trị của bộ/template).
5. **Bước 4 – Kiểm tra**: nhấn **Kiểm tra trước** để đọc header, kiểm tra dòng tổng từng file, đếm dòng ngoài kỳ và dòng không hợp lệ, kiểm tra kết nối Data Source. Mục trạng thái **Sẵn sàng** hoặc **Cảnh báo** thì chạy được (có thể bỏ chọn mục cảnh báo); mục **Lỗi** phải thay file rồi kiểm tra lại. Nếu bộ chạy trên Data Source PROD, hệ thống yêu cầu xác nhận một lần, liệt kê các Data Source PROD liên quan.
6. **Bước 5 – Chạy**: nhấn **Chạy** và theo dõi tiến độ từng mục. Lỗi một mục không chặn các mục khác.

### 11.3. Xem kết quả (`/batch-runs/<id>/result`)

- **Ma trận kết quả**: tổng Excel, tổng DB, chênh lệch, số dòng khớp/lệch/thiếu, tỷ lệ khớp từng mục và chênh lệch so với kỳ trước (cùng bộ, cùng template, lần chạy DONE gần nhất).
- **Chạy lại run lỗi**: chạy lại toàn bộ mục lỗi, hoặc chạy lại từng mục (mục đã xong vẫn chạy lại được sau khi sửa file). Lần chạy lại tạo run con mới, giữ nguyên file và tham số.
- **Thay file**: ở mục lỗi, tải file khác lên để thay file cũ rồi kiểm tra lại mà không cần tạo lần chạy mới.
- **Tải tất cả (.zip)**: một file `.zip` gồm file Excel riêng từng mục (giống hệt file xuất của run đơn lẻ) và file tổng hợp `00_TONG_HOP` (sheet Ma trận, Tham số, File).
- **Đánh dấu đã kiểm tra**: chọn các mục rồi xác nhận đã kiểm tra xong (giống run đơn lẻ). **Xóa dữ liệu tạm** hàng loạt chỉ dành cho Admin.
- **Hủy lần chạy**: chỉ hủy được khi lần chạy đang ở trạng thái Nháp hoặc Đang chạy; run con đang chạy sẽ dừng ở bước kiểm tra tiếp theo.

### 11.4. Giới hạn và lưu ý

- Tối đa 50 mục trong một bộ, 50 file trong một mục, 200 file trong một lần chạy.
- Một kỳ dùng chung cho cả bộ; nếu ngày chốt của các template lệch nhau vài ngày thì dùng công thức `{ky.tu±Nd}` trong tham số ghi đè.
- Người tạo lần chạy và Admin thấy lần chạy đó; Operator chỉ thấy lần chạy do mình tạo; Viewer không thấy mục chạy bộ ở thanh bên.
- Lịch sử run (`/history`) có bộ lọc **Lần chạy bộ** (Tất cả / Chỉ run bộ / Chỉ run đơn lẻ); run con thuộc bộ có chip **Bộ \<mã bộ\>** ở cột Template.

---
*ReconHub — Hệ thống Đối soát Dữ liệu Doanh nghiệp.*
