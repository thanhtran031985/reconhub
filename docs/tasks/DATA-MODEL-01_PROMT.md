# ============================================================
# DATA-MODEL-01
# DATA MODEL EXPLORER + AUTOMATIC ER DIAGRAM
# EXECUTION MODE: GENERATE TASK ONLY
# ============================================================


# 0. EXECUTION POLICY

Yêu cầu hiện tại CHỈ tạo tài liệu task.

KHÔNG IMPLEMENT.
KHÔNG sửa production code.
KHÔNG tạo page thật.
KHÔNG tạo route thật.
KHÔNG tạo schema inspector thật.
KHÔNG sửa database.
KHÔNG sửa model.
KHÔNG sửa migration.
KHÔNG sửa AGENTS.md trong bước generate task.
KHÔNG chạy schema-introspect.
KHÔNG bắt đầu coding sau khi generate task.

Hãy đọc specification bên dưới và chuyển thành task triển khai chính thức của ReconHub.

Sau khi generate task:

STOP.

Chỉ khi người dùng yêu cầu chính xác:

"Làm DATA-MODEL-01"

thì mới được triển khai.


# 1. ĐỌC TRƯỚC KHI GENERATE TASK

Đọc theo thứ tự:

1. AGENTS.md
2. cấu trúc thư mục tasks/ hiện tại
3. 2–3 task gần nhất để hiểu convention
4. .agents/rules/ui-dash.md
5. designs/tokens.json
6. designs/README.md
7. docs/DESIGN_SYSTEM.md nếu có
8. docs/ui-migration.md nếu có
9. database/model architecture hiện tại
10. migration architecture hiện tại
11. designs/reference/reconhub-er-diagram.html nếu tồn tại

Nếu repository sử dụng convention task khác:

tuân thủ convention hiện tại.

KHÔNG tạo một convention task mới.


# 2. FILE PHẢI GENERATE

Ưu tiên:

tasks/DATA-MODEL-01/
├── task.md
└── test-checklist.md

Nếu repository đang dùng cấu trúc khác thì đặt theo cấu trúc hiện tại.

Task ID:

DATA-MODEL-01

Task name:

Data Model Explorer + Automatic ER Diagram


# 3. MỤC TIÊU NGHIỆP VỤ

ReconHub hiện được phát triển theo workflow AI/vibe coding.

Khi nhiều AI liên tục bổ sung:

- page;
- feature;
- table;
- column;
- foreign key;
- index;
- database model;

người phát triển khó hình dung database hiện được thiết kế như thế nào.

DATA-MODEL-01 tạo một page:

Mô hình dữ liệu / Data Model Explorer

nhằm mục tiêu:

1. Xem toàn bộ database structure của ReconHub.
2. Xem ER Diagram trực quan.
3. Xem table → columns → datatype → PK/FK.
4. Xem relationships.
5. Tìm table hoặc column.
6. Lọc table theo module/domain.
7. Theo dõi database schema đã thay đổi thế nào qua từng task.
8. Phát hiện schema drift.
9. Đảm bảo task AI sau này thay đổi database phải tự cập nhật Data Model Explorer.
10. Giúp developer hiểu architecture mà không phải đọc toàn bộ source code/database manually.


# 4. READ-ONLY PRINCIPLE

Data Model Explorer là:

READ ONLY.

UI này TUYỆT ĐỐI KHÔNG được:

CREATE TABLE
ALTER TABLE
DROP TABLE
ADD COLUMN
DROP COLUMN
MODIFY COLUMN
CREATE INDEX
DROP INDEX

hoặc:

run database migration
apply migration
rollback migration
fix schema automatically.

Mọi thay đổi database vẫn phải đi qua workflow migration/model chính thức của ReconHub.

Data Model Explorer chỉ:

READ
INSPECT
COMPARE
VISUALIZE
AUDIT


# 5. SOURCE OF TRUTH

Không được hardcode ER Diagram.

Không được manually maintain danh sách table trong page.

Không được manually maintain relationship lines.

Luồng dữ liệu phải là:

Database metadata
      +
Application DB models
      +
Database migrations
      ↓
Schema Inspector
      ↓
Schema Manifest
      ↓
Schema Diff / Drift
      ↓
Data Model Explorer UI

Source of truth vẫn là database/model/migration architecture hiện tại.

schema-manifest.json chỉ là:

GENERATED ARTIFACT.

Không phải source of truth.


# 6. KIỂM TRA ARCHITECTURE THỰC TẾ

Trước khi IMPLEMENT DATA-MODEL-01 sau này, AI bắt buộc audit source code.

Không được giả định project sử dụng:

SQLAlchemy
Alembic
Oracle SQLAlchemy
Pydantic ORM

nếu source code thực tế không dùng.

Phải xác định:

- database engine;
- ORM/model technology;
- migration technology;
- schema owner;
- connection abstraction;
- repository layer;
- existing metadata utilities.

Sau đó mới chọn implementation strategy.


# 7. SCHEMA MANIFEST

Tạo một generated artifact dạng:

docs/data-model/schema-manifest.json

hoặc generated folder phù hợp convention hiện tại.

Không sửa tay file này.

Ví dụ cấu trúc:

{
  "generated_at": "...",
  "database": "...",
  "schema": "...",
  "version": "...",

  "tables": [
    {
      "name": "BATCH_DEFINITION",
      "domain": "reconciliation",
      "description": "Bộ đối soát",

      "columns": [
        {
          "name": "BATCH_DEF_ID",
          "type": "NUMBER",
          "nullable": false,
          "primary_key": true,
          "foreign_key": null,
          "unique": false,
          "default": null
        }
      ],

      "primary_key": [...],

      "foreign_keys": [
        {
          "column": "TEMPLATE_ID",
          "references_table": "RECON_TEMPLATE",
          "references_column": "TEMPLATE_ID",
          "constraint_name": "FK_BATCH_TEMPLATE"
        }
      ],

      "unique_constraints": [...],
      "indexes": [...],

      "source": {
        "model": "...",
        "migration": "..."
      }
    }
  ]
}


# 8. SCHEMA HISTORY

Tạo generated artifact tương đương:

docs/data-model/schema-history.json

Lưu CHANGE EVENTS.

Ví dụ:

TABLE_CREATED
TABLE_DROPPED

COLUMN_ADDED
COLUMN_REMOVED
COLUMN_CHANGED

PK_CHANGED
FK_CHANGED
INDEX_CHANGED
CONSTRAINT_CHANGED

Mỗi record nếu metadata cho phép gồm:

timestamp
task_id
migration_id
entity
change_type
before
after


# 9. SCHEMA INTROSPECTOR

Tạo một command chung.

Ưu tiên theo convention:

uv run poe schema-introspect

Command phải:

1. đọc database metadata;
2. đọc model metadata nếu cần;
3. đọc migration metadata nếu cần;
4. normalize schema;
5. generate schema-manifest;
6. generate schema diff/history;
7. validate PK/FK/index/constraint;
8. chạy drift comparison.

Command phải deterministic.

Chạy hai lần khi schema không thay đổi:

KHÔNG tạo fake diff.


# 10. SCHEMA DRIFT

Phải phát hiện khác nhau giữa:

Database

và:

Application metadata / migration / model.

Trạng thái:

SYNCED
DRIFT
UNKNOWN
ERROR

Các drift type:

TABLE_MISSING
TABLE_EXTRA

COLUMN_MISSING
COLUMN_EXTRA

TYPE_CHANGED
NULLABILITY_CHANGED

PK_CHANGED
FK_CHANGED

INDEX_CHANGED
CONSTRAINT_CHANGED


# 11. ROUTE

Tạo page:

Mô hình dữ liệu

Route đề xuất:

/data-model

Nếu repository có route convention khác:

tuân thủ convention hiện tại.


# 12. PERMISSION

Đây là metadata kỹ thuật nội bộ.

Page bắt buộc:

authentication
+
authorization.

Không mặc định expose cho tất cả user.

Sử dụng permission/menu system hiện tại.

Permission có thể dạng:

VIEW_DATA_MODEL

nhưng KHÔNG tự tạo permission này nếu project đang dùng permission convention khác.

Tuân thủ architecture hiện tại.


# 13. MENU

Menu group:

QUẢN TRỊ

Ví dụ:

Data Sources
Danh mục hệ thống
Mô hình dữ liệu

Mô hình dữ liệu dùng icon từ icon library hiện tại.

Không dùng emoji production.


# 14. VISUAL STYLE

Bắt buộc:

Fluent Compact + Master–Detail.

Tuân thủ:

AGENTS.md
.agents/rules/ui-dash.md
designs/tokens.json

Reference:

designs/reference/reconhub-er-diagram.html

Nếu prototype chưa có trong repo, người implement phải đặt prototype đã được duyệt vào designs/reference/ theo convention.

Visual reference xác định:

layout
interaction
hierarchy

Không copy hardcoded CSS/hex từ prototype.


# 15. DESKTOP LAYOUT

Desktop >= 1280:

PAGE KHÔNG CUỘN.

Layout:

AppShell
└── PageContent
    ├── PageHeader
    ├── CommandBar
    ├── Workspace
    │   ├── Schema Explorer
    │   ├── ER Canvas
    │   └── Detail Panel
    └── Status Bar

Workspace:

┌───────────────────┬───────────────────────────────┬───────────────────┐
│ Schema Explorer   │ ER Diagram                    │ Detail Panel      │
│                   │                               │                   │
│ internal scroll   │ pan / zoom / internal scroll  │ internal scroll   │
│                   │                               │                   │
└───────────────────┴───────────────────────────────┴───────────────────┘

Không hardcode width trong page.

Dùng layout/token foundation.


# 16. PAGE HEADER

Bên trái:

Title:

Mô hình dữ liệu

Description:

ER Diagram được sinh tự động từ metadata database, migrations và model của ứng dụng.

Bên phải:

[Lịch sử thay đổi]
[Đồng bộ schema]


# 17. BUTTON — LỊCH SỬ THAY ĐỔI

Label:

Lịch sử thay đổi

Ý nghĩa:

Cho developer xem schema đã thay đổi thế nào qua các task/migration.

Click:

Mở Drawer hoặc Modal compact.

KHÔNG chuyển route.

Nội dung:

Search
Change Type Filter
Timeline/List


## Filter

Tất cả

TABLE_CREATED
TABLE_DROPPED

COLUMN_ADDED
COLUMN_REMOVED
COLUMN_CHANGED

FK_CHANGED
INDEX_CHANGED
CONSTRAINT_CHANGED


## History item

Ví dụ:

09/11/2026 19:42

COLUMN_ADDED

REPORT_TEMPLATE.COLUMN_LAYOUT

Task:
UI-REPORT-12

Migration:
202611091942_add_column_layout

Before:
-

After:
CLOB NULL


## Không được

History không được hardcode production.

Dữ liệu phải đến từ generated schema history nếu architecture cho phép.


# 18. BUTTON — ĐỒNG BỘ SCHEMA

Label:

Đồng bộ schema

Icon:

Refresh / Sync icon chuẩn.

Ý nghĩa:

Refresh metadata và kiểm tra drift.

Click thực hiện:

1. trigger Schema Inspector;
2. đọc database metadata mới;
3. regenerate manifest;
4. compare drift;
5. regenerate schema history nếu có change;
6. reload Explorer;
7. reload Canvas;
8. reload Detail;
9. update health status.


# 19. SYNC BUTTON STATE MACHINE

## NORMAL

Button:

[Refresh] Đồng bộ schema

enabled = true


## RUNNING

Button:

[Spinner] Đang đồng bộ…

enabled = false

Schema Health:

Đang kiểm tra schema…


## SUCCESS — NO CHANGE

Button quay về:

Đồng bộ schema

Health:

✓ Schema đồng bộ


## SUCCESS — CHANGED

Button quay về normal.

Thông báo:

✓ Đã cập nhật mô hình

Ví dụ:

2 tables changed
4 columns changed


## DRIFT

Button quay về normal.

Health:

⚠ Schema drift

Hiển thị action:

Xem khác biệt


## ERROR

Button quay về normal.

ErrorState:

Không thể đọc metadata database.

Action:

Thử lại


# 20. BUTTON — THỬ LẠI

Chỉ xuất hiện trong ErrorState.

Click:

gọi lại schema inspection / metadata loading tương ứng.

Không reload toàn browser nếu không cần.


# 21. BUTTON — XEM KHÁC BIỆT

Chỉ xuất hiện khi:

Schema Health = DRIFT.

Click:

mở Drawer/Panel:

Schema Drift

Ví dụ:

Database ↔ Application

+ COLUMN_EXTRA
  REPORT_TEMPLATE.COLUMN_LAYOUT

! TYPE_CHANGED
  REPORT_PARAMETER.GRID_SPAN
  DB: NUMBER(2)
  Model: NUMBER(1)

- FK_MISSING
  BATCH_DEFINITION_ITEM.TEMPLATE_ID
  → RECON_TEMPLATE.TEMPLATE_ID


## Drift filters

Tất cả
Table
Column
Relationship
Index
Constraint


## Button

Copy report

Copy text report để developer gửi cho AI/task.


## Tuyệt đối không có

Fix schema
Apply
Run migration
Auto repair


# 22. COMMAND BAR

Control:

1. Search
2. Domain Filter
3. Display Mode
4. Schema Health
5. Last Sync


# 23. SEARCH

Placeholder:

Tìm table hoặc column…

Search trên:

table name
column name
table description

Nếu available:

constraint/index name.

Search phải filter đồng thời:

Schema Explorer
ER Canvas.


# 24. SEARCH — COLUMN BEHAVIOR

Ví dụ user search:

GRID_SPAN

ER Canvas phải:

- giữ table REPORT_PARAMETER visible;
- highlight column GRID_SPAN.

Detail Panel:

Search match

REPORT_PARAMETER.GRID_SPAN

NUMBER

Nullable:
...

Không chỉ hiển thị table mà bỏ highlight matching column.


# 25. DOMAIN FILTER

Dropdown:

Tất cả phân hệ

Domain ví dụ:

Core
Đối soát
Báo cáo
Quản trị
Khác / Unclassified

Domain mapping không hardcode trong page.

Source từ metadata/config.


# 26. DISPLAY MODE

Options:

Hiển thị quan hệ
Chỉ tên table


## Hiển thị quan hệ

Entity card:

TABLE_NAME
columns
PK/FK
datatype

relationships visible.


## Chỉ tên table

Entity card compact:

TABLE_NAME
column count

Relationship có thể vẫn hiển thị simplified nếu UX phù hợp.

Không mất selection.


# 27. SCHEMA HEALTH

Read-only badge.

States:

✓ Schema đồng bộ

⚠ Schema drift

? Không xác định

✕ Lỗi metadata

Không phải button.


# 28. LAST SYNC

Text:

Cập nhật:
DD/MM/YYYY HH:mm:ss

Timezone theo app:

Vietnam timezone / app configured timezone.

Không hardcode timezone nếu project đã có timezone utility.


# 29. SCHEMA EXPLORER

Panel bên trái.

Header:

Schema Explorer
N tables

Table được group theo domain.

Ví dụ:

CORE

APP_USER              5
ROLE                  4
USER_ROLE             3

ĐỐI SOÁT

RECON_TEMPLATE        5
BATCH_DEFINITION      5


# 30. DOMAIN GROUP EXPAND/COLLAPSE

Group header có:

chevron
domain name
table count

Click group:

collapse / expand.

State giữ trong page.

Nếu user search:

group có match tự expand.


# 31. TABLE ITEM

Mỗi table là compact row.

Hiển thị:

status marker
TABLE_NAME
column count

Khoảng cao compact.

Không dùng card lớn.


# 32. HOVER TABLE

Hover:

tooltip:

table description

Nếu có.

Không gọi backend khi hover.


# 33. CLICK TABLE

Khi click table:

1. selected table được cập nhật;
2. Explorer row active;
3. ER entity highlight;
4. relationship liên quan highlight;
5. Detail Panel load table;
6. canvas tự pan/scroll tới table nếu cần;
7. update URL query;
8. không reload page.


# 34. DOUBLE CLICK TABLE

Double click:

1. select table;
2. center selected table trên Canvas;
3. zoom đủ để đọc columns.

Không mở page khác.


# 35. TABLE CONTEXT MENU

Button:

More / ellipsis

hoặc right-click nếu app convention hỗ trợ.

Menu:

Center trong ER Diagram
Xem columns
Xem relationships
Xem lịch sử thay đổi
Copy table name


## Center trong ER Diagram

Pan canvas để table ở trung tâm.


## Xem columns

Select table.

Detail Panel focus section Columns.


## Xem relationships

Select table.

Detail Panel focus section Relationships.


## Xem lịch sử thay đổi

Mở history được filter theo selected table.


## Copy table name

Copy TABLE_NAME.


## Không được có

Drop table
Alter table
Delete column
Run SQL


# 36. URL DEEP LINK

Selection/filter quan trọng phải reflect trên URL nếu phù hợp với Dash routing architecture.

Ví dụ:

/data-model?table=BATCH_DEFINITION

hoặc:

/data-model?domain=reconciliation&table=BATCH_DEFINITION

Có thể thêm:

mode=compact

Mục tiêu:

- refresh page vẫn giữ context;
- developer copy URL gửi cho AI/người khác;
- browser Back/Forward hợp lý.

Không đưa zoom/pan pixel vào URL nếu không cần.


# 37. ER CANVAS

Center workspace.

Phải hỗ trợ:

pan
scroll
zoom
fit-to-screen

Canvas phải có bounded viewport.

Không sinh giant SVG làm tăng page height.


# 38. TABLE ENTITY

Header:

TABLE_NAME
column count

Body:

PK/FK marker
COLUMN_NAME
DATA_TYPE


# 39. COLUMN MARKERS

PK:

phải có icon/text marker.

FK:

phải có icon/text marker.

PK+FK:

phải thể hiện cả hai.

Unique:

marker nếu cần.

Nullable:

Detail Panel thể hiện rõ.

Không truyền đạt semantic chỉ bằng màu.


# 40. RELATIONSHIPS

Vẽ từ:

FK
→
Referenced PK / Unique Key

Relationship data lấy từ metadata.

Không hardcode endpoints.


# 41. RELATIONSHIP VISUAL STATE

NORMAL:

neutral line.

SELECTED TABLE:

related relationship line = accent.

unrelated relationship = lower emphasis.


# 42. CLICK RELATIONSHIP

Relationship line phải selectable nếu implementation technology cho phép.

Click relationship:

1. select relationship;
2. source table highlight;
3. target table highlight;
4. relationship line accent;
5. Detail Panel chuyển sang Relationship Detail.


# 43. RELATIONSHIP DETAIL

Hiển thị:

Source:

BATCH_DEFINITION_ITEM.BATCH_DEF_ID

Target:

BATCH_DEFINITION.BATCH_DEF_ID

Constraint:

FK_BATCH_ITEM_BATCH

Cardinality nếu derive được:

N : 1

Delete Rule:

CASCADE
RESTRICT
SET NULL

nếu metadata có.


Buttons:

Source table
Target table


## Source table button

Click:

select source table.


## Target table button

Click:

select target table.


# 44. ZOOM IN

Icon-only button.

Tooltip:

Phóng to

aria-label:

Phóng to ER Diagram

Click:

zoom + one step.

Có MAX_ZOOM.


# 45. ZOOM OUT

Tooltip:

Thu nhỏ

Click:

zoom - one step.

Có MIN_ZOOM.


# 46. FIT TO SCREEN

Tooltip:

Vừa màn hình

Click:

1. lấy bounding box của visible entities;
2. tính scale;
3. pan;
4. fit visible ER graph vào viewport.

Không clear:

search
domain
selection.


# 47. DETAIL PANEL — EMPTY

Nếu chưa chọn:

Empty State:

Chọn một table hoặc relationship để xem chi tiết.


# 48. DETAIL PANEL — TABLE

Header:

TABLE_NAME

Description.


## KPI

Columns: N

Relationships: N


## Metadata badges

Domain
Schema status.


# 49. COLUMN LIST

Mỗi column row:

COLUMN_NAME
DATA_TYPE

metadata:

PK
FK
UNIQUE
NULLABLE / NOT NULL
DEFAULT

Ví dụ:

BATCH_DEF_ID
NUMBER
PK · NOT NULL

BATCH_CODE
VARCHAR2(50)
UNIQUE · NOT NULL


# 50. RELATIONSHIPS SECTION

Hiển thị:

Incoming

Outgoing

Mỗi item:

SOURCE.TABLE_COLUMN
→
TARGET.TABLE_COLUMN

constraint name.


# 51. INDEX / CONSTRAINT SECTION

Hiển thị:

Primary Key
Unique constraints
Foreign keys
Indexes

Nếu dài:

collapsible section.

Không hide critical PK/FK information.


# 52. RECENT CHANGES

Detail Panel section:

Thay đổi gần nhất

filter:

selected table.

Ví dụ:

COLUMN_ADDED
REPORT_TEMPLATE.COLUMN_LAYOUT
09/11/2026 19:42

Nếu không có:

Chưa ghi nhận thay đổi schema cho table này.


# 53. STATUS BAR

Bottom compact status bar.

Hiển thị:

N tables
N columns
N relationships

Bên phải:

metadata sources thực tế.

Ví dụ:

Oracle metadata + migrations + application models

Chỉ ghi technology thực tế.


# 54. LOADING STATE

Initial load:

Schema Explorer → Skeleton rows

Canvas → loader/skeleton

Detail → SkeletonPanel

Không block trắng toàn screen.


# 55. EMPTY SCHEMA

Nếu không có table:

Không tìm thấy table trong schema hiện tại.

Button:

Đồng bộ lại

Click:

same sync metadata action.


# 56. EMPTY SEARCH

Nếu search/filter không có match:

Không tìm thấy table hoặc column phù hợp.

Action:

Xóa bộ lọc

Click:

clear search
+
domain → All

Không gọi error state.


# 57. ERROR STATE

Nếu metadata load fail:

Không thể đọc metadata database.

Button:

Thử lại

Sanitize error.

Không expose:

password
token
DB secret
full credential connection string.


# 58. PERFORMANCE

Schema <= 50 tables:

render full interface.

Schema > 50:

consider:
- domain filter;
- lazy column rendering;
- compact entity mode.

Schema > 100:

phải đánh giá virtualization/lazy graph strategy.

Không để browser freeze.


# 59. AUTO LAYOUT

ER entity positions không hardcode per table.

Phải dùng:

graph layout algorithm

hoặc deterministic grouping/layout logic.

Yêu cầu:

- position deterministic;
- hạn chế overlap;
- related entities tương đối gần nhau;
- preserve domain grouping nếu phù hợp.

Không manually write:

TABLE_A = x,y
TABLE_B = x,y


# 60. MOBILE

390×844:

Page scroll được phép.

Order:

CommandBar
Schema Explorer
ER Canvas
Detail Panel

Không horizontal PAGE overflow.

ER Canvas được:

internal horizontal scroll
pan.


# 61. ACCESSIBILITY

- icon button có tooltip;
- icon button có aria-label;
- table item keyboard selectable;
- aria-selected;
- relationship keyboard selectable nếu feasible;
- PK/FK không chỉ phân biệt bằng màu;
- focus visible;
- status aria-live="polite";
- controls có label/aria-label.


# 62. SECURITY

Data Model Explorer chỉ expose metadata.

Không expose:

table row data
sample sensitive data
password
secret
token
raw credential
database password
connection string password.

SQL DDL nếu hiển thị:

phải kiểm tra không chứa secrets.

Page phải permission protected.


# 63. SCHEMA CHANGE AUTO-UPDATE RULE

Khi IMPLEMENT DATA-MODEL-01, phải bổ sung vào AGENTS.md hoặc database rule phù hợp:

Khi task tạo/xóa/thay đổi:

TABLE
COLUMN
DATATYPE
NULLABILITY
PK
FK
UNIQUE
INDEX
CONSTRAINT

AI bắt buộc:

1. cập nhật migration/model đúng workflow;
2. chạy schema-introspect;
3. regenerate schema-manifest;
4. generate schema diff/history;
5. chạy schema drift;
6. chạy Data Model Explorer tests;
7. verify table/column mới xuất hiện;
8. bảo đảm generated artifacts được commit nếu project policy yêu cầu.


# 64. DATABASE TASK DEFINITION OF DONE

Task template phải bổ sung:

## Data Model Impact

[ ] Task không thay đổi database schema.

HOẶC:

[ ] Migration cập nhật.
[ ] DB model cập nhật.
[ ] schema-introspect chạy.
[ ] schema-manifest regenerate.
[ ] schema history cập nhật.
[ ] Schema drift = 0 hoặc documented.
[ ] Data Model Explorer hiển thị thay đổi.
[ ] Regression tests pass.


# 65. CI SCHEMA FRESHNESS

Không chỉ dựa vào AI nhớ chạy generator.

CI phải phát hiện stale manifest.

Strategy:

1. generate schema manifest vào temp;
2. normalize deterministic;
3. diff với committed manifest;
4. nếu khác → FAIL.

Error message:

Schema manifest is stale.

Run:

uv run poe schema-introspect


# 66. KHÔNG AUTO COMMIT

schema-introspect:

không git add
không git commit
không git push.

AI/task workflow xử lý Git riêng.


# 67. GIT HISTORY

Production Data Model page không chạy:

git log
git diff

mỗi lần user mở page.

Nếu Task ID / migration ID cần history:

generate trước thành artifact.

Runtime UI chỉ đọc generated history.


# 68. GENERATED FILE SAFETY

Manifest/history phải có header/metadata:

GENERATED.

Không sửa tay.

Nếu schema tooling tạo file mới:

document rõ generator command.


# 69. TEST — GENERATOR

Test:

table extraction
column extraction
datatype
nullable
default
PK
FK
unique
index
constraint

deterministic output

schema diff

drift.


# 70. TEST — UI

Test:

permission

loading
empty
error
data

search table
search column

domain filter

display mode

group expand/collapse

click table

double click table

context menu

copy table

deep link URL

relationship highlight

relationship click

relationship detail

source table navigation

target table navigation

zoom in

zoom out

fit

history

history filter

sync success

sync changed

sync drift

sync error

retry

view diff

copy drift report.


# 71. TEST — SECURITY

Verify:

unauthorized access denied.

No credentials present in:

page DOM
schema manifest
history
error messages
logs exposed to page.


# 72. REGRESSION

Existing database functionality không được thay đổi.

Existing:

reconciliation
reporting
permissions
data-source logic

phải tiếp tục hoạt động.


# 73. VISUAL TEST

Chụp:

1366×768
1440×900
390×844


Desktop:

document.documentElement.scrollHeight <= innerHeight

document.documentElement.scrollWidth <= innerWidth

Canvas internal scroll allowed.


# 74. ACCEPTANCE CRITERIA

[ ] DATA-MODEL page tồn tại.
[ ] Route đúng.
[ ] Menu đúng.
[ ] Permission đúng.
[ ] Fluent Compact đúng.
[ ] Không hardcode table list.
[ ] Không hardcode relationships.
[ ] Schema Inspector tồn tại.
[ ] schema-manifest generate tự động.
[ ] schema-history generate tự động.
[ ] schema drift check tồn tại.
[ ] Search table hoạt động.
[ ] Search column hoạt động.
[ ] Matching column highlight.
[ ] Domain filter hoạt động.
[ ] Display mode hoạt động.
[ ] Schema Explorer group collapse/expand.
[ ] Click table hoạt động.
[ ] Double click table center canvas.
[ ] Table context actions hoạt động.
[ ] URL deep-link hoạt động.
[ ] ER auto-layout không hardcode coordinates.
[ ] PK/FK hiển thị.
[ ] Relationships đúng.
[ ] Click relationship hoạt động.
[ ] Relationship Detail hoạt động.
[ ] Zoom In hoạt động.
[ ] Zoom Out hoạt động.
[ ] Fit hoạt động.
[ ] Detail Panel đầy đủ.
[ ] History hoạt động.
[ ] History filter hoạt động.
[ ] Sync state machine đầy đủ.
[ ] Drift View hoạt động.
[ ] Copy drift report hoạt động.
[ ] Loading state.
[ ] Empty state.
[ ] Error + Retry.
[ ] Không credential exposure.
[ ] Desktop không page scroll.
[ ] Mobile không horizontal page overflow.
[ ] Light/Dark đúng.
[ ] Unit tests pass.
[ ] E2E tests pass.
[ ] Schema freshness CI tồn tại.
[ ] AGENTS/database rule được cập nhật khi IMPLEMENT.
[ ] Database task Definition of Done đã bổ sung khi IMPLEMENT.


# 75. BUG SAFETY

Repository do nhiều AI cùng code.

Trước IMPLEMENT:

git status --short
git branch --show-current
git log -1 --oneline

Chạy baseline tests.

Phân loại bug:

PRE-EXISTING UNRELATED
PRE-EXISTING BLOCKER
INTRODUCED BY TASK
DISCOVERED RELATED BUG
UNKNOWN

Không sửa PRE-EXISTING UNRELATED.

Bug related chỉ sửa nếu:

- thuộc scope;
- không đổi business contract;
- có regression test.

Security/data-loss/permission bypass:

STOP và báo user.


# 76. FILE EXPECTED TO CHANGE KHI IMPLEMENT

Danh sách cụ thể phải được task generator xác định dựa trên source thực tế.

Dự kiến nhóm:

app/ui/pages/
app/ui/components/
app/ui/layout/ nếu cần menu integration
schema inspection module
generated data-model artifacts
tests/
Poe task/config
AGENTS.md hoặc database rule
CI schema freshness test

Task generator phải thay bằng đường dẫn chính xác sau khi audit repository.


# 77. FILE MUST NOT CHANGE

Không sửa nếu không cần:

business services
reconciliation algorithms
report SQL
permission semantics
authentication behavior
existing database schema

DATA-MODEL-01 không được tự tạo schema change nghiệp vụ chỉ để demo.


# 78. TASK.MD PHẢI CHỨA

task.md bắt buộc có:

Status

Dependencies

Objective

Problem Statement

Read First

Architecture

Source of Truth

Schema Inspector

Schema Manifest

Schema History

Schema Drift

Route

Permission

Menu

Layout

Component Specification

Button & Interaction Specification

URL State

Loading/Empty/Error/Data

Security

Performance

Responsive

Accessibility

Auto-update Rule

CI Freshness

Allowed Scope

Forbidden Scope

Bug Safety

Implementation Steps

Tests

Visual Tests

Acceptance Criteria

Expected Files

Files Must Not Change

Completion Report Format

STOP Condition


# 79. TEST-CHECKLIST.MD

Tạo checklist riêng:

## Preflight

## Schema Inspector

## Manifest

## History

## Drift

## Permissions

## Page Layout

## Explorer

## Search

## Domain

## ER Canvas

## Table Selection

## Relationship Selection

## Detail Panel

## Zoom & Fit

## Sync State Machine

## Drift Viewer

## Loading

## Empty

## Error

## Security

## Responsive

## Accessibility

## CI Freshness

## Regression

## Lint

## Typecheck

## Unit

## E2E

## Screenshot


# 80. COMPLETION REPORT FORMAT TRONG TASK

Khi DATA-MODEL-01 được IMPLEMENT sau này, AI phải report:

## DATA-MODEL-01 completed

### Architecture

Schema source:
...

Inspector:
...

Manifest:
...

History:
...

Drift strategy:
...


### UI

Route:
...

Permission:
...

Tables discovered:
N

Columns discovered:
N

Relationships discovered:
N


### Automated Update

Command:

...

CI validation:

...


### Files Changed

...


### Tests

Lint:
...

Typecheck:
...

Unit:
...

E2E:
...

Schema drift:
...

Console:
...


### Visual Validation

1366×768:
...

1440×900:
...

390×844:
...


### Screenshots

...


### Existing Bugs Discovered

| Bug | Existing/New | Severity | Action |
|---|---|---|---|


### Safety

Data Model Explorer:
READ ONLY

Database schema changed by this page:
NO


# 81. STOP CONDITION CHO IMPLEMENTATION

Sau khi DATA-MODEL-01 hoàn thành:

STOP.

Không tự bắt đầu task khác.

Không tự sửa drift phát hiện được.

Không tự tạo migration.

Không tự sửa database.


# 82. YÊU CẦU CUỐI CỦA LẦN GENERATE TASK NÀY

Bây giờ CHỈ generate:

tasks/DATA-MODEL-01/task.md

và:

tasks/DATA-MODEL-01/test-checklist.md

Review lại hai file sau khi tạo.

Xác minh:

- mọi button có behavior;
- mọi control có behavior;
- Sync có state machine;
- drift có viewer;
- relationship click có detail;
- search column có highlight;
- context menu table có actions;
- deep link có specification;
- UI read-only;
- manifest generated;
- history generated;
- CI stale-manifest check có specification;
- task DB tương lai có auto-update rule.

Sau đó trả về:

## DATA-MODEL-01 task generated

Files:

- tasks/DATA-MODEL-01/task.md
- tasks/DATA-MODEL-01/test-checklist.md

Implementation started:
NO

Production code changed:
NONE

Database changed:
NO

Recommended next action:

Review task.md.

Nếu được duyệt, người dùng sẽ yêu cầu:

"Làm DATA-MODEL-01"

STOP.

KHÔNG IMPLEMENT DATA-MODEL-01 TRONG LẦN NÀY.