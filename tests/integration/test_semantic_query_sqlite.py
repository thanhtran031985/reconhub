"""Test Bước 4 — Execution Service trên SQLite thật (Task 108).

Star Schema SQLite: FACT_SALES + DIM_CUSTOMER + DIM_DATE + DIM_SERVICE,
model publish ACTIVE qua service task 106 rồi chạy preview qua
``app.services.semantic_query``. Ngày bán sinh tương đối theo "hôm nay"
(giờ Việt Nam) để test RELATIVE_DATE luôn xác định.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx, Role
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_data_source, recon_user
from app.engine.catalog import invalidate_catalog_cache
from app.schemas.errors import ErrorCode

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def _today() -> date:
    return datetime.now(VN).date()


def _d(days: int) -> date:
    return _today() + timedelta(days=days)


def _last_month_day() -> date:
    first_this = date(_today().year, _today().month, 1)
    return first_this - timedelta(days=1)


def _jan10() -> date:
    return date(_today().year, 1, 10)


def _dt(d: date, hour: int = 10) -> str:
    return datetime.combine(d, time(hour, 0)).strftime("%Y-%m-%d %H:%M:%S")


# (SALE_ID, CUSTOMER_ID, SERVICE_ID, SALE_DAY, SALE_DATE, REVENUE, COST, QTY, OWNER, ORG)
SALES = [
    (1, 1, 1, _d(0), _dt(_d(0), 10), 500000, 300000, 5, "owner", "VTOS"),
    (2, 1, 2, _d(0), _dt(_d(0), 11), 200000, 200000, 2, "owner", "VTOS"),
    (3, 3, 1, _d(0), _dt(_d(0), 12), 100000, 0, 1, "viewer", "HCM"),
    (4, 2, 1, _d(-1), _dt(_d(-1), 10), 300000, 100000, 3, "owner", "VTOS"),
    (5, 2, 1, _d(-5), _dt(_d(-5), 10), 100000, 50000, 1, "owner", "VTOS"),
    (6, 1, 1, _last_month_day(), _dt(_last_month_day(), 10), 700000, 100000, 7, "owner", "VTOS"),
    (7, 2, 2, _jan10(), _dt(_jan10(), 10), 400000, 400000, 4, "viewer", "HCM"),
]

CUSTOMERS = [
    (1, "Cong ty A", "VIP", "VTOS", "OPERATOR"),
    (2, "Cong ty B", "STD", "VTOS", "VIEWER"),
    (3, "Cong ty C", "VIP", "HCM", "OPERATOR"),
]


@pytest.fixture
def sq_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    invalidate_catalog_cache()
    from app.services.semantic_query import invalidate_semantic_query_cache

    invalidate_semantic_query_cache()  # version_id trùng nhau giữa các DB tạm
    db_file = tmp_path / "sq_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    src_db = tmp_path / "star_src.db"

    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-123456789")
    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    src_engine = create_engine(f"sqlite:///{src_db.as_posix()}")
    sale_days = sorted({s[3] for s in SALES})
    with src_engine.begin() as sconn:
        sconn.execute(
            text(
                """
                CREATE TABLE DIM_CUSTOMER (
                    CUSTOMER_ID INTEGER PRIMARY KEY,
                    CUSTOMER_NAME TEXT NOT NULL,
                    SEGMENT TEXT NOT NULL,
                    ORG_CODE TEXT NOT NULL,
                    ROLE_COL TEXT NOT NULL
                )
                """
            )
        )
        sconn.execute(text("CREATE TABLE DIM_DATE (CAL_DATE DATE PRIMARY KEY, MONTH_LABEL TEXT NOT NULL)"))
        sconn.execute(text("CREATE TABLE DIM_SERVICE (SERVICE_ID INTEGER PRIMARY KEY, SERVICE_NAME TEXT NOT NULL)"))
        sconn.execute(
            text(
                """
                CREATE TABLE FACT_SALES (
                    SALE_ID INTEGER PRIMARY KEY,
                    CUSTOMER_ID INTEGER NOT NULL,
                    SERVICE_ID INTEGER NOT NULL,
                    SALE_DAY DATE NOT NULL,
                    SALE_DATE DATETIME NOT NULL,
                    REVENUE NUMERIC NOT NULL,
                    COST NUMERIC NOT NULL,
                    QUANTITY INTEGER NOT NULL,
                    OWNER_COL TEXT NOT NULL,
                    ORG_CODE TEXT NOT NULL
                )
                """
            )
        )
        for cid, name, seg, org, role in CUSTOMERS:
            sconn.execute(
                text("INSERT INTO DIM_CUSTOMER VALUES (:a, :b, :c, :d, :e)"),
                {"a": cid, "b": name, "c": seg, "d": org, "e": role},
            )
        for day in sale_days:
            sconn.execute(
                text("INSERT INTO DIM_DATE VALUES (:a, :b)"),
                {"a": day.isoformat(), "b": day.strftime("%Y-%m")},
            )
        sconn.execute(text("INSERT INTO DIM_SERVICE VALUES (1, 'Dich vu 1'), (2, 'Dich vu 2')"))
        for row in SALES:
            sconn.execute(
                text("INSERT INTO FACT_SALES VALUES (:a, :b, :c, :d, :e, :f, :g, :h, :i, :j)"),
                {
                    "a": row[0],
                    "b": row[1],
                    "c": row[2],
                    "d": row[3].isoformat(),
                    "e": row[4],
                    "f": row[5],
                    "g": row[6],
                    "h": row[7],
                    "i": row[8],
                    "j": row[9],
                },
            )

    import app.services.semantic_model  # noqa: F401

    for mod_path in (
        "app.db.engine",
        "app.services.perm",
        "app.services.menu_sync",
        "app.engine.catalog",
        "app.services.semantic_model",
        "app.services.semantic_model_validate",
        "app.services.semantic_query",
        "app.services.report_source",
    ):
        monkeypatch.setattr(f"{mod_path}.get_recon_engine", lambda: engine)

    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(VN).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, uname in [(1, "admin"), (2, "owner"), (3, "viewer"), (4, "operator")]:
            conn.execute(
                recon_user.insert().values(
                    ID=uid,
                    USERNAME=uname,
                    FULL_NAME=uname.title(),
                    PASSWORD_HASH="hash",
                    IS_ACTIVE="Y",
                    MUST_CHANGE_PW="N",
                    FAILED_COUNT=0,
                    SESSION_VERSION=1,
                    CREATED_BY="system",
                    CREATED_AT=now,
                    UPDATED_AT=now,
                    ROW_VERSION=1,
                )
            )
        res_ds = conn.execute(
            recon_data_source.insert().values(
                NAME="STAR_SQLITE",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="SQLITE",
                FILE_PATH=str(src_db),
                USERNAME="ro_user",
                PASSWORD_ENC=encrypt_secret("top_secret_pw"),
                CALL_TIMEOUT_S=30,
                MAX_ROWS=1000000,
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ds_id = int(res_ds.inserted_primary_key[0])

    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["TEMPLATE_OWNER"], 3: ["VIEWER"], 4: ["OPERATOR"]})
    clear_perm_cache()

    ctxs = {
        "admin": Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN]),
        "owner": Ctx(user_id=2, username="owner", full_name="Owner", roles=[Role.TEMPLATE_OWNER]),
        "viewer": Ctx(user_id=3, username="viewer", full_name="Viewer", roles=[Role.VIEWER]),
        "operator": Ctx(user_id=4, username="operator", full_name="Operator", roles=[Role.OPERATOR]),
    }

    active_version_id = _build_model(ctxs["owner"], ds_id, "M_SALES_Q")
    draft_version_id = _build_draft_only(ctxs["owner"], ds_id, "M_DRAFT_Q")
    yield {
        "engine": engine,
        "ds_id": ds_id,
        "ctxs": ctxs,
        "active_version_id": active_version_id,
        "draft_version_id": draft_version_id,
        "src_db": src_db,
    }
    src_engine.dispose()
    engine.dispose()


def _build_model(owner_ctx: Ctx, ds_id: int, code: str, rls: list[dict] | None = None) -> int:
    """Dựng model đầy đủ qua service task 106 rồi publish ACTIVE. Trả version_id."""
    from app.services.semantic_model import (
        add_table_to_draft,
        create_model,
        update_table_props,
        upsert_measure,
        upsert_rls_policy,
    )
    from app.services.semantic_model_validate import publish_model_version, upsert_relationship

    created = create_model(owner_ctx, {"code": code, "name": "Sales Q", "data_source_id": ds_id})
    assert created.ok, created.message
    ver_id = created.data["draft_version"]["id"]
    tables = {}
    for obj in ("FACT_SALES", "DIM_CUSTOMER", "DIM_DATE", "DIM_SERVICE"):
        res = add_table_to_draft(owner_ctx, ver_id, {"source_object": obj})
        assert res.ok, res.message
        tables[obj] = res.data
    fact = tables["FACT_SALES"]
    fact_cols = {f["source_column"]: f for f in fact["fields"]}
    assert update_table_props(
        owner_ctx,
        fact["id"],
        {"table_role": "FACT", "grain_desc": "Theo dòng bán", "grain_keys": ["SALE_ID"]},
    ).ok
    for obj in ("DIM_CUSTOMER", "DIM_DATE", "DIM_SERVICE"):
        assert update_table_props(owner_ctx, tables[obj]["id"], {"table_role": "DIMENSION"}).ok

    rels = [
        ("SALES_CUSTOMER", fact["id"], "CUSTOMER_ID", tables["DIM_CUSTOMER"]["id"], "CUSTOMER_ID"),
        ("SALES_DATE", fact["id"], "SALE_DAY", tables["DIM_DATE"]["id"], "CAL_DATE"),
        ("SALES_SERVICE", fact["id"], "SERVICE_ID", tables["DIM_SERVICE"]["id"], "SERVICE_ID"),
    ]
    for name, from_tid, from_col, to_tid, to_col in rels:
        res = upsert_relationship(
            owner_ctx,
            ver_id,
            {
                "name": name,
                "from_table_id": from_tid,
                "from_column": from_col,
                "to_table_id": to_tid,
                "to_column": to_col,
                "cardinality": "MANY_TO_ONE",
                "join_type": "LEFT_OUTER",
            },
        )
        assert res.ok, res.message

    m_rev = upsert_measure(
        owner_ctx,
        ver_id,
        {
            "code": "REV_SUM",
            "name": "Tong doanh thu",
            "table_id": fact["id"],
            "measure_type": "SIMPLE",
            "base_field_id": fact_cols["REVENUE"]["id"],
            "aggregation": "SUM",
        },
    )
    assert m_rev.ok, m_rev.message
    m_qty = upsert_measure(
        owner_ctx,
        ver_id,
        {
            "code": "QTY_SUM",
            "name": "Tong so luong",
            "table_id": fact["id"],
            "measure_type": "SIMPLE",
            "base_field_id": fact_cols["QUANTITY"]["id"],
            "aggregation": "SUM",
        },
    )
    assert m_qty.ok, m_qty.message
    m_margin = upsert_measure(
        owner_ctx,
        ver_id,
        {
            "code": "MARGIN_RATE",
            "name": "Ty suat loi nhuan",
            "table_id": fact["id"],
            "measure_type": "CALCULATED",
            "expr_json": {
                "op": "DIVIDE",
                "left": {"op": "SUM", "arg": {"op": "FIELD", "field_id": fact_cols["REVENUE"]["id"]}},
                "right": {"op": "SUM", "arg": {"op": "FIELD", "field_id": fact_cols["COST"]["id"]}},
            },
        },
    )
    assert m_margin.ok, m_margin.message
    m_x100 = upsert_measure(
        owner_ctx,
        ver_id,
        {
            "code": "REV_X100",
            "name": "Doanh thu x100",
            "table_id": fact["id"],
            "measure_type": "CALCULATED",
            "expr_json": {
                "op": "MUL",
                "left": {"op": "MEASURE", "measure_id": m_rev.data["id"]},
                "right": {"op": "CONST", "value": 100},
            },
        },
    )
    assert m_x100.ok, m_x100.message

    if rls:
        for pol in rls:
            policy = dict(pol)
            policy["table_id"] = tables[policy.pop("table_alias")]["id"]
            res = upsert_rls_policy(owner_ctx, ver_id, policy)
            assert res.ok, res.message

    pub = publish_model_version(owner_ctx, ver_id, {"change_note": "Phat hanh v1"})
    assert pub.ok, pub.message
    return ver_id


def _build_draft_only(owner_ctx: Ctx, ds_id: int, code: str) -> int:
    from app.services.semantic_model import create_model

    created = create_model(owner_ctx, {"code": code, "name": "Draft Q", "data_source_id": ds_id})
    assert created.ok, created.message
    return created.data["draft_version"]["id"]


def _intent(version_id: int, **overrides):
    payload = {"model_version_id": version_id}
    payload.update(overrides)
    return payload


def _field_ids(sq_env, version_id=None):
    """Map field_code -> field_id của version (mặc định ACTIVE)."""
    from app.db.engine import get_recon_engine
    from app.services.semantic_model import load_version_bundle

    engine = get_recon_engine()
    with engine.connect() as conn:
        bundle = load_version_bundle(conn, version_id or sq_env["active_version_id"])
    out = {}
    for t in bundle["tables"]:
        for f in t["fields"]:
            out[f["source_column"]] = f["id"]
    return out


def _measure_ids(sq_env, version_id=None):
    from app.db.engine import get_recon_engine
    from app.services.semantic_model import load_version_bundle

    engine = get_recon_engine()
    with engine.connect() as conn:
        bundle = load_version_bundle(conn, version_id or sq_env["active_version_id"])
    return {m["code"]: m["id"] for m in bundle["measures"]}


def _preview(sq_env, ctx_key, payload, **kwargs):
    from app.services.semantic_query import execute_semantic_preview

    return execute_semantic_preview(sq_env["ctxs"][ctx_key], payload, **kwargs)


# ---------------------------------------------------------------------------
# Preview cơ bản: GROUP BY khách hàng / tháng, AST chia 0
# ---------------------------------------------------------------------------
def test_preview_group_by_customer_sums(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    res = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_SUM"]}, {"measure_id": mids["QTY_SUM"]}],
            sorts=[{"target_type": "FIELD", "id": fids["CUSTOMER_NAME"]}],
        ),
    )
    assert res.ok, res.message
    data = res.data
    assert data["row_count"] == 3
    assert data["truncated"] is False
    assert data["request_seq"] is None
    assert data["warning_message"] is None
    by_name = {r["CUSTOMER_NAME"]: r for r in data["rows"]}
    # Tổng kỳ vọng tính từ fixture SALES.
    assert by_name["Cong ty A"]["REV_SUM"] == 500000 + 200000 + 700000
    assert by_name["Cong ty A"]["QTY_SUM"] == 5 + 2 + 7
    assert by_name["Cong ty B"]["REV_SUM"] == 300000 + 100000 + 400000
    assert by_name["Cong ty B"]["QTY_SUM"] == 3 + 1 + 4
    assert by_name["Cong ty C"]["REV_SUM"] == 100000
    assert by_name["Cong ty C"]["QTY_SUM"] == 1
    assert [c["name"] for c in data["columns"]] == ["CUSTOMER_NAME", "REV_SUM", "QTY_SUM"]


def test_preview_group_by_month(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    res = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CAL_DATE"], "date_part": "MONTH", "alias": "CAL_MONTH"}],
            measures=[{"measure_id": mids["REV_SUM"]}],
            sorts=[{"target_type": "FIELD", "id": fids["CAL_DATE"]}],
        ),
    )
    assert res.ok, res.message
    data = res.data
    expected: dict[str, int] = {}
    for row in SALES:
        expected[row[3].strftime("%Y-%m")] = expected.get(row[3].strftime("%Y-%m"), 0) + row[5]
    got = {r["CAL_MONTH"]: r["REV_SUM"] for r in data["rows"]}
    assert got == expected


def test_preview_ast_divide_by_zero_returns_null(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    res = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["MARGIN_RATE"]}],
        ),
    )
    assert res.ok, res.message
    by_name = {r["CUSTOMER_NAME"]: r["MARGIN_RATE"] for r in res.data["rows"]}
    assert by_name["Cong ty A"] == pytest.approx(1400000 / 600000)
    assert by_name["Cong ty B"] == pytest.approx(800000 / 550000)
    assert by_name["Cong ty C"] is None  # SUM(COST) = 0 -> NULLIF -> NULL


def test_preview_measure_ref_expands(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    res = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_X100"]}],
        ),
    )
    assert res.ok, res.message
    by_name = {r["CUSTOMER_NAME"]: r["REV_X100"] for r in res.data["rows"]}
    assert by_name["Cong ty A"] == 1400000 * 100
    assert by_name["Cong ty C"] == 100000 * 100


def test_preview_filter_segment_and_revenue(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    res = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_SUM"]}],
            filters=[{"field_id": fids["SEGMENT"], "operator": "=", "value": "VIP"}],
        ),
    )
    assert res.ok, res.message
    assert {r["CUSTOMER_NAME"] for r in res.data["rows"]} == {"Cong ty A", "Cong ty C"}

    res2 = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_SUM"]}],
            filters=[{"field_id": fids["REVENUE"], "operator": ">=", "value": 400000}],
        ),
    )
    assert res2.ok, res2.message
    by_name = {r["CUSTOMER_NAME"]: r["REV_SUM"] for r in res2.data["rows"]}
    assert by_name == {"Cong ty A": 500000 + 700000, "Cong ty B": 400000}


def test_preview_like_prefix(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    res = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_SUM"]}],
            filters=[{"field_id": fids["CUSTOMER_NAME"], "operator": "LIKE_PREFIX", "value": "Cong ty A"}],
        ),
    )
    assert res.ok, res.message
    assert [r["CUSTOMER_NAME"] for r in res.data["rows"]] == ["Cong ty A"]


def test_preview_relative_date_today_and_last_7_days(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    today_rows = [s for s in SALES if s[3] == _today()]
    last7_rows = [s for s in SALES if _today() - timedelta(days=6) <= s[3] <= _today()]
    for value, expected_rows in (("TODAY", today_rows), ("LAST_7_DAYS", last7_rows)):
        res = _preview(
            sq_env,
            "admin",
            _intent(
                sq_env["active_version_id"],
                dimensions=[],
                measures=[{"measure_id": mids["REV_SUM"]}],
                filters=[{"field_id": fids["SALE_DATE"], "operator": "RELATIVE_DATE", "value": value}],
            ),
        )
        assert res.ok, res.message
        assert res.data["row_count"] == 1
        assert res.data["rows"][0]["REV_SUM"] == sum(s[5] for s in expected_rows)


def test_preview_relative_date_this_month_and_last_month(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    this_month_rows = [s for s in SALES if s[3].year == _today().year and s[3].month == _today().month]
    last_month_rows = [s for s in SALES if s[3] == _last_month_day()]
    res = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[],
            measures=[{"measure_id": mids["REV_SUM"]}],
            filters=[{"field_id": fids["SALE_DATE"], "operator": "RELATIVE_DATE", "value": "THIS_MONTH"}],
        ),
    )
    assert res.ok, res.message
    assert res.data["rows"][0]["REV_SUM"] == sum(s[5] for s in this_month_rows)
    res2 = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[],
            measures=[{"measure_id": mids["REV_SUM"]}],
            filters=[{"field_id": fids["SALE_DATE"], "operator": "RELATIVE_DATE", "value": "LAST_MONTH"}],
        ),
    )
    assert res2.ok, res2.message
    assert res2.data["rows"][0]["REV_SUM"] == sum(s[5] for s in last_month_rows)
    assert res2.data["rows"][0]["REV_SUM"] == 700000


# ---------------------------------------------------------------------------
# Truncated, request_seq, lỗi đầu vào
# ---------------------------------------------------------------------------
def test_preview_truncated_table_and_chart(sq_env, monkeypatch):
    from app.core.config import Settings

    monkeypatch.setattr(
        "app.services.semantic_query.get_settings",
        lambda: Settings(PREVIEW_MAX_ROWS=2, CHART_MAX_POINTS=2, PREVIEW_TIMEOUT_SECONDS=25),
    )
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    res = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_SUM"]}],
        ),
    )
    assert res.ok, res.message
    assert res.data["row_count"] == 2
    assert res.data["truncated"] is True
    res_chart = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_SUM"]}],
            visual_type="BAR",
        ),
    )
    assert res_chart.ok, res_chart.message
    assert res_chart.data["row_count"] == 2
    assert res_chart.data["truncated"] is True


def test_preview_request_seq_echo(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    res = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_SUM"]}],
        ),
        request_seq=7,
    )
    assert res.ok, res.message
    assert res.data["request_seq"] == 7
    res2 = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_SUM"]}],
            request_seq=9,
        ),
        request_seq=7,
    )
    assert res2.ok, res2.message
    assert res2.data["request_seq"] == 7  # tham số hàm thắng payload (chống stale)


def test_preview_draft_version_blocked(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    res = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["draft_version_id"],
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_SUM"]}],
        ),
    )
    assert not res.ok and res.code == ErrorCode.MODEL_VERSION_LOCKED


def test_preview_unknown_version_and_field_blocked(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    res = _preview(
        sq_env,
        "admin",
        _intent(
            999999,
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_SUM"]}],
        ),
    )
    assert not res.ok and res.code == ErrorCode.NOT_FOUND  # _load_version_row dùng NOT_FOUND
    res2 = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": 999999}],
            measures=[{"measure_id": mids["REV_SUM"]}],
        ),
    )
    assert not res2.ok and res2.code == ErrorCode.MODEL_INVALID


# ---------------------------------------------------------------------------
# RLS theo user/role/org (dựng model riêng + 1 chính sách rồi publish;
# KHÔNG dùng clone_model vì clone task 106 không remap FIELD trong AST measure)
# ---------------------------------------------------------------------------
def _rls_preview(sq_env, version_id, ctx_key, **kwargs):
    fids = _field_ids(sq_env, version_id)
    mids = _measure_ids(sq_env, version_id)
    return _preview(
        sq_env,
        ctx_key,
        _intent(
            version_id,
            dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
            measures=[{"measure_id": mids["REV_SUM"]}],
            sorts=[{"target_type": "FIELD", "id": fids["CUSTOMER_NAME"]}],
        ),
        **kwargs,
    )


def test_preview_rls_owner_username(sq_env):
    ver_id = _build_model(
        sq_env["ctxs"]["owner"],
        sq_env["ds_id"],
        "M_RLS_OWNER",
        rls=[
            {
                "table_alias": "FACT_SALES",
                "column_name": "OWNER_COL",
                "policy_type": "OWNER_USERNAME",
                "admin_bypass": True,
            }
        ],
    )
    res_owner = _rls_preview(sq_env, ver_id, "owner")
    assert res_owner.ok, res_owner.message
    assert {r["CUSTOMER_NAME"] for r in res_owner.data["rows"]} == {"Cong ty A", "Cong ty B"}
    res_viewer = _rls_preview(sq_env, ver_id, "viewer")
    assert res_viewer.ok, res_viewer.message
    assert {r["CUSTOMER_NAME"] for r in res_viewer.data["rows"]} == {"Cong ty B", "Cong ty C"}


def test_preview_rls_role_list(sq_env):
    ver_id = _build_model(
        sq_env["ctxs"]["owner"],
        sq_env["ds_id"],
        "M_RLS_ROLE",
        rls=[
            {"table_alias": "DIM_CUSTOMER", "column_name": "ROLE_COL", "policy_type": "ROLE_LIST", "admin_bypass": True}
        ],
    )
    res_op = _rls_preview(sq_env, ver_id, "operator")
    assert res_op.ok, res_op.message
    assert {r["CUSTOMER_NAME"] for r in res_op.data["rows"]} == {"Cong ty A", "Cong ty C"}
    res_viewer = _rls_preview(sq_env, ver_id, "viewer")
    assert res_viewer.ok, res_viewer.message
    assert {r["CUSTOMER_NAME"] for r in res_viewer.data["rows"]} == {"Cong ty B"}


def test_preview_rls_org_scope_hook(sq_env):
    ver_id = _build_model(
        sq_env["ctxs"]["owner"],
        sq_env["ds_id"],
        "M_RLS_ORG",
        rls=[
            {
                "table_alias": "FACT_SALES",
                "column_name": "ORG_CODE",
                "policy_type": "ORG_SCOPE_HOOK",
                "scope_attr": "org_code",
                "admin_bypass": True,
            }
        ],
    )
    res = _rls_preview(sq_env, ver_id, "owner", org_scopes={"org_code": "VTOS"})
    assert res.ok, res.message
    assert {r["CUSTOMER_NAME"] for r in res.data["rows"]} == {"Cong ty A", "Cong ty B"}
    res_missing = _rls_preview(sq_env, ver_id, "owner")
    assert not res_missing.ok and res_missing.code == ErrorCode.RLS_SCOPE_MISSING


def test_preview_rls_admin_bypass_and_warning(sq_env):
    ver_id = _build_model(
        sq_env["ctxs"]["owner"],
        sq_env["ds_id"],
        "M_RLS_ADM",
        rls=[
            {
                "table_alias": "FACT_SALES",
                "column_name": "OWNER_COL",
                "policy_type": "OWNER_USERNAME",
                "admin_bypass": True,
            }
        ],
    )
    res = _rls_preview(sq_env, ver_id, "admin")
    assert res.ok, res.message
    assert {r["CUSTOMER_NAME"] for r in res.data["rows"]} == {"Cong ty A", "Cong ty B", "Cong ty C"}
    assert res.data["warning_message"] is not None
    assert "bỏ qua cho ADMIN" in res.data["warning_message"]


# ---------------------------------------------------------------------------
# PROD, phân trang cho run, SQL debug, cache
# ---------------------------------------------------------------------------
def test_preview_prod_blocked_for_non_admin(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    payload = _intent(
        sq_env["active_version_id"],
        dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
        measures=[{"measure_id": mids["REV_SUM"]}],
    )
    engine = sq_env["engine"]
    with engine.begin() as conn:
        conn.execute(recon_data_source.update().where(recon_data_source.c.ID == sq_env["ds_id"]).values(ENV="PROD"))
    res_owner = _preview(sq_env, "owner", payload)
    assert not res_owner.ok and res_owner.code == ErrorCode.FORBIDDEN
    res_admin = _preview(sq_env, "admin", payload)
    assert res_admin.ok, res_admin.message


def test_for_run_pagination_and_total(sq_env):
    from app.services.semantic_query import execute_semantic_query_for_run

    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    payload = _intent(
        sq_env["active_version_id"],
        dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
        measures=[{"measure_id": mids["REV_SUM"]}],
        sorts=[{"target_type": "FIELD", "id": fids["CUSTOMER_NAME"]}],
    )
    page1 = execute_semantic_query_for_run(
        sq_env["ctxs"]["admin"], sq_env["active_version_id"], payload, page=1, page_size=2
    )
    assert page1.ok, page1.message
    assert page1.data["total"] == 3
    assert page1.data["row_count"] == 2
    assert page1.data["page"] == 1
    assert [r["CUSTOMER_NAME"] for r in page1.data["rows"]] == ["Cong ty A", "Cong ty B"]
    page2 = execute_semantic_query_for_run(
        sq_env["ctxs"]["admin"], sq_env["active_version_id"], payload, page=2, page_size=2
    )
    assert page2.ok, page2.message
    assert page2.data["total"] == 3
    assert page2.data["row_count"] == 1
    assert [r["CUSTOMER_NAME"] for r in page2.data["rows"]] == ["Cong ty C"]
    bad_page = execute_semantic_query_for_run(
        sq_env["ctxs"]["admin"], sq_env["active_version_id"], payload, page=0, page_size=2
    )
    assert not bad_page.ok and bad_page.code == ErrorCode.VALIDATION_ERROR


def test_debug_sql_admin_only_and_no_bind_values(sq_env):
    from app.services.semantic_query import get_semantic_sql_debug

    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    payload = _intent(
        sq_env["active_version_id"],
        dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
        measures=[{"measure_id": mids["REV_SUM"]}],
        filters=[{"field_id": fids["CUSTOMER_NAME"], "operator": "=", "value": "Cong ty A"}],
    )
    res = get_semantic_sql_debug(sq_env["ctxs"]["admin"], payload)
    assert res.ok, res.message
    assert res.data["sql"].startswith("SELECT")
    assert "Cong ty A" not in str(res.data)  # giá trị bind không lộ
    assert res.data["binds"] == ["b0"]
    assert res.data["dialect"] == "SQLITE"
    res_owner = get_semantic_sql_debug(sq_env["ctxs"]["owner"], payload)
    assert not res_owner.ok and res_owner.code == ErrorCode.FORBIDDEN
    res_viewer = get_semantic_sql_debug(sq_env["ctxs"]["viewer"], payload)
    assert not res_viewer.ok and res_viewer.code == ErrorCode.FORBIDDEN


def test_preview_uses_cached_bundle(sq_env, monkeypatch):
    import app.services.semantic_query as sq_mod
    from app.services.semantic_model import load_version_bundle as real_load

    calls = {"n": 0}

    def counting_load(conn, version_id):
        calls["n"] += 1
        return real_load(conn, version_id)

    monkeypatch.setattr(sq_mod, "load_version_bundle", counting_load)
    sq_mod.invalidate_semantic_query_cache()
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    payload = _intent(
        sq_env["active_version_id"],
        dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
        measures=[{"measure_id": mids["REV_SUM"]}],
    )
    assert _preview(sq_env, "admin", payload).ok
    assert _preview(sq_env, "admin", payload).ok
    assert calls["n"] == 1
    sq_mod.invalidate_semantic_query_cache()
    assert _preview(sq_env, "admin", payload).ok
    assert calls["n"] == 2


def test_preview_group_by_quarter_and_year(sq_env):
    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    res = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CAL_DATE"], "date_part": "QUARTER", "alias": "CAL_Q"}],
            measures=[{"measure_id": mids["REV_SUM"]}],
            sorts=[{"target_type": "FIELD", "id": fids["CAL_DATE"]}],
        ),
    )
    assert res.ok, res.message
    expected_q: dict[str, int] = {}
    for row in SALES:
        q = (row[3].month - 1) // 3 + 1
        key = f"{row[3].year}-Q{q}"
        expected_q[key] = expected_q.get(key, 0) + row[5]
    assert {r["CAL_Q"]: r["REV_SUM"] for r in res.data["rows"]} == expected_q
    res_y = _preview(
        sq_env,
        "admin",
        _intent(
            sq_env["active_version_id"],
            dimensions=[{"field_id": fids["CAL_DATE"], "date_part": "YEAR", "alias": "CAL_Y"}],
            measures=[{"measure_id": mids["REV_SUM"]}],
        ),
    )
    assert res_y.ok, res_y.message
    assert {r["CAL_Y"]: r["REV_SUM"] for r in res_y.data["rows"]} == {str(_today().year): sum(s[5] for s in SALES)}


def test_preview_archived_version_rejected_despite_cached_bundle(sq_env):
    """Hồi quy (TC-FN-06): version bị ARCHIVED sau khi bundle đã cache vẫn bị chặn.

    Cache theo version_id chỉ được giữ nội dung bất biến; trạng thái đổi khi
    publish version mới (version cũ -> ARCHIVED) nên service phải đọc lại
    STATUS mỗi lần, nếu không preview chạy nhầm version đã khóa.
    """
    from app.db.metadata import recon_rpt_model_ver

    fids = _field_ids(sq_env)
    mids = _measure_ids(sq_env)
    payload = _intent(
        sq_env["active_version_id"],
        dimensions=[{"field_id": fids["CUSTOMER_NAME"]}],
        measures=[{"measure_id": mids["REV_SUM"]}],
    )
    assert _preview(sq_env, "admin", payload).ok  # nạp bundle vào cache
    with sq_env["engine"].begin() as conn:
        conn.execute(
            recon_rpt_model_ver.update()
            .where(recon_rpt_model_ver.c.ID == sq_env["active_version_id"])
            .values(STATUS="ARCHIVED")
        )
    res = _preview(sq_env, "admin", payload)
    assert not res.ok and res.code == ErrorCode.MODEL_VERSION_LOCKED
