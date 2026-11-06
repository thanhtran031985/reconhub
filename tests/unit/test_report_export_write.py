"""Tests cho Streaming fetchmany và write-only XLSX — Bước 2 task 26.

T26-02 (RAM không tăng tuyến tính), T26-03 (XLSX write-only),
T26-04 (leading zero giữ text), T26-05 (CSV encoding).
"""

from __future__ import annotations

import csv
import tracemalloc
from datetime import datetime
from unittest.mock import patch

from openpyxl import load_workbook

from tests.unit.test_report_export_queue import (
    ROWS,
    _done_run,
    _mock_stream_conn,
    _request,
    export_env,
)
from tests.unit.test_report_run_execute import operator_ctx, run_env

__all__ = ["export_env", "operator_ctx", "run_env"]


class _FakeStreamCursor:
    """Cursor giả stream theo lô: sinh rows theo yêu cầu, không giữ toàn bộ.

    fetchall chỉ dùng cho bước kiểm tra read-only (1 lần); dữ liệu chỉ
    đi qua fetchmany.
    """

    def __init__(self, total: int) -> None:
        self._total = total
        self._idx = 0
        self.fetchmany_calls: list[int] = []
        self.fetchall_calls = 0
        self.description = [
            ("AMOUNT", None, 0, 0, 18, 2, True),
            ("ORG", None, 0, 0, 60, 0, True),
            ("TXN_DATE", None, 0, 0, 0, 0, True),
        ]

    def execute(self, sql: str, binds: dict | None = None) -> None:
        return None

    def fetchone(self) -> tuple[int]:
        return (self._total,)

    def fetchall(self) -> list:
        self.fetchall_calls += 1
        return []

    def fetchmany(self, n: int) -> list[tuple]:
        self.fetchmany_calls.append(n)
        if self._idx >= self._total:
            return []
        take = min(n, self._total - self._idx)
        rows = [
            (1000 + i, "HN", "2026-02-01")
            for i in range(self._idx, self._idx + take)
        ]
        self._idx += take
        return rows


def _fake_conn(total: int):
    from unittest.mock import MagicMock

    conn = MagicMock()
    conn.cursor.return_value = _FakeStreamCursor(total)
    return conn


def _peak_rows(export_env, operator_ctx, total: int, fmt: str = "CSV") -> int:
    from app.services.report_export import execute_export

    run = _done_run(operator_ctx, export_env)
    exp = _request(operator_ctx, export_env, run["id"], fmt).data
    conn = _fake_conn(total)
    tracemalloc.start()
    try:
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            result = execute_export(exp["id"], engine=export_env["engine"])
        assert result["status"] == "DONE", result
        assert result["row_count"] == total
        _, peak = tracemalloc.get_traced_memory()
        return peak
    finally:
        tracemalloc.stop()


class TestStreaming:
    def test_fetchmany_no_linear_ram(self, export_env, operator_ctx):
        # 10x rows → peak < 3x (T26-02).
        peak_small = _peak_rows(export_env, operator_ctx, 10_000)
        peak_big = _peak_rows(export_env, operator_ctx, 100_000)
        assert peak_big < 3 * peak_small, (peak_small, peak_big)

    def test_fetchmany_batch_size_and_no_fetchall(self, export_env, operator_ctx):
        from app.services.report_export import FETCH_BATCH_SIZE, execute_export

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        conn = _fake_conn(12_000)
        cursor = conn.cursor.return_value
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            assert execute_export(exp["id"], engine=export_env["engine"])[
                "status"
            ] == "DONE"
        assert set(cursor.fetchmany_calls) == {FETCH_BATCH_SIZE}
        assert len(cursor.fetchmany_calls) == 4  # 5000+5000+2000+rỗng
        # fetchall chỉ 1 lần cho bước kiểm tra read-only, không dùng lấy dữ liệu.
        assert cursor.fetchall_calls == 1


class TestXlsxWriter:
    def test_xlsx_roundtrip(self, export_env, operator_ctx):
        from app.services.report_export import execute_export

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX").data
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            result = execute_export(exp["id"], engine=export_env["engine"])
        assert result["status"] == "DONE", result
        wb = load_workbook(result["file_path"], read_only=True)
        ws = wb["Data"]
        rows = list(ws.iter_rows(values_only=True))
        assert rows[0] == ("AMOUNT", "ORG", "TXN_DATE")
        assert rows[1][0] == 1000 and rows[1][1] == "HN"
        assert rows[1][2] == datetime(2026, 2, 1)
        assert rows[2][0] == 2000 and rows[2][1] == "HN"
        assert rows[3][0] == 3000 and rows[3][1] == "HN"

    def test_leading_zero_kept_as_text(self, export_env, operator_ctx):
        from app.services.report_export import execute_export

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX").data
        rows_lz = [
            (1000, "00123", "2026-02-01"),
            (2000, "00456", "2026-02-02"),
        ]
        conn, _ = _mock_stream_conn(rows_lz)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            result = execute_export(exp["id"], engine=export_env["engine"])
        assert result["status"] == "DONE", result
        wb = load_workbook(result["file_path"], read_only=True)
        ws = wb["Data"]
        rows = list(ws.iter_rows(values_only=True))
        # STRING giữ nguyên text "00123" (T26-04); NUMBER vẫn là số.
        assert rows[1][1] == "00123"
        assert isinstance(rows[1][1], str)
        assert rows[2][1] == "00456"
        assert rows[1][0] == 1000
        assert isinstance(rows[1][0], int)

    def test_csv_bom_and_vietnamese(self, export_env, operator_ctx):
        from app.services.report_export import execute_export

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        rows_vn = [
            (1000, "Hà Nội", "2026-02-01"),
            (2000, "00123", "2026-02-02"),
        ]
        conn, _ = _mock_stream_conn(rows_vn)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            result = execute_export(exp["id"], engine=export_env["engine"])
        assert result["status"] == "DONE", result
        raw = open(result["file_path"], "rb").read()
        assert raw.startswith(b"\xef\xbb\xbf")  # BOM UTF-8 (T26-05)
        text = raw.decode("utf-8-sig")  # BOM chỉ ở đầu file, không dính header
        parsed = list(csv.reader(text.splitlines()))
        assert parsed[0] == ["AMOUNT", "ORG", "TXN_DATE"]
        assert parsed[1] == ["1000", "Hà Nội", "2026-02-01"]
        assert parsed[2] == ["2000", "00123", "2026-02-02"]
