# Checklist kiểm thử – 22-reporting-source

| ✓ | ID | Ca kiểm thử | Loại | Ưu tiên |
|---|---|---|---|---|
| ☑ | T22-01 | CUSTOM_SQL SELECT và WITH SELECT hợp lệ | pytest | Cao |
| ☑ | T22-02 | Chặn INSERT/UPDATE/DELETE/MERGE/DDL/PLSQL/multi-statement | pytest | Cao |
| ☑ | T22-03 | Bind variable không nối chuỗi | pytest | Cao |
| ☑ | T22-04 | VIEW discover owner/view/columns | pytest | Cao |
| ☑ | T22-05 | TABLE discover owner/table/columns | pytest | Cao |
| ☑ | T22-06 | Identifier lạ hoặc không whitelist bị chặn | pytest | Cao |
| ☐ | T22-07 | Oracle DATE/TIMESTAMP/NUMBER/VARCHAR2/CLOB metadata | Oracle | Cao |
| ☑ | T22-08 | Source đổi phát hiện cột mới/mất/đổi type | pytest | Cao |
| ☑ | T22-09 | Timeout/read-only account | pytest | Cao |

Ghi chú: T22-07 nhánh mock đã đạt (test_report_source_discovery.TestMapOracleType + TestListReportColumns); nhánh Oracle thật chưa chạy được trên máy ảo (không VPN) — kiểm chứng phía người dùng khi có VPN.
