# Task 63 — Modal stepper chuyển Oracle + switch thật/fake

## Yêu cầu gốc (user, 11/11/2026 21:44)
> "phương án A, khi bấm chuyển sang oracle, thì mở modal lên và chạy, làm để check trước, chưa Migration thật, thêm switch để bật hoặc tắt migration thật hay fake"

Người dùng đã chọn phương án A từ 3 phương án ở task 62-follow-up (A: một nút chạy hết, xem tiến trình trực tiếp; B: chạy từng bước bằng tay; C: giữ chạy như cũ, chỉ thêm stepper + checklist sau khi xong). Trước đó user yêu cầu: chỗ bấm "Chuyển sang Oracle" thêm các bước chạy theo layout stepper dọc như hình (wizard 6 bước: Thông tin / Nguồn dữ liệu / Tham số & LOV / Cấu hình cột / Xem trước / Hoàn tất), bước chính nào chạy thì ghi lại checklist từng bước con.

## Phạm vi đã duyệt (plan trình 21:47, user "ok" 21:48)
1. Modal "Chuyển sang Oracle": bấm nút thì mở modal (thay vì chạy ngay). Trong modal: tóm tắt đích + chế độ đã chọn, switch "Migration thật" (mặc định TẮT = fake), nút "Bắt đầu", stepper dọc 6 bước, mỗi bước có checklist bước con với trạng thái từng dòng.
2. Fake (mặc định, để check trước): chạy precheck thật (chỉ đọc), các bước 2–6 mô phỏng theo ước tính từ precheck, hiện báo cáo đối chiếu giả + 4 bước làm tay tiếp theo. Không ghi gì sang Oracle, không bật bảo trì, không tạo bản ghi migration.
3. Thật (switch BẬT): chạy migration thật trong luồng nền, service ghi tiến độ checklist vào bản ghi migration (thêm cột CHECKLIST_JSON — migration 0008), modal poll để cập nhật trực tiếp. Lỗi ở bước nào dừng ở đó. Đóng modal giữa chừng thì migration vẫn chạy tiếp; mở lại thấy đúng tiến độ. Cảnh báo rõ khi switch BẬT.
4. Kiểm chứng: test unit + check live Playwright + full suite xanh rồi giao patch.

## 6 bước chính (map từ code migration hiện tại)
1. Kiểm tra trước — quyền ADMIN; Data Source đích tồn tại; đích khác DB đang dùng; không có run đang chờ/chạy; schema đích trống; ước tính số bảng/dòng/dung lượng.
2. Bật chế độ bảo trì — ghi MAINTENANCE=Y; ghi audit log; tạo phiên migration (PROCESSING, 10%).
3. Tạo schema đích — tạo các bảng RECON_* trên Oracle.
4. Sao chép dữ liệu — chép từng bảng theo lô 5.000 dòng; đồng bộ Identity Oracle; nối lại liên kết RECON_RUN ↔ RECON_BATCH_RUN_ITEM; đối chiếu số dòng từng bảng.
5. Đối chiếu toàn vẹn — checksum SHA256 3 bảng lớn nhất, nguồn vs đích.
6. Hoàn tất — ghi phiên migration DONE 100% + báo cáo đối chiếu; hiện 4 bước làm tay tiếp theo (dừng app/worker → đổi RECON_DB_URL → db-migrate → khởi động lại).

## Ràng buộc an toàn
- Mặc định là fake: user cứ bấm kiểm tra thoải mái, không có gì ghi sang Oracle cho tới khi chủ động gạt switch sang BẬT.
- Nút "Kiểm tra trước" và "Xóa schema đích" hiện tại giữ nguyên.
- Khi switch BẬT, modal phải hiện cảnh báo rõ: sẽ ghi dữ liệu thật sang Oracle và bật chế độ bảo trì.
