# TASK UI-00A — UI Inventory & Fluent Migration Assessment

## 1. Mục tiêu

Kiểm kê toàn bộ giao diện hiện tại của ReconHub trước khi migrate sang:

Fluent Compact + Master–Detail

Task này CHỈ:
- đọc code;
- chạy ứng dụng;
- mở các màn hình;
- chụp baseline;
- phân tích layout;
- phân loại màn hình;
- tìm vấn đề UI;
- lập kế hoạch migration.

KHÔNG redesign.
KHÔNG sửa UI.
KHÔNG refactor.
KHÔNG sửa callback.
KHÔNG sửa service.
KHÔNG sửa tokens.
KHÔNG sửa CSS.
KHÔNG sửa component hiện tại.

Đầu ra chính:

docs/ui-migration.md

Đây sẽ là source để chia các task UI-00B, UI-01...UI-n tiếp theo.


# 2. Bắt buộc đọc trước

Đọc theo thứ tự:

1. AGENTS.md
2. .agents/rules/ui-dash.md
3. designs/tokens.json
4. designs/README.md
5. docs/DESIGN_SYSTEM.md nếu tồn tại
6. docs/specs/05_services_pages.md nếu tồn tại

Sau đó đọc code:

- app/ui/**
- tests/e2e/**

Nếu tồn tại:

designs/reference/preview-fluent.html

thì mở và dùng CHỈ làm visual reference cho phong cách đích.

Không sửa bất kỳ file nào ở designs/.


# 3. Source of truth

Khi có mâu thuẫn, ưu tiên:

1. AGENTS.md
2. .agents/rules/ui-dash.md
3. designs/tokens.json
4. docs/DESIGN_SYSTEM.md
5. task này
6. visual reference
7. skill

Không tự suy diễn style khác.


# 4. Không dùng skill để redesign

Task này là inventory/audit.

KHÔNG dùng taste-skill để redesign.

KHÔNG dùng emilkowalski/skills để thêm animation hoặc interaction.

KHÔNG dùng gstack để tự động sửa UI.

Nếu sử dụng design-review thì chỉ được dùng ở chế độ:

AUDIT ONLY

Tức là:

- phát hiện inconsistency;
- ghi issue;
- KHÔNG sửa code.


# 5. Bước 1 — Inventory routes/pages

Tìm tất cả page đã được register trong Dash.

Kiểm tra:

dash.register_page(...)

và cấu trúc:

app/ui/pages/**

Lập danh sách:

| ID | Page | Route | Source file | Access/Permission | Layout hiện tại |
|----|------|-------|-------------|-------------------|-----------------|

Không được bỏ sót page.

Bao gồm cả những màn:

- chưa hoàn thiện;
- chỉ admin dùng;
- route ẩn;
- page không có menu;
- page lỗi hoặc chưa có dữ liệu.


# 6. Bước 2 — Inventory shared UI

Kiểm kê:

app/ui/layout/**
app/ui/components/**
app/ui/theme.py
assets/**

Tìm các component dùng chung hiện tại như:

- AppShell
- Navbar
- Header
- PageHeader
- Breadcrumb
- DataGrid
- CommandBar
- FilterBar
- Modal
- Drawer
- Card
- EmptyState
- Loading
- ErrorState
- Form
- Stepper
- MasterDetail

Nếu component chưa tồn tại thì ghi:

MISSING

KHÔNG tạo mới trong task này.


# 7. Bước 3 — Chạy ứng dụng

Chạy ReconHub theo hướng dẫn hiện tại của repository.

Không thay đổi cấu hình để làm cho test pass.

Nếu cần authentication:

- dùng test account/test fixture đã có trong repository;
- không bypass authorization;
- không hardcode quyền.


# 8. Bước 4 — Chụp baseline UI hiện tại

Dùng Playwright hoặc browser của Antigravity.

Với MỖI page, chụp tối thiểu:

1366 × 768

Nếu page có layout responsive quan trọng, chụp thêm:

1440 × 900
390 × 844

Baseline phải phản ánh UI hiện tại TRƯỚC migration.

Tên ảnh nên theo format:

<route-or-page>-before-1366x768.png

Ví dụ:

reports-before-1366x768.png
templates-before-1366x768.png
admin-menu-before-1366x768.png

Không chỉnh CSS chỉ để ảnh đẹp.


# 9. Bước 5 — Kiểm tra page scrolling

Tại viewport:

1366 × 768

đo:

document.documentElement.scrollHeight
document.documentElement.clientHeight
document.documentElement.scrollWidth
document.documentElement.clientWidth

Page được coi là có vertical page scroll khi:

scrollHeight > clientHeight

Page được coi là có horizontal page scroll khi:

scrollWidth > clientWidth

Ghi kết quả cụ thể.

Phân biệt rõ:

PAGE SCROLL

và:

INTERNAL SCROLL

Internal scroll trong:

- AgGrid;
- ScrollArea;
- danh sách;
- panel chi tiết;

là hợp lệ.

Mục tiêu migration sau này là:

desktop >= 1280px:
không có PAGE SCROLL trong luồng sử dụng bình thường.

Không đánh lỗi chỉ vì grid phải scroll bên trong.


# 10. Bước 6 — Audit mật độ UI

Kiểm tra từng page để phát hiện:

## Typography

- Title quá lớn.
- dmc.Title order=1/2/3 không cần thiết.
- body text lớn hơn quy chuẩn.
- typography khác nhau giữa các page.

## Spacing

Tìm:

p="lg"
p="xl"
gap="lg"
gap="xl"

hoặc spacing tương đương làm UI quá thoáng.

Tìm section/card có padding quá lớn.

## Controls

Tìm:

size="md"
size="lg"
size="xl"

trong:

Button
TextInput
Select
NumberInput
DatePicker
MultiSelect
Textarea

nếu không có lý do đặc biệt.

## Card

Tìm nơi đang dùng:

Grid + Card

để hiển thị danh sách nhiều record.

Ví dụ:

report list
template list
menu list
user list
data source list

Đánh dấu:

CANDIDATE: COMPACT LIST / AGRID

nhưng KHÔNG sửa.


# 11. Bước 7 — Audit hardcode

Tìm trong:

app/ui/**

các trường hợp:

- màu hex;
- rgb / rgba;
- px hardcode;
- style={...};
- class CSS riêng ghi trực tiếp màu / height / padding;
- rowHeight đặt riêng từng AgGrid;
- headerHeight đặt riêng;
- border-radius riêng;
- width sidebar riêng;
- height header riêng.

Phân loại:

TOKEN CANDIDATE
LAYOUT CANDIDATE
PAGE-SPECIFIC VALID
REVIEW REQUIRED

Không kết luận mọi px đều sai.

Ví dụ:

width cột nghiệp vụ cụ thể của AgGrid

có thể là:

PAGE-SPECIFIC VALID.


# 12. Bước 8 — Audit AgGrid

Tìm tất cả dag.AgGrid.

Với mỗi grid ghi:

- page;
- rowModelType;
- rowHeight;
- headerHeight;
- pagination/infinite;
- fixed height hay flex;
- horizontal scroll;
- vertical scroll;
- metadata-driven columnDefs hay hardcode;
- empty/loading/error state.

Đánh dấu grid có:

rowHeight/headerHeight riêng

để UI-00B xem xét đưa về GRID_DEFAULTS.


# 13. Bước 9 — Audit Modal / Drawer

Tìm:

dmc.Modal
dmc.Drawer

Phân loại:

CONFIRMATION
SHORT ACTION
LONG FORM
CRUD FORM
DETAIL VIEW

Modal hợp lệ:

- xác nhận xóa;
- cảnh báo;
- thao tác ngắn.

Đánh dấu:

MASTER-DETAIL CANDIDATE

nếu Modal đang chứa:

- form dài;
- cấu hình template;
- cấu hình parameter;
- LOV setup;
- cấu hình menu;
- role/permission;
- Data Source;
- mapping column;
- detail record phức tạp.

KHÔNG chuyển đổi trong task này.


# 14. Bước 10 — Audit trạng thái dữ liệu

Với từng màn có dữ liệu hoặc grid, kiểm tra 4 trạng thái:

1. Loading
2. Empty
3. Error
4. Data

Kiểm tra có sử dụng:

dmc.Skeleton
EmptyState
dmc.Alert
Retry

theo ui-dash.md hay không.

Ghi:

PASS
PARTIAL
MISSING


# 15. Bước 11 — Audit responsive

Kiểm tra tối thiểu:

1366 × 768
390 × 844

Không yêu cầu desktop và mobile giống nhau.

Desktop:

- ưu tiên mật độ cao;
- không page scroll;
- master/detail song song.

Mobile:

- được page scroll;
- không horizontal page overflow;
- master/detail được stack;
- navbar chuyển burger/drawer.

Ghi lỗi cụ thể nếu có.


# 16. Bước 12 — Phân loại layout đích

Mỗi page CHỈ được đề xuất một trong các pattern chuẩn sau.

## LIST

PageHeader
CommandBar
DataGrid / CompactList

Dùng cho:

- danh sách template;
- danh sách bộ đối soát;
- lịch sử;
- danh sách menu;
- danh sách user...


## REPORT

PageHeader
FilterBar
ResultGrid

Dùng cho:

- xem báo cáo;
- chạy truy vấn;
- xem kết quả đối soát.


## MASTER_DETAIL

PageHeader

Master                 Detail
--------------------   ----------------
Grid/List              Properties/Form
flex: 1                fixed panel
internal scroll        internal scroll

Dùng cho:

- parameter + LOV;
- menu configuration;
- permission;
- data source;
- mapping;
- cấu hình template.


## WIZARD

PageHeader
Stepper
Body
Footer

Dùng cho quy trình thật sự có thứ tự bước.

Không dùng Wizard nếu các section có thể chỉnh độc lập.

Nếu phát hiện wizard thực tế phù hợp hơn với:

MASTER_DETAIL + TABS

ghi:

WIZARD → MASTER_DETAIL/TABS CANDIDATE

nhưng KHÔNG thay đổi trong task này.


## FORM

Chỉ dùng cho màn form đơn giản ít trường.

Không tự tạo layout pattern thứ 6.


# 17. Bước 13 — Đánh giá độ khó migration

Mỗi page đánh:

S
M
L
XL

Quy tắc:

S
- chủ yếu CSS/layout;
- ít callback;
- list đơn giản.

M
- filter + grid;
- một số responsive/layout dependency.

L
- nhiều callback;
- Modal/form;
- master-detail;
- dynamic columns.

XL
- wizard;
- dynamic UI;
- callback phụ thuộc component tree;
- permission phức tạp;
- drag/drop;
- nhiều state.


# 18. Bước 14 — Đánh giá rủi ro callback

Kiểm tra callback Input/Output/State.

Nếu migration layout có khả năng ảnh hưởng component tree, ghi:

CALLBACK RISK: LOW / MEDIUM / HIGH

Không đổi component ID.

Không đề xuất rename component ID nếu không bắt buộc.

Ưu tiên migration bằng cách:

giữ component hiện tại
→ thay wrapper/layout bên ngoài.


# 19. Tạo docs/ui-migration.md

Cấu trúc bắt buộc:


# ReconHub UI Migration Inventory

## 1. Executive Summary

Ghi:

- tổng số page;
- số page có page scroll ở 1366×768;
- số page có horizontal overflow;
- số page có hardcoded style cần review;
- số Master–Detail candidate;
- số Wizard/complex page;
- số page thiếu 4 state.


## 2. Current Shared Foundation

Bảng:

| Component | Existing | Location | Reusable | Issue | Recommendation |


## 3. Page Inventory

| ID | Page | Route | Source | Current Layout | Target Pattern | Complexity | Callback Risk |


## 4. Visual / Layout Audit

| Page | Page Scroll | H.Scroll | Density | Oversized Controls | Cards | Modal/Form Issue | Main Issue |


## 5. Hardcoded Styling

| File | Line/Component | Type | Current | Classification | Recommendation |


Không cần dump tất cả CSS.

Chỉ ghi những item có ảnh hưởng migration.


## 6. AgGrid Inventory

| Page | Grid ID | rowModel | rowHeight | headerHeight | Height Model | State Coverage | Action |


## 7. Data State Coverage

| Page | Loading | Empty | Error | Data | Result |


## 8. Responsive Audit

| Page | 1366×768 | 390×844 | Issue |


## 9. Screenshot Baseline

Liệt kê screenshot:

| Page | Desktop baseline | Mobile baseline |


## 10. Proposed Migration Tasks

Đề xuất:

UI-00B
UI-01
UI-02
...
UI-n
UI-99

Mỗi task ghi:

### UI-XX — <Tên>

Pages:
- ...

Target pattern:
LIST / REPORT / MASTER_DETAIL / WIZARD / FORM

Complexity:
S/M/L/XL

Dependencies:
...

Allowed scope:
...

Do not change:
...

Acceptance focus:
...


# 20. Quy tắc chia task

Không nhất thiết mỗi page là một task.

Có thể gom khi:

- cùng layout;
- dùng cùng component;
- complexity S;
- callback độc lập.

Ví dụ:

UI-01 — Compact Lists
- Templates
- Reconciliation Sets
- History

Không gom:

- wizard với list;
- admin permission với report viewer;
- các page complexity L/XL.

Một task migration nên đủ nhỏ để AI:

- code;
- test;
- screenshot;
- review;

trong một lượt làm việc.


# 21. Đề xuất UI-00B

Trong docs/ui-migration.md phải có riêng phần:

## UI-00B — Fluent Foundation Proposal

CHỈ đề xuất, chưa implement.

Xác định component dùng chung cần có, ví dụ:

AppShell
PageHeader
CommandBar
MasterDetail
WizardShell
Grid defaults

Với từng component ghi:

EXISTING / EXTEND / CREATE

và page nào sẽ dùng.


# 22. Không được làm

Trong UI-00A tuyệt đối KHÔNG:

- sửa app/ui/**;
- sửa callback;
- sửa route;
- sửa service;
- sửa SQL;
- sửa models;
- sửa permissions;
- sửa designs/tokens.json;
- chạy formatter làm đổi source;
- update dependency;
- tạo component mới;
- migrate page;
- sửa CSS;
- sửa assets;
- sửa screenshot để trông đẹp hơn.


# 23. File được phép tạo

Chỉ được tạo:

docs/ui-migration.md

và screenshot baseline theo convention hiện có của repository.

Nếu repository chưa có thư mục screenshot chuẩn:

KHÔNG tự tạo cấu trúc lớn.

Đặt screenshot tạm ở:

artifacts/ui-inventory/

nếu AGENTS.md cho phép.

Nếu AGENTS.md quy định vị trí khác thì tuân thủ AGENTS.md.


# 24. Acceptance Criteria

Task chỉ hoàn thành khi:

[ ] Đã đọc AGENTS.md và ui-dash.md.
[ ] Đã inventory tất cả dash.register_page.
[ ] Không bỏ sót admin/hidden page.
[ ] Shared components đã được inventory.
[ ] Tất cả page đã được phân loại layout đích.
[ ] Tất cả page đã được đánh Complexity.
[ ] Tất cả page đã được đánh Callback Risk.
[ ] Page scroll được đo ở 1366×768.
[ ] Horizontal page overflow được đo.
[ ] AgGrid inventory hoàn tất.
[ ] Modal/Drawer audit hoàn tất.
[ ] 4-state audit hoàn tất.
[ ] Responsive audit hoàn tất.
[ ] Baseline screenshot hoàn tất.
[ ] docs/ui-migration.md đã tạo.
[ ] Đã đề xuất UI-00B và UI-01...UI-n.
[ ] Không có source code production nào bị thay đổi.


# 25. Báo cáo cuối task

Khi hoàn thành, KHÔNG bắt đầu UI-00B.

Trả về đúng cấu trúc:

## UI-00A completed

Pages inventoried: X
Pages with desktop page-scroll: X
Pages with horizontal overflow: X
Master–Detail candidates: X
Complex pages (L/XL): X

Generated:
- docs/ui-migration.md
- <screenshot location>

Recommended next task:
UI-00B — Fluent Foundation

Important findings:
1. ...
2. ...
3. ...
4. ...
5. ...

STOP.

Chờ người dùng review docs/ui-migration.md trước khi thực hiện bất kỳ migration nào.