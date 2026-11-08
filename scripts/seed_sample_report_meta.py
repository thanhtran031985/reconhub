"""Seed sample report parameters and columns for testing and screenshot comparison."""

from __future__ import annotations

from sqlalchemy import text

from app.db.engine import get_recon_engine


def seed():
    engine = get_recon_engine()
    with engine.begin() as conn:
        # Update version 1
        conn.execute(
            text("""
                UPDATE RECON_RPT_TPL_VER
                SET SQL_TEXT = 'SELECT invoice_no, invoice_date, customer_name, total_amount FROM fin_invoice'
                WHERE ID = 1
            """)
        )

        # Clear existing params and columns for version 1
        conn.execute(text("DELETE FROM RECON_RPT_PARAM_LOV WHERE PARAM_ID IN (SELECT ID FROM RECON_RPT_PARAM WHERE VERSION_ID = 1)"))
        conn.execute(text("DELETE FROM RECON_RPT_PARAM WHERE VERSION_ID = 1"))
        conn.execute(text("DELETE FROM RECON_RPT_COLUMN WHERE VERSION_ID = 1"))

        # Insert 4 params matching preview.html
        conn.execute(
            text("""
                INSERT INTO RECON_RPT_PARAM (ID, VERSION_ID, CODE, LABEL, DATA_TYPE, CONTROL_TYPE, REQUIRED, DEFAULT_TYPE, DEFAULT_VALUE, DISPLAY_ROW, DISPLAY_ORDER, GRID_SPAN, IS_VISIBLE)
                VALUES
                (101, 1, 'p_from_date', 'Từ ngày', 'DATE', 'DATE', 1, 'NONE', '2026-10-01', 1, 1, 3, 1),
                (102, 1, 'p_to_date', 'Đến ngày', 'DATE', 'DATE', 1, 'NONE', '2026-10-31', 1, 2, 3, 1),
                (103, 1, 'p_org', 'Đơn vị', 'STRING', 'SELECT', 0, 'NONE', 'ALL', 1, 3, 3, 1),
                (104, 1, 'p_status', 'Trạng thái', 'STRING', 'SELECT', 0, 'STATIC', 'ALL', 1, 4, 3, 1)
            """)
        )

        # Insert LOVs
        conn.execute(
            text("""
                INSERT INTO RECON_RPT_PARAM_LOV (PARAM_ID, LOV_TYPE, SQL_TEXT, STATIC_JSON, CACHE_SECONDS, MAX_ROWS)
                VALUES
                (103, 'SQL', 'SELECT org_code AS value, org_name AS label FROM organization', NULL, 300, 1000),
                (104, 'STATIC', NULL, '[{"value": "ALL", "label": "Tất cả"}, {"value": "OPEN", "label": "Đang mở"}, {"value": "CLOSED", "label": "Đã đóng"}]', 0, 100)
            """)
        )

        # Insert columns matching preview.html
        conn.execute(
            text("""
                INSERT INTO RECON_RPT_COLUMN (ID, VERSION_ID, FIELD_NAME, LABEL, DATA_TYPE, DISPLAY_ORDER, WEB_VISIBLE, EXCEL_VISIBLE, FORMAT_MASK, ALIGNMENT, WIDTH, IS_TOTAL)
                VALUES
                (201, 1, 'INVOICE_NO', 'Số hóa đơn', 'STRING', 1, 'Y', 'Y', NULL, 'LEFT', 130, 'N'),
                (202, 1, 'INVOICE_DATE', 'Ngày hóa đơn', 'DATE', 2, 'Y', 'Y', 'DD/MM/YYYY', 'LEFT', 130, 'N'),
                (203, 1, 'CUSTOMER_NAME', 'Tên khách hàng', 'STRING', 3, 'Y', 'Y', NULL, 'LEFT', 190, 'N'),
                (204, 1, 'TOTAL_AMOUNT', 'Tổng tiền', 'NUMBER', 4, 'Y', 'Y', '#,##0', 'RIGHT', 130, 'Y')
            """)
        )

    print("Seed metadata hoàn tất!")

if __name__ == "__main__":
    seed()
