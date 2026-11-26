# Quyết định — 106-semantic-model-core

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-26 | Chia `REPORT-STUDIO-01` thành 4 task nối tiếp (`106`–`109`) thay vì gộp 1 task khổng lồ | Tuân thủ quy ước `docs/tasks/NN-slug/` và quy trình `lam-task` từng bước, dễ review và test độc lập từng tầng | Tạo 4 thư mục task `106`–`109` trong `docs/tasks/` |
| 2026-11-26 | Không tạo `app/repo/`, đặt service dùng SQLAlchemy Core + `app/db/metadata.py` | Codebase hiện tại không tồn tại `app/repo/`, toàn bộ Reporting Core dùng trực tiếp SQLAlchemy Core | Đồng bộ kiến trúc với `app/services/report*.py` |
| 2026-11-26 | Dùng `STATUS IN ('DRAFT', 'VALIDATED', 'ACTIVE', 'ARCHIVED')` cho `RECON_RPT_MODEL_VER` | Khớp trạng thái `ACTIVE` sẵn có của `RECON_RPT_TPL_VER` trong Reporting Core | UI vẫn hiển thị nhãn tiếng Việt "Đang phát hành (Active)" |
| 2026-11-26 | V1 chỉ tạo khung metadata RLS (`RECON_RPT_MODEL_RLS`) | `RECON_USER` và `Ctx` hiện chưa có trường đơn vị (`allowed_orgs`); V1 tập trung khung metadata + rule `ADMIN`/`username` | Giảm phạm vi rủi ro ở V1, sẵn sàng gắn `RECON_USER_SCOPE` ở V2 |
| 2026-11-26 | Validation quan hệ tách 2 tầng: Cấu trúc/Đồ thị (tức thì) + Profiling mẫu có timeout | Tránh quét full bảng Fact Oracle chục triệu dòng làm treo request khi lưu hoặc kiểm tra quan hệ | Thêm hàm `profile_relationship_data` tách riêng với `validate_relationship_structure` |
| 2026-11-26 | Calculated Measure V1 dùng JSON AST whitelist thay vì text parser tự do | Đảm bảo không thể tiêm SQL/subquery qua công thức, tái sử dụng triết lý builder an toàn như `sql_builder.py` | Đơn giản hóa form Measure Editor ở Task 107 |
| 2026-11-26 | Validation đồ thị quan hệ (cycle & ambiguous active paths) dùng DFS/BFS Python thuần | Đồ thị Semantic Model kích thước vừa (~5–30 bảng), thuật toán Python thuần gọn nhẹ và không phát sinh package ngoài | Không cần cài `networkx` trong `pyproject.toml` |

## Câu hỏi còn mở
- Không có (đã chốt toàn bộ khi hoàn tất Bước 5).
