# Quyết định kỹ thuật — TASK UI-01: Compact Lists

| Ngày | Quyết định | Lý do | Ảnh hưởng spec |
|---|---|---|---|
| 2026-11-07 | Giữ nguyên pattern-matching component IDs cho các thao tác dòng | Đảm bảo 100% callback Dash hiện có (nhân bản, xuất JSON, lưu trữ, xóa) không bị gãy vỡ | Không đổi callback logic |
| 2026-11-07 | Áp dụng container flex 1 với header bảng `position: sticky` cho Compact Tables | Triệt tiêu triệt để hiện tượng cuộn trang desktop 1366×768 trong khi giữ nguyên các thao tác trực quan | Tuân thủ triệt để UI spec & preview-fluent |
| 2026-11-07 | Chuyển `/reports` từ Card Grid sang Grouped Table (`rlist`) | Thẻ Card chiếm quá nhiều chiều cao, không hiển thị được nhiều báo cáo cùng lúc | Phù hợp mục 10 của docs/ui-migration.md |
