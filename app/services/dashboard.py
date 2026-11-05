from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, desc, func, or_, select

from app.core.context import Ctx, Role
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_result_row,
    recon_run,
    recon_run_summary,
    recon_template,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import check_owned, owner_filter, requires_menu
from app.services.temp_data import usage

ALL_ROLES = (Role.VIEWER, Role.OPERATOR, Role.TEMPLATE_OWNER, Role.ADMIN)


@service
@requires_menu("dashboard")
def get_dashboard_summary(ctx: Ctx, month: str | None = None) -> dict[str, Any]:
    """Tổng hợp số liệu thống kê cho Dashboard (PRD C1).

    Bao gồm 4 thẻ KPI chỉ số, 10 run gần đây và thống kê tỉ lệ lệch theo template.
    """

    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    scope = owner_filter(ctx, engine)
    owner_cond = [] if scope["is_admin"] else [recon_run.c.CREATED_BY == scope["username"]]

    # Xác định khoảng thời gian tháng cần thống kê
    if month:
        try:
            parts = month.split("-")
            year = int(parts[0])
            m = int(parts[1])
            start_date = datetime(year, m, 1)
        except Exception:
            start_date = datetime(now.year, now.month, 1)
    else:
        start_date = datetime(now.year, now.month, 1)

    if start_date.month == 12:
        end_date = datetime(start_date.year + 1, 1, 1)
    else:
        end_date = datetime(start_date.year, start_date.month + 1, 1)

    with engine.connect() as conn:
        # 1. Thống kê run trong tháng được chỉ định
        runs_query = select(recon_run).where(
            recon_run.c.CREATED_AT >= start_date,
            recon_run.c.CREATED_AT < end_date,
            *owner_cond,
        )
        all_month_runs = conn.execute(runs_query).mappings().fetchall()
        total_runs = len(all_month_runs)

        done_count = sum(1 for r in all_month_runs if r["STATUS"] == "DONE")
        failed_count = sum(1 for r in all_month_runs if r["STATUS"] == "FAILED")
        running_count = sum(1 for r in all_month_runs if r["STATUS"] in ("RUNNING", "QUEUED"))
        unchecked_count = sum(1 for r in all_month_runs if r["STATUS"] == "DONE" and r["CHECKED_AT"] is None)

        my_unchecked = sum(
            1
            for r in all_month_runs
            if r["CREATED_BY"] == ctx.username and r["STATUS"] == "DONE" and r["CHECKED_AT"] is None
        )
        my_failed = sum(1 for r in all_month_runs if r["CREATED_BY"] == ctx.username and r["STATUS"] == "FAILED")
        my_work = my_unchecked + my_failed

        # 2. Tỉ lệ khớp trung bình từ recon_run_summary
        avg_match_pct: float | None = None
        sum_stmt = (
            select(
                func.sum(recon_run_summary.c.CNT_MATCHED).label("TOTAL_MATCHED"),
                func.sum(recon_run_summary.c.CNT_MISMATCH).label("TOTAL_MISMATCH"),
                func.sum(recon_run_summary.c.CNT_MISSING_IN_DB).label("TOTAL_MISSING_DB"),
                func.sum(recon_run_summary.c.CNT_MISSING_IN_EXCEL).label("TOTAL_MISSING_EXCEL"),
            )
            .select_from(recon_run_summary.join(recon_run, recon_run_summary.c.RUN_ID == recon_run.c.ID))
            .where(
                recon_run.c.CREATED_AT >= start_date,
                recon_run.c.CREATED_AT < end_date,
                recon_run.c.STATUS == "DONE",
                *owner_cond,
            )
        )
        sums = conn.execute(sum_stmt).mappings().first()
        if sums and sums["TOTAL_MATCHED"] is not None:
            tot_matched = sums["TOTAL_MATCHED"] or 0
            tot_diff = (
                (sums["TOTAL_MISMATCH"] or 0) + (sums["TOTAL_MISSING_DB"] or 0) + (sums["TOTAL_MISSING_EXCEL"] or 0)
            )
            tot_compared = tot_matched + tot_diff
            if tot_compared > 0:
                avg_match_pct = round((tot_matched / tot_compared) * 100, 1)

        # 3. 10 run gần đây nhất
        recent_stmt = (
            select(
                recon_run.c.ID,
                recon_run.c.PROFILE_CODE,
                recon_run.c.STATUS,
                recon_run.c.PROGRESS_PCT,
                recon_run.c.CREATED_AT,
                recon_run.c.CHECKED_AT,
                recon_run.c.CHECKED_BY,
                recon_run.c.P_FROM,
                recon_run.c.P_TO,
                recon_template.c.NAME.label("TEMPLATE_NAME"),
                recon_template.c.CODE.label("TEMPLATE_CODE"),
                recon_run_summary.c.CNT_MATCHED,
                recon_run_summary.c.CNT_MISMATCH,
                recon_run_summary.c.CNT_MISSING_IN_DB,
                recon_run_summary.c.CNT_MISSING_IN_EXCEL,
            )
            .select_from(
                recon_run.outerjoin(recon_template, recon_run.c.TEMPLATE_ID == recon_template.c.ID).outerjoin(
                    recon_run_summary, recon_run.c.ID == recon_run_summary.c.RUN_ID
                )
            )
            .order_by(desc(recon_run.c.CREATED_AT))
            .limit(10)
        )
        if owner_cond:
            recent_stmt = recent_stmt.where(*owner_cond)
        recent_rows = conn.execute(recent_stmt).mappings().fetchall()

        recent_items = []
        for r in recent_rows:
            cnt_matched = r["CNT_MATCHED"] or 0
            cnt_mismatch = r["CNT_MISMATCH"] or 0
            cnt_missing_db = r["CNT_MISSING_IN_DB"] or 0
            cnt_missing_excel = r["CNT_MISSING_IN_EXCEL"] or 0
            tot_comp = cnt_matched + cnt_mismatch + cnt_missing_db + cnt_missing_excel
            m_pct = (
                round((cnt_matched / tot_comp) * 100, 1) if tot_comp > 0 else (100.0 if r["STATUS"] == "DONE" else None)
            )

            recent_items.append(
                {
                    "id": int(r["ID"]),
                    "template_name": str(r["TEMPLATE_NAME"] or r["TEMPLATE_CODE"] or "Template"),
                    "profile_code": str(r["PROFILE_CODE"] or "—"),
                    "status": str(r["STATUS"]),
                    "progress_pct": int(r["PROGRESS_PCT"] or 0),
                    "created_at": r["CREATED_AT"].isoformat() if r["CREATED_AT"] else None,
                    "checked_at": r["CHECKED_AT"].isoformat() if r["CHECKED_AT"] else None,
                    "checked_by": r["CHECKED_BY"],
                    "p_from": r["P_FROM"].isoformat() if r["P_FROM"] else None,
                    "p_to": r["P_TO"].isoformat() if r["P_TO"] else None,
                    "cnt_mismatch": cnt_mismatch,
                    "cnt_missing_in_db": cnt_missing_db,
                    "cnt_missing_in_excel": cnt_missing_excel,
                    "match_pct": m_pct,
                }
            )

        last_run_time_str = "—"
        if recent_items and recent_items[0]["created_at"]:
            try:
                l_dt = datetime.fromisoformat(recent_items[0]["created_at"])
                last_run_time_str = l_dt.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                pass

        # 4. Tỉ lệ lệch theo template (PRD C1)
        tmpl_diff_stmt = (
            select(
                recon_template.c.ID.label("TEMPLATE_ID"),
                recon_template.c.CODE.label("TEMPLATE_CODE"),
                recon_template.c.NAME.label("TEMPLATE_NAME"),
                func.count(recon_run.c.ID).label("RUN_COUNT"),
                func.sum(recon_run_summary.c.CNT_MATCHED).label("TOTAL_MATCHED"),
                func.sum(recon_run_summary.c.CNT_MISMATCH).label("TOTAL_MISMATCH"),
                func.sum(recon_run_summary.c.CNT_MISSING_IN_DB).label("TOTAL_MISSING_DB"),
                func.sum(recon_run_summary.c.CNT_MISSING_IN_EXCEL).label("TOTAL_MISSING_EXCEL"),
            )
            .select_from(
                recon_template.join(recon_run, recon_template.c.ID == recon_run.c.TEMPLATE_ID).join(
                    recon_run_summary, recon_run.c.ID == recon_run_summary.c.RUN_ID
                )
            )
            .where(
                recon_run.c.CREATED_AT >= start_date,
                recon_run.c.CREATED_AT < end_date,
                recon_run.c.STATUS == "DONE",
                *owner_cond,
            )
            .group_by(
                recon_template.c.ID,
                recon_template.c.CODE,
                recon_template.c.NAME,
            )
            .order_by(desc("RUN_COUNT"))
        )
        tmpl_diff_rows = conn.execute(tmpl_diff_stmt).mappings().fetchall()

        diff_by_tmpl: list[dict[str, Any]] = []
        for tr in tmpl_diff_rows:
            t_matched = tr["TOTAL_MATCHED"] or 0
            t_diff = (tr["TOTAL_MISMATCH"] or 0) + (tr["TOTAL_MISSING_DB"] or 0) + (tr["TOTAL_MISSING_EXCEL"] or 0)
            t_total = t_matched + t_diff
            diff_pct = round((t_diff / t_total) * 100, 1) if t_total > 0 else 0.0

            diff_by_tmpl.append(
                {
                    "template_id": int(tr["TEMPLATE_ID"]),
                    "template_code": str(tr["TEMPLATE_CODE"]),
                    "template_name": str(tr["TEMPLATE_NAME"]),
                    "run_count": int(tr["RUN_COUNT"]),
                    "total_compared": t_total,
                    "total_diff": t_diff,
                    "diff_pct": diff_pct,
                }
            )

    # 5. Dung lượng dữ liệu tạm
    temp_bytes = 0
    try:
        u_res = usage(ctx)
        if u_res.ok and u_res.data:
            temp_bytes = u_res.data.get("total_bytes", 0)
    except Exception:
        pass

    return {
        "period_month": start_date.strftime("%m/%Y"),
        "total_runs": total_runs,
        "done_count": done_count,
        "failed_count": failed_count,
        "running_count": running_count,
        "unchecked_count": unchecked_count,
        "my_work": my_work,
        "my_unchecked": my_unchecked,
        "my_failed": my_failed,
        "avg_match_pct": avg_match_pct,
        "recent_runs": recent_items,
        "last_run_time": last_run_time_str,
        "temp_bytes": temp_bytes,
        "diff_rate_by_template": diff_by_tmpl,
    }


@service
@requires_menu("dashboard")
def compare_runs(ctx: Ctx, run_id_a: int, run_id_b: int) -> dict[str, Any]:
    """So sánh kết quả giữa 2 run cùng Template và Profile (PRD C6).

    Phân loại các khóa đối soát thành 3 nhóm:
    1. ONLY_IN_A: Khóa chỉ xuất hiện trong Run A (đã hết lệch hoặc không còn dòng ở Run B).
    2. ONLY_IN_B: Khóa chỉ xuất hiện trong Run B (mới xuất hiện ở Run B).
    3. IN_BOTH: Khóa xuất hiện ở cả 2 run (phân loại tiếp STATUS_CHANGED hoặc SAME_STATUS).
    """

    engine = get_recon_engine()

    with engine.connect() as conn:
        # 1. Kiểm tra Run A
        run_a = (
            conn.execute(
                select(recon_run, recon_template.c.NAME.label("TEMPLATE_NAME"))
                .outerjoin(recon_template, recon_run.c.TEMPLATE_ID == recon_template.c.ID)
                .where(recon_run.c.ID == run_id_a)
            )
            .mappings()
            .first()
        )
        if not run_a:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy Run #{run_id_a}.")

        # 2. Kiểm tra Run B
        run_b = (
            conn.execute(
                select(recon_run, recon_template.c.NAME.label("TEMPLATE_NAME"))
                .outerjoin(recon_template, recon_run.c.TEMPLATE_ID == recon_template.c.ID)
                .where(recon_run.c.ID == run_id_b)
            )
            .mappings()
            .first()
        )
        if not run_b:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy Run #{run_id_b}.")

        # Phạm vi dữ liệu (task 19): chỉ so sánh run của mình
        check_owned(conn, recon_run, "ID", run_id_a, ctx, engine=engine)
        check_owned(conn, recon_run, "ID", run_id_b, ctx, engine=engine)

        if run_a["STATUS"] != "DONE" or run_b["STATUS"] != "DONE":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ có thể so sánh các run đã hoàn thành thành công (DONE).",
            )

        if run_a["TEMPLATE_ID"] != run_b["TEMPLATE_ID"] or run_a["PROFILE_CODE"] != run_b["PROFILE_CODE"]:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Hai run phải có cùng Template và cùng Profile mới có thể đối chiếu so sánh.",
            )

        # 3. Lấy dòng kết quả của Run A và Run B
        rows_a = (
            conn.execute(
                select(
                    recon_result_row.c.ROW_NO,
                    recon_result_row.c.KEY_TEXT,
                    recon_result_row.c.KEY_HASH,
                    recon_result_row.c.STATUS,
                    recon_result_row.c.ABS_DIFF_MAIN,
                    recon_result_row.c.KEY_JSON,
                    recon_result_row.c.EXCEL_JSON,
                    recon_result_row.c.DB_JSON,
                    recon_result_row.c.DIFF_JSON,
                ).where(recon_result_row.c.RUN_ID == run_id_a)
            )
            .mappings()
            .fetchall()
        )

        rows_b = (
            conn.execute(
                select(
                    recon_result_row.c.ROW_NO,
                    recon_result_row.c.KEY_TEXT,
                    recon_result_row.c.KEY_HASH,
                    recon_result_row.c.STATUS,
                    recon_result_row.c.ABS_DIFF_MAIN,
                    recon_result_row.c.KEY_JSON,
                    recon_result_row.c.EXCEL_JSON,
                    recon_result_row.c.DB_JSON,
                    recon_result_row.c.DIFF_JSON,
                ).where(recon_result_row.c.RUN_ID == run_id_b)
            )
            .mappings()
            .fetchall()
        )

        dict_a = {str(r["KEY_HASH"]): dict(r) for r in rows_a}
        dict_b = {str(r["KEY_HASH"]): dict(r) for r in rows_b}
        all_hashes = sorted(set(dict_a.keys()) | set(dict_b.keys()))

        items: list[dict[str, Any]] = []
        count_only_a = 0
        count_only_b = 0
        count_both = 0
        count_status_changed = 0
        count_same_status = 0

        for kh in all_hashes:
            in_a = kh in dict_a
            in_b = kh in dict_b

            if in_a and not in_b:
                count_only_a += 1
                r_a = dict_a[kh]
                items.append(
                    {
                        "key_hash": kh,
                        "key_text": str(r_a["KEY_TEXT"]),
                        "category": "ONLY_IN_A",
                        "status_a": str(r_a["STATUS"]),
                        "status_b": None,
                        "diff_a": str(r_a["ABS_DIFF_MAIN"]) if r_a["ABS_DIFF_MAIN"] is not None else None,
                        "diff_b": None,
                        "status_changed": False,
                    }
                )
            elif in_b and not in_a:
                count_only_b += 1
                r_b = dict_b[kh]
                items.append(
                    {
                        "key_hash": kh,
                        "key_text": str(r_b["KEY_TEXT"]),
                        "category": "ONLY_IN_B",
                        "status_a": None,
                        "status_b": str(r_b["STATUS"]),
                        "diff_a": None,
                        "diff_b": str(r_b["ABS_DIFF_MAIN"]) if r_b["ABS_DIFF_MAIN"] is not None else None,
                        "status_changed": False,
                    }
                )
            else:
                count_both += 1
                r_a = dict_a[kh]
                r_b = dict_b[kh]
                st_a = str(r_a["STATUS"])
                st_b = str(r_b["STATUS"])
                changed = st_a != st_b
                if changed:
                    count_status_changed += 1
                else:
                    count_same_status += 1

                items.append(
                    {
                        "key_hash": kh,
                        "key_text": str(r_b["KEY_TEXT"]),
                        "category": "IN_BOTH",
                        "status_a": st_a,
                        "status_b": st_b,
                        "diff_a": str(r_a["ABS_DIFF_MAIN"]) if r_a["ABS_DIFF_MAIN"] is not None else None,
                        "diff_b": str(r_b["ABS_DIFF_MAIN"]) if r_b["ABS_DIFF_MAIN"] is not None else None,
                        "status_changed": changed,
                    }
                )

        tmpl_name = str(run_a["TEMPLATE_NAME"] or run_a["TEMPLATE_ID"])

        return {
            "run_a": {
                "id": run_id_a,
                "created_at": run_a["CREATED_AT"].isoformat() if run_a["CREATED_AT"] else None,
                "p_from": run_a["P_FROM"].isoformat() if run_a["P_FROM"] else None,
                "p_to": run_a["P_TO"].isoformat() if run_a["P_TO"] else None,
                "template_name": tmpl_name,
                "profile_code": str(run_a["PROFILE_CODE"]),
            },
            "run_b": {
                "id": run_id_b,
                "created_at": run_b["CREATED_AT"].isoformat() if run_b["CREATED_AT"] else None,
                "p_from": run_b["P_FROM"].isoformat() if run_b["P_FROM"] else None,
                "p_to": run_b["P_TO"].isoformat() if run_b["P_TO"] else None,
                "template_name": tmpl_name,
                "profile_code": str(run_b["PROFILE_CODE"]),
            },
            "summary": {
                "total_keys": len(all_hashes),
                "count_only_a": count_only_a,
                "count_only_b": count_only_b,
                "count_both": count_both,
                "count_status_changed": count_status_changed,
                "count_same_status": count_same_status,
            },
            "items": items,
        }


@service
@requires_menu("dashboard")
def get_previous_run(ctx: Ctx, run_id: int) -> dict[str, Any] | None:
    """Tìm run DONE trước đó gần nhất cùng Template và Profile."""

    engine = get_recon_engine()

    with engine.connect() as conn:
        curr = (
            conn.execute(
                select(
                    recon_run.c.ID,
                    recon_run.c.TEMPLATE_ID,
                    recon_run.c.PROFILE_CODE,
                    recon_run.c.CREATED_AT,
                ).where(recon_run.c.ID == run_id)
            )
            .mappings()
            .first()
        )

        if not curr:
            return None

        # Phạm vi dữ liệu (task 19): run gốc không phải của mình thì coi như không có
        prev_scope = owner_filter(ctx, engine)
        if not prev_scope["is_admin"]:
            curr_owner = conn.execute(
                select(recon_run.c.CREATED_BY).where(recon_run.c.ID == run_id)
            ).scalar_one_or_none()
            if curr_owner != ctx.username:
                return None

        prev = (
            conn.execute(
                select(
                    recon_run.c.ID,
                    recon_run.c.CREATED_AT,
                    recon_run.c.P_FROM,
                    recon_run.c.P_TO,
                )
                .where(
                    recon_run.c.TEMPLATE_ID == curr["TEMPLATE_ID"],
                    recon_run.c.PROFILE_CODE == curr["PROFILE_CODE"],
                    recon_run.c.STATUS == "DONE",
                    recon_run.c.ID != run_id,
                    *([recon_run.c.CREATED_BY == prev_scope["username"]] if not prev_scope["is_admin"] else []),
                    or_(
                        recon_run.c.CREATED_AT < curr["CREATED_AT"],
                        and_(
                            recon_run.c.CREATED_AT == curr["CREATED_AT"],
                            recon_run.c.ID < curr["ID"],
                        ),
                    ),
                )
                .order_by(desc(recon_run.c.CREATED_AT), desc(recon_run.c.ID))
                .limit(1)
            )
            .mappings()
            .first()
        )

        if not prev:
            return None

        return {
            "id": int(prev["ID"]),
            "created_at": prev["CREATED_AT"].isoformat() if prev["CREATED_AT"] else None,
            "p_from": prev["P_FROM"].isoformat() if prev["P_FROM"] else None,
            "p_to": prev["P_TO"].isoformat() if prev["P_TO"] else None,
        }
