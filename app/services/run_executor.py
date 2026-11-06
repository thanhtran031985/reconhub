from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl
import structlog
from sqlalchemy import delete, select, update

from app.core.context import Ctx, Role
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_batch_run_file,
    recon_batch_run_item,
    recon_data_source,
    recon_excel_load,
    recon_file,
    recon_invalid_row,
    recon_issue,
    recon_result_diff,
    recon_result_row,
    recon_run,
    recon_run_queue,
    recon_run_summary,
    recon_template_version,
)
from app.engine.fetch import fetch_df
from app.engine.pipeline import PipelineResult, run_pipeline
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import TemplateConfig
from app.services.excel_load import load_excel_to_temp
from app.services.source_conn import open_source_connection

logger = structlog.get_logger("executor")


class SourceFetcherWrapper:
    """Wrapper kết nối Oracle thực hiện kéo dữ liệu theo Spec 04 mục 8."""

    def __init__(self, ds_id: int, max_rows: int = 1_000_000, timeout: int = 600) -> None:
        self.ds_id = ds_id
        self.max_rows = max_rows
        self.timeout = timeout

    def fetch_df(self, conn: Any, sql: str, binds: dict[str, Any]) -> pl.DataFrame:
        ora_conn = open_source_connection(self.ds_id)
        try:
            return fetch_df(
                ora_conn,
                sql,
                binds,
                max_rows=self.max_rows,
                timeout=self.timeout,
            )
        finally:
            try:
                ora_conn.close()
            except Exception:
                pass


def _serialize_val(v: Any) -> Any:
    """Chuyển đổi kiểu dữ liệu phù hợp với JSON lưu trữ."""
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (datetime, date, pl.Date, pl.Datetime)):
        return str(v)
    return v


# Số biến bind tối đa cho một mệnh đề IN. 500 an toàn cho cả SQLite
# (giới hạn thấp nhất thường gặp là 999 biến/câu lệnh) và Oracle (tối đa
# 1000 biểu thức trong IN list). Đừng tăng lên quá 900 nếu không kiểm chứng
# lại trên cả hai dialect.
_ISSUE_UPDATE_BATCH_SIZE = 500


def _update_issues_last_run(conn: Any, template_id: int, profile_code: str, key_hashes: list[str], run_id: int) -> None:
    """Cập nhật LAST_RUN_ID cho các issue khớp key_hash, chia lô để không vượt giới hạn biến SQL.

    key_hashes gom từ mọi dòng kết quả nên có thể lên tới hàng trăm nghìn
    (file lớn) và có thể trùng nhau; đưa cả danh sách vào một mệnh đề IN
    duy nhất sẽ gây lỗi "too many SQL variables" và làm run FAILED ở giai
    đoạn SAVE, dù kết quả đã ghi xong.
    """
    unique_hashes = list(dict.fromkeys(key_hashes))
    for start in range(0, len(unique_hashes), _ISSUE_UPDATE_BATCH_SIZE):
        batch = unique_hashes[start : start + _ISSUE_UPDATE_BATCH_SIZE]
        conn.execute(
            update(recon_issue)
            .where(
                recon_issue.c.TEMPLATE_ID == template_id,
                recon_issue.c.PROFILE_CODE == profile_code,
                recon_issue.c.KEY_HASH.in_(batch),
            )
            .values(LAST_RUN_ID=run_id)
        )


def _sync_batch_after_run(run_id: int, batch_run_id: int) -> None:
    """Đồng bộ trạng thái batch sau khi một run con kết thúc (DONE/FAILED).

    Lỗi đồng bộ không làm hỏng kết quả run con đã ghi.
    """
    try:
        from app.services.batch_run import sync_batch_status

        sync_batch_status(get_recon_engine(), batch_run_id)
    except Exception as exc:  # noqa: BLE001 - đồng bộ batch là phụ, không chặn run
        logger.error("Lỗi đồng bộ trạng thái batch", run_id=run_id, batch_run_id=batch_run_id, error=str(exc))


def execute_run(
    run_id: int,
    mock_fetcher: Any = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Thực thi toàn bộ luồng đối soát qua 5 giai đoạn READ -> FILTER -> FETCH_DB -> COMPARE -> SAVE."""
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Đọc thông tin run
    with engine.connect() as conn:
        run_row = conn.execute(select(recon_run).where(recon_run.c.ID == run_id)).mappings().first()
        if not run_row:
            return {"run_id": run_id, "status": "FAILED", "error_code": ErrorCode.NOT_FOUND}

        template_id = int(run_row["TEMPLATE_ID"])
        template_version = int(run_row["TEMPLATE_VERSION"])
        profile_code = str(run_row["PROFILE_CODE"])
        file_id = int(run_row["FILE_ID"]) if run_row["FILE_ID"] else None
        batch_run_id = int(run_row["BATCH_RUN_ID"]) if run_row["BATCH_RUN_ID"] else None
        batch_run_item_id = int(run_row["BATCH_RUN_ITEM_ID"]) if run_row["BATCH_RUN_ITEM_ID"] else None
        data_source_id = int(run_row["DATA_SOURCE_ID"])
        p_from = run_row["P_FROM"]
        p_to = run_row["P_TO"]
        params_json = run_row["PARAMS_JSON"] or {}
        apply_range_excel = run_row["APPLY_RANGE_EXCEL"] == "Y"

        tv_row = (
            conn.execute(
                select(recon_template_version).where(
                    recon_template_version.c.TEMPLATE_ID == template_id,
                    recon_template_version.c.VERSION == template_version,
                )
            )
            .mappings()
            .first()
        )
        if not tv_row:
            return {"run_id": run_id, "status": "FAILED", "error_code": ErrorCode.NOT_FOUND}

        cfg_dict = tv_row["CONFIG_JSON"]
        cfg = TemplateConfig.model_validate(cfg_dict)

        f_row = None
        if file_id:
            f_row = conn.execute(select(recon_file).where(recon_file.c.ID == file_id)).mappings().first()

    excel_path = Path(str(f_row["STORAGE_PATH"])) if f_row and f_row["STORAGE_PATH"] else None

    # Cập nhật RUNNING, STAGE=READ (10%)
    with engine.begin() as conn:
        conn.execute(
            recon_run.update()
            .where(recon_run.c.ID == run_id)
            .values(
                STATUS="RUNNING",
                STAGE="READ",
                PROGRESS_PCT=10,
                STARTED_AT=now,
            )
        )

    try:
        # Giai đoạn 1 & 2: READ + FILTER (nạp Excel vào bảng tạm nếu có file)
        excel_load_id = None
        excel_files: list[tuple[str | Path, str]] | None = None
        if batch_run_item_id:
            # Run con của batch: nạp tập file của mục (gộp nhiều file).
            from app.services.excel_load import load_excel_files_to_temp

            with engine.connect() as conn:
                batch_files = (
                    conn.execute(
                        select(
                            recon_batch_run_file.c.FILE_ID,
                            recon_batch_run_file.c.ORIGINAL_NAME,
                            recon_file.c.STORAGE_PATH,
                        )
                        .select_from(
                            recon_batch_run_file.join(recon_file, recon_batch_run_file.c.FILE_ID == recon_file.c.ID)
                        )
                        .where(recon_batch_run_file.c.BATCH_RUN_ITEM_ID == batch_run_item_id)
                        .where(recon_batch_run_file.c.MATCH_STATE == "MATCHED")
                        .order_by(recon_batch_run_file.c.ID)
                    )
                    .mappings()
                    .all()
                )
            if not batch_files:
                raise ServiceError(ErrorCode.NOT_FOUND, "Mục chạy bộ không còn file đã ghép để thực hiện đối soát.")
            excel_files = [(Path(str(f["STORAGE_PATH"])), str(f["ORIGINAL_NAME"])) for f in batch_files]
            if not all(Path(p).exists() for p, _ in excel_files):
                raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy file Excel để thực hiện đối soát.")
            ctx_system = Ctx(user_id=1, username="system", full_name="System Worker", roles=[Role.ADMIN])
            load_res = load_excel_files_to_temp(
                ctx_system,
                file_ids=[int(f["FILE_ID"]) for f in batch_files],
                template_id=template_id,
                template_version=template_version,
                sheet_name=cfg.file.sheet,
            )
            if load_res.ok and load_res.data:
                excel_load_id = load_res.data.get("load_id")
            with engine.begin() as conn:
                conn.execute(
                    recon_batch_run_item.update()
                    .where(recon_batch_run_item.c.ID == batch_run_item_id)
                    .values(STATUS="RUNNING", UPDATED_BY="system", UPDATED_AT=now)
                )
        elif file_id and excel_path and excel_path.exists():
            # Tạo admin ctx tạm thời để gọi service nạp excel
            ctx_system = Ctx(user_id=1, username="system", full_name="System Worker", roles=[Role.ADMIN])
            load_res = load_excel_to_temp(
                ctx_system,
                file_id=file_id,
                template_id=template_id,
                template_version=template_version,
                sheet_name=cfg.file.sheet,
            )
            if load_res.ok and load_res.data:
                excel_load_id = load_res.data.get("load_id")

        with engine.begin() as conn:
            conn.execute(
                recon_run.update()
                .where(recon_run.c.ID == run_id)
                .values(
                    EXCEL_LOAD_ID=excel_load_id,
                    STAGE="FETCH_DB",
                    PROGRESS_PCT=55,
                )
            )

        # Giai đoạn 3 & 4: FETCH_DB & COMPARE
        params_combined = dict(params_json)
        params_combined["p_from"] = p_from
        params_combined["p_to"] = p_to
        params_combined["apply_range_excel"] = apply_range_excel

        fetcher: Any = None
        if mock_fetcher is not None:
            fetcher = mock_fetcher
        else:
            with engine.connect() as conn:
                ds = (
                    conn.execute(select(recon_data_source).where(recon_data_source.c.ID == data_source_id))
                    .mappings()
                    .first()
                )
            max_rows = int(ds["MAX_ROWS"] or 1_000_000) if ds else 1_000_000
            timeout_s = int(ds["CALL_TIMEOUT_S"] or 600) if ds else 600
            fetcher = SourceFetcherWrapper(ds_id=data_source_id, max_rows=max_rows, timeout=timeout_s)

        pipeline_res: PipelineResult
        if excel_files is not None:
            if not excel_files:
                raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy file Excel để thực hiện đối soát.")
            # Thực thi pipeline với tập file đã gộp
            pipeline_res = run_pipeline(
                excel_files=excel_files,
                config=cfg,
                profile_code=profile_code,
                params=params_combined,
                fetcher=fetcher,
            )
        else:
            if not excel_path or not excel_path.exists():
                raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy file Excel để thực hiện đối soát.")

            # Thực thi pipeline
            pipeline_res = run_pipeline(
                excel_path=excel_path,
                config=cfg,
                profile_code=profile_code,
                params=params_combined,
                fetcher=fetcher,
            )

        with engine.begin() as conn:
            conn.execute(
                recon_run.update()
                .where(recon_run.c.ID == run_id)
                .values(
                    STAGE="SAVE",
                    PROGRESS_PCT=90,
                )
            )

        # Giai đoạn 5: SAVE
        result_df = pipeline_res.result_df
        invalid_df = pipeline_res.invalid_df
        summary_dict = pipeline_res.summary
        target_profile = pipeline_res.profile
        ct_res = pipeline_res.control_total

        # Map tên file hiển thị -> file_id để ghi EXCEL_ROW_NOS dạng {f, r}
        # khi run gộp nhiều file (spec 10a §7). Run 1 file giữ dạng cũ.
        name_to_file_id: dict[str, int] = {}
        if excel_load_id:
            with engine.connect() as conn:
                load_row = (
                    conn.execute(select(recon_excel_load).where(recon_excel_load.c.ID == excel_load_id))
                    .mappings()
                    .first()
                )
            if load_row and load_row["SOURCE_FILES_JSON"]:
                source_files = load_row["SOURCE_FILES_JSON"]
                if isinstance(source_files, str):
                    source_files = json.loads(source_files)
                for sf in source_files or []:
                    name_to_file_id[str(sf.get("name"))] = int(sf.get("file_id"))

        finished_now = datetime.now(timezone.utc).replace(tzinfo=None)

        if persist:
            # Ghi nhận kết quả vào cơ sở dữ liệu
            with engine.begin() as conn:
                # Dọn sạch nếu có dữ liệu cũ của run này
                conn.execute(delete(recon_result_diff).where(recon_result_diff.c.RUN_ID == run_id))
                conn.execute(delete(recon_result_row).where(recon_result_row.c.RUN_ID == run_id))
                conn.execute(delete(recon_invalid_row).where(recon_invalid_row.c.RUN_ID == run_id))
                conn.execute(delete(recon_run_summary).where(recon_run_summary.c.RUN_ID == run_id))

                # 1. Ghi RECON_RESULT_ROW theo batch 5000
                rows_to_insert: list[dict[str, Any]] = []
                diffs_to_insert: list[dict[str, Any]] = []
                all_key_hashes: list[str] = []

                for idx, row in enumerate(result_df.iter_rows(named=True)):
                    row_no = idx + 1
                    key_text = str(row.get("KEY_TEXT") or row.get("__KEY_TEXT") or "")
                    key_hash = hashlib.sha256(key_text.encode("utf-8")).hexdigest()
                    all_key_hashes.append(key_hash)
                    status = str(row.get("STATUS") or row.get("__STATUS") or "")

                    key_dict = {f: _serialize_val(row.get(f)) for f in target_profile.group_by}
                    excel_dict = {
                        f"x__{m.name}": _serialize_val(row.get(f"x__{m.name}")) for m in target_profile.measures
                    }
                    db_dict = {f"d__{m.name}": _serialize_val(row.get(f"d__{m.name}")) for m in target_profile.measures}
                    diff_dict = {
                        f"diff__{m.name}": _serialize_val(row.get(f"diff__{m.name}")) for m in target_profile.measures
                    }

                    row_nos_list = row.get("__row_nos") or []
                    if row_nos_list and isinstance(row_nos_list[0], dict):
                        # Gộp nhiều file: [{f: tên file, r: dòng}] -> [{f: file_id, r: dòng}]
                        row_nos_str = json.dumps(
                            [
                                {"f": name_to_file_id.get(str(d.get("f")), d.get("f")), "r": d.get("r")}
                                for d in row_nos_list
                                if isinstance(d, dict)
                            ],
                            ensure_ascii=False,
                        )
                    else:
                        row_nos_str = ",".join(str(n) for n in row_nos_list) if isinstance(row_nos_list, list) else ""

                    abs_diff_main = row.get("ABS_DIFF_MAIN")
                    abs_diff_sort = float(row.get("ABS_DIFF_SORT") or 0.0)

                    rows_to_insert.append(
                        {
                            "RUN_ID": run_id,
                            "ROW_NO": row_no,
                            "KEY_TEXT": key_text,
                            "KEY_HASH": key_hash,
                            "STATUS": status,
                            "KEY_JSON": key_dict,
                            "EXCEL_JSON": excel_dict,
                            "DB_JSON": db_dict,
                            "DIFF_JSON": diff_dict,
                            "EXCEL_ROW_NOS": row_nos_str,
                            "ABS_DIFF_MAIN": Decimal(str(abs_diff_main)) if abs_diff_main is not None else None,
                            "ABS_DIFF_SORT": abs_diff_sort,
                        }
                    )

                    # Bổ sung RECON_RESULT_DIFF cho các measure bị lệch
                    for m in target_profile.measures:
                        diff_val = row.get(f"diff__{m.name}")
                        if diff_val is not None:
                            diff_abs = (
                                abs(Decimal(str(diff_val))) if isinstance(diff_val, (Decimal, int, float)) else None
                            )
                            diffs_to_insert.append(
                                {
                                    "RUN_ID": run_id,
                                    "ROW_NO": row_no,
                                    "MEASURE": m.name,
                                    "EXCEL_VAL": str(excel_dict.get(f"x__{m.name}") or ""),
                                    "DB_VAL": str(db_dict.get(f"d__{m.name}") or ""),
                                    "DIFF_ABS": diff_abs,
                                    "DIFF_PCT": None,
                                }
                            )

                    if len(rows_to_insert) >= 5000:
                        conn.execute(recon_result_row.insert(), rows_to_insert)
                        rows_to_insert.clear()

                if rows_to_insert:
                    conn.execute(recon_result_row.insert(), rows_to_insert)

                if diffs_to_insert:
                    conn.execute(recon_result_diff.insert(), diffs_to_insert)

                # Cập nhật LAST_RUN_ID cho các issue hiện có (chia lô, xem _update_issues_last_run)
                if all_key_hashes:
                    _update_issues_last_run(conn, template_id, profile_code, all_key_hashes, run_id)

                # 2. Ghi RECON_INVALID_ROW
                invalid_to_insert: list[dict[str, Any]] = []
                for inv_row in invalid_df.iter_rows(named=True):
                    invalid_to_insert.append(
                        {
                            "RUN_ID": run_id,
                            "EXCEL_ROW_NO": int(inv_row.get("__row_no") or 0),
                            "FIELD": str(inv_row.get("field") or ""),
                            "RAW_VALUE": str(inv_row.get("raw_value") or ""),
                            "REASON_CODE": str(inv_row.get("reason_code") or ""),
                        }
                    )
                if invalid_to_insert:
                    conn.execute(recon_invalid_row.insert(), invalid_to_insert)

                # 3. Ghi RECON_RUN_SUMMARY
                ct_file = ct_res.file_total if ct_res else None
                ct_calc = ct_res.calc_total if ct_res else None
                ct_ok = "Y" if (ct_res and ct_res.is_matched) else "N"

                def _get_sum(key: str, default: Any = 0) -> Any:
                    return summary_dict.get(key.upper(), summary_dict.get(key.lower(), default))

                conn.execute(
                    recon_run_summary.insert().values(
                        RUN_ID=run_id,
                        EXCEL_ROWS_READ=_get_sum("EXCEL_ROWS_READ", 0),
                        EXCEL_ROWS_OUT_OF_RANGE=_get_sum("EXCEL_ROWS_OUT_OF_RANGE", 0),
                        EXCEL_ROWS_INVALID=_get_sum("EXCEL_ROWS_INVALID", 0),
                        EXCEL_GROUPS=_get_sum("EXCEL_GROUPS", 0),
                        DB_ROWS=_get_sum("DB_ROWS", 0),
                        DB_GROUPS=_get_sum("DB_GROUPS", 0),
                        CNT_MATCHED=_get_sum("CNT_MATCHED", 0),
                        CNT_MISMATCH=_get_sum("CNT_MISMATCH", 0),
                        CNT_MISSING_IN_DB=_get_sum("CNT_MISSING_IN_DB", 0),
                        CNT_MISSING_IN_EXCEL=_get_sum("CNT_MISSING_IN_EXCEL", 0),
                        CNT_INCONSISTENT=_get_sum("CNT_INCONSISTENT", 0),
                        CNT_DUPLICATE=_get_sum("CNT_DUPLICATE", 0),
                        CONTROL_TOTAL_FILE=ct_file,
                        CONTROL_TOTAL_CALC=ct_calc,
                        CONTROL_TOTAL_OK=ct_ok,
                        MEASURE_TOTALS_JSON=_get_sum("MEASURE_TOTALS_JSON", None) or summary_dict.get("measure_totals"),
                        STATUS_AMOUNTS_JSON=_get_sum("STATUS_AMOUNTS_JSON", None) or summary_dict.get("status_amounts"),
                        COLUMNS_JSON=_get_sum("COLUMNS_JSON", None) or summary_dict.get("columns"),
                        SOURCE_SQL=_get_sum("SOURCE_SQL", None) or summary_dict.get("source_sql"),
                        DURATION_MS=_get_sum("DURATION_MS", 0),
                    )
                )

                # 4. Cập nhật RECON_RUN và RECON_RUN_QUEUE hoàn thành
                conn.execute(
                    recon_run.update()
                    .where(recon_run.c.ID == run_id)
                    .values(
                        STATUS="DONE",
                        STAGE="DONE",
                        PROGRESS_PCT=100,
                        ERROR_CODE=None,
                        ERROR_MSG=None,
                        FINISHED_AT=finished_now,
                    )
                )
                conn.execute(
                    recon_run_queue.update()
                    .where(recon_run_queue.c.RUN_ID == run_id)
                    .values(
                        STATUS="DONE",
                        HEARTBEAT_AT=finished_now,
                    )
                )
        else:
            # Chế độ Dry-run (persist=False)
            with engine.begin() as conn:
                conn.execute(
                    recon_template_version.update()
                    .where(
                        recon_template_version.c.TEMPLATE_ID == template_id,
                        recon_template_version.c.VERSION == template_version,
                    )
                    .values(
                        DRY_RUN_OK="Y",
                        DRY_RUN_JSON=summary_dict,
                    )
                )
                conn.execute(
                    recon_run.update()
                    .where(recon_run.c.ID == run_id)
                    .values(
                        STATUS="DONE",
                        STAGE="DONE",
                        PROGRESS_PCT=100,
                        ERROR_CODE=None,
                        ERROR_MSG=None,
                        FINISHED_AT=finished_now,
                    )
                )
                conn.execute(
                    recon_run_queue.update()
                    .where(recon_run_queue.c.RUN_ID == run_id)
                    .values(
                        STATUS="DONE",
                        HEARTBEAT_AT=finished_now,
                    )
                )

        if batch_run_id is not None:
            _sync_batch_after_run(run_id, batch_run_id)

        return {"run_id": run_id, "status": "DONE", "summary": summary_dict}

    except Exception as exc:
        logger.error("Lỗi thực thi run", run_id=run_id, error=str(exc))
        finished_err_now = datetime.now(timezone.utc).replace(tzinfo=None)

        if isinstance(exc, ServiceError):
            err_code = str(exc.code)
            err_msg = exc.message
        else:
            err_code = ErrorCode.INTERNAL_ERROR
            err_msg = f"Lỗi nội bộ hệ thống trong quá trình thực thi: {exc}"

        # Dọn dẹp kết quả dở dang
        with engine.begin() as conn:
            conn.execute(delete(recon_result_diff).where(recon_result_diff.c.RUN_ID == run_id))
            conn.execute(delete(recon_result_row).where(recon_result_row.c.RUN_ID == run_id))
            conn.execute(delete(recon_invalid_row).where(recon_invalid_row.c.RUN_ID == run_id))
            conn.execute(delete(recon_run_summary).where(recon_run_summary.c.RUN_ID == run_id))

            conn.execute(
                recon_run.update()
                .where(recon_run.c.ID == run_id)
                .values(
                    STATUS="FAILED",
                    STAGE="ERROR",
                    ERROR_CODE=err_code,
                    ERROR_MSG=err_msg,
                    FINISHED_AT=finished_err_now,
                )
            )
            conn.execute(
                recon_run_queue.update()
                .where(recon_run_queue.c.RUN_ID == run_id)
                .values(
                    STATUS="ERROR",
                    HEARTBEAT_AT=finished_err_now,
                )
            )

        if batch_run_id is not None:
            _sync_batch_after_run(run_id, batch_run_id)

        return {
            "run_id": run_id,
            "status": "FAILED",
            "error_code": err_code,
            "error_msg": err_msg,
        }
