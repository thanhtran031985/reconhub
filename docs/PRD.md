# Đặc tả chức năng: ReconHub – Đối soát dữ liệu Excel và Oracle

_Phiên bản 1.1, 31/10/2026. Gom spec docs/specs/00–08 và thiết kế designs/ thành mô tả theo màn hình. Khi khác nhau, spec là gốc cho nghiệp vụ và dữ liệu, designs/ là gốc cho hiển thị._

**Quyết định đã chốt (31/10/2026):**
- **Template động**: 3 lớp Excel mapping, nguồn DB, Recon Profile. Thêm loại file mới chỉ cần đăng ký template.
- **So sánh theo profile**: Group by + Measures (sum, count, count_distinct, min, max, first_distinct) với quy tắc exact, abs_tol, pct_tol, display_only.
- **Tham số thời gian**: `p_from`, `p_to` do người dùng nhập khi chạy, áp cho cả DB và Excel; không lấy min/max trong file.
- **Nguồn DB**: khai báo bằng bảng/view + cột lọc (Từ ngày, Đến ngày, Đơn vị, cột khác); hệ thống sinh SELECT. SQL tự viết là tùy chọn nâng cao.
- **Kiến trúc**: toàn Python (Dash + dash-mantine-components + dash-ag-grid, Polars), code bằng Google Antigravity theo AGENTS.md. Không Docker: dev trên Windows, Oracle qua VPN; triển khai chạy trực tiếp trên Windows hoặc Linux.
- **RECON_APP**: SQLite (file local), chuyển được sang Oracle; user/password schema Oracle đăng ký ở Data Sources.
- **Người dùng**: lưu trong RECON_APP, đăng nhập bằng username/mật khẩu của ứng dụng (mật khẩu tự do, không rỗng). Không Entra ID.
- **Dữ liệu tạm**: người dùng chủ động xóa (từng run, nhiều run, theo điều kiện); không tự xóa; chỉ cảnh báo khi nhiều. File SQLite cũ sau khi chuyển sang Oracle cũng chỉ xóa khi Admin yêu cầu.

**Ký hiệu:** [GĐ0] nền tảng; [GĐ1] engine và template; [GĐ2] giao diện MVP; [GĐ3] mở rộng. Vai trò: **AD** Admin, **TO** Template Owner, **OP** Operator, **VW** Viewer.

---

## Phần A. Tổng quan và vai trò

### A1. Sản phẩm làm gì
Bộ phận tài chính/vận hành nhận file Excel xuất từ hệ thống tác nghiệp (ví dụ báo cáo hóa đơn theo tác nghiệp DTP) và phải đối chiếu với dữ liệu trong DWH/ODS. Hiện làm tay bằng pivot và VLOOKUP. ReconHub đọc file theo template, lấy dữ liệu Oracle theo cùng khoảng thời gian, gộp, ghép, so sánh, phân loại chênh lệch, cho xem chi tiết và xuất báo cáo.

**Ngoài phạm vi:** sửa dữ liệu nguồn; đối soát DB–DB; pushdown Excel vào staging; theo dõi thư mục; lịch chạy; SSO; tự động xóa dữ liệu.

### A2. Vai trò và quyền

| Việc | AD | TO | OP | VW |
|---|---|---|---|---|
| Quản lý người dùng (tạo, sửa, khóa/mở khóa, đặt lại mật khẩu, gán vai trò) | Có | | | |
| Quản lý Data Source (nguồn, đích lưu RECON_APP), kiểm tra kết nối | Có | | | |
| Chuyển RECON_APP sang Oracle; xóa bản lưu SQLite cũ | Có | | | |
| Xóa dữ liệu tạm nhiều run / theo điều kiện; xóa kết quả cũ | Có | | | |
| Tạo, sửa, clone, kích hoạt template; dry-run | Có | Có | | |
| Chạy đối soát (PROD cần xác nhận) | Có | Có | Có | |
| "Đã kiểm tra xong" và xóa dữ liệu tạm của một run | Có | Có | Có | |
| Xử lý chênh lệch [GĐ3] | Có | Có | Có | |
| Xem kết quả, lịch sử, export; đổi mật khẩu của mình | Có | Có | Có | Có |

Quyền kiểm ở service, không dựa vào việc ẩn nút.

---

## Phần B. Yêu cầu chung về giao diện

| Hạng mục | Yêu cầu |
|---|---|
| Bố cục | Máy tính trước, 1440px, dùng tốt 1366px. Thanh bên tối 232px (thu 64px dưới 1000px), thanh trên trắng: breadcrumb, nhãn môi trường, người dùng (menu: Tài khoản, Đăng xuất). |
| Màu | Xanh dương chủ đạo. Bảy trạng thái kết quả có màu riêng, luôn kèm chữ và icon. |
| Chữ | Inter/Segoe UI, số `tabular-nums`; mono cho số hóa đơn, mã, SQL, tên trường. |
| Bốn trạng thái | Bình thường; đang tải (skeleton); trống (lý do + một hành động); lỗi (giữ dữ liệu cũ, Thử lại). |
| Lời văn | Tiếng Việt có dấu, giữ thuật ngữ Template, Profile, Measure, Group by, Data Source, Run, Dry-run. Không emoji, không dấu chấm than. |
| Số và ngày | `24.114.547.250`; `dd/MM/yyyy HH:mm:ss` giờ Việt Nam. |
| Thao tác xóa | Luôn có hộp thoại nêu sẽ xóa gì, giữ lại gì; xóa hàng loạt phải gõ xác nhận. |
| Banner | Chế độ bảo trì (khi chuyển DB); cảnh báo dữ liệu tạm nhiều (chỉ Admin). |

---

## Phần C. Màn hình

### Sơ đồ điều hướng
```
/login (đăng nhập, đổi mật khẩu bắt buộc) ─► Dashboard
Thanh bên:
 ├─ Đối soát: Dashboard · Chạy đối soát ─► Kết quả run ─► Ngăn chi tiết · Kết quả run · Lịch sử
 └─ Cấu hình: Templates ─► Đăng ký template (5 bước + Sơ đồ diễn giải) · Data Sources (AD) · Người dùng (AD)
Menu người dùng: Tài khoản (đổi mật khẩu) · Đăng xuất
```

### C1. Dashboard [GĐ2 tối thiểu, GĐ3 đầy đủ]
Screen01. 4 thẻ chỉ số (run trong kỳ, tỉ lệ khớp, chênh lệch mở, việc của tôi); bảng run gần đây; tỉ lệ lệch theo template. GĐ2 chỉ có bảng run gần đây + nút Chạy đối soát.

### C2. Templates [GĐ1 service, GĐ2 UI]
Screen02. Bảng: Mã, Tên, Nhận diện file, Số trường, Profiles, Version, Owner, Trạng thái, Run gần nhất. Hành động: Đăng ký, Sửa, Clone, Archive, Export/Import JSON.

### C3. Đăng ký template – wizard 5 bước [GĐ2]
Screen03. Tab Cấu hình template | Sơ đồ diễn giải.
- **Bước 1 – File mẫu:** upload, sheet, dòng header, dòng dữ liệu, header nhận diện. Hệ thống phát hiện dòng tổng (đề xuất loại + control total), khóa trùng (đề xuất gộp), cột lẫn số/chữ, số 0 ở đầu. Xem trước 5 dòng.
- **Bước 2 – Định nghĩa trường:** Dùng · Cột Excel · Trường logic · Nhãn · Kiểu · Chuẩn hóa · Giá trị mẫu; trường dẫn xuất; alias.
- **Bước 3 – Nguồn DB:** Data Source; cách khai báo **Bảng/View** (mặc định) hoặc SQL tự viết.
  - Bảng/View: tìm và chọn bảng (danh sách từ DB) hoặc gõ `SCHEMA.TABLE`; danh sách cột + kiểu.
  - Điều kiện lọc theo tham số: Từ ngày giờ `p_from` (cột ngày, `>=`, bắt buộc), Đến ngày giờ `p_to` (cột ngày, `<=`, bắt buộc), Đơn vị `p_org` (cột, `=`/`in`, mặc định), Thêm tham số lọc (bỏ qua nếu trống).
  - Điều kiện cố định; Câu SELECT sinh ra (chỉ đọc).
  - SQL tự viết: textarea + Kiểm tra & lấy cột (SQL guard).
  - Mapping Cột DB → Trường logic; Lọc Excel theo cùng khoảng (trường thời gian, gợi ý mặc định khi chạy); Đẩy phép gộp xuống DB.
- **Bước 4 – Profile:** tab profile; trường có sẵn (nút Key/Σ); Group by; Measures (hàm, trường, so sánh, sai số, làm tròn); bộ lọc profile; drill-down; grain "200 dòng → 190 nhóm"; SQL gộp sinh tự động.
- **Bước 5 – Dry-run:** Từ/Đến ngày giờ, tham số; kết quả control total, số nhóm, khớp, thời gian; "Lưu & kích hoạt vN" chỉ khi dry-run đạt.

### C4. Sơ đồ diễn giải [GĐ2]
Screen04. 5 sơ đồ Mermaid sinh từ cấu hình: quy trình 5 bước; ba lớp mapping; tham số thời gian; profile gộp → ghép → so; trình tự khi chạy. Nút Sao chép mã; fallback hiện mã nguồn.

### C5. Chạy đối soát [GĐ2]
Screen05. Upload → nhận diện template → validate (dòng hợp lệ, dòng tổng, lỗi). Profile, Data Source, **Từ/Đến ngày giờ bắt buộc** (chọn nhanh), tham số khác theo template, áp khoảng cho Excel, measure bật/tắt. Precheck: số dòng ngoài khoảng, control total, cảnh báo trùng run. PROD cần xác nhận. Tiến độ theo stage; rời trang vẫn chạy.

### C6. Kết quả run [GĐ2]
Screen06.
- Header: run, template, profile, khoảng thời gian, tham số, Data Source, người chạy. Chip dữ liệu tạm: "Chưa kiểm tra · dữ liệu tạm còn" hoặc "Đã kiểm tra · dữ liệu tạm đã xóa lúc …". Nút **Đã kiểm tra xong** (hộp thoại: lựa chọn "Xóa luôn dữ liệu tạm" mặc định bật; liệt kê sẽ xóa / giữ lại), Chạy lại, So với run trước (GĐ3), Export Excel.
- KPI: control total, tổng Excel trong khoảng, tổng DB, chênh lệch.
- Thanh tỉ lệ + tab trạng thái (đếm + tổng tiền chênh); tìm khóa, lọc measure lệch, chỉ cột lệch.
- Grid cột động Excel | DB | Chênh; ô lệch tô màu.
- Ngăn chi tiết: dòng Excel gốc (hoặc "Dữ liệu Excel gốc đã xóa lúc …"), dòng DB truy vấn lại theo khóa.

### C7. Lịch sử [GĐ2]
Screen07. Bảng: Run, Thời gian, Template (ver), Profile, Khoảng tìm kiếm, File, Người chạy, Trạng thái, % khớp, Thời lượng, Kiểm tra (Chưa / Đã + người), Dữ liệu tạm (Còn · dung lượng / Đã xóa). Lọc template, trạng thái, người chạy, đã/chưa kiểm tra, còn/đã xóa dữ liệu tạm, tên file. **Chọn nhiều run → "Xóa dữ liệu tạm" (AD)** với hộp thoại tổng hợp số run, dung lượng, gõ XOA. Hành động dòng: Xem, Tải file gốc (ẩn khi đã xóa), Chạy lại.

### C8. Data Sources [GĐ0 service, GĐ2 UI] – chỉ AD
Screen08. Hai tab:
- **Nguồn đối soát:** bảng Tên, Env, Host:port/Service, User, Schema mặc định, Kiểm tra gần nhất, Template dùng; ngăn kéo thêm/sửa (mật khẩu chỉ nhập); kiểm tra kết nối (cảnh báo quyền ghi).
- **Lưu trữ RECON_APP:**
  - Khối DB đang dùng: loại, đường dẫn/host, phiên bản schema, dung lượng (phần dữ liệu tạm), sao lưu gần nhất.
  - Khối **Dữ liệu tạm**: dung lượng, số run chưa kiểm tra, số run giữ quá N ngày; ngưỡng cảnh báo (GB, ngày) sửa được; **Xóa theo điều kiện** (template, khoảng ngày chạy, đã/chưa kiểm tra, người chạy) → Xem trước (số run, dòng, dung lượng) → gõ XOA → Xóa; Nhật ký xóa.
  - Đích Oracle đã đăng ký (user/password schema), script tạo user.
  - Khối Chuyển dữ liệu sang Oracle (C10).
  - Khối **Bản lưu SQLite cũ** (sau khi chuyển): đường dẫn, dung lượng, ngày chuyển, nút Xóa bản lưu (gõ tên file).

### C9. Xử lý chênh lệch [GĐ3]
Screen09. Gán nguyên nhân, người xử lý (chọn từ RECON_USER), trạng thái; hàng loạt; run sau nhận diện dòng đã chấp nhận lệch.

### C10. Chuyển RECON_APP sang Oracle [GĐ3]
Trong Screen08. Chọn đích, phạm vi (Không gồm dữ liệu tạm – mặc định / Toàn bộ / Chỉ cấu hình); Kiểm tra trước; gõ tên schema; tiến độ theo bảng; đối chiếu; hướng dẫn đổi `RECON_DB_URL`. Chi tiết spec 08.

### C11. Đăng nhập và tài khoản [GĐ0]
Screen10. Ô Tên đăng nhập, Mật khẩu, nút Đăng nhập; lỗi chung "Tên đăng nhập hoặc mật khẩu không đúng"; khóa tạm "Tài khoản tạm khóa đến HH:mm…". Bước đổi mật khẩu bắt buộc (mật khẩu mới, nhập lại). Trang Tài khoản: họ tên, vai trò, lần đăng nhập cuối, Đổi mật khẩu (mật khẩu hiện tại, mới, nhập lại).

### C12. Người dùng [GĐ2] – chỉ AD
Screen11. Bảng: Username, Họ tên, Email, Vai trò (chip), Trạng thái (Hoạt động / Tạm khóa đến … / Đã tắt), Đăng nhập cuối. Lọc theo vai trò, trạng thái, tìm. Ngăn kéo Thêm/Sửa: username (không sửa sau khi tạo), họ tên, email, vai trò (nhiều), mật khẩu ban đầu (khi tạo), "Bắt đổi mật khẩu lần đầu". Hành động: Đặt lại mật khẩu, Mở khóa, Tắt/Bật, Lịch sử đăng nhập. Không tắt/bỏ vai trò Admin cuối cùng.

---

## Phần D. Quy tắc nghiệp vụ
- **D1 Đọc/chuẩn hóa** (spec 04 mục 1–2): mọi cột String; lỗi parse → Không hợp lệ kèm số dòng.
- **D2 Control total** (mục 3): lệch thì vẫn chạy, đánh dấu nổi bật.
- **D3 Thời gian** (mục 4): bắt buộc, `p_from ≤ p_to`, ≤ 93 ngày; dòng Excel ngoài khoảng đếm và hiển thị.
- **D4 Gộp/ghép/so** (mục 5–7): ưu tiên Không hợp lệ > Trùng khóa > Không nhất quán > Thiếu > Lệch > Khớp.
- **D5 Truy vấn an toàn** (spec 03 mục 5, spec 04 mục 8, spec 06): whitelist cột, bind, user chỉ đọc, timeout (600 giây qua VPN), giới hạn dòng.
- **D6 Version** (spec 03 mục 9).
- **D7 Run và hàng đợi** (spec 04 mục 9): QUEUED → RUNNING → DONE/FAILED/CANCELLED; mất kết nối Oracle → FAILED, không ghi dở.
- **D8 Dữ liệu tạm** (spec 04 mục 12): chỉ xóa theo yêu cầu; dùng chung thì chỉ xóa khi mọi run liên quan được yêu cầu; cảnh báo theo ngưỡng.
- **D9 Export** (mục 10): sinh từ kết quả, vẫn dùng được sau khi xóa dữ liệu tạm.
- **D10 Người dùng** (spec 06 mục 1): mật khẩu tự do không rỗng, argon2id; khóa 15 phút sau 5 lần sai; phiên 8 giờ; đổi mật khẩu vô hiệu phiên cũ; luôn còn ít nhất một Admin.

---

## Phần E. Dữ liệu
Nguồn chi tiết: docs/specs/02_database_schema.md. SQLite `data/recon_app.db` hoặc Oracle.

| Nhóm | Bảng |
|---|---|
| Người dùng, hệ thống | RECON_USER, RECON_USER_ROLE, RECON_LOGIN_LOG, RECON_AUDIT_LOG, RECON_APP_SETTING, alembic_version |
| Kết nối | RECON_DATA_SOURCE |
| Template | RECON_TEMPLATE, RECON_TEMPLATE_VERSION |
| Dữ liệu tạm | RECON_FILE, RECON_EXCEL_LOAD, RECON_EXCEL_ROW (+ storage/) |
| Run, kết quả | RECON_RUN, RECON_RUN_QUEUE, RECON_RUN_SUMMARY, RECON_RESULT_ROW, RECON_RESULT_DIFF, RECON_INVALID_ROW |
| Xóa, chuyển DB | RECON_PURGE_LOG, RECON_METADATA_MIGRATION |
| Xử lý [GĐ3] | RECON_ISSUE, RECON_ISSUE_REASON |

---

## Phần F. Công nghệ và quy trình
Xem AGENTS.md, spec 01 và spec 05. Quy trình (skill `lam-task`): Implementation Plan được duyệt → plan.md → TDD từng bước → dừng sau mỗi bước → progress.md → decisions.md khi khác spec. Definition of Done: test hành vi; golden cho thay đổi engine; kiểm quyền và validate ở mọi service; Alembic chạy trên SQLite (và Oracle khi có VPN); typecheck, lint, test xanh; task giao diện có e2e và đủ 4 trạng thái.

---

## Phần G. Giai đoạn xây dựng

| GĐ | Task | Kết quả |
|---|---|---|
| **0. Nền tảng** | 00-repo-setup, 01-auth-users, 02-data-sources | Dash chạy trên Windows, SQLite + Alembic, đăng nhập bằng user của ứng dụng, Data Source kết nối Oracle qua VPN |
| **1. Engine và template** | 03 → 07 | Chạy đối soát DTP end-to-end bằng service (`demo-run`), golden xanh, xóa dữ liệu tạm theo yêu cầu |
| **2. Giao diện MVP** | 08 → 12 | Người dùng nghiệp vụ tự đăng ký template, chạy, xem, xuất, quản lý người dùng, xóa dữ liệu tạm |
| **3. Mở rộng** | 13 → 16 | Chuyển RECON_APP sang Oracle, xử lý chênh lệch, dashboard, triển khai Windows/Linux |

---

## Phần H. Prompt thiết kế lại (tùy chọn)
> Thiết kế hệ thống giao diện "ReconHub" (dựng bằng Dash Mantine Components, Mantine v8) cho ứng dụng nội bộ đối soát dữ liệu Excel với Oracle. Bảng điều khiển dày dữ liệu, xanh dương chủ đạo, mặt trắng, viền mảnh, thanh bên tối. Chữ Inter, số tabular, mã và SQL font mono. Tiếng Việt có dấu, không emoji. 7 trạng thái kết quả có màu kèm chữ. Mỗi màn có 4 trạng thái. Màn: Screen01-Dashboard, Screen02-Templates, Screen03-TemplateWizard, Screen04-TemplateDiagram, Screen05-NewRun, Screen06-RunResult (có nút Đã kiểm tra xong), Screen07-History (chọn nhiều run để xóa dữ liệu tạm), Screen08-DataSources (tab Nguồn đối soát; tab Lưu trữ RECON_APP gồm DB đang dùng SQLite, Dữ liệu tạm với xóa theo điều kiện, đích Oracle, chuyển dữ liệu, bản lưu SQLite cũ), Screen09-Issues, Screen10-Login, Screen11-Users.
