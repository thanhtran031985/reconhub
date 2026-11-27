# Quyết định — 109-report-studio-viewer

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-26 | Tái sử dụng `RECON_REPORT` + `RECON_REPORT_TEMPLATE` + `RECON_RPT_TPL_VER` (`SOURCE_TYPE='SEMANTIC_MODEL'`) | Đưa báo cáo Studio vào chung `/reports`, dùng lại toàn bộ `RECON_RPT_PARAM`, LOV cache, preset, favorite, export worker | Migration `0019` mở rộng bảng sẵn có + thêm `RECON_RPT_VISUAL*` |
| 2026-11-26 | Tách `RECON_RPT_VISUAL` & `RECON_RPT_VISUAL_FIELD` dạng normalized | Cho phép Impact Analysis từ Model Studio truy vấn SQL chính xác visual nào dùng field/measure nào | Đáp ứng mục §12 & §76 của prompt gốc |
| 2026-11-26 | Lưới 12 cột dùng `GRID_SPAN` (`3/4/6/8/12`) + `HEIGHT_SIZE` + kéo đổi thứ tự | Chưa cài `react-grid-layout`; dùng lưới `dmc.Grid` tránh chồng lấn visual, đảm bảo desktop không page-scroll và mobile tự xếp dọc | Điều chỉnh từ mục §49 (thay free-resize pixel) |
| 2026-11-26 | Export theo từng visual (Per-Visual Export) | Một báo cáo Studio có thể gồm KPI, Chart và Table có cấu trúc cột khác nhau; xuất từng visual khớp tự nhiên với 1 `RECON_REPORT_RUN` / `RECON_RPT_EXPORT` | Mở rộng `RECON_REPORT_RUN` thêm `VISUAL_ID` + `QUERY_SPEC_JSON` |
| 2026-11-26 | Đưa `Drill-through` và đa trang (`REPORT_PAGE`) sang V2 | Prompt chỉ nhắc tên well trong §45, không có đặc tả Visual V1 hay điều hướng drill-through | Giữ V1 gọn, chắc và đồng bộ với multi-template tabs của `/reports/<id>` |
| 2026-11-27 | Phân quyền `report_studio` chỉ cho `ADMIN` + `TEMPLATE_OWNER`; giữ HTML5 Drag & Drop thuần (`studio_drag_drop.js`) | Đồng bộ phân quyền thiết kế với `report_model` (Operator/Viewer xem & xuất ở `/reports`); giữ kiến trúc không thêm JS ngoài như `mail_drag_drop.js` / `drag_drop_reporting.js` | `app/ui/menus.py` cấp cho `TEMPLATE_OWNER`; không cài `SortableJS` |
| 2026-11-27 | Sắp thứ tự `RECON_RPT_MODEL*` trước `RECON_RPT_TPL_VER` trong `RECON_TABLES_ORDER` | `RECON_RPT_TPL_VER` thêm FK `MODEL_VERSION_ID` trỏ sang `RECON_RPT_MODEL_VER.ID` nên migration dữ liệu sang Oracle cần bảng cha model đi trước | Cập nhật `app/services/metadata_migration.py` ở Bước 1 |

## Câu hỏi còn mở
- Không có.
