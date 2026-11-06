from __future__ import annotations

from sqlalchemy import Engine, text


class DatabaseDialect:
    """Lớp cơ sở trừu tượng hóa khác biệt giữa SQLite và Oracle."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.is_sqlite = engine.dialect.name == "sqlite"
        self.is_oracle = engine.dialect.name == "oracle"

    # Giới hạn song song theo Data Source cho run thuộc bộ (task 18, spec 10
    # §5.5): bỏ qua run có BATCH_RUN_ID mà số run đang PROCESSING cùng
    # DATA_SOURCE_ID và cùng batch run đã >= MAX_PARALLEL_PER_DS của bộ
    # (mặc định 2). Đếm theo hàng đợi PROCESSING (không đếm RECON_RUN
    # STATUS='RUNNING') để việc claim và đếm là nguyên tử trong cùng
    # transaction — tránh 2 worker cùng claim vượt giới hạn trong lúc run
    # chưa kịp chuyển sang RUNNING. Ưu tiên: PRIORITY của mục (nhỏ trước),
    # rồi SEQ_NO, rồi ENQUEUED_AT; run không thuộc bộ (PRIORITY NULL) xếp
    # sau run thuộc bộ.
    _BATCH_CLAIM_FILTER = """
        AND (
            r.BATCH_RUN_ID IS NULL
            OR NOT EXISTS (
                SELECT 1 FROM RECON_RUN_QUEUE q2
                JOIN RECON_RUN r2 ON r2.ID = q2.RUN_ID
                WHERE q2.STATUS = 'PROCESSING'
                AND r2.BATCH_RUN_ID = r.BATCH_RUN_ID
                AND r2.DATA_SOURCE_ID = r.DATA_SOURCE_ID
                GROUP BY r2.BATCH_RUN_ID, r2.DATA_SOURCE_ID
                HAVING COUNT(*) >= COALESCE(bd.MAX_PARALLEL_PER_DS, 2)
            )
        )
    """
    _BATCH_CLAIM_ORDER = """
        ORDER BY COALESCE(bri.PRIORITY, 999999) ASC,
            COALESCE(bri.SEQ_NO, 999999) ASC, q.ENQUEUED_AT ASC
    """

    def claim_next_queued_job(self, locked_by: str) -> int | None:
        """Lấy 1 job sẵn sàng (READY) từ RECON_RUN_QUEUE và chuyển sang PROCESSING an toàn với concurrency."""
        if self.is_sqlite:
            # SQLite: sử dụng UPDATE RETURNING trong transaction
            sql = text(
                f"""
                UPDATE RECON_RUN_QUEUE
                SET STATUS = 'PROCESSING',
                    LOCKED_BY = :locked_by,
                    LOCKED_AT = CURRENT_TIMESTAMP,
                    HEARTBEAT_AT = CURRENT_TIMESTAMP
                WHERE RUN_ID = (
                    SELECT q.RUN_ID FROM RECON_RUN_QUEUE q
                    JOIN RECON_RUN r ON r.ID = q.RUN_ID
                    LEFT JOIN RECON_BATCH_RUN_ITEM bri ON bri.ID = r.BATCH_RUN_ITEM_ID
                    LEFT JOIN RECON_BATCH_RUN br ON br.ID = r.BATCH_RUN_ID
                    LEFT JOIN RECON_BATCH_DEF bd ON bd.ID = br.BATCH_DEF_ID
                    WHERE q.STATUS = 'READY'
                    {self._BATCH_CLAIM_FILTER}
                    {self._BATCH_CLAIM_ORDER}
                    LIMIT 1
                )
                RETURNING RUN_ID
                """
            )
            with self.engine.begin() as conn:
                res = conn.execute(sql, {"locked_by": locked_by}).scalar()
                return int(res) if res is not None else None
        elif self.is_oracle:
            # Oracle: chọn ứng viên rồi khóa dòng hàng đợi bằng
            # FOR UPDATE SKIP LOCKED (không khóa trên câu JOIN).
            sql_select = text(
                f"""
                SELECT q.RUN_ID FROM RECON_RUN_QUEUE q
                JOIN RECON_RUN r ON r.ID = q.RUN_ID
                LEFT JOIN RECON_BATCH_RUN_ITEM bri ON bri.ID = r.BATCH_RUN_ITEM_ID
                LEFT JOIN RECON_BATCH_RUN br ON br.ID = r.BATCH_RUN_ID
                LEFT JOIN RECON_BATCH_DEF bd ON bd.ID = br.BATCH_DEF_ID
                WHERE q.STATUS = 'READY'
                {self._BATCH_CLAIM_FILTER}
                {self._BATCH_CLAIM_ORDER}
                FETCH FIRST 1 ROWS ONLY
                """
            )
            sql_lock = text(
                """
                SELECT RUN_ID FROM RECON_RUN_QUEUE
                WHERE RUN_ID = :run_id AND STATUS = 'READY'
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
                locked = conn.execute(sql_lock, {"run_id": run_id}).fetchone()
                if locked is None:
                    return None
                conn.execute(sql_update, {"run_id": run_id, "locked_by": locked_by})
                return run_id
        else:
            raise NotImplementedError(f"Dialect {self.engine.dialect.name} chưa được hỗ trợ.")

    def claim_next_queued_export(self, locked_by: str, max_per_user: int = 2) -> int | None:
        """Lấy 1 export QUEUED và chuyển sang RUNNING an toàn với concurrency.

        Bỏ qua user đã có >= max_per_user export RUNNING (task 26 Q4).
        """
        if self.is_sqlite:
            sql = text(
                """
                UPDATE RECON_RPT_EXPORT
                SET STATUS = 'RUNNING',
                    LOCKED_BY = :locked_by,
                    LOCKED_AT = CURRENT_TIMESTAMP,
                    HEARTBEAT_AT = CURRENT_TIMESTAMP
                WHERE ID = (
                    SELECT e.ID FROM RECON_RPT_EXPORT e
                    WHERE e.STATUS = 'QUEUED'
                    AND NOT EXISTS (
                        SELECT 1 FROM RECON_RPT_EXPORT r
                        WHERE r.CREATED_BY = e.CREATED_BY
                        AND r.STATUS = 'RUNNING'
                        GROUP BY r.CREATED_BY
                        HAVING COUNT(*) >= :max_per_user
                    )
                    ORDER BY e.CREATED_AT ASC, e.ID ASC
                    LIMIT 1
                )
                RETURNING ID
                """
            )
            with self.engine.begin() as conn:
                res = conn.execute(sql, {"locked_by": locked_by, "max_per_user": max_per_user}).scalar()
                return int(res) if res is not None else None
        elif self.is_oracle:
            sql_select = text(
                """
                SELECT e.ID FROM RECON_RPT_EXPORT e
                WHERE e.STATUS = 'QUEUED'
                AND NOT EXISTS (
                    SELECT 1 FROM RECON_RPT_EXPORT r
                    WHERE r.CREATED_BY = e.CREATED_BY
                    AND r.STATUS = 'RUNNING'
                    GROUP BY r.CREATED_BY
                    HAVING COUNT(*) >= :max_per_user
                )
                ORDER BY e.CREATED_AT ASC, e.ID ASC
                FETCH FIRST 1 ROWS ONLY
                FOR UPDATE SKIP LOCKED
                """
            )
            sql_update = text(
                """
                UPDATE RECON_RPT_EXPORT
                SET STATUS = 'RUNNING',
                    LOCKED_BY = :locked_by,
                    LOCKED_AT = CURRENT_TIMESTAMP,
                    HEARTBEAT_AT = CURRENT_TIMESTAMP
                WHERE ID = :export_id
                """
            )
            with self.engine.begin() as conn:
                row = conn.execute(sql_select, {"max_per_user": max_per_user}).fetchone()
                if row is None:
                    return None
                export_id = int(row[0])
                conn.execute(sql_update, {"export_id": export_id, "locked_by": locked_by})
                return export_id
        else:
            raise NotImplementedError(f"Dialect {self.engine.dialect.name} chưa được hỗ trợ.")


def get_dialect(engine: Engine) -> DatabaseDialect:
    return DatabaseDialect(engine)
