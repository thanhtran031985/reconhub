from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_file,
    recon_run,
    recon_run_summary,
    recon_template,
    recon_template_version,
    recon_user,
    recon_user_role,
)
from app.ui.pages.history import (
    format_date_range,
    format_short_dt,
    handle_confirm_bulk_purge,
    render_bulk_alert,
    render_bulk_purge_modal,
    render_filter_bar,
    render_header,
    render_runs_table,
    update_history_table,
)


@pytest.fixture
def history_env(tmp_path, monkeypatch):
    db_file = tmp_path / "history_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        # Admin user
        res_adm = conn.execute(
            recon_user.insert().values(
                USERNAME="admin_test",
                FULL_NAME="Quản Trị Viên",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        adm_id = res_adm.inserted_primary_key[0]
        conn.execute(recon_user_role.insert().values(USER_ID=adm_id, ROLE=Role.ADMIN.value, CREATED_AT=now))

        # Operator user
        res_op = conn.execute(
            recon_user.insert().values(
                USERNAME="op_test",
                FULL_NAME="Vận Hành Viên",
                PASSWORD_HASH=hash_password("op123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        op_id = res_op.inserted_primary_key[0]
        conn.execute(recon_user_role.insert().values(USER_ID=op_id, ROLE=Role.OPERATOR.value, CREATED_AT=now))

        # Data Source
        res_ds = conn.execute(
            recon_data_source.insert().values(
                NAME="ORCL_TEST",
                ENV="TEST",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="XEPDB1",
                USERNAME="recon_test",
                PASSWORD_ENC="dummy",
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="admin_test",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ds_id = res_ds.inserted_primary_key[0]

        # File
        res_file = conn.execute(
            recon_file.insert().values(
                ORIGINAL_NAME="test_file.xlsx",
                SIZE_BYTES=1024 * 1024 * 2,  # 2 MB
                SHA256="dummy_hash_12345",
                STORAGE_PATH="files/test_file.xlsx",
                UPLOADED_BY="op_test",
                UPLOADED_AT=now,
            )
        )
        file_id = res_file.inserted_primary_key[0]

        # Template
        res_tpl = conn.execute(
            recon_template.insert().values(
                CODE="DTP",
                NAME="Hóa đơn tác nghiệp DTP",
                OWNER="admin_test",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        tpl_id = res_tpl.inserted_primary_key[0]

        conn.execute(
            recon_template_version.insert().values(
                TEMPLATE_ID=tpl_id,
                VERSION=1,
                CONFIG_JSON={"fields": []},
                STATUS="ACTIVE",
                CREATED_BY="admin_test",
                CREATED_AT=now,
            )
        )

        # Run 101: Done, unchecked, unpurged
        conn.execute(
            recon_run.insert().values(
                ID=101,
                TEMPLATE_ID=tpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="DEFAULT",
                FILE_ID=file_id,
                DATA_SOURCE_ID=ds_id,
                P_FROM=datetime(2026, 2, 1, 0, 0, 0),
                P_TO=datetime(2026, 2, 5, 23, 59, 59),
                STATUS="DONE",
                STAGE=5,
                PROGRESS_PCT=100,
                CREATED_BY="op_test",
                CREATED_AT=now,
                FINISHED_AT=now,
            )
        )

        conn.execute(
            recon_run_summary.insert().values(
                RUN_ID=101,
                EXCEL_ROWS_READ=100,
                DB_ROWS=100,
                EXCEL_GROUPS=10,
                DB_GROUPS=10,
                CNT_MATCHED=8,
                CNT_MISMATCH=2,
                CNT_MISSING_IN_DB=0,
                CNT_MISSING_IN_EXCEL=0,
                EXCEL_ROWS_INVALID=0,
            )
        )

        # Run 102: Done, checked, already temp purged
        conn.execute(
            recon_run.insert().values(
                ID=102,
                TEMPLATE_ID=tpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="BY_DATE",
                FILE_ID=file_id,
                DATA_SOURCE_ID=ds_id,
                P_FROM=datetime(2026, 2, 1, 0, 0, 0),
                P_TO=datetime(2026, 2, 5, 23, 59, 59),
                STATUS="DONE",
                STAGE=5,
                PROGRESS_PCT=100,
                CHECKED_BY="op_test",
                CHECKED_AT=now,
                TEMP_PURGED_BY="admin_test",
                TEMP_PURGED_AT=now,
                CREATED_BY="op_test",
                CREATED_AT=now,
                FINISHED_AT=now,
            )
        )

        conn.execute(
            recon_run_summary.insert().values(
                RUN_ID=102,
                EXCEL_ROWS_READ=50,
                DB_ROWS=50,
                EXCEL_GROUPS=5,
                DB_GROUPS=5,
                CNT_MATCHED=5,
                CNT_MISMATCH=0,
                CNT_MISSING_IN_DB=0,
                CNT_MISSING_IN_EXCEL=0,
                EXCEL_ROWS_INVALID=0,
            )
        )

    return {
        "engine": engine,
        "admin_ctx": Ctx(user_id=adm_id, username="admin_test", full_name="Quản Trị Viên", roles=[Role.ADMIN]),
        "op_ctx": Ctx(user_id=op_id, username="op_test", full_name="Vận Hành Viên", roles=[Role.OPERATOR]),
        "tpl_id": tpl_id,
        "run1_id": 101,
        "run2_id": 102,
    }


def test_format_helpers():
    assert format_short_dt(None) == "—"
    assert format_short_dt("2026-02-01T15:30:00") == "01/02 15:30"
    rng = format_date_range("2026-02-01T00:00:00", "2026-02-05T23:59:59")
    assert "01/02 00:00 → 05/02 23:59" in rng


def test_render_header_and_filters():
    hd = render_header(count=42, month_year="tháng 10/2026")
    assert hd is not None
    assert "42 run trong tháng 10/2026" in str(hd)

    fb = render_filter_bar([], [])
    assert fb is not None


def test_bulk_alert():
    # Không phải Admin -> ẩn
    alert_non_adm = render_bulk_alert(5, is_admin=False)
    assert alert_non_adm.style == {"display": "none"}

    # Admin nhưng count = 0 -> ẩn
    alert_zero = render_bulk_alert(0, is_admin=True)
    assert alert_zero.style == {"display": "none"}

    # Admin và count > 0 -> hiện
    alert_active = render_bulk_alert(3, is_admin=True)
    style = getattr(alert_active, "style", None)
    assert style is None or style.get("display") != "none"
    assert "3" in str(alert_active)


def test_render_runs_table_empty():
    node = render_runs_table([], is_admin=True, selected_ids=set())
    assert "Chưa có run nào" in str(node)


def test_render_runs_table_admin_vs_operator(history_env):
    items = [
        {
            "id": 101,
            "template_id": history_env["tpl_id"],
            "template_code": "DTP",
            "template_version": 1,
            "profile_code": "DEFAULT",
            "status": "DONE",
            "progress_pct": 100,
            "created_by": "op_test",
            "created_at": "2026-02-01T10:00:00",
            "p_from": "2026-02-01T00:00:00",
            "p_to": "2026-02-05T23:59:59",
            "filename": "test.xlsx",
            "file_size": 1024 * 1024,
            "cnt_mismatch": 2,
            "temp_purged_at": None,
            "checked_at": None,
            "match_pct": 80.0,
        },
        {
            "id": 102,
            "template_id": history_env["tpl_id"],
            "template_code": "DTP",
            "template_version": 1,
            "profile_code": "BY_DATE",
            "status": "DONE",
            "progress_pct": 100,
            "created_by": "op_test",
            "created_at": "2026-02-01T11:00:00",
            "p_from": "2026-02-01T00:00:00",
            "p_to": "2026-02-05T23:59:59",
            "filename": "test.xlsx",
            "file_size": 1024 * 1024,
            "cnt_mismatch": 0,
            "temp_purged_at": "2026-02-01T12:00:00",
            "checked_at": "2026-02-01T12:00:00",
            "match_pct": 100.0,
        },
    ]

    # Kiểm tra bảng hiển thị cho Admin: có checkbox
    admin_table = render_runs_table(items, is_admin=True, selected_ids={101})
    table_str_adm = str(admin_table)
    assert "history-select-all-cb" in table_str_adm
    assert "#101" in table_str_adm
    assert "#102" in table_str_adm
    assert "Có lệch" in table_str_adm
    assert "Đã xóa" in table_str_adm

    # Kiểm tra bảng hiển thị cho Operator: KHÔNG có checkbox
    op_table = render_runs_table(items, is_admin=False, selected_ids=set())
    table_str_op = str(op_table)
    assert "history-select-all-cb" not in table_str_op


def test_bulk_purge_modal():
    modal = render_bulk_purge_modal()
    assert modal is not None
    m_str = str(modal)
    assert "XOA" in m_str
    assert "Sẽ xóa" in m_str
    assert "Giữ lại" in m_str


def test_update_history_table_callback(history_env, monkeypatch):
    # Khi chưa đăng nhập (ctx is None)
    monkeypatch.setattr("app.ui.pages.history.get_current_ctx", lambda: None)
    node, title = update_history_table("ALL", "ALL", "ALL", "ALL", "", 0, [])
    assert "Bạn cần đăng nhập" in str(node)

    # Khi đăng nhập bằng Admin
    monkeypatch.setattr("app.ui.pages.history.get_current_ctx", lambda: history_env["admin_ctx"])
    node, title = update_history_table("ALL", "ALL", "ALL", "ALL", "", 0, [])
    assert "Lịch sử:" in title
    assert "#101" in str(node)
    assert "#102" in str(node)

    # Lọc chưa kiểm tra -> chỉ thấy run 101
    node_chk, _ = update_history_table("ALL", "UNCHECKED", "ALL", "ALL", "", 0, [])
    assert "#101" in str(node_chk)
    assert "#102" not in str(node_chk)

    # Lọc đã xóa tạm -> chỉ thấy run 102
    node_purged, _ = update_history_table("ALL", "ALL", "PURGED", "ALL", "", 0, [])
    assert "#102" in str(node_purged)
    assert "#101" not in str(node_purged)


def test_bulk_purge_confirm_flow(history_env, monkeypatch):
    # 1. Nhập sai confirm_text -> báo lỗi
    monkeypatch.setattr("app.ui.pages.history.get_current_ctx", lambda: history_env["admin_ctx"])
    err_style, err_msg, opened, _, _, notif = handle_confirm_bulk_purge(
        n_clicks=1,
        confirm_text="SAI",
        selected_data=[101],
        refresh_count=0,
    )
    assert err_style == {"display": "block"}
    assert "XOA" in err_msg
    assert opened is True

    # 2. Operator cố tình gọi xóa -> bị chặn quyền
    monkeypatch.setattr("app.ui.pages.history.get_current_ctx", lambda: history_env["op_ctx"])
    err_style, err_msg, opened, _, _, notif = handle_confirm_bulk_purge(
        n_clicks=1,
        confirm_text="XOA",
        selected_data=[101],
        refresh_count=0,
    )
    assert err_style == {"display": "block"}
    assert "Quản trị viên" in err_msg

    # 3. Admin nhập đúng "XOA" -> xóa thành công, giải phóng dung lượng
    monkeypatch.setattr("app.ui.pages.history.get_current_ctx", lambda: history_env["admin_ctx"])
    err_style, err_msg, opened, new_selected, new_refresh, notif = handle_confirm_bulk_purge(
        n_clicks=1,
        confirm_text="XOA",
        selected_data=[101],
        refresh_count=0,
    )
    assert err_style == {"display": "none"}
    assert opened is False
    assert new_selected == []
    assert new_refresh == 1
    assert notif is not None
    assert "Thành công" in str(notif)
