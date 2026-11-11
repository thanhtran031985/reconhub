# Task 52 — decisions

- D1: Chạy ngầm chỉ đổi giao diện chờ/tải ở viewer; engine
  (`request_export`, worker, hàng đợi) giữ nguyên.
- D2: Không thông báo chủ động khi export xong — user tự vào Lịch sử
  xem (theo yêu cầu user 11/11/2026).
- D3: "Xuất lại" = run mới (chạy lại báo cáo với cùng tham số, dữ liệu
  mới) + tự xuất; không dùng lại file DONE cũ (vì `execute_export` đọc
  kết quả đã lưu của run — xuất lại cùng run sẽ ra file cũ).
- D4: Xếp hàng giữ nguyên FIFO theo CREATED_AT, tối đa 2 export RUNNING
  mỗi user (worker hiện tại); muốn song song hơn thì tăng số worker lúc
  vận hành, không phải code.
- D5: Dọn file: setting trong `RECON_APP_SETTING`
  (`EXPORT_RETENTION_MODE` manual|scheduler, mặc định manual;
  `EXPORT_RETENTION_DAYS`, mặc định 30); scheduler thì worker export
  sweep tối đa 1 lần/giờ, chỉ xóa export đã kết thúc (DONE/FAILED/
  CANCELLED) quá N ngày — xóa cả file trên đĩa + dòng export, không xóa
  run, ghi audit.
- D6: "Xuất lại" không cần cột cờ hay migration: run của viewer chạy
  đồng bộ trong web process (`execute_report_run`: count + 1 trang) nên
  service `rerun_and_export` tạo run mới → chạy ngay → DONE thì gọi
  `request_export` trong một lần gọi. Version theo ACTIVE như "Chạy
  lại" (task 43). Không có hook trong `execute_run` (worker chạy run
  đối soát /runs/new, không chạy run của viewer).
- D7: Nhánh `feat/52-export-background` từ `973a431` (tip task 51);
  patch áp sau patch 51, không cần `db-migrate`, khởi động lại app và
  worker.
- D8: 4 nút hành động export ở Lịch sử (Thử lại/Hủy/Xóa/Xuất lại) dùng
  CHUNG 1 callback (`ALL` + `triggered_id`, logic thuần trong
  `_do_export_action`): 4 callback MATCH riêng cùng ghi 2 output chung
  làm Dash báo "Overlapping wildcard callback outputs" khiến cả app
  không mount được (login cũng không hiện) — phát hiện khi chạy
  Playwright check-52. Nút "Xuất lại" vì vậy không có loading chống
  bấm 2 lần như nút Xem/Xuất ở viewer; bấm 2 lần sẽ tạo 2 run (thấy rõ
  trong bảng, hủy/xóa được).
- D9: Guard chống kích nhầm (phát hiện khi chạy check-52 lần 2): ALL
  inputs đổi mỗi khi bảng Lịch sử render lại (tập nút thay đổi khi
  export đổi trạng thái/run mới xuất hiện) nên callback hành động bị
  kích lại mà không có bấm thật — đã gây ra hủy/xóa/xuất-lại ngẫu nhiên
  (audit log có CANCEL/DELETE/RERUN không ai bấm) và làm lỗi tải file
  (500 do file bị xóa đúng lúc tải). Sửa bằng store
  `report-runs-action-clicks` lưu map nút → số lần bấm: chỉ hành động
  khi nút trigger tăng count; lần kích lại chỉ reset map. Sau sửa,
  check-52 13/13 và audit sạch (2 run, 2 export DONE, 0 hủy/xóa thừa).
