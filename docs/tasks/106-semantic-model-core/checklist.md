# Checklist kiểm thử — 106-semantic-model-core

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task `106-semantic-model-core` (Semantic Model Core, Catalog Constraints & Impact Analysis).

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Preflight & Migration `0018_semantic_model` trên SQLite | Upgrade/downgrade thành công, đủ 7 bảng `RECON_RPT_MODEL*`, `schema-introspect` drift = 0 | ✅ |
| **TC-FN-02** | `catalog.list_table_constraints` & ước lượng `NUM_ROWS` (SQLite + mock Oracle) | Lấy đúng PK, FK, Unique key; View không có constraint vẫn trả danh sách cột và rỗng constraint không lỗi | ✅ |
| **TC-FN-03** | Tạo Model mới (`create_model`) | `CODE` duy nhất, immutable sau khi lưu; tạo version 1 `DRAFT`; chưa tự publish; ghi `RECON_AUDIT_LOG` | ✅ |
| **TC-FN-04** | Clone Model (`clone_model`) & Archive Model (`archive_model`) | Clone tạo Model/Draft mới không kéo dependency report; Archive chặn dùng cho report mới nhưng giữ nguyên report cũ | ✅ |
| **TC-FN-05** | Thêm/Xóa bảng (`add_table_to_draft`, `remove_table_from_draft`) & nhãn cột | Nạp đủ cột từ catalog, tự gợi ý nhãn tiếng Việt từ `DB_COLUMN_MAPPING`, từ chối thêm trùng bảng | ✅ |
| **TC-FN-06** | Phân loại bảng (`FACT`/`DIMENSION`/`BRIDGE`) & bắt buộc `Grain` cho `FACT` | `validate_model` báo ERROR nếu `FACT` thiếu `GRAIN_DESC` hoặc `GRAIN_KEYS`; chặn `publish_model_version` | ✅ |
| **TC-FN-07** | Quy tắc `Field Properties` & `Default Aggregation` | Khóa `SUM` trên kiểu `STRING`/`DATE`/`DATETIME`/`BOOLEAN`; hỗ trợ `HIDDEN`, `FILTERABLE`, `FOLDER`, `Virtual Date Hierarchy` | ✅ |
| **TC-FN-08** | `Measure Studio` (Simple & Structured AST Calculated Measure) | Chấp nhận phép tính whitelist (`DIVIDE`, `ROUND`, `CASE`...); từ chối trùng code, thiếu field hoặc cú pháp SQL tự do | ✅ |
| **TC-FN-09** | Relationship CRUD & Validation Tầng 1 (Structural/Graph) | Kiểm tra datatype tương thích, `*:1` / `1:1`, chặn relationship loop và ambiguous active paths | ✅ |
| **TC-FN-10** | Relationship Profiling Tầng 2 (`profile_relationship_data`) | Phát hiện duplicate dimension key, null rate, orphan fact keys, join coverage với timeout ngắn và limit mẫu | ✅ |
| **TC-FN-11** | Optimistic Concurrency (`ROW_VERSION`) khi `save_draft` | Hai luồng cùng sửa một bản Draft → luồng sau nhận lỗi `STALE_DATA`, không ghi đè dữ liệu | ✅ |
| **TC-FN-12** | Publish Model (`publish_model_version`) & Immutability | Chuyển version cũ sang `ARCHIVED`, bản mới thành `ACTIVE` (bắt buộc `change_note`), chặn sửa trực tiếp bản `ACTIVE` | ✅ |
| **TC-FN-13** | Model Diff & Breaking Change Detection + Impact Analysis | Phát hiện xóa/ẩn field, đổi kiểu dữ liệu, đổi relationship/measure/grain/RLS; trả Impact Analysis không lỗi khi chưa có `RECON_RPT_VISUAL` | ✅ |
| **TC-FN-14** | Khung metadata RLS V1 (`upsert_rls_policy`) | Lưu policy hợp lệ; báo lỗi nếu cột RLS không thuộc bảng hoặc bảng không nằm trong model | ✅ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Menu `report_model` trong `app/ui/menus.py` & đồng bộ `RECON_MENU` | Menu xuất hiện đúng nhóm `CAU_HINH`, gán seed cho `ADMIN` và `TEMPLATE_OWNER` | ✅ |
| **TC-UI-02** | Page `/data-model` sau khi chạy `schema-introspect` | 7 bảng `RECON_RPT_MODEL*` hiển thị đầy đủ ở phân hệ `report` trên ER Diagram | ✅ (kiểm chứng qua `schema-introspect` & `test_page_data_model.py`) |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy strict | ✅ |
| **TC-REG-03** | `uv run poe schema-introspect --check` | Manifest và history khớp 100% metadata | ✅ |
| **TC-REG-04** | `uv run poe test-engine` | Toàn bộ unit/integration test không cần Oracle xanh | ⚠️ (Còn pre-existing fail trên `main`: `test_dark_mode73`, `test_perm_registry` và count=20 cũ ở `test_menu_sync`/`test_menu_admin_service`/`test_page_roles`) |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | `uv run poe security-check` | Toàn bộ 6/6 kiểm tra bảo mật tự động đạt | ✅ |
| **TC-SEC-02** | Phân quyền truy cập (`@requires_menu("report_model")`) | Chưa đăng nhập → `UNAUTHENTICATED`; user không được cấp menu (vd `VIEWER`) → `FORBIDDEN` | ✅ |
| **TC-SEC-03** | An toàn metadata & SQL | Không lưu credential Data Source trong bảng model; không nhận raw SQL cho Calculated Measure; profiling dùng bind param | ✅ |
