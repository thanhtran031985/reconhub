"""Tests cho service batch_run — Bước 4 task 18 (test viết trước).

Tạo lần chạy bộ + tải/ghép file + tham số (spec 10 mục 5.1–5.3, 8).
Fixture theo mẫu tests/unit/test_batch_def_service.py.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def batch_run_env(tmp_path, monkeypatch):
    db_path = tmp_path / "batch_run.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.batch_def",
        "app.services.batch_run",
        "app.services.file_service",
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


def _default_params() -> list[dict]:
    return [
        {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày giờ", "required": True},
        {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày giờ", "required": True},
        {"name": "p_ky", "type": "text", "source": "user", "label": "Kỳ", "required": True},
        {"name": "p_so", "type": "number", "source": "user", "label": "Số", "required": False},
    ]


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


def _make_template(engine, code: str, status: str = "ACTIVE", ds_id: int | None = None) -> int:
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
                "CONFIG_JSON, DATA_SOURCE_ID, CREATED_BY, CREATED_AT) VALUES (:t, 1, :s, "
                ":cfg, :ds, 'admin', :now)"
            ),
            {
                "t": tmpl_id,
                "s": status,
                "cfg": json.dumps(_sample_config(_default_params()), ensure_ascii=False),
                "ds": ds_id,
                "now": now,
            },
        )
    return int(tmpl_id)


def _make_def(engine, admin_ctx, code: str = "DOANH_THU", items: list[dict] | None = None) -> dict:
    from app.services.batch_def import add_batch_def_items, create_batch_def

    res = create_batch_def(admin_ctx, {"code": code, "name": code, "max_parallel_per_ds": 2})
    assert res.ok is True, res.message
    d = res.data
    if items:
        added = add_batch_def_items(admin_ctx, d["id"], items)
        assert added.ok is True, added.message
    return d


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


def _dtp_bytes() -> bytes:
    return Path("samples/dtp_sample_200.xlsx").read_bytes()


def _other_xlsx_bytes() -> bytes:
    import xlsxwriter

    buf = io.BytesIO()
    with xlsxwriter.Workbook(buf) as wb:
        ws = wb.add_worksheet("Data")
        ws.write_row(0, 0, ["Cột A", "Cột B"])
        ws.write_row(1, 0, ["x", 1])
    return buf.getvalue()


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


class TestCreate:
    def test_create_ok(self, batch_run_env, admin_ctx):
        from app.services.batch_run import create_batch_run

        ds_id = _make_data_source(batch_run_env)
        tmpl = _make_template(batch_run_env, "DTP_TMPL", ds_id=ds_id)
        d = _make_def(batch_run_env, admin_ctx, items=[_item_payload(tmpl)])
        from app.services.batch_def import activate_batch_def

        assert activate_batch_def(admin_ctx, d["id"]).ok is True
        res = create_batch_run(admin_ctx, d["id"], "2026-10")
        assert res.ok is True
        run = res.data
        assert run["status"] == "DRAFT"
        assert run["name"] == "Tháng 10/2026"
        assert run["period_from"] == "2026-10-01T00:00:00"
        assert run["period_to"] == "2026-10-31T23:59:59"
        assert run["period_warning"] is False
        assert len(run["items"]) == 1
        item = run["items"][0]
        assert item["status"] == "PENDING"
        assert item["profile_code"] == "BY_INVOICE"
        assert item["data_source_id"] == ds_id
        assert item["template_version"] == 1

    def test_create_name_override_and_period_warning(self, batch_run_env, admin_ctx):
        from app.services.batch_run import create_batch_run

        ds_id = _make_data_source(batch_run_env)
        tmpl = _make_template(batch_run_env, "DTP_TMPL", ds_id=ds_id)
        d = _make_def(batch_run_env, admin_ctx, items=[_item_payload(tmpl)])
        from app.services.batch_def import activate_batch_def

        activate_batch_def(admin_ctx, d["id"])
        first = create_batch_run(admin_ctx, d["id"], "2026-10", name="Lần 1")
        assert first.ok is True
        assert first.data["name"] == "Lần 1"
        second = create_batch_run(admin_ctx, d["id"], "2026-10")
        assert second.ok is True
        assert second.data["period_warning"] is True

    def test_create_draft_def_blocked(self, batch_run_env, admin_ctx):
        from app.services.batch_run import create_batch_run

        ds_id = _make_data_source(batch_run_env)
        tmpl = _make_template(batch_run_env, "DTP_TMPL", ds_id=ds_id)
        d = _make_def(batch_run_env, admin_ctx, items=[_item_payload(tmpl)])
        res = create_batch_run(admin_ctx, d["id"], "2026-10")
        assert res.ok is False
        assert res.code == "BATCH_NOT_ACTIVE"

    def test_create_invalid_period_and_missing_def(self, batch_run_env, admin_ctx):
        from app.services.batch_run import create_batch_run

        assert create_batch_run(admin_ctx, 999, "2026-10").code == "BATCH_NOT_FOUND"
        ds_id = _make_data_source(batch_run_env)
        tmpl = _make_template(batch_run_env, "DTP_TMPL", ds_id=ds_id)
        d = _make_def(batch_run_env, admin_ctx, items=[_item_payload(tmpl)])
        from app.services.batch_def import activate_batch_def

        activate_batch_def(admin_ctx, d["id"])
        assert create_batch_run(admin_ctx, d["id"], "2026-13").code == "BATCH_FORMULA_INVALID"

    def test_create_archived_template_item_skipped(self, batch_run_env, admin_ctx):
        from app.services.batch_run import create_batch_run

        ds_id = _make_data_source(batch_run_env)
        tmpl = _make_template(batch_run_env, "DTP_TMPL", ds_id=ds_id)
        d = _make_def(batch_run_env, admin_ctx, items=[_item_payload(tmpl)])
        from app.services.batch_def import activate_batch_def

        activate_batch_def(admin_ctx, d["id"])
        with batch_run_env.begin() as conn:
            conn.execute(text("UPDATE RECON_TEMPLATE SET STATUS = 'ARCHIVED' WHERE ID = :t"), {"t": tmpl})
        res = create_batch_run(admin_ctx, d["id"], "2026-10")
        assert res.ok is True
        item = res.data["items"][0]
        assert item["status"] == "SKIPPED"
        assert item["skip_reason"] == "TEMPLATE_ARCHIVED"

    def test_create_operator_ok_viewer_forbidden(self, batch_run_env, admin_ctx, operator_ctx, viewer_ctx):
        from app.services.batch_run import create_batch_run

        ds_id = _make_data_source(batch_run_env)
        tmpl = _make_template(batch_run_env, "DTP_TMPL", ds_id=ds_id)
        d = _make_def(batch_run_env, admin_ctx, items=[_item_payload(tmpl)])
        from app.services.batch_def import activate_batch_def

        activate_batch_def(admin_ctx, d["id"])
        assert create_batch_run(operator_ctx, d["id"], "2026-10").ok is True
        assert create_batch_run(viewer_ctx, d["id"], "2026-10").code == "FORBIDDEN"

    def test_create_missing_data_source(self, batch_run_env, admin_ctx):
        from app.services.batch_run import create_batch_run

        tmpl = _make_template(batch_run_env, "DTP_TMPL", ds_id=None)
        d = _make_def(batch_run_env, admin_ctx, items=[_item_payload(tmpl)])
        from app.services.batch_def import activate_batch_def

        activate_batch_def(admin_ctx, d["id"])
        res = create_batch_run(admin_ctx, d["id"], "2026-10")
        assert res.ok is False
        assert res.code == "NOT_FOUND"


class TestGetList:
    def _setup_run(self, batch_run_env, admin_ctx):
        from app.services.batch_run import create_batch_run

        ds_id = _make_data_source(batch_run_env)
        tmpl = _make_template(batch_run_env, "DTP_TMPL", ds_id=ds_id)
        d = _make_def(batch_run_env, admin_ctx, items=[_item_payload(tmpl)])
        from app.services.batch_def import activate_batch_def

        activate_batch_def(admin_ctx, d["id"])
        res = create_batch_run(admin_ctx, d["id"], "2026-10")
        assert res.ok is True
        return d, res.data

    def test_get_ok_and_owner_scope(self, batch_run_env, admin_ctx, operator_ctx):
        from app.services.batch_run import get_batch_run

        _d, run = self._setup_run(batch_run_env, admin_ctx)
        assert get_batch_run(admin_ctx, run["id"]).ok is True
        assert get_batch_run(operator_ctx, run["id"]).code == "NOT_FOUND"

    def test_list_pagination_and_owner_scope(self, batch_run_env, admin_ctx, operator_ctx):
        from app.services.batch_run import create_batch_run, list_batch_runs

        ds_id = _make_data_source(batch_run_env)
        tmpl = _make_template(batch_run_env, "DTP_TMPL", ds_id=ds_id)
        d = _make_def(batch_run_env, admin_ctx, items=[_item_payload(tmpl)])
        from app.services.batch_def import activate_batch_def

        activate_batch_def(admin_ctx, d["id"])
        for period in ("2026-08", "2026-09", "2026-10"):
            assert create_batch_run(admin_ctx, d["id"], period).ok is True
        assert create_batch_run(operator_ctx, d["id"], "2026-11").ok is True
        res = list_batch_runs(admin_ctx, page=1, page_size=2)
        assert res.ok is True
        assert res.data["total"] == 4
        assert len(res.data["items"]) == 2
        res = list_batch_runs(operator_ctx)
        assert res.data["total"] == 1
        res = list_batch_runs(admin_ctx, period="2026-09")
        assert res.data["total"] == 1


class TestAddFiles:
    def _setup_run(self, batch_run_env, admin_ctx, items=None):
        from app.services.batch_run import create_batch_run

        ds_id = _make_data_source(batch_run_env)
        tmpl = _make_template(batch_run_env, "DTP_TMPL", ds_id=ds_id)
        d = _make_def(batch_run_env, admin_ctx, items=items or [_item_payload(tmpl)])
        from app.services.batch_def import activate_batch_def

        activate_batch_def(admin_ctx, d["id"])
        res = create_batch_run(admin_ctx, d["id"], "2026-10")
        assert res.ok is True
        return d, res.data

    def test_add_file_pattern_match(self, batch_run_env, admin_ctx):
        from app.services.batch_run import add_files, get_batch_run

        _d, run = self._setup_run(batch_run_env, admin_ctx)
        res = add_files(admin_ctx, run["id"], [{"filename": "dtp_2026-10.xlsx", "content": _dtp_bytes()}])
        assert res.ok is True
        assert len(res.data["added"]) == 1
        assert res.data["added"][0]["match_state"] == "MATCHED"
        assert res.data["added"][0]["match_by"] == "PATTERN"
        assert res.data["skipped"] == []
        got = get_batch_run(admin_ctx, run["id"])
        assert len(got.data["items"][0]["files"]) == 1

    def test_add_file_header_match(self, batch_run_env, admin_ctx):
        from app.services.batch_run import add_files

        _d, run = self._setup_run(batch_run_env, admin_ctx)
        res = add_files(admin_ctx, run["id"], [{"filename": "khong_khop.xlsx", "content": _dtp_bytes()}])
        assert res.ok is True
        assert res.data["added"][0]["match_state"] == "MATCHED"
        assert res.data["added"][0]["match_by"] == "HEADER"

    def test_add_file_unmatched(self, batch_run_env, admin_ctx):
        from app.services.batch_run import add_files

        _d, run = self._setup_run(batch_run_env, admin_ctx)
        res = add_files(admin_ctx, run["id"], [{"filename": "la.xlsx", "content": _other_xlsx_bytes()}])
        assert res.ok is True
        assert res.data["added"][0]["match_state"] == "UNMATCHED"

    def test_add_file_ambiguous(self, batch_run_env, admin_ctx):
        from app.services.batch_run import add_files

        ds_id = _make_data_source(batch_run_env)
        t1 = _make_template(batch_run_env, "DTP_TMPL", ds_id=ds_id)
        t2 = _make_template(batch_run_env, "KHAC_TMPL", ds_id=ds_id)
        d = _make_def(
            batch_run_env,
            admin_ctx,
            items=[_item_payload(t1, file_pattern="*DTP*"), _item_payload(t2, file_pattern="*2026*")],
        )
        from app.services.batch_def import activate_batch_def
        from app.services.batch_run import create_batch_run

        activate_batch_def(admin_ctx, d["id"])
        run = create_batch_run(admin_ctx, d["id"], "2026-10").data
        res = add_files(admin_ctx, run["id"], [{"filename": "dtp_2026-10.xlsx", "content": _dtp_bytes()}])
        assert res.ok is True
        added = res.data["added"][0]
        assert added["match_state"] == "AMBIGUOUS"
        assert len(added["candidate_item_ids"]) == 2

    def test_add_duplicate_name_skipped(self, batch_run_env, admin_ctx):
        from app.services.batch_run import add_files

        _d, run = self._setup_run(batch_run_env, admin_ctx)
        first = add_files(admin_ctx, run["id"], [{"filename": "dtp.xlsx", "content": _dtp_bytes()}])
        assert first.ok is True
        second = add_files(admin_ctx, run["id"], [{"filename": "dtp.xlsx", "content": _other_xlsx_bytes()}])
        assert second.ok is True
        assert len(second.data["added"]) == 0
        assert len(second.data["skipped"]) == 1
        assert second.data["skipped"][0]["reason"] == "BATCH_FILE_DUPLICATE"

    def test_add_duplicate_content_warning(self, batch_run_env, admin_ctx):
        from app.services.batch_run import add_files

        _d, run = self._setup_run(batch_run_env, admin_ctx)
        add_files(admin_ctx, run["id"], [{"filename": "a.xlsx", "content": _dtp_bytes()}])
        res = add_files(admin_ctx, run["id"], [{"filename": "b.xlsx", "content": _dtp_bytes()}])
        assert res.ok is True
        assert len(res.data["added"]) == 1
        assert any(w["code"] == "BATCH_FILE_DUPLICATE" for w in res.data["warnings"])

    def test_add_zip(self, batch_run_env, admin_ctx):
        from app.services.batch_run import add_files

        _d, run = self._setup_run(batch_run_env, admin_ctx)
        content = _zip_bytes(
            {
                "dtp_a.xlsx": _dtp_bytes(),
                "sub/dtp_b.xlsx": _dtp_bytes(),
                "readme.txt": b"hello",
            }
        )
        res = add_files(admin_ctx, run["id"], [{"filename": "files.zip", "content": content}])
        assert res.ok is True
        assert len(res.data["added"]) == 2
        assert {f["original_name"] for f in res.data["added"]} == {
            "files.zip/dtp_a.xlsx",
            "files.zip/sub/dtp_b.xlsx",
        }
        assert len(res.data["skipped"]) == 1

    def test_add_zip_slip_rejected(self, batch_run_env, admin_ctx):
        from app.services.batch_run import add_files

        _d, run = self._setup_run(batch_run_env, admin_ctx)
        content = _zip_bytes({"../evil.xlsx": _dtp_bytes()})
        res = add_files(admin_ctx, run["id"], [{"filename": "evil.zip", "content": content}])
        assert res.ok is False
        assert res.code == "BATCH_ZIP_INVALID"

    def test_add_file_too_large_and_bad_type(self, batch_run_env, admin_ctx):
        from app.services.batch_run import add_files

        _d, run = self._setup_run(batch_run_env, admin_ctx)
        big = add_files(admin_ctx, run["id"], [{"filename": "big.xlsx", "content": b"x" * (51 * 1024 * 1024)}])
        assert big.ok is False
        assert big.code == "FILE_TOO_LARGE"
        bad = add_files(admin_ctx, run["id"], [{"filename": "run.exe", "content": b"MZ" + b"x" * 100}])
        assert bad.ok is False
        assert bad.code == "FILE_TYPE_NOT_ALLOWED"

    def test_add_files_forbidden_for_non_creator(self, batch_run_env, admin_ctx, operator_ctx):
        from app.services.batch_run import add_files

        _d, run = self._setup_run(batch_run_env, admin_ctx)
        res = add_files(operator_ctx, run["id"], [{"filename": "dtp.xlsx", "content": _dtp_bytes()}])
        assert res.code == "FORBIDDEN"


class TestAssignIgnoreSkipParams:
    def _setup_run_with_file(self, batch_run_env, admin_ctx):
        from app.services.batch_run import add_files, create_batch_run

        ds_id = _make_data_source(batch_run_env)
        tmpl = _make_template(batch_run_env, "DTP_TMPL", ds_id=ds_id)
        d = _make_def(batch_run_env, admin_ctx, items=[_item_payload(tmpl)])
        from app.services.batch_def import activate_batch_def

        activate_batch_def(admin_ctx, d["id"])
        run = create_batch_run(admin_ctx, d["id"], "2026-10").data
        added = add_files(admin_ctx, run["id"], [{"filename": "la.xlsx", "content": _other_xlsx_bytes()}])
        assert added.ok is True
        return d, run, added.data["added"][0]

    def test_assign_manual(self, batch_run_env, admin_ctx):
        from app.services.batch_run import assign_file, get_batch_run

        _d, run, f = self._setup_run_with_file(batch_run_env, admin_ctx)
        item_id = run["items"][0]["id"]
        res = assign_file(admin_ctx, f["id"], item_id)
        assert res.ok is True
        assert res.data["match_state"] == "MATCHED"
        assert res.data["match_by"] == "MANUAL"
        got = get_batch_run(admin_ctx, run["id"])
        assert len(got.data["items"][0]["files"]) == 1
        unassigned = assign_file(admin_ctx, f["id"], None)
        assert unassigned.data["match_state"] == "UNMATCHED"

    def test_ignore_file(self, batch_run_env, admin_ctx):
        from app.services.batch_run import get_batch_run, ignore_file

        _d, run, f = self._setup_run_with_file(batch_run_env, admin_ctx)
        res = ignore_file(admin_ctx, f["id"])
        assert res.ok is True
        assert res.data["match_state"] == "IGNORED"
        assert get_batch_run(admin_ctx, run["id"]).data["files"][0]["match_state"] == "IGNORED"

    def test_skip_item(self, batch_run_env, admin_ctx):
        from app.services.batch_run import get_batch_run, skip_item

        _d, run, _f = self._setup_run_with_file(batch_run_env, admin_ctx)
        item_id = run["items"][0]["id"]
        res = skip_item(admin_ctx, item_id, True)
        assert res.ok is True
        assert res.data["status"] == "SKIPPED"
        assert res.data["skip_reason"] == "USER_SKIP"
        assert res.data["skipped_by"] == "admin"
        back = skip_item(admin_ctx, item_id, False)
        assert back.data["status"] == "PENDING"
        assert get_batch_run(admin_ctx, run["id"]).data["items"][0]["skip_reason"] is None

    def test_set_param_override(self, batch_run_env, admin_ctx):
        from app.services.batch_run import get_batch_run, set_param_override

        _d, run, _f = self._setup_run_with_file(batch_run_env, admin_ctx)
        item_id = run["items"][0]["id"]
        res = set_param_override(admin_ctx, item_id, "p_ky", "202609")
        assert res.ok is True
        assert res.data["params_run_override"] == {"p_ky": "202609"}
        assert res.data["params_resolved"]["p_ky"] == "202609"
        assert res.data["params_resolved"]["p_from"] == "2026-10-01T00:00:00"
        cleared = set_param_override(admin_ctx, item_id, "p_ky", None)
        assert cleared.data["params_run_override"] == {}
        assert cleared.data["params_resolved"]["p_ky"] == "202610"
        got = get_batch_run(admin_ctx, run["id"])
        assert got.data["items"][0]["params_resolved"]["p_ky"] == "202610"

    def test_set_param_override_errors(self, batch_run_env, admin_ctx):
        from app.services.batch_run import set_param_override

        _d, run, _f = self._setup_run_with_file(batch_run_env, admin_ctx)
        item_id = run["items"][0]["id"]
        assert set_param_override(admin_ctx, item_id, "p_la", "x").code == "BATCH_PARAM_UNKNOWN"
        assert set_param_override(admin_ctx, item_id, "p_ky", "{ky.tu+99d}").code == "BATCH_FORMULA_INVALID"
