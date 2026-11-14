# Task 90 — Drawer chi tiết run bị khựng vài giây khi thao tác

## Yêu cầu (user, 14/11/2026)
- Trang `/runs/1034` (vd nhóm `2026-04-13 14:45:56 | C26TBD0082654`): tải modal
  và dữ liệu thì nhanh, nhưng thao tác trên modal bị khựng lại vài giây mới
  thao tác được (click vào list, textbox, scroll).

## Phân tích nguyên nhân (đã đo, xem decisions D1)
- Mở drawer → nút Lưu mount mới → callback lưu chạy theo (Dash chạy callback
  khi component mới xuất hiện) → nhánh chặn trả `(no_update, 0)` → số `0`
  là một lần gán thật vào Store kích hoạt vẽ lại grid → Dash coi mọi lần gán
  vào Store là thay đổi (không so sánh giá trị Store) → callback vẽ lại grid
  chạy → vẽ lại cả 50 dòng (response 140KB) → renderer tốn ~7,4 giây
  diff props trên main thread → drawer đứng hình đúng lúc user thao tác.
- Đo trên máy ảo (run #1040, nhóm 2 dòng): mở drawer lần nào cũng có đúng
  4 response theo thứ tự — drawer 9KB, ghi trigger Store 0KB, vẽ lại grid
  140KB, shell 11KB — và một longtask 7,3–8,4 giây trong `dash_renderer`
  (`isFirstLevelPropsChild`, `determineChangedProps`). Lặp lại ở lần mở
  thứ 2, không phụ thuộc kích thước nhóm → không phải do dữ liệu to.
- Server nhanh (~80ms/lần mở), truy vấn đều dùng khóa chính, không thiếu index.

## Thay đổi
- `app/ui/pages/run_result.py::handle_save_issue_from_drawer`: 5 chỗ trả về
  ở nhánh chặn/lỗi đổi `0` thành `dash.no_update` cho output trigger Store.
  Chỉ khi lưu thật thành công mới kích hoạt vẽ lại grid (giữ nguyên
  `int(n_clicks or 1)`).
- Test: `test_handle_save_issue_from_drawer` đổi `assert trig == 0` thành
  `trig is dash.no_update`; thêm test mới cho các nhánh lỗi còn lại
  (meta không phải dict, chưa đăng nhập, run/row không hợp lệ, upsert lỗi)
  đều trả `no_update` cho trigger; nhánh thành công vẫn bump trigger.

## Không đổi
- Hành vi lưu thành công: vẫn vẽ lại grid để cập nhật badge trạng thái.
- Thời gian vẽ lại grid khi thật sự cần (đổi filter, lưu thành công) vẫn
  ~7 giây vì bảng 50 dòng vẽ tay — làm nhanh phần đó là việc khác, lớn hơn.
- Không db-migrate; chỉ khởi động lại app.
