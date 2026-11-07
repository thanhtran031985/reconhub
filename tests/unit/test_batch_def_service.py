"""Tests cho service batch_def — Bước 3 task 18 (test viết trước).

CRUD bộ đối soát + thêm/gỡ template + addable_templates +
preview_params + activate (spec 10 mục 4, 8; spec 10a mục 1).
Fixture theo mẫu tests/unit/test_reporting_services.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def batch_env(tmp_path, monkeypatch):
    db_path = tmp_path / "batch_def.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.batch_def",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, username in [
            (1, "admin"),
            (2, "owner"),
            (3, "operator"),
            (4, "viewer"),
        ]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": username, "now": now},
            )
    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["TEMPLATE_OWNER"], 3: ["OPERATOR"], 4: ["VIEWER"]})
    clear_perm_cache()
    return engine


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


@pytest.fixture()
def owner_ctx() -> Ctx:
    return Ctx(user_id=2, username="owner", full_name="owner", roles=["TEMPLATE_OWNER"])


@pytest.fixture()
def operator_ctx() -> Ctx:
    return Ctx(user_id=3, username="operator", full_name="operator", roles=["OPERATOR"])


@pytest.fixture()
def viewer_ctx() -> Ctx:
    return Ctx(user_id=4, username="viewer", full_name="viewer", roles=["VIEWER"])


def _sample_config(params: list[dict]) -> dict:
    data = json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))
    data["db_source"]["params"] = params
    return data


def _make_data_source(engine) -> int:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        ds_id = conn.execute(
            text(
                "INSERT INTO RECON_DATA_SOURCE (NAME, ENV, PURPOSE, DB_TYPE, HOST, "
                "PORT, SERVICE_NAME, CALL_TIMEOUT_S, MAX_ROWS, IS_ACTIVE, "
                "IS_CURRENT_METADATA, CREATED_BY, CREATED_AT, UPDATED_AT) VALUES "
                "('ORACLE_TEST', 'DEV', 'SOURCE', 'ORACLE', 'localhost', 1521, 'XE', "
                "600, 1000000, 'Y', 'N', 'admin', :now, :now)"
            ),
            {"now": now},
        ).lastrowid
    return int(ds_id)


def _make_template(engine, code: str, status: str = "ACTIVE", params: list[dict] | None = None) -> int:
    params = (
        params
        if params is not None
        else [
            {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày giờ", "required": True},
            {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày giờ", "required": True},
            {"name": "p_ky", "type": "text", "source": "user", "label": "Kỳ", "required": True},
            {"name": "p_so", "type": "number", "source": "user", "label": "Số", "required": False},
        ]
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        tmpl_id = conn.execute(
            text(
                "INSERT INTO RECON_TEMPLATE (CODE, NAME, OWNER, STATUS, CURRENT_VERSION, "
                "CREATED_AT, UPDATED_AT, ROW_VERSION) VALUES (:c, :n, 'admin', :s, 1, :now, :now, 1)"
            ),
            {"c": code, "n": code, "s": status, "now": now},
        ).lastrowid
        conn.execute(
            text(
                "INSERT INTO RECON_TEMPLATE_VERSION (TEMPLATE_ID, VERSION, STATUS, "
                "CONFIG_JSON, CREATED_BY, CREATED_AT) VALUES (:t, 1, :s, :cfg, 'admin', :now)"
            ),
            {"t": tmpl_id, "s": status, "cfg": json.dumps(_sample_config(params), ensure_ascii=False), "now": now},
        )
    return int(tmpl_id)


def _def_payload(**overrides) -> dict:
    payload = {"code": "DOANH_THU", "name": "Doanh thu cuối tháng", "max_parallel_per_ds": 2}
    payload.update(overrides)
    return payload


def _item_payload(template_id: int, **overrides) -> dict:
    payload = {
        "template_id": template_id,
        "file_pattern": "*DTP*",
        "multi_file": True,
        "is_required": True,
        "priority": 100,
        "params_override": {"p_ky": "{ky.thang}"},
    }
    payload.update(overrides)
    return payload


def _create_def(admin_ctx, **overrides) -> dict:
    from app.services.batch_def import create_batch_def

    res = create_batch_def(admin_ctx, _def_payload(**overrides))
    assert res.ok is True, res.message
    return res.data


class TestCreateListGet:
    def test_create_ok(self, batch_env, admin_ctx):
        from app.services.batch_def import create_batch_def

        res = create_batch_def(admin_ctx, _def_payload())
        assert res.ok is True
        assert res.data["code"] == "DOANH_THU"
        assert res.data["status"] == "DRAFT"
        assert res.data["row_version"] == 1
        assert res.data["owner_id"] == 1

    def test_create_by_template_owner_ok(self, batch_env, owner_ctx):
        from app.services.batch_def import create_batch_def

        res = create_batch_def(owner_ctx, _def_payload())
        assert res.ok is True

    def test_create_forbidden_for_operator_and_viewer(self, batch_env, operator_ctx, viewer_ctx):
        from app.services.batch_def import create_batch_def

        assert create_batch_def(operator_ctx, _def_payload()).code == "FORBIDDEN"
        assert create_batch_def(viewer_ctx, _def_payload()).code == "FORBIDDEN"

    def test_create_duplicate_code(self, batch_env, admin_ctx):
        from app.services.batch_def import create_batch_def

        _create_def(admin_ctx)
        res = create_batch_def(admin_ctx, _def_payload(name="Khác"))
        assert res.ok is False
        assert res.code == "CONFLICT"

    def test_create_invalid_code_and_parallel(self, batch_env, admin_ctx):
        from app.services.batch_def import create_batch_def

        assert create_batch_def(admin_ctx, _def_payload(code="doanh_thu")).code == "VALIDATION_ERROR"
        assert create_batch_def(admin_ctx, _def_payload(max_parallel_per_ds=5)).code == "VALIDATION_ERROR"
        assert create_batch_def(admin_ctx, _def_payload(max_parallel_per_ds=0)).code == "VALIDATION_ERROR"

    def test_list_filter(self, batch_env, admin_ctx, viewer_ctx):
        from app.services.batch_def import list_batch_defs

        _create_def(admin_ctx, code="DOANH_THU", name="Doanh thu")
        _create_def(admin_ctx, code="CHI_PHI", name="Chi phí")
        res = list_batch_defs(viewer_ctx, q="doanh")
        assert res.ok is True
        assert [d["code"] for d in res.data] == ["DOANH_THU"]
        res = list_batch_defs(viewer_ctx, status="DRAFT")
        assert len(res.data) == 2
        res = list_batch_defs(viewer_ctx, status="ACTIVE")
        assert res.data == []

    def test_get_not_found(self, batch_env, admin_ctx):
        from app.services.batch_def import get_batch_def

        res = get_batch_def(admin_ctx, 999)
        assert res.ok is False
        assert res.code == "BATCH_NOT_FOUND"


class TestUpdateArchiveActivate:
    def test_update_ok_and_stale(self, batch_env, admin_ctx):
        from app.services.batch_def import update_batch_def

        d = _create_def(admin_ctx)
        res = update_batch_def(admin_ctx, d["id"], {"name": "Tên mới", "max_parallel_per_ds": 3}, d["row_version"])
        assert res.ok is True
        assert res.data["name"] == "Tên mới"
        assert res.data["row_version"] == 2
        stale = update_batch_def(admin_ctx, d["id"], {"name": "Cũ"}, d["row_version"])
        assert stale.ok is False
        assert stale.code == "STALE_DATA"

    def test_update_forbidden_for_viewer(self, batch_env, admin_ctx, viewer_ctx):
        from app.services.batch_def import update_batch_def

        d = _create_def(admin_ctx)
        res = update_batch_def(viewer_ctx, d["id"], {"name": "X"}, d["row_version"])
        assert res.code == "FORBIDDEN"

    def test_archive(self, batch_env, admin_ctx):
        from app.services.batch_def import archive_batch_def, get_batch_def

        d = _create_def(admin_ctx)
        res = archive_batch_def(admin_ctx, d["id"])
        assert res.ok is True
        assert res.data["status"] == "ARCHIVED"
        assert get_batch_def(admin_ctx, d["id"]).data["status"] == "ARCHIVED"

    def test_activate_requires_items(self, batch_env, admin_ctx):
        from app.services.batch_def import activate_batch_def

        d = _create_def(admin_ctx)
        res = activate_batch_def(admin_ctx, d["id"])
        assert res.ok is False
        assert res.code == "BATCH_NOT_ACTIVE"

    def test_activate_ok(self, batch_env, admin_ctx):
        from app.services.batch_def import activate_batch_def, add_batch_def_items

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        added = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl)])
        assert added.ok is True
        res = activate_batch_def(admin_ctx, d["id"])
        assert res.ok is True
        assert res.data["status"] == "ACTIVE"

    def test_activate_blocked_by_param_error(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        added = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl, params_override={"p_la": "x"})])
        assert added.ok is False
        assert added.code == "BATCH_PARAM_UNKNOWN"


class TestItems:
    def test_add_item_ok(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items, get_batch_def

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        res = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl)])
        assert res.ok is True
        assert len(res.data) == 1
        item = res.data[0]
        assert item["template_code"] == "DTP_TMPL"
        assert item["seq_no"] == 1
        assert item["params_override"] == {"p_ky": "{ky.thang}"}
        got = get_batch_def(admin_ctx, d["id"])
        assert len(got.data["items"]) == 1

    def test_add_draft_and_archived_template(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items

        d = _create_def(admin_ctx)
        draft = _make_template(batch_env, "DRAFT_TMPL", status="DRAFT")
        archived = _make_template(batch_env, "ARCH_TMPL", status="ARCHIVED")
        assert add_batch_def_items(admin_ctx, d["id"], [_item_payload(draft)]).code == "BATCH_TEMPLATE_NOT_ACTIVE"
        assert add_batch_def_items(admin_ctx, d["id"], [_item_payload(archived)]).code == "BATCH_TEMPLATE_NOT_ACTIVE"

    def test_add_duplicate_template(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        assert add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl)]).ok is True
        res = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl)])
        assert res.ok is False
        assert res.code == "BATCH_TEMPLATE_EXISTS"

    def test_add_without_pattern(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        res = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl, file_pattern="  ")])
        assert res.ok is False
        assert res.code == "BATCH_ITEM_PATTERN_REQUIRED"

    def test_add_invalid_formula(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        res = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl, params_override={"p_ky": "{ky.tu+99d}"})])
        assert res.ok is False
        assert res.code == "BATCH_FORMULA_INVALID"

    def test_update_item(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items, update_batch_def_item

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        item = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl)]).data[0]
        res = update_batch_def_item(
            admin_ctx, item["id"], {"priority": 10, "file_pattern": "*DTP2026*"}, item["row_version"]
        )
        assert res.ok is True
        assert res.data["priority"] == 10
        assert res.data["file_pattern"] == "*DTP2026*"
        assert res.data["row_version"] == 2
        stale = update_batch_def_item(admin_ctx, item["id"], {"priority": 20}, item["row_version"])
        assert stale.code == "STALE_DATA"

    def test_remove_item_hard_delete_when_no_runs(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items, get_batch_def, remove_batch_def_item

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        item = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl)]).data[0]
        res = remove_batch_def_item(admin_ctx, item["id"])
        assert res.ok is True
        assert res.data["is_active"] is True  # xóa hẳn, không còn dòng
        assert get_batch_def(admin_ctx, d["id"]).data["items"] == []

    def test_remove_item_soft_delete_when_referenced(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items, get_batch_def, remove_batch_def_item

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        item = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl)]).data[0]
        ds_id = _make_data_source(batch_env)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with batch_env.begin() as conn:
            run_id = conn.execute(
                text(
                    "INSERT INTO RECON_BATCH_RUN (BATCH_DEF_ID, NAME, PERIOD, PERIOD_FROM, "
                    "PERIOD_TO, STATUS, INCLUDE_WARN, CNT_ITEMS, CNT_DONE, CNT_FAILED, "
                    "CNT_SKIPPED, CNT_NOT_RUN, CREATED_BY, CREATED_AT, "
                    "UPDATED_BY, UPDATED_AT, ROW_VERSION) VALUES (:d, 'Tháng 10/2026', "
                    "'2026-10', :now, :now, 'DRAFT', 'Y', 1, 0, 0, 0, 0, 'admin', :now, 'admin', :now, 1)"
                ),
                {"d": d["id"], "now": now},
            ).lastrowid
            conn.execute(
                text(
                    "INSERT INTO RECON_BATCH_RUN_ITEM (BATCH_RUN_ID, BATCH_DEF_ITEM_ID, "
                    "TEMPLATE_ID, PROFILE_CODE, DATA_SOURCE_ID, SEQ_NO, PRIORITY, MULTI_FILE, "
                    "IS_REQUIRED, STATUS, ATTEMPT_NO, CREATED_BY, CREATED_AT, UPDATED_BY, "
                    "UPDATED_AT, ROW_VERSION) VALUES (:r, :i, :t, 'DEFAULT', :ds, 1, 100, 'Y', "
                    "'Y', 'PENDING', 0, 'admin', :now, 'admin', :now, 1)"
                ),
                {"r": run_id, "i": item["id"], "t": tmpl, "now": now, "ds": ds_id},
            )
        res = remove_batch_def_item(admin_ctx, item["id"])
        assert res.ok is True
        assert res.data["is_active"] is False
        got = get_batch_def(admin_ctx, d["id"])
        assert got.data["items"] == []

    def test_readd_soft_deleted_item_reactivates(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items, remove_batch_def_item

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        item = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl)]).data[0]
        ds_id = _make_data_source(batch_env)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with batch_env.begin() as conn:
            run_id = conn.execute(
                text(
                    "INSERT INTO RECON_BATCH_RUN (BATCH_DEF_ID, NAME, PERIOD, PERIOD_FROM, "
                    "PERIOD_TO, STATUS, INCLUDE_WARN, CNT_ITEMS, CNT_DONE, CNT_FAILED, "
                    "CNT_SKIPPED, CNT_NOT_RUN, CREATED_BY, CREATED_AT, "
                    "UPDATED_BY, UPDATED_AT, ROW_VERSION) VALUES (:d, 'Tháng 10/2026', "
                    "'2026-10', :now, :now, 'DRAFT', 'Y', 1, 0, 0, 0, 0, 'admin', :now, 'admin', :now, 1)"
                ),
                {"d": d["id"], "now": now},
            ).lastrowid
            conn.execute(
                text(
                    "INSERT INTO RECON_BATCH_RUN_ITEM (BATCH_RUN_ID, BATCH_DEF_ITEM_ID, "
                    "TEMPLATE_ID, PROFILE_CODE, DATA_SOURCE_ID, SEQ_NO, PRIORITY, MULTI_FILE, "
                    "IS_REQUIRED, STATUS, ATTEMPT_NO, CREATED_BY, CREATED_AT, UPDATED_BY, "
                    "UPDATED_AT, ROW_VERSION) VALUES (:r, :i, :t, 'DEFAULT', :ds, 1, 100, 'Y', "
                    "'Y', 'PENDING', 0, 'admin', :now, 'admin', :now, 1)"
                ),
                {"r": run_id, "i": item["id"], "t": tmpl, "now": now, "ds": ds_id},
            )
        removed = remove_batch_def_item(admin_ctx, item["id"])
        assert removed.data["is_active"] is False
        res = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl, file_pattern="*DTP2*")])
        assert res.ok is True
        assert res.data[0]["id"] == item["id"]
        assert res.data[0]["file_pattern"] == "*DTP2*"


class TestAddableAndPreview:
    def test_addable_templates(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items, addable_templates

        d = _create_def(admin_ctx)
        active = _make_template(batch_env, "DTP_TMPL")
        _make_template(batch_env, "DRAFT_TMPL", status="DRAFT")
        _make_template(batch_env, "ARCH_TMPL", status="ARCHIVED")
        add_batch_def_items(admin_ctx, d["id"], [_item_payload(active)])
        res = addable_templates(admin_ctx, d["id"], q=None, include_unavailable=False)
        assert res.ok is True
        assert res.data == []
        res = addable_templates(admin_ctx, d["id"], q=None, include_unavailable=True)
        codes = {t["code"]: t for t in res.data}
        assert codes["DTP_TMPL"]["addable"] is False
        assert codes["DRAFT_TMPL"]["addable"] is False
        assert "dry-run" in codes["DRAFT_TMPL"]["reason"]
        assert codes["ARCH_TMPL"]["addable"] is False
        res = addable_templates(admin_ctx, d["id"], q="draft", include_unavailable=True)
        assert [t["code"] for t in res.data] == ["DRAFT_TMPL"]

    def test_preview_params(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items, preview_params

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl)])
        res = preview_params(admin_ctx, d["id"], "2026-10")
        assert res.ok is True
        item = res.data["items"][0]
        assert item["template_code"] == "DTP_TMPL"
        assert item["params"]["p_ky"] == "202610"
        assert item["params"]["p_from"] == "2026-10-01T00:00:00"
        assert item["params"]["p_to"] == "2026-10-31T23:59:59"
        assert item["errors"] == []

    def test_preview_params_unknown_param_error(self, batch_env, admin_ctx):
        from app.services.batch_def import add_batch_def_items, preview_params

        d = _create_def(admin_ctx)
        tmpl = _make_template(batch_env, "DTP_TMPL")
        # Ghi đè tham số lạ trực tiếp vào DB (đường add đã chặn).
        item = add_batch_def_items(admin_ctx, d["id"], [_item_payload(tmpl)]).data[0]
        with batch_env.begin() as conn:
            conn.execute(
                text("UPDATE RECON_BATCH_DEF_ITEM SET PARAMS_OVERRIDE_JSON = :j WHERE ID = :i"),
                {"j": json.dumps({"p_la": "x"}, ensure_ascii=False), "i": item["id"]},
            )
        res = preview_params(admin_ctx, d["id"], "2026-10")
        assert res.ok is True
        assert res.data["items"][0]["errors"][0]["code"] == "BATCH_PARAM_UNKNOWN"

    def test_preview_params_invalid_period(self, batch_env, admin_ctx):
        from app.services.batch_def import preview_params

        d = _create_def(admin_ctx)
        res = preview_params(admin_ctx, d["id"], "2026-13")
        assert res.ok is False
        assert res.code == "BATCH_FORMULA_INVALID"
