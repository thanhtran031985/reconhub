# Checklist kiểm thử – 26-reporting-export

| ✓ | ID | Ca kiểm thử | Loại | Ưu tiên |
|---|---|---|---|---|
| ☑ | T26-01 | Queue per-user concurrency | pytest | Cao |
| ☑ | T26-02 | Fetchmany không tăng RAM tuyến tính | pytest | Cao |
| ☑ | T26-03 | XLSX write-only | pytest | Cao |
| ☑ | T26-04 | Leading zero giữ text | pytest | Cao |
| ☑ | T26-05 | CSV encoding | pytest | Cao |
| ☑ | T26-06 | 1,000,000 rows/file split | pytest | Cao |
| ☑ | T26-07 | ZIP parts + summary | pytest | Cao |
| ☑ | T26-08 | Hash/size/status | pytest | Cao |
| ☑ | T26-09 | Retry export | pytest | Cao |
| ☑ | T26-10 | User B download A → NOT_FOUND | E2E | Cao |
| ☑ | T26-11 | Expired/missing file | pytest | Cao |
| ☐ | T26-12 | Oracle large dataset benchmark | Oracle | Cao |
