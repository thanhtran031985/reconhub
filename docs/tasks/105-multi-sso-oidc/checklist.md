# Checklist kiểm thử — 105-multi-sso-oidc

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task, theo dõi trạng thái kiểm thử trước và sau khi hoàn thành code.

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Migration `0017_multi_sso_oidc` tạo bảng `RECON_SSO_PROVIDER` và `RECON_USER_IDENTITY` | Upgrade/downgrade thành công trên SQLite, `schema-introspect` drift = 0 | ✅ |
| **TC-FN-02** | CRUD SSO Provider (`ADMIN` tạo/sửa/bật/tắt/xóa, non-admin bị `FORBIDDEN`) | Secret mã hóa Fernet trong DB, không trả về UI, ghi `RECON_AUDIT_LOG` | ✅ |
| **TC-FN-03** | Auto-Discovery đọc `.well-known/openid-configuration` | Trích xuất đúng `issuer`, `authorization_endpoint`, `token_endpoint`, `jwks_uri`, `userinfo_endpoint` | ✅ |
| **TC-FN-04** | OIDC Authorize URL + PKCE (`S256`) + `state` + `nonce` | URL đầy đủ tham số chuẩn OIDC, lưu session đúng `state`, `nonce`, `code_verifier` | ✅ |
| **TC-FN-05** | OIDC Token Exchange & Verify `id_token` (JWKS RS256) | Chấp nhận token hợp lệ; từ chối sai chữ ký, sai `nonce`, sai `aud`, sai `iss`, hết hạn | ✅ |
| **TC-FN-06** | Email làm `USERNAME` + Auto-link user sẵn có + `ALLOWED_DOMAINS` | Khớp user sẵn có theo email đã verified và tạo `RECON_USER_IDENTITY`; tạo mới JIT với role `VIEWER`; chặn domain ngoài whitelist | ✅ |
| **TC-FN-07** | Dynamic routes `/auth/sso/<provider_code>/login` & `/callback` | Đăng nhập thành công tạo session Flask và ghi `RECON_LOGIN_LOG`; alias `/auth/sso/login` tương thích ngược | ✅ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Trang `/sso-flow` có 2 tab (*Nhà cung cấp SSO* & *Kiến trúc & Luồng SSO*) | Chuyển tab mượt, sơ đồ Archify vẫn hiển thị bình thường ở tab 2 | ✅ |
| **TC-UI-02** | Đăng ký SSO với Preset (`Google`, `Microsoft Entra ID`, `OIDC`, `Internal`) | Điền sẵn URL mẫu, hiển thị Redirect URI để copy, không lộ `CLIENT_SECRET` sau khi lưu | ✅ |
| **TC-UI-03** | Trang `/login` hiển thị động các nút SSO đang bật | Chỉ hiện nút của các provider `IS_ACTIVE='Y'` khi `SSO_ENABLED=True` | ✅ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy | ✅ |
| **TC-REG-03** | `uv run poe test-engine` | Toàn bộ unit/integration test xanh | ✅ |
| **TC-REG-04** | `uv run poe schema-introspect --check` | Manifest đồng bộ với schema mới | ✅ |
| **TC-REG-05** | `uv run poe e2e` | Toàn bộ E2E Playwright xanh | ✅ |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | `uv run poe security-check` | Toàn bộ 6/6 kiểm tra bảo mật tự động đạt | ✅ |
| **TC-SEC-02** | Phân quyền truy cập (RBAC) | Service quản lý provider kiểm tra `ADMIN` qua `require_admin` | ✅ |
| **TC-SEC-03** | Bảo vệ bí mật `CLIENT_SECRET` | Mã hóa Fernet trong DB, không leak qua UI/Store/log/audit | ✅ |
