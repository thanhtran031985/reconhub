# Progress — Task 91

- Nhánh `feat/91-data-sources-mount-firing` từ 9b2ada5 (task 90).
- Đã đo: mở `/data-sources` 13 request, nội dung sau 2,7s; danh sách
  tải 2 lần; audit giả ACTIVATE_DATA_SOURCE ID 11 ghi lúc mở trang.
- Đã viết task.md / plan.md / decisions.md (D1–D6).
- Đã sửa `app/ui/pages/data_sources.py` (D1 toggle guard theo DB,
  D2 storage chỉ tải khi tab storage + prevent_initial_call, D3 guard
  n_clicks cho purge preview, D4 drawer trả no_update khi mount).
- Test: 8 test mới trong `tests/unit/test_page_data_sources.py`
  (13 passed cả file); suite liên quan (data_source_service,
  migration_fixes65, migration_followup65) 34 passed.
- Live check `check-91-data-sources.py` PASS (port 8147): S0 list 1
  lần, không toggle, không storage, không audit mới; S1 bấm Switch
  thật đổi trạng thái + audit +1; S2 tab Lưu trữ tải khi bấm, không
  tự chạy preview; không lỗi console. Lưu ý: nội dung hiện sau ~7,8s
  trong check là do `networkidle` chờ request icon CDN bị proxy chặn,
  không phải app chậm (longtask max 93ms).
- Lint chỉ còn lỗi I001 cũ; typecheck sạch.
- Full suite: **2001 passed, 6 skipped** (1993 + 8 test mới).
