from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import polars as pl
import pytest

from app.engine.fetch import MockFetcher, fetch_df
from app.schemas.errors import ErrorCode, ServiceError


class FakeCursor:
    def __init__(self, description: list[tuple[str, ...]], rows: list[tuple[Any, ...]]) -> None:
        self.description = description
        self.rows = rows
        self._pos = 0
        self.arraysize = 1000

    def execute(self, sql: str, binds: dict[str, Any] | None = None) -> None:
        pass

    def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        chunk = self.rows[self._pos : self._pos + size]
        self._pos += size
        return chunk


def test_fetch_df_success() -> None:
    desc = [("ID", 2), ("AMOUNT", 2), ("NAME", 1)]
    rows = [(1, Decimal("100.50"), "A"), (2, Decimal("200.00"), "B")]
    fake_cursor = FakeCursor(desc, rows)
    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cursor

    df = fetch_df(fake_conn, "SELECT id, amount, name FROM test", binds={"p": 1})
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 2
    assert df.columns == ["ID", "AMOUNT", "NAME"]
    assert df["AMOUNT"].to_list() == [Decimal("100.50"), Decimal("200.00")]


def test_fetch_df_max_rows_exceeded() -> None:
    desc = [("ID", 2)]
    rows = [(i,) for i in range(50)]
    fake_cursor = FakeCursor(desc, rows)
    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cursor

    # Giới hạn max_rows = 20 < 50 dòng
    with pytest.raises(ServiceError) as exc_info:
        fetch_df(fake_conn, "SELECT id FROM test", max_rows=20)
    assert exc_info.value.code == ErrorCode.SOURCE_TOO_MANY_ROWS


def test_fetch_df_timeout() -> None:
    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_cursor.execute.side_effect = TimeoutError("Statement cancelled: call timeout")
    fake_conn.cursor.return_value = fake_cursor

    with pytest.raises(ServiceError) as exc_info:
        fetch_df(fake_conn, "SELECT * FROM long_running_query", timeout=5)
    assert exc_info.value.code == ErrorCode.SOURCE_TIMEOUT


def test_fetch_df_connection_lost() -> None:
    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    # Giả lập lỗi ORA-03113: end-of-file on communication channel
    fake_cursor.execute.side_effect = Exception("ORA-03113: end-of-file on communication channel")
    fake_conn.cursor.return_value = fake_cursor

    with pytest.raises(ServiceError) as exc_info:
        fetch_df(fake_conn, "SELECT * FROM test")
    assert exc_info.value.code == ErrorCode.SOURCE_CONNECTION_LOST


def test_mock_fetcher(tmp_path) -> None:
    df_expected = pl.DataFrame({"INVOICE_NO": ["HD01", "HD02"], "AMOUNT": [Decimal("100"), Decimal("200")]})
    parquet_path = tmp_path / "mock_db.parquet"
    df_expected.write_parquet(parquet_path)

    fetcher = MockFetcher(default_path=parquet_path)
    res_df = fetcher.fetch_df(None, "SELECT * FROM inv")
    assert len(res_df) == 2
    assert res_df["INVOICE_NO"].to_list() == ["HD01", "HD02"]
