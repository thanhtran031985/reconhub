# Tiến độ — 30-menu-search

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Bỏ hẳn badge "Mới" ở menu thanh bên | ✅ | 2026-11-09 | 30-menu-search: steps 1-2 |
| 2 | Ô tìm kiếm menu ở header (sau breadcrumb, trước badge môi trường) | ✅ | 2026-11-09 | 30-menu-search: steps 1-2 |
| 3 | Chọn menu bằng phím mũi tên lên/xuống trong ô tìm kiếm | ✅ | 2026-11-09 | 30-menu-search: step 3 - arrow-key navigation |

## Nhật ký
- 2026-11-09: Khởi tạo task 30 từ yêu cầu của người dùng (bỏ badge "Mới" + thêm ô tìm kiếm menu ở header, bo tròn kiểu Google Search, tìm có dấu/không dấu). Tạo nhánh `feat/30-menu-search` từ `4cf90bf`. Lên plan và được duyệt (Q0–Q3 theo đề xuất: Enter tới kết quả đầu, giới hạn 8 kết quả, chỉ khớp tên menu, rộng 320px).
- 2026-11-09: Hoàn thành bước 1 + 2 trong một commit chung (thay vì mỗi bước một commit như plan, vì cả hai bước cùng sửa `shell.py` và dùng chung file test `test_ui_shell.py`, tách ra sẽ làm commit giữa bị vỡ test): bỏ khối `dmc.Badge("Mới")` trong `create_navbar`; thêm `dmc.TextInput` bo tròn + `dcc.Store` + `dmc.Paper` kết quả trong `create_header`, helper `_strip_accents`/`filter_menu_items`, callback `handle_menu_search`. Test shell 17 pass, ruff + mypy sạch.
- 2026-11-09: Sửa lỗi phát hiện khi kiểm chứng Playwright: sau khi chuyển trang, ô tìm kiếm vẫn giữ từ vừa gõ (Dash giữ lại giá trị input theo id khi header dựng lại). Sửa: `TextInput` đặt sẵn `value=""` + callback `handle_menu_search` thêm Input `app-location.pathname` và Output giá trị ô tìm kiếm (đổi trang → xoá trắng + đóng dropdown). Test shell 18 pass (thêm test đổi trang xoá ô tìm kiếm), ruff + mypy sạch.
- 2026-11-09: Kiểm chứng Playwright trên server thử (DB có IS_NEW='Y' cho cả 16 menu): thanh bên không còn "Mới" (1440×900 và 1366×768); ô tìm kiếm hiện giữa breadcrumb và badge môi trường (x 518–838 ở 1440, 481–801 ở 1366), rộng 320px; gõ "doi soat" → 3 kết quả (Chạy đối soát, Chạy bộ đối soát, Bộ đối soát); Enter → /runs/new, ô tìm kiếm trống; bấm "Lịch sử" → /history; gõ "xyz" → "Không tìm thấy menu nào". Ảnh: `~/workspace/dashboard-preview/menu-search-1440.png`, `menu-search-1366.png`.
- 2026-11-09: Full suite 1247 pass, 6 skipped (Oracle skip, không VPN). Patch `~/workspace/reconhub-menu-search.patch` (3 commit, `4cf90bf..HEAD`) đã kiểm chứng `git am` sạch trên worktree mới. Task xong, chờ người dùng áp patch + khởi động lại app (không cần db-migrate).
- 2026-11-09: Người dùng áp patch xong, phản hồi: tìm xong phải bấm chuột vào kết quả, chưa dùng được phím mũi tên lên/xuống. Thêm bước 3: phím ↓/↑ chọn menu trong ô tìm kiếm (file JS assets + CSS highlight, không đổi code Python).
- 2026-11-09: Hoàn thành bước 3: `app/ui/assets/menu_search_keys.js` (listener `keydown` ở tầng document, capture phase; ↓/↑ tô sáng kết quả, kẹp ở 2 đầu; Enter khi đã tô sáng thì bấm vào kết quả đó và chặn `n_submit`; Enter chưa tô sáng thì tới kết quả đầu như cũ) + rule CSS `a.menu-search-highlight` nền `var(--primary-soft)`. Kiểm chứng Playwright 1440×900/1366×768: ↓×1 → /runs/new, ↓×2 → /batch-runs, ↓×3 → /batches, ↓×4 vẫn /batches (kẹp), ↑ → /batch-runs, Enter → /batch-runs; Enter không bấm mũi tên → /runs/new; ↑ ở đầu danh sách → /runs/new. Test shell 18 pass (không đổi code Python). Ảnh: `~/workspace/dashboard-preview/menu-search-keys-1440.png`, `menu-search-keys-1366.png`.
