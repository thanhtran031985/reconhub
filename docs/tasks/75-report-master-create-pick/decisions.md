# Task 75 — Decisions

- D1: tạo mã báo cáo là modal trên /reports (mẫu modal task 74),
  không làm trang riêng — nhỏ, đủ dùng, hub làm mới ngay sau khi tạo.
- D2: wizard bước 1 thêm Select "Báo cáo *" với option "Báo cáo mới"
  (mặc định, giữ hành vi hiện tại). Chọn báo cáo có sẵn → khóa các ô
  báo cáo, lưu đi nhánh D4 của task 74 (chỉ `create_template`).
- D3: nhánh `feat/75-report-master-create-pick` tách từ HEAD task 74
  (`6c97076`); patch 75 áp sau patch 74.
