# Task 77 — Plan: viewer chuyển tab template đổi form + xóa kết quả cũ

## Thiết kế (theo chẩn đoán)

1. **Handler thuần + callback mới** (mẫu handler task 74/75):
   `handle_viewer_tab_switch(tab_value, version_store, templates_store,
   run_store)` + callback `handle_viewer_tab_switch_click`:
   - Input `viewer-tabs.value`; State `viewer-version-store`,
     `viewer-templates-store`, `viewer-run-store`.
   - Outputs: `viewer-param-form.children`, `viewer-version-store.data`,
     `viewer-run-store.data`, `viewer-page-store.data`,
     `viewer-run-error.children`.
   - Guard: `prevent_initial_call=True` + chỉ chạy khi template chọn
     khác template của version-store hiện tại (lúc mở trang Tabs đã
     mang id template đầu tiên và version-store đã đúng nó → không vẽ
     lại). Giá trị rỗng/không đổi → PreventUpdate.
   - Tìm `active_version_id` của template chọn trong templates-store;
     không có → báo lỗi, giữ nguyên form cũ. Có → `get_version` +
     `preview_layout(ctx, version_id)` + `_lov_options` cho từng param
     SELECT + `render_param_form(preview, options, action=nút "Xem
     báo cáo")` (giữ đúng id `viewer-run-btn` để callback chạy dùng
     lại được). Version-store nhận version detail mới; run-store → {},
     page → 1, xóa lỗi (kết quả cũ thuộc template kia; count + grid do
     `handle_result_render` tự về empty state khi run-store rỗng).
2. **Không tự chạy khi đổi tab** (D1): người dùng bấm "Xem báo cáo"
   để tải dữ liệu template mới.

## Các bước

1. Test đỏ trước: handler switch (đổi sang template 2 → form mới +
   version-store mới + run-store rỗng; cùng template → PreventUpdate;
   template không có ACTIVE version → lỗi + giữ form cũ); render
   (viewer 2 template hiện đủ 2 tab).
2. Sửa report_viewer.py theo thiết kế trên.
3. Check live (port 8128, DB riêng): seed báo cáo 2 template ACTIVE
   với tham số KHÁC NHAU (vd catos: Tdate/Fdate/Org/App; vtos: mã
   tham số khác hoặc nhãn khác để form đổi visibly); mở viewer, chạy
   catos → có dữ liệu; bấm tab vtos → form hiện tham số vtos, kết
   quả về trạng thái trống; bấm Xem → dữ liệu vtos (kiểm run có
   template_id/version_id của vtos); bấm lại tab catos → form về
   tham số catos; JS sạch (quét CẢ console error VÀ pageerror).
4. Typecheck/ruff + full suite → commit → patch (áp sau patch 76;
   file rời nhau với 76 nên thứ tự chỉ để giữ số) → giao user.

## Lưu ý

- Nhánh `feat/77-viewer-template-tabs` tách từ HEAD task 75
  (`bcc5b5c`), cùng gốc với nhánh 76 (file rời nhau).
- Nút Xuất Excel + tab SQL đọc run-store nên xóa run-store khi đổi
  tab cũng giữ chúng nhất quán (không xuất nhầm kết quả catos khi
  đang ở tab vtos).
