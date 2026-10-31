from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import polars as pl


def build_golden_db() -> None:
    sql_path = Path("scripts/oracle/02_seed_src_test.sql")
    lines = sql_path.read_text(encoding="utf-8").splitlines()

    rows = []
    pattern = re.compile(
        r"VALUES\s*\('([^']+)',\s*TO_DATE\('([^']+)','YYYY-MM-DD HH24:MI:SS'\),\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*(\d+),\s*(\d+),\s*'([^']+)',\s*'([^']+)'\)"
    )
    for line in lines:
        line = line.strip()
        if not line.startswith("INSERT INTO SRC_FACT_INVOICE_DTP"):
            continue
        m = pattern.search(line)
        if m:
            inv, dt, point, txn, pin, srv, qty, amt, status, org = m.groups()
            rows.append({
                "INVOICE_NO": inv,
                "INVOICE_DATE": datetime.strptime(dt, "%Y-%m-%d %H:%M:%S"),
                "COLLECT_POINT": point,
                "TXN_ID": txn,
                "PIN_NO": pin,
                "SERVICE_CODE": srv,
                "QUANTITY": Decimal(qty),
                "AMOUNT": Decimal(amt),
                "INVOICE_STATUS": status,
                "ORG_CODE": org,
            })

    df = pl.DataFrame(rows)
    print(f"Total rows parsed: {len(df)}")
    out_dir = Path("tests/golden/G01_dtp_by_invoice")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_dir / "db.parquet")
    print(f"Saved db.parquet to {out_dir / 'db.parquet'}")


if __name__ == "__main__":
    build_golden_db()
