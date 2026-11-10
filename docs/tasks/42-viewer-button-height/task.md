# Task 42 — Nút "Xem báo cáo" cao bằng ô nhập tham số

## Yêu cầu (10/11/2026, người dùng, kèm ảnh màn hình)

- Nút "Xem báo cáo" ở form tham số /reports/<id> thấp hơn các ô nhập
  (Từ ngày, Đến ngày, App, Org) — chỉnh độ cao nút bằng chiều cao của item.

## Chẩn đoán

- Nút Xem: `dmc.Button(..., size="xs")` trong `report_viewer.py` → cao
  30px (Mantine xs).
- Các ô nhập (`dmc.DateInput`/`dmc.Select`/`dmc.TextInput` trong
  `render_param_control`) không đặt size → mặc định Mantine "sm" → cao
  36px. Nút nằm ở ô grid cuối với `alignSelf: "end"` nên đáy bằng đáy
  ô nhập nhưng đỉnh thấp hơn 6px, nhìn lệch.
- Sửa: đổi nút Xem sang `size="sm"` (36px, đúng bằng ô nhập, không cần
  hardcode px). Không đụng nút "Xuất Excel" (không nằm trong yêu cầu).

## Ghi chú ngoài phạm vi (không code)

- Người dùng báo binds `p_org = None` ở tab SQL: đó là hành vi đúng —
  Org trống thì bind NULL (task 39). Lỗi làm Org trống ra 0 dòng nằm ở
  SQL của version: `(org_CODE = :p_org or org_code is null)` — vế sau
  kiểm tra CỘT `org_code` null chứ không phải bind; khi `:p_org` NULL
  thì `org_CODE = NULL` luôn UNKNOWN. Sửa SQL version trong /report-admin
  thành `where (:p_org is null or org_CODE = :p_org)`.
- Binds trong tab SQL là của lần chạy gần nhất; đổi ngày trên form rồi
  chạy lại thì binds cập nhật theo.
