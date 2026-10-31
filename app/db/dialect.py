from __future__ import annotations

from sqlalchemy import Engine, text


class DatabaseDialect:
    """Lớp cơ sở trừu tượng hóa khác biệt giữa SQLite và Oracle."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.is_sqlite = engine.dialect.name == "sqlite"
        self.is_oracle = engine.dialect.name == "oracle"

    def claim_next_queued_job(self, locked_by: str) -> int | None:
        """Lấy 1 job sẵn sàng (READY) từ RECON_RUN_QUEUE và chuyển sang PROCESSING an toàn với concurrency."""
        if self.is_sqlite:
            # SQLite: sử dụng UPDATE RETURNING trong transaction
            sql = text(
                """
                UPDATE RECON_RUN_QUEUE
                SET STATUS = 'PROCESSING',
                    LOCKED_BY = :locked_by,
                    LOCKED_AT = CURRENT_TIMESTAMP,
                    HEARTBEAT_AT = CURRENT_TIMESTAMP
                WHERE RUN_ID = (
                    SELECT RUN_ID FROM RECON_RUN_QUEUE
                    WHERE STATUS = 'READY'
                    ORDER BY ENQUEUED_AT ASC
                    LIMIT 1
                )
                RETURNING RUN_ID
                """
            )
            with self.engine.begin() as conn:
                res = conn.execute(sql, {"locked_by": locked_by}).scalar()
                return int(res) if res is not None else None
        elif self.is_oracle:
            # Oracle: FOR UPDATE SKIP LOCKED
            sql_select = text(
                """
                SELECT RUN_ID FROM RECON_RUN_QUEUE
                WHERE STATUS = 'READY'
                ORDER BY ENQUEUED_AT ASC
                FETCH FIRST 1 ROWS ONLY
                FOR UPDATE SKIP LOCKED
                """
            )
            sql_update = text(
                """
                UPDATE RECON_RUN_QUEUE
                SET STATUS = 'PROCESSING',
                    LOCKED_BY = :locked_by,
                    LOCKED_AT = CURRENT_TIMESTAMP,
                    HEARTBEAT_AT = CURRENT_TIMESTAMP
                WHERE RUN_ID = :run_id
                """
            )
            with self.engine.begin() as conn:
                row = conn.execute(sql_select).fetchone()
                if row is None:
                    return None
                run_id = int(row[0])
                conn.execute(sql_update, {"run_id": run_id, "locked_by": locked_by})
                return run_id
        else:
            raise NotImplementedError(f"Dialect {self.engine.dialect.name} chưa được hỗ trợ.")


def get_dialect(engine: Engine) -> DatabaseDialect:
    return DatabaseDialect(engine)
