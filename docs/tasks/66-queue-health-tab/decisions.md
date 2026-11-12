# Decisions — Task 66

- D1: "1 tab" được hiểu là 1 mục menu riêng trong sidebar (trang /queue-health), card rời khỏi dashboard hẳn — không phải tab con trong trang dashboard.
- D2: link run kẹt → /report-runs (nơi run tồn tại + có đủ thao tác), không tạo trang chi tiết riêng cho run báo cáo.
- D3: cấp quyền bằng migration 0009 (dữ liệu) thay vì để ADMIN gán tay trên /roles — user chỉ cần db-migrate sau khi áp patch.
- D4: `format_short_dt` KHÔNG import từ dashboard.py (lệch plan): plan ghi import từ dashboard, nhưng check live 66 phát hiện import chéo giữa các module trang làm Dash báo "modules ['app.ui.pages.dashboard', 'pages.dashboard'] have duplicate paths" và MỌI request trả 500 (app vẫn lên, chỉ request mới lỗi nên unit test không bắt được). Fix: định nghĩa bản sao y hệt ngay trong queue_health.py — đúng mẫu có sẵn (history.py đã sao y hệt hàm này). Quy tắc: các module trang Dash không được import lẫn nhau.
- D5: migration 0009 downgrade chỉ gỡ các dòng grant do chính nó thêm (GRANTED_BY='SEED'), giữ nguyên dòng RECON_MENU (thuộc về menu_sync; xóa có thể làm mất DISPLAY_* do ADMIN tùy chỉnh).
- D6: card trên trang riêng giữ nguyên body maxHeight 220 như trên dashboard — chỉ bề rộng thay đổi.

- D6 (parent, 12/11/2026): check 66-2 FAIL lặp lại khi parent chạy lại (10/11) dù subagent báo 11/11 — KHÔNG phải lỗi app: Dash Pages vẽ lại layout 2 lần khi điều hướng SPA nên #queue-health-card-body có thể bị gỡ rồi gắn lại trong ~100ms sau khi hiện lần đầu (probe: count ngay sau wait_for = 0 ở 2/5 lần, 100ms sau luôn = 1, app chỉ dùng use_pages=True, không có display_page tự viết). Sửa check script (chờ nội dung ổn định qua wait_for_function thay vì đếm ngay sau wait_for) → 11/11. Bài học: check Playwright sau điều hướng SPA phải chờ nội dung/text ổn định, không assert count() ngay sau wait_for.

- D7 (parent, 12/11/2026): full suite bắt 3 test test_role_service.py sót chưa cập nhật kỳ vọng menu OPERATOR (thêm queue_health) — sửa test, không sửa app (menu mới cho OPERATOR là đúng ý task).

## Follow-up: bảng Đang chạy / Đang chờ + badge + filter (12/11/2026)

- F1: bảng mới lấy từ cùng service (thêm key `"active"`), không thêm query mới.
- F2: badge trạng thái bằng `status_chip` (RUNNING → Đang chạy, QUEUED → Đang chờ); cột Loại giữ chữ Export/Run như bảng kẹt, không thêm badge loại.
- F3: 2 Select filter ở header tĩnh của card (ngoài vùng body vẽ lại); chỉ lọc bảng đang chạy/đang chờ, bảng kẹt giữ nguyên.
- F4: không thêm cột tiến độ % cho export đang chạy (ngoài phạm vi).
- F5: không migration; patch follow-up áp sau patch 66, chỉ khởi động lại app.
