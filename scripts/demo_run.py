"""Script chạy demo đối soát DTP end-to-end theo Spec 04 và G01.

Lệnh chạy: uv run poe demo-run (dùng mock fetcher)
           uv run poe demo-run --oracle (dùng kết nối Oracle thật qua VPN)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.context import Ctx, Role
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_data_source,
    recon_template,
)
from app.schemas.run import CreateRunParams
from app.schemas.template_config import TemplateConfig
from app.services.file_service import upload_file
from app.services.run_executor import execute_run
from app.services.run_service import create_run, export_run, get_run
from app.services.template import activate_version, save_draft_template
from worker.runner import ReconWorker


def main() -> None:
    if sys.platform == "win32":
        try:
            reconfig_out = getattr(sys.stdout, "reconfigure", None)
            if callable(reconfig_out):
                reconfig_out(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Chạy Demo đối soát DTP end-to-end")
    parser.add_argument("--oracle", action="store_true", help="Kết nối tới nguồn Oracle thật qua VPN")
    parser.add_argument("--purge", action="store_true", help="Xóa dữ liệu tạm sau khi đối soát xong")
    args = parser.parse_args()

    print("=" * 65)
    print("      RECONHUB - DEMO ĐỐI SOÁT HÓA ĐƠN TÁC NGHIỆP DTP      ")
    print("=" * 65)

    ctx = Ctx(user_id=1, username="demo_user", full_name="Chuyên viên Demo", roles=[Role.ADMIN, Role.OPERATOR])
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Đảm bảo Data Source tồn tại
    with engine.begin() as conn:
        ds_row = (
            conn.execute(select(recon_data_source).where(recon_data_source.c.NAME == "ORACLE_DEMO")).mappings().first()
        )
        if not ds_row:
            ins = conn.execute(
                recon_data_source.insert().values(
                    NAME="ORACLE_DEMO",
                    ENV="DEV",
                    PURPOSE="SOURCE",
                    DB_TYPE="ORACLE",
                    HOST=os.getenv("ORACLE_TEST_HOST", "localhost"),
                    PORT=int(os.getenv("ORACLE_TEST_PORT", "1521")),
                    SERVICE_NAME=os.getenv("ORACLE_TEST_SERVICE_NAME", "orcl"),
                    USERNAME=os.getenv("ORACLE_TEST_USERNAME", "RECON_SRC_RO"),
                    PASSWORD_ENC="",
                    DEFAULT_SCHEMA="RECON_SRC",
                    IS_ACTIVE="Y",
                    CREATED_BY="demo",
                    CREATED_AT=now,
                    UPDATED_AT=now,
                )
            )
            ds_id = int(ins.inserted_primary_key[0])
        else:
            ds_id = int(ds_row["ID"])

    # 2. Đảm bảo Template DTP tồn tại và ACTIVE
    tmpl_path = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")
    with open(tmpl_path, "r", encoding="utf-8") as f:
        tmpl_dict = json.load(f)
    cfg = TemplateConfig.model_validate(tmpl_dict)

    with engine.connect() as conn:
        tmpl_rec = (
            conn.execute(select(recon_template).where(recon_template.c.CODE == "DTP_HOA_DON_TAC_NGHIEP"))
            .mappings()
            .first()
        )

    if not tmpl_rec:
        save_res = save_draft_template(
            ctx,
            code="DTP_HOA_DON_TAC_NGHIEP",
            name="Đối soát hóa đơn tác nghiệp DTP",
            config=cfg,
            data_source_id=ds_id,
        )
        tmpl_id = int(save_res.data["id"])
        # Kích hoạt với override dry_run cho demo
        activate_version(ctx, template_id=tmpl_id, version=1, dry_run_override=True)
    else:
        tmpl_id = int(tmpl_rec["ID"])

    # 3. Tải file mẫu DTP 200 dòng
    sample_file = Path("samples/dtp_sample_200.xlsx")
    up_res = upload_file(ctx, filename=sample_file.name, content=sample_file.read_bytes())
    file_id = int(up_res.data["id"])
    print(f"[OK] Đã nạp file mẫu: {sample_file.name} (File ID: {file_id})")

    # 4. Tạo run
    p_from = datetime(2026, 2, 1, 0, 0, 0)
    p_to = datetime(2026, 2, 5, 23, 59, 59)
    run_res = create_run(
        ctx,
        CreateRunParams(
            template_id=tmpl_id,
            file_id=file_id,
            profile_code="BY_INVOICE",
            p_from=p_from,
            p_to=p_to,
        ),
    )
    run_id = int(run_res.data["run_id"])
    print(f"[OK] Đã tạo Run #{run_id} trong hàng đợi RECON_RUN_QUEUE (Trạng thái: READY)")

    # 5. Worker nhận job và thực thi
    print("[...] Worker đang claim job và tiến hành đối soát...")
    if args.oracle:
        print("[Oracle] Kết nối tới CSDL Oracle qua VPN...")
        worker = ReconWorker()
        worker.poll_once()
    else:
        # Mock fetcher từ G01 Parquet
        import polars as pl

        golden_parquet = Path("tests/golden/G01_dtp_by_invoice/db.parquet")
        db_df = pl.read_parquet(golden_parquet)

        def mock_fetcher(
            config: Any, profile: Any, p_from: Any, p_to: Any, max_rows: Any, timeout: Any
        ) -> pl.DataFrame:
            return db_df

        execute_run(run_id, mock_fetcher=mock_fetcher)

    # 6. Hiển thị kết quả
    run_info = get_run(ctx, run_id).data
    summary = run_info.get("summary") or {}

    print("\n" + "=" * 65)
    print(f"               KẾT QUẢ ĐỐI SOÁT (RUN #{run_id})              ")
    print("=" * 65)
    print(f"Trạng thái tổng thể : {run_info['status']} ({run_info['stage']})")
    print(f"Số dòng Excel đọc   : {summary.get('EXCEL_ROWS_READ', 0):,} dòng")
    print(f"Số nhóm Excel gộp   : {summary.get('EXCEL_GROUPS', 0):,} nhóm")
    print(f"Số dòng DB nguồn    : {summary.get('DB_ROWS', 0):,} dòng")
    print(f"Số nhóm DB gộp      : {summary.get('DB_GROUPS', 0):,} nhóm")
    print("-" * 65)
    print(f"  [+] Khớp hoàn toàn (MATCHED)        : {summary.get('CNT_MATCHED', 0):>5} nhóm")
    print(f"  [-] Lệch giá trị (MISMATCH)         : {summary.get('CNT_MISMATCH', 0):>5} nhóm")
    print(f"  [!] Thiếu trong DB (MISSING_IN_DB)  : {summary.get('CNT_MISSING_IN_DB', 0):>5} nhóm")
    print(f"  [?] Thiếu trong Excel (MISSING_EX)  : {summary.get('CNT_MISSING_IN_EXCEL', 0):>5} nhóm")
    print(f"  [*] Không nhất quán (INCONSISTENT)  : {summary.get('CNT_INCONSISTENT', 0):>5} nhóm")
    print(f"  [#] Trùng khóa (DUPLICATE)          : {summary.get('CNT_DUPLICATE', 0):>5} nhóm")
    print("-" * 65)
    print(f"Control Total File  : {summary.get('CONTROL_TOTAL_FILE', 0):>15} VND")
    print(f"Control Total Calc  : {summary.get('CONTROL_TOTAL_CALC', 0):>15} VND")
    print(f"Control Total Khớp  : {'ĐỒNG BỘ CHÍNH XÁC' if summary.get('CONTROL_TOTAL_OK') == 'Y' else 'LỆCH'}")
    print(f"Thời gian xử lý     : {summary.get('DURATION_MS', 0)} ms")

    # 7. Xuất file báo cáo Excel
    exp_res = export_run(ctx, run_id)
    export_path = exp_res.data["export_path"]
    print(f"\n[OK] Đã xuất file báo cáo Excel: {export_path}")

    # 8. Xóa dữ liệu tạm nếu có cờ --purge
    if args.purge:
        from app.services.temp_data import mark_checked

        mark_checked(ctx, run_id=run_id, purge=True)
        print("[OK] Đã đánh dấu kiểm tra và xóa toàn bộ dữ liệu tạm của run!")
        print("     (Dữ liệu kết quả RECON_RESULT_* và file Excel xuất vẫn được lưu trữ nguyên vẹn)")

    print("=" * 65)
    print("                  DEMO HOÀN TẤT THÀNH CÔNG                   ")
    print("=" * 65)


if __name__ == "__main__":
    main()
