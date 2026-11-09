"""Tests cho Schema Inspector — Bước 1 task 31 (test viết trước)."""

from __future__ import annotations

import copy
import json

from sqlalchemy import create_engine

from app.db.metadata import metadata
from app.services import schema_inspector as si


def _manifest() -> dict:
    return si.build_manifest()


def _tables(manifest: dict) -> dict[str, dict]:
    return {t["name"]: t for t in manifest["tables"]}


# --- Extraction từ model -------------------------------------------------


def test_extract_model_schema_has_43_tables():
    tables = si.extract_model_schema()
    assert len(tables) == 43
    names = {t["name"] for t in tables}
    assert names == set(metadata.tables.keys())
    assert [t["name"] for t in tables] == sorted(names)


def test_extract_columns_datatype_nullable_default_spot_check():
    tables = _tables(_manifest())
    run = tables["RECON_RUN"]
    cols = {c["name"]: c for c in run["columns"]}
    assert cols["TEMPLATE_ID"]["type"] == "INTEGER"
    assert cols["TEMPLATE_ID"]["nullable"] is False
    assert cols["STATUS"]["type"] == "VARCHAR(10)"
    assert cols["STATUS"]["default"] == "QUEUED"
    assert cols["P_FROM"]["type"] == "DATETIME"
    assert cols["P_FROM"]["nullable"] is False
    assert cols["ERROR_MSG"]["type"] == "VARCHAR(2000)"
    assert cols["ERROR_MSG"]["nullable"] is True
    assert cols["ERROR_MSG"]["default"] is None

    template = tables["RECON_TEMPLATE"]
    tcols = {c["name"]: c for c in template["columns"]}
    assert tcols["CODE"]["type"] == "VARCHAR(60)"
    assert tcols["CODE"]["unique"] is True
    assert tcols["STATUS"]["default"] == "DRAFT"

    report = tables["RECON_REPORT"]
    rcols = {c["name"]: c for c in report["columns"]}
    assert rcols["CODE"]["type"] == "VARCHAR(60)"
    assert rcols["OWNER"]["nullable"] is False
    # DecimalText / JsonText render qua SQLite dialect.
    assert (
        tables["RECON_EXCEL_LOAD"]["columns"][
            [c["name"] for c in tables["RECON_EXCEL_LOAD"]["columns"]].index("CONTROL_TOTAL_FILE")
        ]["type"]
        == "VARCHAR(60)"
    )
    assert (
        tables["RECON_RUN"]["columns"][[c["name"] for c in tables["RECON_RUN"]["columns"]].index("PARAMS_JSON")]["type"]
        == "TEXT"
    )


def test_extract_primary_keys():
    tables = _tables(_manifest())
    assert tables["RECON_RUN"]["primary_key"] == ["ID"]
    assert tables["RECON_USER_ROLE"]["primary_key"] == ["USER_ID", "ROLE_ID"]
    assert tables["RECON_EXCEL_ROW"]["primary_key"] == ["LOAD_ID", "SOURCE_FILE_ID", "EXCEL_ROW_NO"]
    assert tables["RECON_MENU"]["primary_key"] == ["CODE"]
    run_cols = {c["name"]: c for c in tables["RECON_RUN"]["columns"]}
    assert run_cols["ID"]["primary_key"] is True
    assert run_cols["STATUS"]["primary_key"] is False


def test_extract_foreign_keys_with_constraint_name():
    tables = _tables(_manifest())
    run_fks = {fk["column"]: fk for fk in tables["RECON_RUN"]["foreign_keys"]}
    assert run_fks["FILE_ID"]["references_table"] == "RECON_FILE"
    assert run_fks["FILE_ID"]["references_column"] == "ID"
    assert run_fks["FILE_ID"]["constraint_name"] == "fk_RECON_RUN_FILE_ID_RECON_FILE"
    assert run_fks["DATA_SOURCE_ID"]["references_table"] == "RECON_DATA_SOURCE"
    user_role_fks = {fk["column"]: fk for fk in tables["RECON_USER_ROLE"]["foreign_keys"]}
    assert user_role_fks["USER_ID"]["references_table"] == "RECON_USER"
    assert user_role_fks["ROLE_ID"]["references_table"] == "RECON_ROLE"
    # Cột không có FK thì foreign_key None.
    run_cols = {c["name"]: c for c in tables["RECON_RUN"]["columns"]}
    assert run_cols["STATUS"]["foreign_key"] is None
    assert run_cols["FILE_ID"]["foreign_key"] == "RECON_FILE.ID"


def test_extract_unique_constraints():
    tables = _tables(_manifest())
    user_uqs = tables["RECON_USER"]["unique_constraints"]
    assert any(uq["columns"] == ["USERNAME"] for uq in user_uqs)
    ds_uqs = tables["RECON_DATA_SOURCE"]["unique_constraints"]
    assert any(uq["name"] == "uq_recon_data_source_name_env" and uq["columns"] == ["NAME", "ENV"] for uq in ds_uqs)
    issue_uqs = tables["RECON_ISSUE"]["unique_constraints"]
    assert any(uq["columns"] == ["TEMPLATE_ID", "PROFILE_CODE", "KEY_HASH"] for uq in issue_uqs)


def test_extract_indexes():
    tables = _tables(_manifest())
    run_idx = {ix["name"]: ix for ix in tables["RECON_RUN"]["indexes"]}
    assert run_idx["ix_recon_run_batch"]["columns"] == ["BATCH_RUN_ID", "STATUS"]
    assert run_idx["ix_recon_run_batch"]["unique"] is False
    log_idx = {ix["name"]: ix for ix in tables["RECON_LOGIN_LOG"]["indexes"]}
    assert log_idx["ix_recon_login_log_username_created_at"]["columns"] == ["USERNAME", "CREATED_AT"]


# --- Domain mapping ------------------------------------------------------


def test_domain_mapping_counts():
    tables = _tables(_manifest())
    counts: dict[str, int] = {}
    for t in tables.values():
        counts[t["domain"]] = counts.get(t["domain"], 0) + 1
    assert counts == {"core": 10, "recon": 19, "report": 11, "admin": 3}
    assert "other" not in counts
    assert _manifest()["warnings"] == []


def test_domain_for_table_spot_check():
    assert si.domain_for_table("RECON_USER") == ("core", "Core")
    assert si.domain_for_table("RECON_MENU_GROUP") == ("core", "Core")
    assert si.domain_for_table("RECON_METADATA_MIGRATION") == ("core", "Core")
    assert si.domain_for_table("RECON_RUN") == ("recon", "Đối soát")
    assert si.domain_for_table("RECON_BATCH_DEF") == ("recon", "Đối soát")
    assert si.domain_for_table("RECON_TEMPLATE") == ("recon", "Đối soát")
    assert si.domain_for_table("RECON_REPORT") == ("report", "Báo cáo")
    assert si.domain_for_table("RECON_RPT_PARAM") == ("report", "Báo cáo")
    assert si.domain_for_table("RECON_RPT_LOV_CACHE") == ("report", "Báo cáo")
    assert si.domain_for_table("RECON_DATA_SOURCE") == ("admin", "Quản trị")
    assert si.domain_for_table("RECON_LOOKUP_CODE") == ("admin", "Quản trị")
    assert si.domain_for_table("SOMETHING_ELSE") == ("other", "Khác")
    assert si.domain_for_table("FOO") == ("other", "Khác")


def test_table_descriptions_present():
    assert si.TABLE_DESCRIPTIONS["RECON_RUN"] == "Lần chạy đối soát"
    assert si.TABLE_DESCRIPTIONS["RECON_TEMPLATE"]
    tables = _tables(_manifest())
    assert tables["RECON_RUN"]["description"] == "Lần chạy đối soát"
    assert tables["RECON_RUN"]["domain_label"] == "Đối soát"


# --- Manifest ------------------------------------------------------------


def test_build_manifest_header_and_version():
    manifest = _manifest()
    assert manifest["generated"] is True
    assert manifest["generated_at"]
    assert manifest["generator"] == "schema-introspect"
    assert manifest["database"] == "sqlite"
    assert manifest["schema"] == "main"
    assert manifest["version"] == "0006_batch_run"
    tables = _tables(manifest)
    assert tables["RECON_USER"]["source"] == {"model": "app/db/metadata.py", "migration": "0001_init"}
    assert tables["RECON_LOOKUP_CODE"]["source"]["migration"] == "0002_add_lookup_tables"
    assert tables["RECON_MENU"]["source"]["migration"] == "0003_menu_permission"
    assert tables["RECON_REPORT"]["source"]["migration"] == "0004_reporting_core"
    assert tables["RECON_BATCH_DEF"]["source"]["migration"] == "0006_batch_run"
    assert tables["RECON_RPT_EXPORT"]["source"]["migration"] == "0004_reporting_core"


def test_manifest_deterministic():
    first = si.normalize_manifest(si.build_manifest())
    second = si.normalize_manifest(si.build_manifest())
    assert first == second
    # normalize bỏ generated_at (volatile).
    assert "generated_at" not in si.normalize_manifest(si.build_manifest())
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_inspect_live_db_matches_model(tmp_path):
    db_path = tmp_path / "live.db"
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        metadata.create_all(engine)
        live = si.inspect_live_db(engine)
        model = si.extract_model_schema()
        assert [t["name"] for t in live] == [t["name"] for t in model]
        live_map = {t["name"]: t for t in live}
        model_map = {t["name"]: t for t in model}
        for name in model_map:
            assert [c["name"] for c in live_map[name]["columns"]] == [c["name"] for c in model_map[name]["columns"]]
            assert live_map[name]["primary_key"] == model_map[name]["primary_key"]
            live_fks = {
                (fk["column"], fk["references_table"], fk["references_column"]) for fk in live_map[name]["foreign_keys"]
            }
            model_fks = {
                (fk["column"], fk["references_table"], fk["references_column"])
                for fk in model_map[name]["foreign_keys"]
            }
            assert live_fks == model_fks
            assert live_map[name]["indexes"] == model_map[name]["indexes"] or (
                {tuple(sorted(ix["columns"])) for ix in live_map[name]["indexes"]}
                == {tuple(sorted(ix["columns"])) for ix in model_map[name]["indexes"]}
            )
    finally:
        engine.dispose()


# --- History -------------------------------------------------------------


def test_seed_history_has_43_table_created():
    events = si.seed_history_from_migrations()
    created = [e for e in events if e["change_type"] == "TABLE_CREATED"]
    assert len(created) == 43
    assert len({e["entity"] for e in created}) == 43
    assert {e["entity"] for e in created} == set(metadata.tables.keys())
    for e in created:
        assert e["after"] == "TABLE"
        assert e["before"] is None
        assert e["task_id"] is None
        assert e["timestamp"]
    # Revision đúng theo file migration tạo bảng.
    by_entity = {e["entity"]: e for e in created}
    assert by_entity["RECON_USER"]["migration_id"] == "0001_init"
    assert by_entity["RECON_LOOKUP_TYPE"]["migration_id"] == "0002_add_lookup_tables"
    assert by_entity["RECON_ROLE"]["migration_id"] == "0003_menu_permission"
    assert by_entity["RECON_REPORT"]["migration_id"] == "0004_reporting_core"
    assert by_entity["RECON_BATCH_RUN"]["migration_id"] == "0006_batch_run"


def test_seed_history_column_events():
    events = si.seed_history_from_migrations()
    added = {(e["entity"], e["change_type"]) for e in events}
    assert ("RECON_RPT_EXPORT.LOCKED_BY", "COLUMN_ADDED") in added
    assert ("RECON_RPT_EXPORT.LOCKED_AT", "COLUMN_ADDED") in added
    assert ("RECON_RPT_EXPORT.HEARTBEAT_AT", "COLUMN_ADDED") in added
    assert ("RECON_RUN.BATCH_RUN_ID", "COLUMN_ADDED") in added
    assert ("RECON_RUN.BATCH_RUN_ITEM_ID", "COLUMN_ADDED") in added
    assert ("RECON_EXCEL_LOAD.FILE_SET_HASH", "COLUMN_ADDED") in added
    assert ("RECON_USER_ROLE.ROLE_ID", "COLUMN_ADDED") in added
    assert ("RECON_USER_ROLE.ROLE", "COLUMN_REMOVED") in added
    assert ("RECON_EXCEL_LOAD.FILE_SET_HASH", "COLUMN_CHANGED") in added
    # Chỉ parse upgrade(): downgrade() không sinh event ngược.
    assert ("RECON_RPT_EXPORT.LOCKED_BY", "COLUMN_REMOVED") not in added
    locked = [e for e in events if e["entity"] == "RECON_RPT_EXPORT.LOCKED_BY"][0]
    assert locked["after"] == "VARCHAR(60), nullable=True"
    assert locked["migration_id"] == "0005_export_claim"


def test_append_history_events_diff():
    prev = si.build_manifest()
    new = copy.deepcopy(prev)
    # Thêm bảng, xóa bảng, thêm cột, đổi kiểu, đổi nullable, đổi PK.
    tables = _tables(new)
    tables["RECON_FAKE_NEW"] = copy.deepcopy(tables["RECON_RUN"])
    tables["RECON_FAKE_NEW"]["name"] = "RECON_FAKE_NEW"
    del tables["RECON_PURGE_LOG"]
    run_cols = {c["name"]: c for c in tables["RECON_RUN"]["columns"]}
    run_cols["STATUS"]["type"] = "VARCHAR(20)"
    run_cols["ERROR_MSG"]["nullable"] = False
    tables["RECON_RUN"]["columns"].append(
        {
            "name": "NEW_COL",
            "type": "INTEGER",
            "nullable": True,
            "primary_key": False,
            "foreign_key": None,
            "unique": False,
            "default": None,
        }
    )
    tables["RECON_RUN"]["primary_key"] = ["ID", "STATUS"]
    new["tables"] = [tables[name] for name in sorted(tables)]
    events = si.append_history_events(prev, new, "0006_batch_run")
    by_key = {(e["entity"], e["change_type"]): e for e in events}
    assert ("RECON_FAKE_NEW", "TABLE_CREATED") in by_key
    assert ("RECON_PURGE_LOG", "TABLE_DROPPED") in by_key
    assert ("RECON_RUN.NEW_COL", "COLUMN_ADDED") in by_key
    assert ("RECON_RUN.STATUS", "COLUMN_CHANGED") in by_key
    assert ("RECON_RUN.ERROR_MSG", "COLUMN_CHANGED") in by_key
    assert ("RECON_RUN", "PK_CHANGED") in by_key
    for e in events:
        assert e["migration_id"] == "0006_batch_run"
        assert e["task_id"] is None
        assert e["timestamp"]


def test_append_history_events_empty_diff():
    manifest = si.build_manifest()
    assert si.append_history_events(manifest, copy.deepcopy(manifest), "0006_batch_run") == []


def test_generate_all_writes_and_rerun_no_fake_diff(tmp_path):
    out_dir = tmp_path / "data-model"
    si.generate_all(out_dir)
    manifest_path = out_dir / "schema-manifest.json"
    history_path = out_dir / "schema-history.json"
    assert manifest_path.exists()
    assert history_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["tables"]) == 43
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert len([e for e in history if e["change_type"] == "TABLE_CREATED"]) == 43
    first_manifest_text = manifest_path.read_text(encoding="utf-8")
    first_history_text = history_path.read_text(encoding="utf-8")
    second = si.generate_all(out_dir)
    assert second["manifest_changed"] is False
    assert second["history_changed"] is False
    assert manifest_path.read_text(encoding="utf-8") == first_manifest_text
    assert history_path.read_text(encoding="utf-8") == first_history_text
    assert len(json.loads(first_history_text)) == len(json.loads(history_path.read_text(encoding="utf-8")))
