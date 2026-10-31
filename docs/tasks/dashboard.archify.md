# ReconHub — Tiến độ & Bản đồ 17 Task Đối soát Excel - Oracle {#reconhub-dashboard}

Dự án ReconHub gồm 17 task chia làm 4 giai đoạn, hiện đã hoàn thành **Task 00** (nền tảng repo, SQLite, Alembic, poe, CI) và sẵn sàng chuyển sang **Task 01**.

- Giai đoạn 0 (Nền tảng): Đã xong task 00, chuẩn bị thực hiện xác thực và phân quyền người dùng (task 01).
- Giai đoạn 1 (Engine & Template): Xây dựng bộ đọc Excel, sinh SQL truy vấn Oracle, thuật toán so khớp và hàng đợi worker.
- Giai đoạn 2 (Giao diện MVP): Hoàn thiện giao diện Dash Mantine cho Wizard template, màn Chạy đối soát, Kết quả và Lịch sử.
- Giai đoạn 3 (Mở rộng): Chuyển RECON_APP sang Oracle, xử lý chênh lệch, dashboard so sánh và đóng gói triển khai production.

@answer scope="ReconHub · Tiến độ 17 Task · Giai đoạn 0 đến 3"
@meta locale=en

## Chỉ số tiến độ tổng quan {#metrics}

@metric id=metric-done label="Task hoàn thành" value=1 unit="task" limit=17 note="1 / 17 task đạt chuẩn nghiệm thu"
@metric id=metric-progress label="Tiến độ tổng thể" value=6 unit="%" limit=100 note="GĐ0 đang thực hiện"

@facts id=facts-stage
| Giai đoạn hiện tại | GĐ0 — Nền tảng |
| Task kế tiếp | 01-auth-users (Người dùng, Auth) |
| CSDL lưu trữ | SQLite WAL (chuyển Oracle ở GĐ3) |
| Công nghệ UI | Dash 3 + DMC 2.x (Mantine v8) |

## Sơ đồ 4 Giai đoạn & 17 Task {#workflow-map}

@workflow id=phase-flow title="Quy trình 4 Giai đoạn phát triển"
| gd0 | GĐ0 Nền tảng | backend |
| gd1 | GĐ1 Engine | database |
| gd2 | GĐ2 Giao diện | frontend |
| gd3 | GĐ3 Mở rộng | cloud |
| gd0 > gd1 | chuẩn bị | emphasis |
| gd1 > gd2 | hoàn tất | emphasis |
| gd2 > gd3 | vận hành | emphasis |

@tree id=task-tree title="Cơ cấu 17 Task theo Giai đoạn"
| root | ReconHub (17 Task) | - |
| gd0 | GĐ0: Nền tảng (3 task) | root |
| gd1 | GĐ1: Engine & Template (5 task) | root |
| gd2 | GĐ2: Giao diện MVP (5 task) | root |
| gd3 | GĐ3: Mở rộng (4 task) | root |
| t00 | 00-repo-setup (Hoàn thành) | gd0 |
| t01 | 01-auth-users | gd0 |
| t02 | 02-data-sources | gd0 |
| t03 | 03-template-config | gd1 |
| t04 | 04-excel-reader | gd1 |
| t05 | 05-db-fetch | gd1 |
| t06 | 06-compare-engine | gd1 |
| t07 | 07-run-queue-worker | gd1 |
| t08 | 08-app-shell-ui | gd2 |
| t09 | 09-template-wizard-ui | gd2 |
| t10 | 10-new-run-ui | gd2 |
| t11 | 11-run-result-ui | gd2 |
| t12 | 12-export-history | gd2 |
| t13 | 13-metadata-migration | gd3 |
| t14 | 14-issue-handling | gd3 |
| t15 | 15-dashboard-compare | gd3 |
| t16 | 16-production-readiness | gd3 |

## Danh sách chi tiết 17 Task {#task-table}

| Mã | Tên Task | Giai đoạn | Phụ thuộc | Nhánh git | Trạng thái |
| --- | --- | --- | --- | --- | --- |
| 00 | 00-repo-setup — Khung repo Python trên Windows, SQLite + Alembic, poe, CI | GĐ0 | — | feat/00-repo-setup | {good:Hoàn thành} |
| 01 | 01-auth-users — Người dùng trên RECON_APP, đăng nhập, phân quyền 4 vai trò | GĐ0 | 00 | feat/01-auth-users | {caution:Kế tiếp} |
| 02 | 02-data-sources — Data Source: nguồn Oracle và đích lưu RECON_APP | GĐ0 | 01 | feat/02-data-sources | Chưa làm |
| 03 | 03-template-config — TemplateConfig, version và service template | GĐ1 | 02 | feat/03-template-config | Chưa làm |
| 04 | 04-excel-reader — Đọc Excel, chuẩn hóa, control total, nạp dữ liệu tạm | GĐ1 | 00 | feat/04-excel-reader | Chưa làm |
| 05 | 05-db-fetch — SQL sinh từ bảng/cột, SQL guard, fetch Oracle qua VPN | GĐ1 | 02, 03 | feat/05-db-fetch | Chưa làm |
| 06 | 06-compare-engine — Gộp, ghép, so sánh, trạng thái, summary, export | GĐ1 | 04, 05 | feat/06-compare-engine | Chưa làm |
| 07 | 07-run-queue-worker — Run, hàng đợi, worker, dry-run, xóa dữ liệu tạm | GĐ1 | 03, 06 | feat/07-run-queue-worker | Chưa làm |
| 08 | 08-app-shell-ui — Component Dash Mantine, AppShell, Templates, Data Sources, Users | GĐ2 | 01, 02, 03, 07 | feat/08-app-shell-ui | Chưa làm |
| 09 | 09-template-wizard-ui — Wizard đăng ký template 5 bước và Sơ đồ diễn giải | GĐ2 | 07, 08 | feat/09-template-wizard-ui | Chưa làm |
| 10 | 10-new-run-ui — Màn Chạy đối soát | GĐ2 | 07, 08 | feat/10-new-run-ui | Chưa làm |
| 11 | 11-run-result-ui — Màn Kết quả run, grid động, Đã kiểm tra xong | GĐ2 | 07, 08 | feat/11-run-result-ui | Chưa làm |
| 12 | 12-export-history — Lịch sử run, Dashboard tối thiểu, hoàn thiện MVP | GĐ2 | 10, 11 | feat/12-export-history | Chưa làm |
| 13 | 13-metadata-migration — Chuyển RECON_APP từ SQLite sang Oracle | GĐ3 | 02, 12 | feat/13-metadata-migration | Chưa làm |
| 14 | 14-issue-handling — Xử lý chênh lệch | GĐ3 | 12 | feat/14-issue-handling | Chưa làm |
| 15 | 15-dashboard-compare — Dashboard đầy đủ và so sánh hai run | GĐ3 | 12 | feat/15-dashboard-compare | Chưa làm |
| 16 | 16-production-readiness — Triển khai trên Windows và Linux | GĐ3 | 00–15 | feat/16-production-readiness | Chưa làm |

## Tiến độ Task 00 đã hoàn thành {#task-00-done}

@steps id=task-00-steps
| step1 | Bước 1: pyproject + poe + config | Cấu hình uv, poethepoet và Pydantic Settings đọc .env với pathlib. | task-tree | t00 |
| step2 | Bước 2: Schema + Alembic | Định nghĩa toàn bộ schema Spec 02, DecimalText, JsonText, WAL mode. | task-tree | t00 |
| step3 | Bước 3: Oracle test qua VPN | Fixture kiểm tra kết nối Thin mode và tự động skip khi thiếu VPN. | task-tree | t00 |
| step4 | Bước 4: Dash khung + theme | Dash 3 use_pages, Mantine v8 theme sinh từ token, route /health. | task-tree | t00 |
| step5 | Bước 5: Worker + dev server | Tiến trình worker nền bắt signal dừng sạch, script chạy song song dev_server. | task-tree | t00 |
| step6 | Bước 6: CI & hoàn thiện | Thiết lập GitHub Actions CI, lint và typecheck nghiêm ngặt 100% xanh. | task-tree | t00 |
