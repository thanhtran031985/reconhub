# Task 69 — Run SMP lỗi Polars: `date` lạc trong cột Datetime

## Yêu cầu (user 12/11/2026, sau khi áp patch 67)

Run #1033 (mục "Doanh thu smartport BDP", template BILL_SMART_PORT_BDP)
thất bại với lỗi (nay đã hiện ra nhờ card lỗi task 67):

> Lỗi nội bộ hệ thống trong quá trình thực thi: could not append value:
> 2026-07-08 of type: date to the builder; make sure that all rows have
> the same schema or consider increasing `infer_schema_length`...

Trong khi mục "Doanh thu Vtos" (BILL_VTOS_BDP) chạy được. Hai câu SQL:

- SMP: lọc theo `INVOICE_DATE`, `SELECT INVOICE_NO, INVOICE_DATE,
  TOTAL_AMOUNT ... WHERE INVOICE_DATE >= :p_from AND INVOICE_DATE <=
  :p_to AND APPLICATION='SMP' AND org_code=:p_org`, GROUP BY
  INVOICE_NO, INVOICE_DATE.
- VTOS: lọc theo `DATE_VALUE`, `SELECT INVOICE_NO, INVOICE_DATE,
  TOTAL_AMOUNT, DATE_VALUE, ORG_CODE ... WHERE DATE_VALUE >= :p_from AND
  DATE_VALUE <= :p_to AND APPLICATION='VTOS' AND ORG_CODE=:p_org`,
  GROUP BY INVOICE_DATE, INVOICE_NO.

## Phạm vi

- Sửa lỗi crash khi một cột Datetime chứa giá trị `date` thuần (không giờ)
  lúc dựng lại bảng từ các dòng.
- Không đổi logic đối soát, không đổi SQL của template, không migration.
