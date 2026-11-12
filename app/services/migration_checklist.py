"""Checklist stepper chuyển Oracle (task 63) — logic thuần, dùng chung cho
fake mode (mô phỏng phía client) và real mode (ghi tiến độ vào
RECON_METADATA_MIGRATION.CHECKLIST_JSON).

Trạng thái checklist (dict JSON-serializable):
{
  "mode": "fake" | "real",
  "migration_id": int | None,
  "target_ds_id": int,
  "target_name": str,
  "mode_label": "NO_TEMP" | "FULL" | "CONFIG_ONLY",
  "status": "idle" | "running" | "done" | "error",
  "error": str | None,
  "steps": [
    {"key", "label", "error": str | None,
     "items": [{"id", "label", "status": "pending|done|error", "detail": str | None}]},
  ],
  "report": {bảng: {source_rows, target_rows, matched, checksum_matched}} | None,
  "next_steps": [str] | None,
}

Trạng thái bước được suy ra từ các dòng con (step_status): error nếu bước
hoặc dòng con lỗi; done nếu mọi dòng xong; running nếu xong một phần;
pending nếu chưa dòng nào xong.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, cast

from sqlalchemy import Engine, select, update

from app.db.metadata import recon_metadata_migration

MIGRATION_STEP_KEYS = ["precheck", "maintenance", "create_schema", "copy", "verify", "finish", "manual"]
MIGRATION_STEP_LABELS = [
    "Kiểm tra trước",
    "Bật chế độ bảo trì",
    "Tạo schema đích",
    "Sao chép dữ liệu",
    "Đối chiếu toàn vẹn",
    "Hoàn tất",
    "Các bước làm tay",
]

MANUAL_STEP_KEY = "manual"

# (item_id, label) — 6 kiểm tra của precheck, theo đúng thứ tự trong
# app.services.metadata_migration.precheck.
PRECHECK_ITEMS: list[tuple[str, str]] = [
    ("admin", "Quyền ADMIN"),
    ("ds_exists", "Data Source đích tồn tại"),
    ("ds_not_current", "Đích khác cơ sở dữ liệu đang dùng"),
    ("no_busy_runs", "Không có run đang chờ hoặc đang chạy"),
    ("target_empty", "Schema đích trống"),
    ("estimate", "Ước tính số bảng/dòng cần chép"),
]

MAINTENANCE_ITEMS: list[tuple[str, str]] = [
    ("maintenance_on", "Ghi MAINTENANCE=Y vào RECON_APP_SETTING"),
    ("audit_log", "Ghi audit log bật chế độ bảo trì"),
    ("migration_row", "Tạo phiên migration (PROCESSING, 10%)"),
]

FINISH_ITEMS: list[tuple[str, str]] = [
    ("mark_done", "Ghi phiên migration DONE 100%"),
    ("save_report", "Lưu báo cáo đối chiếu"),
]

BACKFILL_ITEM_ID = "__backfill__"
BACKFILL_ITEM_LABEL = "Nối lại liên kết RECON_RUN ↔ RECON_BATCH_RUN_ITEM"


def checklist_item(item_id: str, label: str) -> dict[str, Any]:
    """Một dòng con trong checklist (dùng chung cho service ghi tiến độ)."""
    return {"id": item_id, "label": label, "status": "pending", "detail": None}


def _step(key: str, label: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"key": key, "label": label, "error": None, "items": items}


def new_checklist(
    *,
    mode: str,
    target_ds_id: int,
    target_name: str,
    mode_label: str,
    tables: list[dict[str, Any]],
    top_tables: list[str],
) -> dict[str, Any]:
    """Khung checklist 6 bước, mọi dòng con đang chờ.

    `tables`: [{"table", "rows"}] theo chế độ chép; `top_tables`: tên các bảng
    đối chiếu checksum (3 bảng lớn nhất).
    """
    total_rows = sum(int(t.get("rows", 0)) for t in tables)
    precheck_items = [
        checklist_item(item_id, label)
        for item_id, label in PRECHECK_ITEMS
    ]
    estimate_item = next(i for i in precheck_items if i["id"] == "estimate")
    estimate_item["label"] = f"Ước tính: {len(tables)} bảng, {total_rows:,} dòng".replace(",", ".")

    copy_items = [
        checklist_item(str(t["table"]), f"Sao chép bảng {t['table']}")
        for t in tables
    ]
    copy_items.append(checklist_item(BACKFILL_ITEM_ID, BACKFILL_ITEM_LABEL))

    return {
        "mode": mode,
        "migration_id": None,
        "target_ds_id": target_ds_id,
        "target_name": target_name,
        "mode_label": mode_label,
        "status": "idle",
        "error": None,
        "steps": [
            _step("precheck", MIGRATION_STEP_LABELS[0], precheck_items),
            _step("maintenance", MIGRATION_STEP_LABELS[1], [checklist_item(item_id, label) for item_id, label in MAINTENANCE_ITEMS]),
            _step("create_schema", MIGRATION_STEP_LABELS[2], [checklist_item("create_tables", "Tạo các bảng RECON_* trên Oracle")]),
            _step("copy", MIGRATION_STEP_LABELS[3], copy_items),
            _step("verify", MIGRATION_STEP_LABELS[4], [checklist_item(t, f"Checksum SHA256 bảng {t}") for t in top_tables]),
            _step("finish", MIGRATION_STEP_LABELS[5], [checklist_item(item_id, label) for item_id, label in FINISH_ITEMS]),
            # Bước 7 (task 65): các bước làm tay, chưa có item cho tới khi
            # 6 bước tự động xong (nạp từ next_steps lúc DONE).
            _step("manual", MIGRATION_STEP_LABELS[6], []),
        ],
        "report": None,
        "next_steps": None,
    }


def manual_items(next_steps: list[str]) -> list[dict[str, Any]]:
    """Item bước 7 từ danh sách bước làm tay: bỏ số thứ tự đầu dòng
    ("1. Dừng ứng dụng..." -> "Dừng ứng dụng...")."""
    items: list[dict[str, Any]] = []
    for i, raw in enumerate(next_steps, 1):
        label = re.sub(r"^\s*\d+\.\s*", "", str(raw)).strip()
        items.append(checklist_item(f"manual-{i}", label))
    return items


def populate_manual_items(checklist: dict[str, Any]) -> bool:
    """Nạp item bước 7 từ checklist["next_steps"] khi chưa có item nào.

    Trả True nếu vừa nạp; False nếu bước 7 đã có item (giữ nguyên tick
    user đã đánh) hoặc chưa có next_steps. Dùng lúc migration xong
    (fake tick cuối / real DONE) và khi chuẩn hóa checklist cũ.
    """
    step = _find_step(checklist, MANUAL_STEP_KEY)
    if step is None:
        return False
    if step.get("items"):
        return False
    next_steps = checklist.get("next_steps") or []
    if not next_steps:
        return False
    step["items"] = manual_items([str(s) for s in next_steps])
    return True


def ensure_manual_step(checklist: dict[str, Any] | None) -> bool:
    """Chuẩn hóa checklist cũ (6 bước) lên 7 bước: thêm bước manual trống
    nếu thiếu; chỉ nạp item manual từ next_steps khi 6 bước tự động đã
    xong (phiên DONE) — trước đó bước 7 phải có 0 item để hiện "Chờ".
    Trả True nếu checklist đổi, False nếu đã đủ 7 bước. None -> False."""
    if not isinstance(checklist, dict):
        return False
    steps: list[dict[str, Any]] = checklist.setdefault("steps", [])
    changed = False
    if _find_step(checklist, MANUAL_STEP_KEY) is None:
        steps.append(_step(MANUAL_STEP_KEY, MIGRATION_STEP_LABELS[6], []))
        changed = True
    if overall_status(checklist) == "done" and populate_manual_items(checklist):
        changed = True
    return changed


def set_item_status(
    checklist: dict[str, Any],
    step_key: str,
    item_id: str,
    status: str,
) -> bool:
    """Đặt trạng thái một dòng con (dùng cho tick manual): "done" hoặc
    "pending". Trả True nếu đổi, False nếu không tìm thấy item."""
    step = _find_step(checklist, step_key)
    if step is None:
        return False
    for item in step.get("items", []):
        if item.get("id") == item_id:
            if item.get("status") == status:
                return True
            item["status"] = status
            return True
    return False


def fake_next_steps() -> list[str]:
    """4 bước làm tay sau khi migration xong (bản fake: câu chung, không DSN)."""
    return [
        "1. Dừng ứng dụng web ReconHub và background worker.",
        "2. Cập nhật biến môi trường RECON_DB_URL trong file .env sang Oracle đích.",
        "3. Chạy lệnh kiểm tra schema: uv run poe db-migrate",
        "4. Khởi động lại dịch vụ web và worker để chạy hoàn toàn trên Oracle.",
    ]


def build_fake_checklist(precheck_data: dict[str, Any]) -> dict[str, Any]:
    """Xây checklist fake từ kết quả precheck thật: bước 1 xong, còn lại chờ.

    Báo cáo đối chiếu giả lấy số dòng ước tính làm cả nguồn lẫn đích.
    """
    tables = list(precheck_data.get("tables", []))
    top_tables = [t["table"] for t in sorted(tables, key=lambda t: int(t.get("rows", 0)), reverse=True)[:3]]
    state = new_checklist(
        mode="fake",
        target_ds_id=int(precheck_data.get("target_ds_id", 0)),
        target_name=str(precheck_data.get("target_name", "")),
        mode_label=str(precheck_data.get("mode", "NO_TEMP")),
        tables=tables,
        top_tables=top_tables,
    )
    mark_items_done(state, "precheck")
    # Dòng ước tính ghi rõ tổng số dòng đã đếm được.
    estimate_item = next(i for i in state["steps"][0]["items"] if i["id"] == "estimate")
    estimate_item["detail"] = (
        f"Tổng {int(precheck_data.get('total_rows', 0)):,} dòng".replace(",", ".")
    )
    state["report"] = {
        str(t["table"]): {
            "source_rows": int(t.get("rows", 0)),
            "target_rows": int(t.get("rows", 0)),
            "matched": True,
            "checksum_matched": str(t["table"]) in top_tables,
        }
        for t in tables
    }
    state["next_steps"] = fake_next_steps()
    state["status"] = "running"
    return state


def step_status(step: dict[str, Any]) -> str:
    """Trạng thái bước suy ra từ các dòng con."""
    if step.get("error"):
        return "error"
    items = step.get("items", [])
    if any(i.get("status") == "error" for i in items):
        return "error"
    if not items:
        return "pending"
    if all(i.get("status") == "done" for i in items):
        return "done"
    if any(i.get("status") in ("done", "running") for i in items):
        return "running"
    return "pending"


def overall_status(state: dict[str, Any]) -> str:
    """Trạng thái chung suy ra từ các bước.

    Bước 7 manual không tính vào hoàn thành (task 65): 6 bước tự động
    xong là migration xong, dù các bước làm tay còn chờ user tick."""
    if state.get("error"):
        return "error"
    steps = [s for s in state.get("steps", []) if s.get("key") != MANUAL_STEP_KEY]
    if any(step_status(s) == "error" for s in steps):
        return "error"
    if steps and all(step_status(s) == "done" for s in steps):
        return "done"
    if any(step_status(s) in ("running", "done") for s in steps):
        return "running"
    return "idle"


def count_pending(state: dict[str, Any]) -> int:
    """Số dòng con chưa xong."""
    return sum(
        1
        for step in state.get("steps", [])
        for item in step.get("items", [])
        if item.get("status") != "done"
    )


def step_counts(step: dict[str, Any]) -> tuple[int, int]:
    """(số dòng xong, tổng số dòng) của một bước (task 64)."""
    items = step.get("items", [])
    done = sum(1 for i in items if i.get("status") == "done")
    return done, len(items)


def running_item(step: dict[str, Any]) -> dict[str, Any] | None:
    """Dòng đang làm của một bước = dòng chờ đầu tiên (task 64, D1).

    Bảng chép theo đúng thứ tự nên dòng chờ đầu tiên chính là item đang
    làm. Người gọi chỉ dùng cho bước đang chạy; trả None khi bước không
    còn dòng chờ (đã xong hết).
    """
    for item in step.get("items", []):
        if item.get("status") == "pending":
            return cast("dict[str, Any]", item)
    return None


def running_step_index(state: dict[str, Any]) -> int:
    """Index bước đang chạy/lỗi; nếu chưa có thì bước chờ đầu tiên; nếu
    mọi bước xong thì bước cuối (bước 7 manual sau khi 6 bước xong).
    Dùng làm bước chọn mặc định.

    Bước chưa có dòng con nào (vd bước đối chiếu trước khi biết top-3
    bảng) được bỏ qua khi tìm bước chờ — nó không có việc gì để làm.
    """
    steps = state.get("steps", [])
    for i, step in enumerate(steps):
        if step_status(step) in ("running", "error"):
            return i
    for i, step in enumerate(steps):
        if step_status(step) == "pending" and step.get("items"):
            return i
    return len(steps) - 1 if steps else 0


def error_step_index(state: dict[str, Any]) -> int | None:
    """Index bước lỗi đầu tiên, None nếu không có bước nào lỗi."""
    for i, step in enumerate(state.get("steps", [])):
        if step_status(step) == "error":
            return i
    return None


def _find_step(state: dict[str, Any], step_key: str) -> dict[str, Any] | None:
    steps: list[dict[str, Any]] = state.get("steps", [])
    for step in steps:
        if step.get("key") == step_key:
            return step
    return None


def mark_item_done(
    checklist: dict[str, Any],
    step_key: str,
    item_id: str,
    detail: str | None = None,
) -> None:
    """Đánh dấu một dòng con đã xong (đổi tại chỗ)."""
    step = _find_step(checklist, step_key)
    if step is None:
        return
    for item in step.get("items", []):
        if item.get("id") == item_id:
            item["status"] = "done"
            if detail is not None:
                item["detail"] = detail
            return


def mark_items_done(checklist: dict[str, Any], step_key: str) -> None:
    """Đánh dấu mọi dòng con của một bước đã xong (đổi tại chỗ)."""
    step = _find_step(checklist, step_key)
    if step is None:
        return
    for item in step.get("items", []):
        item["status"] = "done"


def set_step_items(
    checklist: dict[str, Any],
    step_key: str,
    items: list[dict[str, Any]],
) -> None:
    """Thay toàn bộ dòng con của một bước (dùng cho bước verify: top-3 bảng
    chỉ biết sau khi chép xong)."""
    step = _find_step(checklist, step_key)
    if step is not None:
        step["items"] = items


def mark_step_error(checklist: dict[str, Any], step_key: str, message: str) -> None:
    """Đánh dấu một bước lỗi (đổi tại chỗ) + trạng thái chung thành error."""
    step = _find_step(checklist, step_key)
    if step is not None:
        step["error"] = message
    checklist["error"] = message
    checklist["status"] = "error"


def refresh_status(checklist: dict[str, Any]) -> None:
    """Tính lại trạng thái chung từ các bước (đổi tại chỗ)."""
    checklist["status"] = overall_status(checklist)


def advance_fake_checklist(state: dict[str, Any], per_tick: int = 4) -> dict[str, Any]:
    """Thuần: xong thêm tối đa `per_tick` dòng con đang chờ, theo thứ tự
    bước rồi thứ tự dòng. Không sửa state gốc, trả state mới.

    Bước 7 manual không tự chạy (task 65): tick fake bỏ qua nó; khi
    6 bước tự động xong thì nạp item manual từ next_steps để user tick.
    """
    new_state = copy.deepcopy(state)
    if overall_status(new_state) == "done":
        populate_manual_items(new_state)
        return new_state
    remaining = per_tick
    for step in new_state.get("steps", []):
        if step.get("key") == MANUAL_STEP_KEY:
            continue
        if remaining <= 0:
            break
        for item in step.get("items", []):
            if remaining <= 0:
                break
            if item.get("status") == "pending":
                item["status"] = "done"
                remaining -= 1
    if overall_status(new_state) == "done":
        populate_manual_items(new_state)
    refresh_status(new_state)
    return new_state


def checklist_to_json(checklist: dict[str, Any]) -> str:
    return json.dumps(checklist, ensure_ascii=False)


def checklist_from_json(raw: str | dict[str, Any] | None) -> dict[str, Any] | None:
    """Parse checklist từ JSON.

    Cột CHECKLIST_JSON dùng kiểu JsonText nên khi đọc qua SQLAlchemy đã
    thành dict; khi đọc chuỗi thô (ví dụ từ SQLite trực tiếp) thì parse.
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw:
        return None
    try:
        loaded: Any = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if isinstance(loaded, dict):
        return cast("dict[str, Any]", loaded)
    return None


def save_checklist(engine: Engine, migration_id: int, checklist: dict[str, Any]) -> None:
    """Ghi checklist vào bản ghi migration (cột JsonText tự serialize dict)."""
    with engine.begin() as conn:
        conn.execute(
            update(recon_metadata_migration)
            .where(recon_metadata_migration.c.ID == migration_id)
            .values(CHECKLIST_JSON=checklist)
        )


def load_checklist(engine: Engine, migration_id: int) -> dict[str, Any] | None:
    """Đọc checklist từ bản ghi migration, None nếu chưa có."""
    with engine.connect() as conn:
        raw = conn.execute(
            select(recon_metadata_migration.c.CHECKLIST_JSON).where(
                recon_metadata_migration.c.ID == migration_id
            )
        ).scalar()
    return checklist_from_json(raw)
