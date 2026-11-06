# Quyết định – 24-reporting-columns

Tham chiếu spec 12 và data flow. Ghi mọi khác biệt đã duyệt tại đây.

- 06/11/2026 (duyệt plan "làm theo đề xuất và làm xong task"): Q0 — nhánh `feat/24-reporting-columns` từ `57b20fb` (đầu nhánh task 23 đã push). Q1 — làm xong cả task rồi gửi xem (như task 19/20/21/22/23). Q2 — FORMAT_MASK theo type: NUMBER {#,##0, #,##0.00, #,##0%, 0, 0.00}; DATE {DD/MM/YYYY, YYYY-MM-DD, MM/YYYY}; DATETIME {các mask DATE + DD/MM/YYYY HH:mm, DD/MM/YYYY HH:mm:ss}; STRING/BINARY phải để trống. Q3 — LABEL duy nhất trong version, không phân biệt hoa/thường. Q4 — WIDTH NULL = tự động, nếu có thì 40..400. Q5 — IS_TOTAL chỉ khi DATA_TYPE='NUMBER'. Q6 — default khi auto-discover: ALIGNMENT NUMBER→RIGHT, DATE/DATETIME→CENTER, STRING/BINARY→LEFT; WIDTH NUMBER→120, DATE→110, DATETIME→160, STRING/BINARY→180. Q7 — restore DB order = đặt lại DISPLAY_ORDER theo ID (thứ tự discover từ nguồn). Q8 — `get_result_layout(target web/excel)` là MỘT hàm dùng chung cho Viewer và Export.
