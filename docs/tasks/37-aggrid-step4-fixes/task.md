# 37-aggrid-step4-fixes — Sửa 6 lỗi bước 4 / bước 1 / tab 3 sau khi áp 35+36

- Ngày tạo: 2026-11-10
- Giai đoạn: GĐ3 (fix, theo mẫu task 33/36 — không thêm dòng dashboard)
- Phụ thuộc: 34, 35, 36
- Nhánh git: feat/37-aggrid-step4-fixes (rẽ từ `8adbeb7`, đỉnh `feat/36-dryrun-limit`)

## Vấn đề (người dùng báo 10/11/2026, kèm ảnh bước 4 và tab 3)

1. **Xóa cột → grid trống trơn.** Tái hiện live: 3 dòng → xóa 1 dòng, DB
   còn 2 cột nhưng grid chỉ hiện 1 dòng (grid nhiều cột thì hiện trống hẳn).
   Console: `Duplicate node id 'undefined' detected from getRowId callback`
   + AG Grid error #25 (`id=undefined`). Gốc: `getRowId="id"` dạng chuỗi
   KHÔNG hoạt động ở dash-ag-grid 35.3.0 — callback trả `undefined` cho mọi
   dòng nên khi `rowData` đổi (sau xóa), row model đối chiếu theo id trùng
   nhau và rớt dòng. (Kết luận "chuỗi hoạt động" ở prototype task 35 là sai
   — prototype không kiểm tra console warning.)
2. **Thiếu mũi tên lên/xuống** đổi thứ tự cột (task 35 đã bỏ theo Q11, nay
   người dùng yêu cầu thêm lại, bên cạnh kéo-thả).
3. **Cột grid không chiếm full chiều rộng** — còn khoảng trống phía phải
   (tổng width cố định ~980px, container ~1210px).
4. **Card tràn xuống footer gây scroll.** Grid `calc(100vh - 310px)` tính
   thiếu chrome thực tế (~377px tới chân grid): footer 48px + top bar +
   tabs + padding. Người dùng hỏi thu footer còn 1/2.
5. **Bước 1 bấm "Tiếp theo" qua bước 2 lại hiện "Đã lưu thông tin."**
   Gốc: nút Tiếp theo bước 1 là `admin-s1-save-btn`, chạy
   `handle_save_step1` luôn gọi update + toast dù không đổi gì.
6. **Tab 3 layout tham số:** giá trị Hàng/Cột chưa căn giữa thật (nút
   tăng/giảm của NumberInput đẩy chữ lệch) và nhóm Hàng/Cột có thể rớt
   xuống dòng trong box hẹp (dmc.Group mặc định `wrap="wrap"`).

## Phạm vi

- (1) `getRowId` dạng `{"function": "params.data.id"}` (đã kiểm chứng bằng
  prototype: hết warning, xóa giữ đủ dòng) — nếu không được thì bỏ hẳn.
- (2) Nút ↑ Lên / ↓ Xuống cạnh "Xóa cột đã chọn": đổi thứ tự trong
  `rowData` qua callback, "Lưu cột" ghi như kéo-thả; disable khi chưa chọn
  hoặc đã ở đầu/cuối.
- (3) `flex: 1` (+ `minWidth`) cho 2 cột text Trường DB và Nhãn.
- (4) Footer 48px → 26px (nút 30px → 22px, capsule p 3 → 2); grid
  `calc(100vh - 310px)` → `calc(100vh - 380px)` (chrome thực tế đo từ
  ảnh chụp: tới chân grid ~377px).
- (5) `handle_save_step1` nhánh sửa: so sánh form với DB trước khi update;
  không đổi → qua bước 2 im lặng (không gọi service, không toast); có đổi
  → lưu + toast như cũ. Nhánh tạo mới giữ nguyên (bắt buộc tạo mới).
- (6) Hàng/Cột: `hideControls` + `textAlign center` + `lineHeight 22px`
  cho NumberInput; Group ngoài/trong `wrap="nowrap"`, thu w 38 → 34,
  gap xs → 4 để vừa box 2/12.
