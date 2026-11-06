"""Tests cho Split file/zip/hash/storage — Bước 3 task 26.

T26-06 (1.000.000 rows/file split), T26-07 (ZIP parts + summary),
T26-08 (hash/size/status).
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from unittest.mock import patch

from openpyxl import load_workbook

from tests.unit.test_report_export_queue import _done_run, _request
from tests.unit.test_report_export_write import (
    _fake_conn,
    export_env,
    operator_ctx,
    run_env,
)

__all__ = ["export_env", "operator_ctx", "run_env"]


def _run_export(export_env, operator_ctx, total, fmt, max_rows=100):
    from app.services.report_export import execute_export

    run = _done_run(operator_ctx, export_env)
    exp = _request(operator_ctx, export_env, run["id"], fmt).data
    conn = _fake_conn(total)
    with patch(
        "app.services.report_source.open_source_connection",
        return_value=conn,
    ):
        result = execute_export(
            exp["id"], max_rows_per_file=max_rows, engine=export_env["engine"]
        )
    assert result["status"] == "DONE", result
    return result


class TestSplit:
    def test_split_250_rows_3_parts(self, export_env, operator_ctx):
        result = _run_export(export_env, operator_ctx, 250, "XLSX")
        assert result["part_count"] == 3
        assert result["row_count"] == 250
        assert result["format"] == "ZIP"
        with zipfile.ZipFile(result["file_path"]) as zf:
            names = sorted(zf.namelist())
        assert names == [
            "_summary.txt",
            "part-001.xlsx",
            "part-002.xlsx",
            "part-003.xlsx",
        ]

    def test_exact_limit_one_part(self, export_env, operator_ctx):
        result = _run_export(export_env, operator_ctx, 100, "XLSX")
        assert result["part_count"] == 1
        assert result["format"] == "XLSX"
        assert result["file_path"].endswith("part-001.xlsx")

    def test_zip_summary_content(self, export_env, operator_ctx):
        result = _run_export(export_env, operator_ctx, 250, "XLSX")
        with zipfile.ZipFile(result["file_path"]) as zf:
            summary = zf.read("_summary.txt").decode("utf-8")
            part1 = zf.read("part-001.xlsx")
        assert "Tổng số dòng: 250" in summary
        assert "Số file: 3" in summary
        assert "part-001.xlsx" in summary
        wb = load_workbook(filename=io.BytesIO(part1), read_only=True)
        rows = list(wb["Data"].iter_rows(values_only=True))
        assert len(rows) == 101  # header + 100 dòng

    def test_hash_size_status(self, export_env, operator_ctx):
        result = _run_export(export_env, operator_ctx, 250, "CSV")
        assert result["format"] == "ZIP"
        raw = open(result["file_path"], "rb").read()
        assert result["file_size"] == len(raw)
        assert result["file_hash"] == hashlib.sha256(raw).hexdigest()
        assert result["row_count"] == 250
        with zipfile.ZipFile(result["file_path"]) as zf:
            names = sorted(zf.namelist())
        assert names == [
            "_summary.txt",
            "part-001.csv",
            "part-002.csv",
            "part-003.csv",
        ]

    def test_single_file_hash(self, export_env, operator_ctx):
        result = _run_export(export_env, operator_ctx, 50, "XLSX")
        raw = open(result["file_path"], "rb").read()
        assert result["file_size"] == len(raw)
        assert result["file_hash"] == hashlib.sha256(raw).hexdigest()
        assert result["part_count"] == 1
