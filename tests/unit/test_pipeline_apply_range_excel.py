from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from app.engine.pipeline import run_pipeline
from app.schemas.template_config import TemplateConfig


def _run(flag: bool):
    cfg = TemplateConfig.model_validate(
        json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))
    )
    return run_pipeline(
        excel_path=Path("samples/dtp_sample_200.xlsx"),
        config=cfg,
        profile_code="BY_INVOICE",
        params={
            "p_from": "2026-02-01 00:00:00",
            "p_to": "2026-02-02 23:59:59",
            "apply_range_excel": flag,
        },
        fetcher=pl.DataFrame(),
    )


def test_pipeline_applies_excel_time_filter_when_flag_on() -> None:
    res = _run(True)
    assert res.summary["EXCEL_ROWS_OUT_OF_RANGE"] == 117
    assert res.summary["EXCEL_GROUPS"] == 76


def test_pipeline_skips_excel_time_filter_when_flag_off() -> None:
    res = _run(False)
    assert res.summary["EXCEL_ROWS_OUT_OF_RANGE"] == 0
    assert res.summary["EXCEL_GROUPS"] == 190
    assert res.summary["EXCEL_ROWS_READ"] == 201
