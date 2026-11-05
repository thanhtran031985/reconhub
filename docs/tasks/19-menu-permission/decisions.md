# Quyết định — 19-menu-permission

| Ngày | Quyết định | Lý do | Ảnh hưởng |
|---|---|---|---|

## Câu hỏi còn mở
- Có cần màn xem nhật ký thay đổi phân quyền riêng, hay dùng màn audit chung?

## Lệch seed/code cần hỏi trước khi duyệt plan (rà soát 05/11/2026, chưa quyết)

| # | Lệch | Bằng chứng trong code | Cần hỏi |
|---|---|---|---|
| Q0 | Nhánh làm việc: task.md ghi `feat/19-menu-permission`, nhưng toàn bộ chuỗi patch vừa rồi làm trên `feat/17-lookup-codes` (remote hiện ở `0605e02`) | `docs/tasks/19-menu-permission/task.md` (nhánh git) vs `git log` hiện tại | Làm tiếp trên `feat/17-lookup-codes` như cũ, hay tạo `feat/19-menu-permission` từ `0605e02` và bạn checkout nhánh mới trước khi áp patch? |
| Q1 | Tiền đề "làm sau task 18" không khớp code: task 18 chưa có code nào | `docs/tasks/18-batch-run/progress.md` toàn ⬜; không có `RECON_BATCH_RUN`, `app/services/batch_*.py`, `app/ui/pages/batch_*.py` trong clone; chỉ có chữ "batch" là kích thước lô trong `fetch.py`/`run_executor.py` | Làm task 19 ngay trên code hiện tại (menu `batch_run`, `batch_def` chỉ khai báo + seed, chưa có page/service để gắn; owner_filter cho batch để lại khi task 18 làm xong), hay bạn có code task 18 ở chỗ khác cần đẩy lên trước? |
| Q2 | Thiếu file thiết kế Screen14 | task.md ghi `designs/components/Screen14-Permission/preview.html` (đã duyệt), nhưng trong repo chỉ có Screen01–Screen13, không có Screen14 hay Screen15 | Bạn gửi lại file Screen14, hay làm màn `/roles` theo spec 11 mục 7.1 + mô tả 3 tab trong task.md mà không có preview? |
| Q3 | Seed ghi lịch sử ở `/runs`, code ở `/history` | Spec 11a mục 7: `history` → `/runs`; `app/ui/pages/history.py` đăng ký `/history`; nút "Quay lại lịch sử đối soát" ở `run_result.py:1494` link tới `/runs` (không có page nào ở `/runs`) | Giữ `/history` làm đường dẫn menu `history` và sửa link ở run_result sang `/history`, hay đổi page lịch sử sang `/runs`? |
| Q4 | OPERATOR sẽ mất menu Templates, VIEWER sẽ mất Issues và được thêm Templates | Seed 11a mục 7: OPERATOR không có `template`, VIEWER không có `issue` nhưng có `template`; shell hiện tại (`app/ui/layout/shell.py`) cho OPERATOR thấy Templates, cho mọi vai trò (kể cả VIEWER) thấy Issues | Xác nhận đây là thay đổi quyền có chủ ý (không phải lỗi seed), và chấp nhận OPERATOR mất danh sách Templates, VIEWER mất màn Issues? |
| Q5 | Phân biệt đọc/ghi trong cùng một menu `template`: VIEWER có menu `template` theo seed, nhưng hiện tại chỉ TEMPLATE_OWNER/ADMIN mới lưu/kích hoạt/nhân bản template, chỉ ADMIN mới xóa template | `app/services/template.py`: `save_draft_template`/`activate_version`/`clone_template`/`archive_template` yêu cầu ADMIN/TEMPLATE_OWNER, `delete_template` yêu cầu ADMIN; spec 11 nói "có menu = thao tác được trong màn đó" và ngoài phạm vi là "phân quyền mức thao tác" | Giữ rào chắn ghi/xóa template hiện tại (menu chỉ mở cửa đọc/danh sách, ghi vẫn theo vai trò cũ) cho tới khi có quyết định phân quyền mức thao tác, hay bỏ rào chắn và cho mọi vai trò có menu `template` đều lưu/xóa được? |
| Q6 | Menu không có trong seed: `/account`, `/login`, `/forbidden`, `/dev/ui` | `app/ui/pages/account.py`, `login.py`, `forbidden.py`, `dev_gallery.py` đều là page Dash nhưng seed 11a mục 7 không liệt kê | Miễn `menu_code` cho 4 page này (account = tự phục vụ, login/forbidden = công khai, dev_gallery = chỉ hiện khi ADMIN và không đưa vào MENUS), hay phải khai báo menu cho chúng? |
| Q7 | Menu `menu_admin` (`/menus`) thuộc task 20 nhưng phải khai báo ở task 19 để đồng bộ | Spec 11 mục 2 + task 19 phạm vi: `menus.py` khai báo mọi menu; task 20 mới làm page `/menus` | Khai báo `menu_admin` trong `menus.py` ở task 19 nhưng tạm ẩn khỏi thanh bên cho tới khi task 20 xong (tránh link hỏng cho ADMIN), hay làm một page `/menus` tối thiểu ở task 19? |
| Q8 | Tải file gốc qua Flask: `get_file` hiện chỉ yêu cầu đã đăng nhập, không kiểm tra run nào dùng file đó | `app/routes/file_routes.py` + `app/services/file_service.py:get_file` (chỉ `require_role(ctx)`); `RECON_FILE.UPLOADED_BY` là người upload, khác với `RECON_RUN.CREATED_BY` của run dùng file | Chặn tải file theo: (a) file do chính mình upload, hoặc (b) file thuộc về một run của mình (FILE_ID của run), hoặc (c) file mẫu của template mà mình có menu `template`? File không thỏa mãn → 404 như ID không tồn tại. |
| Q9 | Issue: chủ sở hữu tính theo run nào | Spec 11 mục 5: Issue theo run gốc (`FIRST_RUN_ID` của mình); `RECON_ISSUE` còn có `LAST_RUN_ID` (có thể do người khác chạy lại) | owner_filter cho issue chỉ theo `FIRST_RUN_ID` (kể cả khi `LAST_RUN_ID` là của người khác), hay theo cả hai? |
| Q11 | Xóa dữ liệu tạm của một run riêng lẻ: hiện có hai đường với quyền khác nhau | `temp_data.mark_checked(purge=True)` cho OP/TO/ADMIN, trong khi `purge_runs([r_id])` (dùng ở modal xóa riêng ở màn kết quả) chỉ ADMIN; spec D4 chỉ nêu "xóa hàng loạt" là nhạy cảm | Xóa riêng một run của mình thì theo owner_filter (không cần ADMIN), chỉ xóa hàng loạt mới require_admin, hay mọi đường xóa tạm đều require_admin? |
| Q10 | Dữ liệu thật đã kiểm chứng 05/11/2026 (DB thật trên D:\reconhub, `data\recon_app.db`) | User/role: đúng 4 user seed, mỗi người 1 vai trò (`admin` ADMIN, `operator` OPERATOR, `owner` TEMPLATE_OWNER, `viewer` VIEWER), không có user nhiều vai trò, không có user lạ. `RECON_RUN`: **cả 393 run đều có `CREATED_BY = 'admin'`**, không có run nào của owner/operator/viewer. `RECON_BATCH_RUN`: không có bảng (`no such table`), đúng như dự đoán vì task 18 chưa làm. | **Hệ quả cần bạn chốt:** sau migration, owner/operator/viewer sẽ thấy Lịch sử/Dashboard trống (0 run) cho tới khi tự họ chạy run mới; cả 393 run cũ chỉ ADMIN còn thấy. Đây có phải ý bạn muốn không, hay các run đó thực ra do nhiều người chạy chung tài khoản `admin` và bạn muốn gán lại chủ sở hữu trước khi migration? (Nếu gán lại thì không suy ra được từ dữ liệu hiện có — `CREATED_BY` là bằng chứng duy nhất về người chạy.) |

## Ghi nhận rà soát dữ liệu (05/11/2026, chỉ từ code + DB seed trong clone)

- `RECON_RUN.CREATED_BY`: chỉ `create_run` (`app/services/run_service.py`) ghi, bằng `ctx.username`; `dry_run` đi qua `create_run` rồi xóa run tạm, nên không tạo run lạ. Ngoại lệ duy nhất là script demo `scripts/demo_run.py` tạo run với username `demo_user` (không phải user trong `RECON_USER`).
- `RECON_BATCH_RUN.CREATED_BY`: chưa có bảng, chưa kiểm chứng được; theo spec 10a mọi bảng đều có `CREATED_BY`, và task 18 sẽ ghi bằng `ctx.username` khi tạo lần chạy bộ.
- `RECON_USER_ROLE` hiện tại: `USER_ID, ROLE, ORG_SCOPE`; migration đổi sang `ROLE_ID` và bỏ `ORG_SCOPE` (spec 11a mục 5 không nhắc `ORG_SCOPE` — plan sẽ giữ lại hay bỏ cần chốt ở bước 1; DB seed hiện `ORG_SCOPE` đều NULL).
- Sau migration, theo seed 11a mục 7 (ADMIN luôn có mọi menu nên không liệt kê):
  - `admin` (ADMIN): không đổi, thêm menu `role`, `menu_admin`, `batch_run`, `batch_def` khi các menu này xuất hiện.
  - `owner` (TEMPLATE_OWNER): được thêm `batch_run`, `batch_def` (menu mới, chưa có code); các menu khác giữ nguyên.
  - `operator` (OPERATOR): được thêm `batch_run`; **mất `template`** so với thanh bên hiện tại (xem Q4).
  - `viewer` (VIEWER): được thêm `template`, `batch_def`; **mất `issue`** so với thanh bên hiện tại (xem Q4).

## Quyết định khi duyệt plan (05/11/2026, 12:43)

Người dùng nhắn "duyệt plan, làm theo đề xuất làm xong task 19 rồi gửi mình xem". Chốt theo đề xuất đã trình:
- Q0: làm trên nhánh mới `feat/19-menu-permission` từ `ae8e3af`.
- Q1: task 18 tạm bỏ qua; batch chỉ khai báo + seed, owner_filter cho batch để lại sau.
- Q2: Screen14 đã có trên remote (`ae8e3af`), làm màn `/roles` theo preview thật.
- Q3: giữ `/history`, sửa link ở `run_result.py` sang `/history`.
- Q4: chấp nhận OPERATOR mất `template`, VIEWER mất `issue` theo seed.
- Q5: giữ rào chắn ghi/xóa template hiện tại.
- Q6: miễn `menu_code` cho `/account`, `/login`, `/forbidden`, `/dev/ui`.
- Q7: khai báo `menu_admin` nhưng tạm ẩn khỏi thanh bên tới task 20.
- Q8: tải file gốc cho phép nếu thỏa một trong ba: file do mình upload, file thuộc run của mình, hoặc file mẫu của template mình có menu.
- Q9: issue chỉ theo `FIRST_RUN_ID`.
- Q10: **chốt hướng 1** — các run cũ giữ nguyên `CREATED_BY='admin'`, chỉ ADMIN thấy; không gán lại chủ sở hữu (người dùng duyệt plan mà không yêu cầu bảng gán lại).
- Q11: xóa riêng một run của mình theo owner_filter, không cần ADMIN; chỉ xóa hàng loạt mới require_admin.

## Suy ra trong lúc làm

- Bước 3: `effective_menus` tra DB theo `user_id`. Nhưng CLI (`purge-temp`) dùng ctx `cli_admin` và worker dùng ctx `system`, đều không phải user trong DB. Quyết định: user không có trong DB thì tính menu từ `ctx.roles` theo đúng bảng seed 11a mục 7 (đường lui cho luồng nội bộ; ctx chỉ được tạo ở server, không từ input người dùng). User có trong DB nhưng bị vô hiệu thì trả về tập rỗng.

## Cập nhật 05/11/2026 — Task 18 tạm bỏ qua, Q1 và Q2 đã gỡ

- 12:37 bạn nói task 18 tạm thời bỏ qua. Q1 coi như chốt theo hướng: làm task 19 ngay trên code hiện tại; menu `batch_run`, `batch_def` chỉ khai báo + seed, chưa có page/service để gắn; owner_filter cho batch (danh sách, ma trận, .zip, chạy lại run lỗi, thay file) để lại khi task 18 làm sau. Test T19-05-03 và fixture 2 lần chạy bộ ở T19-00-01 sẽ viết dạng skip có ghi chú cho tới khi task 18 xong.
- Q2 đã gỡ bằng commit `ae8e3af` (xem mục dưới).

## Cập nhật 05/11/2026 — Screen14/Screen15 đã có trên remote

- Bạn đã push `ae8e3af` "docs(design): add Screen14 Permission and Screen15 MenuAdmin"; clone đã đồng bộ về `ae8e3af`, có đủ `designs/components/Screen14-Permission/README.md` + `preview.html` và `designs/components/Screen15-MenuAdmin/README.md` + `preview.html`.
- Q2 về mặt file đã gỡ: bước 6 của plan có thể làm theo preview Screen14 thật, không cần làm theo mô tả suông nữa. Vẫn chờ bạn duyệt plan và trả lời các câu còn lại (Q0, Q1, Q3–Q11).
- Lưu ý: lần đồng bộ này dùng `git reset --hard` nên đã xóa bản decisions.md chưa commit trong clone; bản này đã được viết lại nguyên vẹn từ nội dung đã trình trong chat. Từ nay, trước mỗi lần đồng bộ, cần kiểm tra `git status` trong clone để không mất thay đổi chưa commit.

## Cập nhật 05/11/2026 — Làm lại bố cục /roles theo Screen14

Người dùng yêu cầu rà soát bố cục ("nhìn quá xấu"), đã đối chiếu ảnh chụp thật với prototype Screen14 và duyệt "làm luôn, sửa layout theo đề xuất" 17:31. Chỉ đổi bố cục, không đổi hành vi hay quyền:
- Mỗi khối thành 1 thẻ card (cột trái, form vai trò, menu, preview, bảng người dùng, tab 2); Tên vai trò + Mô tả xếp 2 cột; đầu trang gọn thành 1 dòng mô tả, ghi chú phạm vi chuyển xuống dưới thẻ preview.
- Menu xếp lưới 3 cột theo nhóm, mỗi nhóm có số lượng "x/y", tiêu đề card có tổng "X/13 menu".
- Bỏ nhãn "Mới" khỏi checkbox menu: sau migration mọi menu đều IS_NEW='Y' nên nhãn hiện trên cả 13 mục, mất tác dụng. Cờ IS_NEW vẫn giữ trong DB cho màn quản trị menu (task 20).
- Preview thành khung mô phỏng thanh bên, nhưng theo thanh bên THẬT của app (nền sáng xám) chứ không phải khung tối navy của prototype — thanh bên thật là nền sáng, preview tối sẽ không giống thứ người dùng thực sự thấy.
- Thanh Hủy/Lưu dính đáy (sticky), luôn hiện, nút mờ đi khi chưa có thay đổi (trước đây ẩn và nằm cuối trang, phải cuộn xuống mới thấy). Callback form-change giờ trả `disabled` của 2 nút thay vì `style` của thanh.
- Cột trái thêm chip "N vai trò", mỗi vai trò có chip "X/Y menu" + "Hệ thống"/"Đã tắt"; nút chọn vai trò cao tự động theo nội dung 3 dòng (trước đây tràn đè nhau).
