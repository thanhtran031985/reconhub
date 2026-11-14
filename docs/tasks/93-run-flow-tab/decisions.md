# Decisions — Task 93

- **D1 — Vị trí tab:** thêm `TabsTab("Luồng xử lý", value="flow")` vào
  `run-res-main-tabs` sau tab SQL, kèm `TabsPanel(value="flow")`. Render
  tĩnh ở `layout()` như SQL tab (mirror `render_sql_tab_content`), không
  callback riêng cho tab (tránh mount-firing — bài học task 90/91).
- **D2 — Sơ đồ vẽ bằng component Dash:** 4 hộp chặng (dmc.Paper) xếp
  ngang bằng flex, nối bằng mũi tên text "→" (html.Div), không dùng
  Archify HTML, Mermaid hay iframe (tab phải render theo dữ liệu từng
  run, không phải file tĩnh).
- **D3 — Mọi số liệu động theo run đang mở:** tên file, bảng + nguồn DB,
  group_by, measures, compare/tolerance, CNT_*, EXCEL_ROWS_READ, DB_ROWS
  đều lấy từ `run_data` + `summary` + config template của run. Không
  hardcode BILL_VTOS / FACT_BILL / TOTAL_AMOUNT.
- **D4 — Ô ví dụ tĩnh:** lấy nhóm đầu tiên của `initial_rows` (đã xếp
  theo độ nặng + |diff| — chính là nhóm lệch nhất), hiện khóa, trạng
  thái, Excel/DB/diff của measure chính. Không gọi `get_row_detail`
  thêm ở layout (tránh tải chậm); không nối click mở drawer trong task
  này (xem drawer ở tab Kết quả như cũ). `initial_rows` rỗng thì ẩn ô
  ví dụ.
- **D5 — Run FAILED / chưa có summary:** tab vẫn hiện; số thiếu hiện
  "—"; run FAILED hiện alert lỗi như SQL tab (D3/task 67).
- **D6 — Tên hàm xử lý là text tĩnh:** engine giống nhau mọi template
  nên tên hàm mỗi bước (`reader.read_sheets`, `compare.compare`…)
  ghi tĩnh như mockup đã duyệt; chỉ số liệu và tên (bảng/file/group_by/
  measure) là động.
- **D7 — Helper mới, không sửa helper chung:** thêm `_flow_context`
  mới; không đổi kiểu trả về của `_profile_main_measure` hay
  `_resolve_grid_measures` (nơi khác đang dùng).
- **D8 — Không thêm trạng thái mới:** không callback, không Store, không
  đổi id hiện có. Tab flow không tự chạy gì khi mở.
- **D9 — Số task 93:** số 92 giữ lại cho đề xuất fix wizard bước 3
  (đã đề xuất 14/11/2026, user từ chối, chưa làm) để khỏi nhầm.
- **D10 — Không ảnh hưởng code cũ đã test (user chốt 14/11/2026):**
  chỉ thêm code mới (1 tab + 2 hàm mới trong `run_result.py` + file test
  mới); không sửa callback, tab cũ, id, service hay helper dùng chung.
  Mọi khối vẽ tab mới đều bọc try/except: lỗi thì chỉ tab đó hiện
  alert, trang run vẫn mở bình thường. Chứng minh bằng full suite xanh
  + live check 2 tab cũ vẫn hoạt động.
- **D11 — Chỉ dùng design token:** tab dựng bằng component DMC
  (Paper/Text/Group/SimpleGrid/Badge/Code) + token, không viết hex/px
  trong page (AGENTS.md). Style inline trong file mockup xem trước
  (`.archify/.../tab-preview.html`) chỉ là bản vẽ, không copy vào code.
- **D12 — `render_flow_tab_content` nhận thêm `flow_ctx=None` (lệch
  nhỏ so với plan bước 3):** plan ghi hàm nhận 3 tham số
  `(run_info, summary, initial_rows)`, nhưng hàm render thuần không có
  `ctx` nên không tự gọi `get_template` được. `layout()` tính
  `_flow_context(ctx, run_data)` đúng 1 lần rồi truyền vào làm tham số
  thứ 4 tùy chọn; hàm render không tự gọi service (giữ render thuần,
  test được không cần DB). `flow_ctx=None` → mọi giá trị config hiện
  "—". Không đổi chữ ký các hàm cũ.
