"""Tests Bước 5 task 109 — Per-visual export XLSX/CSV cho báo cáo Studio.

Viết trước theo plan: execute_export nhận biết SOURCE_TYPE SEMANTIC_MODEL,
biên dịch lại qua planner + ép RLS theo Ctx chủ export, stream theo lô
FETCH_BATCH_SIZE; kiểm tra owner scope + RLS; hồi quy export cổ điển.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from openpyxl import load_workbook

from app.schemas.errors import ErrorCode
from tests.unit.test_report_viewer_semantic import (
    _bar_visual,
    _build_published_model,
    _field_id,
    _make_classic_report,
    _measure_id,
    _publish_studio_report,
    _run_visual,
    _table_visual,
    viewer_sem_env,
)

__all__ = ["viewer_sem_env"]


def _xlsx_rows(file_path: str) -> tuple[list[str], list[list[object]]]:
    wb = load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    assert rows, "file XLSX rỗng"
    header = [str(c) for c in rows[0]]
    return header, [list(r) for r in rows[1:]]


def _run_and_export(ctx, report_id, visual_id, fmt, engine, values=None, query_spec=None):
    """Chạy 1 visual tới DONE rồi request + thực thi export đồng bộ (như worker)."""
    from app.services.report_export import execute_export, request_export

    data = _run_visual(ctx, report_id, visual_id, values=values, query_spec=query_spec)
    assert data["run"]["status"] == "DONE", data["run"]
    run_id = int(data["run"]["id"])
    req = request_export(ctx, run_id, fmt)
    assert req.ok, req.message
    export_id = int(req.data["id"])
    done = execute_export(export_id, engine=engine)
    assert done["status"] == "DONE", done
    return done


def test_export_visual_xlsx_contains_rows(viewer_sem_env) -> None:
    engine, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(
        ctxs["owner"], ver_id, bundle, [_table_visual(bundle)]
    )
    done = _run_and_export(ctxs["viewer"], report_id, vis_ids["V_TABLE"], "XLSX", engine)
    header, rows = _xlsx_rows(str(done["file_path"]))
    assert header == ["CUSTOMER_NAME", "REV_SUM"]
    by_name = {r[0]: r[1] for r in rows}
    assert by_name == {"Cong ty A": 800000, "Cong ty B": 200000}


def test_export_visual_csv_contains_rows(viewer_sem_env) -> None:
    engine, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(
        ctxs["owner"], ver_id, bundle, [_table_visual(bundle)]
    )
    done = _run_and_export(ctxs["viewer"], report_id, vis_ids["V_TABLE"], "CSV", engine)
    text_out = Path(str(done["file_path"])).read_text(encoding="utf-8-sig")
    assert "CUSTOMER_NAME" in text_out and "REV_SUM" in text_out
    assert "Cong ty A" in text_out and "800000" in text_out
    assert "Cong ty B" in text_out and "200000" in text_out


def test_export_visual_rls_owner_scope(viewer_sem_env) -> None:
    """BẢO MẬT: worker biên dịch lại bằng Ctx của chủ export.

    RLS OWNER_USERNAME trên DIM_CUSTOMER.OWNER_USER: viewer chỉ xuất được
    khách của mình. Nếu worker biên dịch bằng ADMIN/không Ctx thì file sẽ
    chứa cả 2 khách -> test này ĐỎ.
    """
    engine, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id, rls_owner_username=True)
    report_id, _vid, vis_ids = _publish_studio_report(
        ctxs["owner"], ver_id, bundle, [_table_visual(bundle)]
    )
    viewer_done = _run_and_export(ctxs["viewer"], report_id, vis_ids["V_TABLE"], "XLSX", engine)
    _header, rows = _xlsx_rows(str(viewer_done["file_path"]))
    assert [r[0] for r in rows] == ["Cong ty B"]
    admin_done = _run_and_export(ctxs["admin"], report_id, vis_ids["V_TABLE"], "XLSX", engine)
    _header, rows = _xlsx_rows(str(admin_done["file_path"]))
    assert {r[0] for r in rows} == {"Cong ty A", "Cong ty B"}


def test_export_visual_owner_scope_denied(viewer_sem_env) -> None:
    """Viewer không export được run của admin (owner_filter)."""
    from app.services.report_export import request_export

    _engine, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(
        ctxs["owner"], ver_id, bundle, [_table_visual(bundle)]
    )
    data = _run_visual(ctxs["admin"], report_id, vis_ids["V_TABLE"])
    run_id = int(data["run"]["id"])
    denied = request_export(ctxs["viewer"], run_id, "XLSX")
    assert not denied.ok and denied.code == ErrorCode.NOT_FOUND


def test_export_visual_with_query_spec_filter(viewer_sem_env) -> None:
    engine, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(
        ctxs["owner"], ver_id, bundle, [_table_visual(bundle)]
    )
    spec = {
        "filters": [
            {
                "field_id": _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME"),
                "operator": "=",
                "value": "Cong ty A",
            }
        ]
    }
    done = _run_and_export(
        ctxs["viewer"], report_id, vis_ids["V_TABLE"], "XLSX", engine, query_spec=spec
    )
    _header, rows = _xlsx_rows(str(done["file_path"]))
    assert [r[0] for r in rows] == ["Cong ty A"]


def test_export_visual_matrix_exports_table_rows(viewer_sem_env) -> None:
    """MATRIX xuất dữ liệu gốc dạng bảng (không pivot có trần 50x20 ở file)."""
    engine, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    matrix = _table_visual(
        bundle,
        code="V_MATRIX",
        visual_type="MATRIX",
        title="Ma trận doanh thu",
        fields=[
            {"well_role": "ROWS", "field_id": _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")},
            {"well_role": "COLUMNS", "field_id": _field_id(bundle, "DIM_CUSTOMER", "SEGMENT")},
            {"well_role": "VALUES", "measure_id": _measure_id(bundle, "REV_SUM")},
        ],
    )
    report_id, _vid, vis_ids = _publish_studio_report(ctxs["owner"], ver_id, bundle, [matrix])
    done = _run_and_export(ctxs["viewer"], report_id, vis_ids["V_MATRIX"], "XLSX", engine)
    header, rows = _xlsx_rows(str(done["file_path"]))
    assert header == ["CUSTOMER_NAME", "SEGMENT", "REV_SUM"]
    assert {tuple(r) for r in rows} == {("Cong ty A", "VIP", 800000), ("Cong ty B", "STD", 200000)}


def test_export_visual_bar_same_data_as_table(viewer_sem_env) -> None:
    engine, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(
        ctxs["owner"], ver_id, bundle, [_bar_visual(bundle)]
    )
    done = _run_and_export(ctxs["viewer"], report_id, vis_ids["V_BAR"], "CSV", engine)
    text_out = Path(str(done["file_path"])).read_text(encoding="utf-8-sig")
    assert "Cong ty A" in text_out and "Cong ty B" in text_out


def test_export_visual_split_zip_when_small_max_rows(viewer_sem_env) -> None:
    """Vượt max_rows_per_file -> split thành ZIP nhiều part + _summary.txt."""
    engine, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(
        ctxs["owner"], ver_id, bundle, [_table_visual(bundle)]
    )
    from app.services.report_export import execute_export, request_export

    data = _run_visual(ctxs["viewer"], report_id, vis_ids["V_TABLE"])
    req = request_export(ctxs["viewer"], int(data["run"]["id"]), "XLSX")
    assert req.ok, req.message
    done = execute_export(int(req.data["id"]), max_rows_per_file=1, engine=engine)
    assert done["status"] == "DONE"
    assert done["format"] == "ZIP"
    assert done["part_count"] == 2
    with zipfile.ZipFile(str(done["file_path"])) as zf:
        names = zf.namelist()
        assert "_summary.txt" in names
        assert len([n for n in names if n.endswith(".xlsx")]) == 2


def test_classic_export_regression(viewer_sem_env) -> None:
    """Export cổ điển CUSTOM_SQL vẫn chạy qua luồng cũ (không đụng semantic)."""
    engine, ds_id, ctxs = viewer_sem_env
    report_id, _tpl_id, _ver_id = _make_classic_report(ctxs["admin"], ds_id, engine)
    from app.services.report_export import execute_export, request_export
    from app.services.report_run import create_report_run, execute_report_run

    created = create_report_run(ctxs["viewer"], report_id, values={"P_SEG": "FIN"})
    assert created.ok, created.message
    executed = execute_report_run(ctxs["viewer"], int(created.data["id"]))
    assert executed.ok and executed.data["run"]["status"] == "DONE"
    req = request_export(ctxs["viewer"], int(created.data["id"]), "XLSX")
    assert req.ok, req.message
    done = execute_export(int(req.data["id"]), engine=engine)
    assert done["status"] == "DONE", done
    header, rows = _xlsx_rows(str(done["file_path"]))
    assert header == ["Mã", "Tên"]  # XLSX dùng LABEL của cột
    assert rows == [["RPT_CLASSIC", "Báo cáo cổ điển"]]


def test_rerun_and_export_studio_visual_run(viewer_sem_env) -> None:
    """Xuất lại (rerun_and_export) ở /report-runs giữ đúng VISUAL_ID và QUERY_SPEC_JSON."""
    from sqlalchemy import select

    from app.db.metadata import recon_report_run
    from app.services.report_export import execute_export, rerun_and_export

    engine, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(
        ctxs["owner"], ver_id, bundle, [_table_visual(bundle)]
    )
    spec = {
        "filters": [
            {
                "field_id": _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME"),
                "operator": "=",
                "value": "Cong ty A",
            }
        ]
    }
    first = _run_and_export(ctxs["viewer"], report_id, vis_ids["V_TABLE"], "CSV", engine, query_spec=spec)
    rerun = rerun_and_export(ctxs["viewer"], int(first["run_id"]))
    assert rerun.ok, rerun.message
    new_run_id = int(rerun.data["run_id"])
    new_export = rerun.data["export"]
    assert new_export["format"] == "CSV"
    with engine.connect() as conn:
        row = conn.execute(select(recon_report_run).where(recon_report_run.c.ID == new_run_id)).mappings().first()
        assert row is not None
        assert int(row["VISUAL_ID"]) == vis_ids["V_TABLE"]
        assert row["QUERY_SPEC_JSON"] == spec
    done = execute_export(int(new_export["id"]), engine=engine)
    assert done["status"] == "DONE"
    text_out = Path(str(done["file_path"])).read_text(encoding="utf-8-sig")
    assert "Cong ty A" in text_out and "Cong ty B" not in text_out


def test_open_semantic_export_stream_single_connection(viewer_sem_env, monkeypatch) -> None:
    """Export semantic mở 1 connection & 1 cursor stream liên tục thay vì lặp OFFSET mỗi 10k."""
    import app.services.semantic_query as sq
    from app.engine.semantic_planner import resolve_semantic_plan
    from app.engine.semantic_sql import compile_semantic_query
    from app.schemas.semantic_query import SemanticQueryIntent

    _engine, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    intent_dict = {
        "model_version_id": ver_id,
        "dimensions": [{"field_id": _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")}],
        "measures": [{"measure_id": _measure_id(bundle, "REV_SUM")}],
    }
    intent = SemanticQueryIntent(**intent_dict)
    resolved = resolve_semantic_plan(intent, bundle)
    plan = compile_semantic_query(
        resolved, intent, username="viewer", roles=["VIEWER"], dialect="SQLITE", export_max_rows=25000
    )
    assert "LIMIT 25000" in plan.sql and "OFFSET" not in plan.sql

    open_calls = 0
    plan_calls = 0
    orig_open = sq._open_semantic_source
    orig_load = sq._load_plan

    def counted_open(*args, **kwargs):
        nonlocal open_calls
        open_calls += 1
        return orig_open(*args, **kwargs)

    def counted_load(*args, **kwargs):
        nonlocal plan_calls
        plan_calls += 1
        return orig_load(*args, **kwargs)

    monkeypatch.setattr(sq, "_open_semantic_source", counted_open)
    monkeypatch.setattr(sq, "_load_plan", counted_load)

    cols, batches = sq.open_semantic_export_stream(
        ctxs["viewer"], ver_id, intent_dict, batch_size=1, max_rows=25000
    )
    all_rows = [r for b in batches for r in b]
    assert len(cols) == 2
    assert len(all_rows) == 2
    assert plan_calls == 1
    assert open_calls == 1


def test_export_visual_applies_format_mask_to_xlsx(viewer_sem_env) -> None:
    """FORMAT_MASK cấu hình trên trường visual được áp xuống file XLSX."""
    engine, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    vis = _table_visual(
        bundle,
        fields=[
            {"well_role": "X", "field_id": _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")},
            {"well_role": "Y", "measure_id": _measure_id(bundle, "REV_SUM"), "format_mask": "#,##0.00"},
        ],
    )
    report_id, _vid, vis_ids = _publish_studio_report(ctxs["owner"], ver_id, bundle, [vis])
    done = _run_and_export(ctxs["viewer"], report_id, vis_ids["V_TABLE"], "XLSX", engine)
    wb = load_workbook(str(done["file_path"]), read_only=False, data_only=True)
    ws = wb.active
    assert ws is not None
    assert ws["B2"].number_format == "#,##0.00"
    wb.close()
