"""Tests cho schema Reporting Core — Bước 1 task 21 (test viết trước).

Phạm vi: 11 bảng theo spec 12a tồn tại sau create_all; PK/FK/UQ/check
constraints bị vi phạm thì lỗi (T21-02); cột JSON round-trip.
Migration lên/xuống kiểm tra ở tests/integration/test_migrations.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.metadata import metadata

REPORT_TABLES = [
    "RECON_REPORT",
    "RECON_REPORT_TEMPLATE",
    "RECON_RPT_TPL_VER",
    "RECON_RPT_PARAM",
    "RECON_RPT_PARAM_LOV",
    "RECON_RPT_COLUMN",
    "RECON_REPORT_RUN",
    "RECON_RPT_EXPORT",
    "RECON_RPT_FAVORITE",
    "RECON_RPT_PRESET",
    "RECON_RPT_LOV_CACHE",
]


@pytest.fixture()
def schema_engine(tmp_path, monkeypatch):
    from app.db.engine import get_sqlite_engine

    db_file = tmp_path / "reporting_schema.db"
    engine = get_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    metadata.create_all(engine)
    yield engine
    engine.dispose()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _report_id(conn, code: str = "FIN_REVENUE") -> int:
    from app.db.metadata import recon_report

    now = _now()
    res = conn.execute(
        recon_report.insert().values(
            CODE=code,
            NAME="Doanh thu",
            CATEGORY_CODE="FIN",
            OWNER="admin",
            DESCRIPTION="Báo cáo doanh thu",
            DEFAULT_FAVORITE="N",
            IS_VISIBLE="Y",
            IS_ACTIVE="Y",
            CREATED_BY="admin",
            CREATED_AT=now,
            UPDATED_BY="admin",
            UPDATED_AT=now,
            ROW_VERSION=1,
        )
    )
    return int(res.inserted_primary_key[0])


def _template_id(conn, report_id: int, code: str = "MAIN") -> int:
    from app.db.metadata import recon_report_template

    now = _now()
    res = conn.execute(
        recon_report_template.insert().values(
            REPORT_ID=report_id,
            CODE=code,
            NAME="Mẫu chính",
            DISPLAY_ORDER=10,
            ACTIVE_VERSION_ID=None,
            CREATED_BY="admin",
            CREATED_AT=now,
            UPDATED_BY="admin",
            UPDATED_AT=now,
            ROW_VERSION=1,
        )
    )
    return int(res.inserted_primary_key[0])


def _version_id(conn, template_id: int, version_no: int = 1, status: str = "DRAFT") -> int:
    from app.db.metadata import recon_rpt_tpl_ver

    now = _now()
    res = conn.execute(
        recon_rpt_tpl_ver.insert().values(
            TEMPLATE_ID=template_id,
            VERSION_NO=version_no,
            STATUS=status,
            DATA_SOURCE_ID=None,
            SOURCE_TYPE=None,
            SQL_TEXT=None,
            SOURCE_OWNER=None,
            SOURCE_OBJECT=None,
            TIMEOUT_SEC=300,
            PREVIEW_MAX_ROWS=100,
            EXPORT_MAX_ROWS=1000000,
            SQL_HASH=None,
            ACTIVATED_BY=None,
            ACTIVATED_AT=None,
            CREATED_BY="admin",
            CREATED_AT=now,
            UPDATED_BY="admin",
            UPDATED_AT=now,
            ROW_VERSION=1,
        )
    )
    return int(res.inserted_primary_key[0])


class TestReportingTablesExist:
    def test_all_tables_created(self, schema_engine):
        names = set(inspect(schema_engine).get_table_names())
        for table in REPORT_TABLES:
            assert table in names


class TestReportingConstraints:
    def test_report_code_unique(self, schema_engine):

        with schema_engine.begin() as conn:
            _report_id(conn, "FIN_REVENUE")
            with pytest.raises(IntegrityError):
                _report_id(conn, "FIN_REVENUE")

    def test_template_unique_per_report(self, schema_engine):
        with schema_engine.begin() as conn:
            rid = _report_id(conn)
            _template_id(conn, rid, "MAIN")
            with pytest.raises(IntegrityError):
                _template_id(conn, rid, "MAIN")

    def test_version_unique_per_template(self, schema_engine):
        with schema_engine.begin() as conn:
            tid = _template_id(conn, _report_id(conn))
            _version_id(conn, tid, 1)
            with pytest.raises(IntegrityError):
                _version_id(conn, tid, 1)

    def test_version_status_check(self, schema_engine):
        with schema_engine.begin() as conn:
            tid = _template_id(conn, _report_id(conn))
            with pytest.raises(IntegrityError):
                _version_id(conn, tid, 1, status="BOGUS")

    def test_source_type_check(self, schema_engine):
        from app.db.metadata import recon_rpt_tpl_ver

        with schema_engine.begin() as conn:
            vid = _version_id(conn, _template_id(conn, _report_id(conn)))
            with pytest.raises(IntegrityError):
                conn.execute(
                    recon_rpt_tpl_ver.update()
                    .where(recon_rpt_tpl_ver.c.ID == vid)
                    .values(SOURCE_TYPE="PROCEDURE")
                )

    def test_param_unique_per_version(self, schema_engine):
        from app.db.metadata import recon_rpt_param

        def _param(conn, vid, code):
            return conn.execute(
                recon_rpt_param.insert().values(
                    VERSION_ID=vid,
                    CODE=code,
                    LABEL=code,
                    DATA_TYPE="STRING",
                    CONTROL_TYPE="TEXT",
                    REQUIRED="N",
                    DEFAULT_TYPE=None,
                    DEFAULT_VALUE=None,
                    DISPLAY_ROW=1,
                    DISPLAY_ORDER=10,
                    GRID_SPAN=6,
                    FILTER_COLUMN=None,
                    FILTER_OPERATOR=None,
                    IS_VISIBLE="Y",
                )
            )

        with schema_engine.begin() as conn:
            vid = _version_id(conn, _template_id(conn, _report_id(conn)))
            _param(conn, vid, "P_FROM")
            with pytest.raises(IntegrityError):
                _param(conn, vid, "P_FROM")

    def test_grid_span_check(self, schema_engine):
        from app.db.metadata import recon_rpt_param

        with schema_engine.begin() as conn:
            vid = _version_id(conn, _template_id(conn, _report_id(conn)))
            base = dict(
                VERSION_ID=vid,
                CODE="P_X",
                LABEL="X",
                DATA_TYPE="STRING",
                CONTROL_TYPE="TEXT",
                REQUIRED="N",
                DISPLAY_ROW=1,
                DISPLAY_ORDER=10,
                IS_VISIBLE="Y",
            )
            with pytest.raises(IntegrityError):
                conn.execute(recon_rpt_param.insert().values(**base, GRID_SPAN=0))
            with pytest.raises(IntegrityError):
                conn.execute(recon_rpt_param.insert().values(**base, GRID_SPAN=13))
            conn.execute(recon_rpt_param.insert().values(**base, GRID_SPAN=12))

    def test_display_row_check(self, schema_engine):
        from app.db.metadata import recon_rpt_param

        with schema_engine.begin() as conn:
            vid = _version_id(conn, _template_id(conn, _report_id(conn)))
            with pytest.raises(IntegrityError):
                conn.execute(
                    recon_rpt_param.insert().values(
                        VERSION_ID=vid,
                        CODE="P_X",
                        LABEL="X",
                        DATA_TYPE="STRING",
                        CONTROL_TYPE="TEXT",
                        REQUIRED="N",
                        DISPLAY_ROW=0,
                        DISPLAY_ORDER=10,
                        GRID_SPAN=6,
                        IS_VISIBLE="Y",
                    )
                )

    def test_filter_operator_check(self, schema_engine):
        from app.db.metadata import recon_rpt_param

        with schema_engine.begin() as conn:
            vid = _version_id(conn, _template_id(conn, _report_id(conn)))
            with pytest.raises(IntegrityError):
                conn.execute(
                    recon_rpt_param.insert().values(
                        VERSION_ID=vid,
                        CODE="P_X",
                        LABEL="X",
                        DATA_TYPE="STRING",
                        CONTROL_TYPE="TEXT",
                        REQUIRED="N",
                        DISPLAY_ROW=1,
                        DISPLAY_ORDER=10,
                        GRID_SPAN=6,
                        FILTER_COLUMN="AMOUNT",
                        FILTER_OPERATOR="~=",
                        IS_VISIBLE="Y",
                    )
                )

    def test_lov_type_check(self, schema_engine):
        from app.db.metadata import recon_rpt_param, recon_rpt_param_lov

        with schema_engine.begin() as conn:
            vid = _version_id(conn, _template_id(conn, _report_id(conn)))
            res = conn.execute(
                recon_rpt_param.insert().values(
                    VERSION_ID=vid,
                    CODE="P_X",
                    LABEL="X",
                    DATA_TYPE="STRING",
                    CONTROL_TYPE="SELECT",
                    REQUIRED="N",
                    DISPLAY_ROW=1,
                    DISPLAY_ORDER=10,
                    GRID_SPAN=6,
                    IS_VISIBLE="Y",
                )
            )
            pid = int(res.inserted_primary_key[0])
            with pytest.raises(IntegrityError):
                conn.execute(
                    recon_rpt_param_lov.insert().values(
                        PARAM_ID=pid,
                        LOV_TYPE="MAGIC",
                        DATA_SOURCE_ID=None,
                        SQL_TEXT=None,
                        LOOKUP_TYPE=None,
                        STATIC_JSON=None,
                        CACHE_SECONDS=300,
                        MAX_ROWS=5000,
                    )
                )

    def test_column_unique_per_version(self, schema_engine):
        from app.db.metadata import recon_rpt_column

        def _column(conn, vid, field):
            return conn.execute(
                recon_rpt_column.insert().values(
                    VERSION_ID=vid,
                    FIELD_NAME=field,
                    LABEL=field,
                    DATA_TYPE="STRING",
                    DISPLAY_ORDER=10,
                    WEB_VISIBLE="Y",
                    EXCEL_VISIBLE="Y",
                    FORMAT_MASK=None,
                    ALIGNMENT="LEFT",
                    WIDTH=None,
                    IS_TOTAL="N",
                )
            )

        with schema_engine.begin() as conn:
            vid = _version_id(conn, _template_id(conn, _report_id(conn)))
            _column(conn, vid, "AMOUNT")
            with pytest.raises(IntegrityError):
                _column(conn, vid, "AMOUNT")

    def test_run_status_check(self, schema_engine):
        from app.db.metadata import recon_report_run

        with schema_engine.begin() as conn:
            rid = _report_id(conn)
            tid = _template_id(conn, rid)
            vid = _version_id(conn, tid)
            now = _now()
            with pytest.raises(IntegrityError):
                conn.execute(
                    recon_report_run.insert().values(
                        REPORT_ID=rid,
                        TEMPLATE_ID=tid,
                        VERSION_ID=vid,
                        PARAMS_JSON={},
                        STATUS="BOGUS",
                        ROW_COUNT=None,
                        QUERY_MS=None,
                        ERROR_CODE=None,
                        ERROR_MESSAGE=None,
                        CREATED_BY="admin",
                        CREATED_AT=now,
                        FINISHED_AT=None,
                    )
                )

    def test_export_format_check(self, schema_engine):
        from app.db.metadata import recon_report_run, recon_rpt_export

        with schema_engine.begin() as conn:
            rid = _report_id(conn)
            tid = _template_id(conn, rid)
            vid = _version_id(conn, tid)
            now = _now()
            res = conn.execute(
                recon_report_run.insert().values(
                    REPORT_ID=rid,
                    TEMPLATE_ID=tid,
                    VERSION_ID=vid,
                    PARAMS_JSON={},
                    STATUS="DONE",
                    ROW_COUNT=10,
                    QUERY_MS=5,
                    ERROR_CODE=None,
                    ERROR_MESSAGE=None,
                    CREATED_BY="admin",
                    CREATED_AT=now,
                    FINISHED_AT=now,
                )
            )
            run_id = int(res.inserted_primary_key[0])
            with pytest.raises(IntegrityError):
                conn.execute(
                    recon_rpt_export.insert().values(
                        RUN_ID=run_id,
                        FORMAT="PDF",
                        STATUS="DONE",
                        FILE_PATH=None,
                        FILE_SIZE=None,
                        FILE_HASH=None,
                        PART_COUNT=1,
                        ROW_COUNT=10,
                        CREATED_BY="admin",
                        CREATED_AT=now,
                        FINISHED_AT=now,
                        ERROR_MESSAGE=None,
                    )
                )

    def test_favorite_pk(self, schema_engine):
        from app.db.metadata import recon_rpt_favorite, recon_user

        with schema_engine.begin() as conn:
            rid = _report_id(conn)
            now = _now()
            conn.execute(
                recon_user.insert().values(
                    ID=1,
                    USERNAME="admin",
                    FULL_NAME="admin",
                    PASSWORD_HASH="hash",
                    IS_ACTIVE="Y",
                    MUST_CHANGE_PW="N",
                    SESSION_VERSION=1,
                    CREATED_BY="SEED",
                    CREATED_AT=now,
                    UPDATED_AT=now,
                    ROW_VERSION=1,
                )
            )
            conn.execute(
                recon_rpt_favorite.insert().values(USER_ID=1, REPORT_ID=rid, CREATED_AT=now)
            )
            with pytest.raises(IntegrityError):
                conn.execute(
                    recon_rpt_favorite.insert().values(USER_ID=1, REPORT_ID=rid, CREATED_AT=now)
                )

    def test_fk_enforced(self, schema_engine):
        from app.db.metadata import recon_rpt_param

        with schema_engine.begin() as conn:
            with pytest.raises(IntegrityError):
                conn.execute(
                    recon_rpt_param.insert().values(
                        VERSION_ID=999999,
                        CODE="P_X",
                        LABEL="X",
                        DATA_TYPE="STRING",
                        CONTROL_TYPE="TEXT",
                        REQUIRED="N",
                        DISPLAY_ROW=1,
                        DISPLAY_ORDER=10,
                        GRID_SPAN=6,
                        IS_VISIBLE="Y",
                    )
                )


class TestReportingJsonColumns:
    def test_params_json_roundtrip(self, schema_engine):
        from app.db.metadata import recon_report_run

        with schema_engine.begin() as conn:
            rid = _report_id(conn)
            tid = _template_id(conn, rid)
            vid = _version_id(conn, tid)
            now = _now()
            params = {"P_FROM": "2026-01-01", "P_ORG": "HN", "LIMIT": 50}
            res = conn.execute(
                recon_report_run.insert().values(
                    REPORT_ID=rid,
                    TEMPLATE_ID=tid,
                    VERSION_ID=vid,
                    PARAMS_JSON=params,
                    STATUS="DONE",
                    ROW_COUNT=3,
                    QUERY_MS=5,
                    ERROR_CODE=None,
                    ERROR_MESSAGE=None,
                    CREATED_BY="admin",
                    CREATED_AT=now,
                    FINISHED_AT=now,
                )
            )
            run_id = int(res.inserted_primary_key[0])
            from sqlalchemy import select

            stored = conn.execute(
                select(recon_report_run.c.PARAMS_JSON).where(recon_report_run.c.ID == run_id)
            ).scalar_one()
            assert stored == params

    def test_lov_static_json_roundtrip(self, schema_engine):
        from app.db.metadata import recon_rpt_param, recon_rpt_param_lov

        with schema_engine.begin() as conn:
            vid = _version_id(conn, _template_id(conn, _report_id(conn)))
            res = conn.execute(
                recon_rpt_param.insert().values(
                    VERSION_ID=vid,
                    CODE="P_ORG",
                    LABEL="Đơn vị",
                    DATA_TYPE="STRING",
                    CONTROL_TYPE="SELECT",
                    REQUIRED="N",
                    DISPLAY_ROW=1,
                    DISPLAY_ORDER=10,
                    GRID_SPAN=6,
                    IS_VISIBLE="Y",
                )
            )
            pid = int(res.inserted_primary_key[0])
            static = [{"value": "HN", "label": "Hà Nội"}, {"value": "HCM", "label": "TP.HCM"}]
            conn.execute(
                recon_rpt_param_lov.insert().values(
                    PARAM_ID=pid,
                    LOV_TYPE="STATIC",
                    DATA_SOURCE_ID=None,
                    SQL_TEXT=None,
                    LOOKUP_TYPE=None,
                    STATIC_JSON=static,
                    CACHE_SECONDS=300,
                    MAX_ROWS=5000,
                )
            )
            from sqlalchemy import select

            stored = conn.execute(
                select(recon_rpt_param_lov.c.STATIC_JSON).where(
                    recon_rpt_param_lov.c.PARAM_ID == pid
                )
            ).scalar_one()
            assert stored == static
