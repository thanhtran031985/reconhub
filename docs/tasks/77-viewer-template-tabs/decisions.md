# Task 77 — Decisions

- D1: đổi tab template vẽ lại form + xóa kết quả cũ, KHÔNG tự chạy
  báo cáo — người dùng bấm "Xem báo cáo" để tải dữ liệu template
  mới (tránh tạo run không ai yêu cầu; tham số 2 template có thể
  khác nhau).
- D2: guard đổi tab so với template của version-store hiện tại (lúc
  mở trang đã đúng template đầu tiên → không vẽ lại); template chọn
  không có ACTIVE version thì báo lỗi, giữ nguyên form cũ.
- D3: nhánh `feat/77-viewer-template-tabs` tách từ HEAD task 75
  (`bcc5b5c`); patch 77 áp sau patch 76 (file rời nhau với 76).
