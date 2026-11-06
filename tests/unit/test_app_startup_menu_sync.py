"""Hồi quy: app khởi động phải đồng bộ menu từ code vào DB.

Người dùng áp patch task 21–28 nhưng không thấy menu báo cáo ở thanh bên:
`sync_menus_safely` chỉ được gọi trong test (conftest), chưa bao giờ được
gọi từ `create_app()` — DB thật vẫn thiếu 3 dòng menu báo cáo trong khi
thanh bên đọc cây menu từ DB. Test này dựng DB chưa hề đồng bộ menu rồi
khởi động app, kiểm tra 3 menu báo cáo xuất hiện trong RECON_MENU.

Lưu ý: `app/ui/app.py` gọi `create_app()` ngay ở mức module (dòng cuối
file) nên chỉ import module cũng đã chạy đồng bộ — test assert DB trống
TRƯỚC khi import, rồi gọi `create_app()` tường minh (phòng khi module đã
được import từ test khác trong cùng tiến trình).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from app.core.config import get_settings
from app.db.metadata import metadata, recon_menu


@pytest.fixture()
def unsynced_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "startup_menu_sync.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-startup-menu-sync-secret")
    get_settings.cache_clear()
    engine = create_engine(db_url)
    metadata.create_all(engine)
    return engine


def test_create_app_syncs_report_menus_into_db(unsynced_db) -> None:
    with unsynced_db.connect() as conn:
        assert conn.execute(select(recon_menu.c.CODE)).scalars().all() == []

    from app.ui.app import create_app

    create_app()

    with unsynced_db.connect() as conn:
        rows = {str(r["CODE"]): r for r in conn.execute(select(recon_menu)).mappings().all()}
    for code in ("report_center", "report_history", "report_admin"):
        assert code in rows, f"thiếu menu {code} sau khi khởi động app"
        assert rows[code]["IS_REMOVED"] == "N"
        assert rows[code]["IS_NEW"] == "Y"
