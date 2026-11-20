# Checklist kiểm thử — 100-multi-profile-run

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task, theo dõi trạng thái kiểm thử trước và sau khi hoàn thành code.

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | `create_multi_run` với danh sách nhiều profile hợp lệ | Sinh ra đủ N bản ghi `RECON_RUN` độc lập, cùng `FILE_ID`, `EXCEL_LOAD_ID`, khác `PROFILE_CODE`, vào hàng đợi | ✅ |
| **TC-FN-02** | `create_multi_run` khi có profile không hợp lệ | Báo lỗi `VALIDATION_ERROR` và không tạo bản ghi nào | ✅ |
| **TC-FN-03** | Submit từ UI `/runs/new` với 1 profile | Redirect về `/runs/<run_id>` | ✅ |
| **TC-FN-04** | Submit từ UI `/runs/new` với nhiều profile | Tạo thành công N run, redirect về `/history` | ✅ |
| **TC-FN-05** | Lọc danh sách run trên `/history` theo `profile_code` | Trả về đúng các run có profile_code tương ứng | ✅ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Component chọn Profile trên `/runs/new` là MultiSelect | Cho phép chọn nhiều profile, có placeholder rõ ràng | ✅ |
| **TC-UI-02** | Khối SQL preview hiển thị Tabs khi chọn nhiều profile | Mỗi Tab hiển thị tên profile và câu SQL tương ứng | ✅ |
| **TC-UI-03** | Bộ lọc Profile trên `/history` cập nhật theo Template | Khi chọn template A, dropdown profile hiển thị các profile của template A | ✅ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff (All checks passed) | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy (162 source files no issues) | ✅ |
| **TC-REG-03** | `uv run poe test` | Toàn bộ 38 unit test liên quan đều pass | ✅ |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | `uv run poe security-check` | Toàn bộ 6/6 kiểm tra bảo mật tự động đạt | ✅ |
| **TC-SEC-02** | Phân quyền truy cập (RBAC) | Quyền tạo run kiểm tra đúng menu "run" | ✅ |
| **TC-SEC-03** | Ghi Audit log | Ghi đầy đủ `RECON_AUDIT_LOG` cho từng run được tạo | ✅ |
