from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from app.schemas.errors import ErrorCode, ServiceError


def fetch_df(
    conn: Any,
    sql: str,
    binds: dict[str, Any] | None = None,
    max_rows: int = 1_000_000,
    timeout: int = 600,
) -> pl.DataFrame:
    """Kéo dữ liệu từ kết nối CSDL Oracle sang Polars DataFrame theo lô với giới hạn dòng và timeout."""
    if hasattr(conn, "call_timeout"):
        conn.call_timeout = int(timeout * 1000)  # ms

    cursor = conn.cursor()
    if hasattr(cursor, "arraysize"):
        cursor.arraysize = 10000

    try:
        if binds:
            cursor.execute(sql, binds)
        else:
            cursor.execute(sql)
    except Exception as exc:
        err_str = str(exc).upper()
        if isinstance(exc, TimeoutError) or "ORA-01013" in err_str or "TIMEOUT" in err_str:
            raise ServiceError(
                ErrorCode.SOURCE_TIMEOUT,
                f"Truy vấn Oracle bị quá thời gian cho phép ({timeout} giây).",
            ) from exc

        if (
            any(ora in err_str for ora in ["ORA-03113", "ORA-03114", "ORA-03135", "DPI-1010", "DPI-1080"])
            or "CONNECTION LOST" in err_str
            or "NOT CONNECTED" in err_str
        ):
            raise ServiceError(
                ErrorCode.SOURCE_CONNECTION_LOST,
                "Mất kết nối tới cơ sở dữ liệu Oracle (VPN bị gián đoạn).",
            ) from exc

        raise ServiceError(
            ErrorCode.SOURCE_QUERY_FAILED,
            f"Lỗi thực thi truy vấn nguồn Oracle: {exc}",
        ) from exc

    if not cursor.description:
        return pl.DataFrame()

    col_names = [str(d[0]) for d in cursor.description]
    all_rows: list[tuple[Any, ...]] = []
    batch_size = 10000

    try:
        while True:
            chunk = cursor.fetchmany(batch_size)
            if not chunk:
                break
            all_rows.extend(chunk)
            if len(all_rows) > max_rows:
                raise ServiceError(
                    ErrorCode.SOURCE_TOO_MANY_ROWS,
                    f"Số dòng dữ liệu nguồn ({len(all_rows):,}) vượt quá giới hạn tối đa cho phép ({max_rows:,} dòng). Vui lòng thu hẹp khoảng thời gian hoặc bật tính năng pushdown aggregate.",
                )
    except Exception as exc:
        if isinstance(exc, ServiceError):
            raise
        err_str = str(exc).upper()
        if (
            any(ora in err_str for ora in ["ORA-03113", "ORA-03114", "ORA-03135", "DPI-1010", "DPI-1080"])
            or "CONNECTION LOST" in err_str
            or "NOT CONNECTED" in err_str
        ):
            raise ServiceError(
                ErrorCode.SOURCE_CONNECTION_LOST,
                "Mất kết nối tới cơ sở dữ liệu Oracle trong quá trình kéo dữ liệu.",
            ) from exc
        raise ServiceError(
            ErrorCode.SOURCE_QUERY_FAILED,
            f"Lỗi khi đọc dữ liệu từ Oracle: {exc}",
        ) from exc
    finally:
        try:
            cursor.close()
        except Exception:
            pass

    if not all_rows:
        return pl.DataFrame(schema=col_names)

    col_dict = {col: [r[idx] for r in all_rows] for idx, col in enumerate(col_names)}
    return pl.DataFrame(col_dict)


class MockFetcher:
    """Fetcher giả lập đọc dữ liệu từ Parquet hoặc DataFrame cho testing offline."""

    def __init__(
        self,
        default_path: Path | str | None = None,
        df: pl.DataFrame | None = None,
    ) -> None:
        self.default_path = Path(default_path) if default_path else None
        self.df = df

    def fetch_df(
        self,
        conn: Any = None,
        sql: str = "",
        binds: dict[str, Any] | None = None,
        max_rows: int = 1_000_000,
        timeout: int = 600,
    ) -> pl.DataFrame:
        if self.df is not None:
            return self.df
        if self.default_path and self.default_path.exists():
            return pl.read_parquet(self.default_path)
        return pl.DataFrame()
