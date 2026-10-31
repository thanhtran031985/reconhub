from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection

from app.db.metadata import recon_audit_log


def _mask_sensitive(data: Any) -> Any:
    """Ẩn toàn bộ trường chứa mật khẩu hoặc khóa bí mật trước khi lưu audit."""
    if data is None:
        return None
    if isinstance(data, dict):
        masked: dict[str, Any] = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("password", "secret", "token")):
                masked[k] = "***"
            elif isinstance(v, (dict, list)):
                masked[k] = _mask_sensitive(v)
            elif isinstance(v, datetime):
                masked[k] = v.isoformat()
            else:
                masked[k] = v
        return masked
    elif isinstance(data, list):
        return [_mask_sensitive(item) for item in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    return data


def write_audit_log(
    conn: Connection,
    entity: str,
    entity_id: str | int,
    action: str,
    actor: str,
    old_data: dict[str, Any] | None = None,
    new_data: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> None:
    """Ghi nhật ký kiểm toán vào RECON_AUDIT_LOG trong cùng transaction."""
    if now is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

    masked_old = _mask_sensitive(old_data)
    masked_new = _mask_sensitive(new_data)

    conn.execute(
        recon_audit_log.insert().values(
            ENTITY=entity.upper(),
            ENTITY_ID=str(entity_id),
            ACTION=action.upper(),
            OLD_JSON=masked_old,
            NEW_JSON=masked_new,
            ACTOR=actor,
            CREATED_AT=now,
        )
    )
