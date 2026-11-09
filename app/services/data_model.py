"""Service Data Model Explorer — đọc manifest/history + drift + đồng bộ.

Đọc 2 artifact JSON đã commit trong ``docs/data-model`` (không đọc model
trực tiếp lúc mở page) và kiểm tra drift live qua
:func:`app.services.schema_drift.check_live_drift`. Chỉ đọc metadata,
không expose dữ liệu dòng, secret hay connection string.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.services import service
from app.services.perm import requires_menu
from app.services.schema_drift import check_live_drift
from app.services.schema_inspector import generate_all, normalize_manifest

DATA_MODEL_DIR = Path(__file__).resolve().parents[2] / "docs" / "data-model"
MANIFEST_FILE = "schema-manifest.json"
HISTORY_FILE = "schema-history.json"


def load_manifest(data_dir: Path | str | None = None) -> dict[str, Any]:
    """Đọc manifest đã commit. Lỗi file -> FileNotFoundError/JSONDecodeError."""
    directory = Path(data_dir) if data_dir is not None else DATA_MODEL_DIR
    text = (directory / MANIFEST_FILE).read_text(encoding="utf-8")
    manifest = json.loads(text)
    if not isinstance(manifest, dict):
        raise ValueError("Schema manifest không đúng định dạng")
    return manifest


def load_history(data_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Đọc history đã commit (bare JSON list, không có wrapper)."""
    directory = Path(data_dir) if data_dir is not None else DATA_MODEL_DIR
    text = (directory / HISTORY_FILE).read_text(encoding="utf-8")
    history = json.loads(text)
    if not isinstance(history, list):
        raise ValueError("Schema history không đúng định dạng")
    return history


def _live_drift() -> dict[str, Any]:
    """Kiểm tra drift live, tự dispose engine mình tạo.

    ``get_recon_engine`` nằm ở namespace module để test monkeypatch được.
    """
    engine = get_recon_engine()
    try:
        return check_live_drift(engine=engine)
    finally:
        engine.dispose()


def _manifest_diff_counts(prev: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, int]:
    """Đếm bảng/cột thay đổi giữa 2 manifest đã normalize."""
    if prev is None:
        tables = len(new.get("tables", []))
        columns = sum(len(t.get("columns", [])) for t in new.get("tables", []))
        return {"tables": tables, "columns": columns}
    prev_tables = {t["name"]: t for t in prev.get("tables", [])}
    new_tables = {t["name"]: t for t in new.get("tables", [])}
    tables_changed = 0
    columns_changed = 0
    for name in sorted(set(prev_tables) | set(new_tables)):
        old = prev_tables.get(name)
        new_table = new_tables.get(name)
        if old is None and new_table is not None:
            tables_changed += 1
            columns_changed += len(new_table.get("columns", []))
        elif new_table is None and old is not None:
            tables_changed += 1
            columns_changed += len(old.get("columns", []))
        elif old is not None and new_table is not None:
            if normalize_manifest({"tables": [old]}) != normalize_manifest({"tables": [new_table]}):
                tables_changed += 1
            old_cols = {c["name"]: c for c in old.get("columns", [])}
            new_cols = {c["name"]: c for c in new_table.get("columns", [])}
            for col_name in sorted(set(old_cols) | set(new_cols)):
                if old_cols.get(col_name) != new_cols.get(col_name):
                    columns_changed += 1
    return {"tables": tables_changed, "columns": columns_changed}


@service
@requires_menu("data_model")
def get_data_model(ctx: Ctx, data_dir: Path | str | None = None) -> dict[str, Any]:
    """Trả manifest + history + drift live cho page Mô hình dữ liệu."""
    _ = ctx
    manifest = load_manifest(data_dir)
    history = load_history(data_dir)
    drift = _live_drift()
    tables = manifest.get("tables", [])
    return {
        "manifest": manifest,
        "history": history,
        "drift": drift,
        "counts": {
            "tables": len(tables),
            "columns": sum(len(t.get("columns", [])) for t in tables),
            "relationships": sum(len(t.get("foreign_keys", [])) for t in tables),
        },
    }


@service
@requires_menu("data_model")
def sync_schema(ctx: Ctx, out_dir: Path | str | None = None) -> dict[str, Any]:
    """Chạy inspector in-process, regenerate manifest/history, kiểm tra drift.

    Chỉ ghi 2 artifact JSON trong ``docs/data-model`` (không git add/commit/
    push). Nhanh trên SQLite vì manifest suy từ model + migration, drift chỉ
    inspect database của app.
    """
    _ = ctx
    directory = Path(out_dir) if out_dir is not None else DATA_MODEL_DIR
    prev_manifest: dict[str, Any] | None = None
    manifest_path = directory / MANIFEST_FILE
    if manifest_path.exists():
        prev_manifest = load_manifest(directory)
    result = generate_all(directory)
    new_manifest = result["manifest"]
    drift = _live_drift()
    return {
        "changed": _manifest_diff_counts(prev_manifest, new_manifest),
        "drift_status": drift["status"],
        "drifts": drift["drifts"],
        "manifest_changed": bool(result["manifest_changed"]),
        "history_changed": bool(result["history_changed"]),
        "manifest": new_manifest,
        "history": result["history"],
    }
