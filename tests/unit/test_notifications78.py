"""Tests task 78 — trung tâm thông báo trong app.

- Service: tạo/liệt kê (chưa đọc trước, phân trang server-side),
  đếm chưa đọc, đánh dấu đã đọc/xóa (chỉ của mình), pref mặc định
  (lỗi BẬT / DONE TẮT) + ghi đè, notify_admins (chỉ ADMIN + dedup
  60 phút), notify_for_run/report_run/export/batch,
  maybe_notify_worker_health (worker down/kẹt), notify không raise
  khi DB lỗi.
- UI: header có chuông + badge số chưa đọc; trang /notifications
  hiện danh sách + công tắc pref.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

import app.services.notification as notif
from tests.unit.test_page_report_viewer import _dump, _find_by_id
from tests.unit.test_report_run_execute import admin_ctx, norole_ctx, operator_ctx, run_env

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def _patch_engine(run_env, monkeypatch):
    """Service @service đọc engine qua module notification."""
    monkeypatch.setattr(notif, "get_recon_engine", lambda: run_env["engine"])
    return run_env


def _seed_notifs(engine, user_id: int, n: int = 3) -> list[int]:
    ids = []
    for i in range(n):
        nid = notif.insert_notification(
            engine,
            user_id,
            "RUN_FAILED" if i % 2 == 0 else "EXPORT_FAILED",
            f"Tiêu đề {i}",
            f"Nội dung {i}",
            link=f"/runs/{i + 1}",
        )
        assert nid is not None
        ids.append(nid)
    return ids


class TestCreateListCount:
    def test_list_unread_first_and_paging(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        ids = _seed_notifs(engine, 2, 3)
        # Đánh dấu 1 cái đã đọc -> 2 chưa đọc phải lên trước.
        assert notif.mark_read(operator_ctx, ids[2]).ok
        res = notif.list_notifications(operator_ctx, page=1, page_size=2)
        assert res.ok, res.message
        assert res.data["total"] == 3
        assert len(res.data["items"]) == 2
        assert all(not item["is_read"] for item in res.data["items"])
        res2 = notif.list_notifications(operator_ctx, page=2, page_size=2)
        assert len(res2.data["items"]) == 1
        assert res2.data["items"][0]["is_read"] is True
        # Chưa đọc trước: item đầu là chưa đọc, có đủ trường hiển thị.
        first = res.data["items"][0]
        assert first["title"].startswith("Tiêu đề")
        assert first["link"].startswith("/runs/")
        assert first["type_label"]

    def test_unread_count_and_mark_all_read(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        _seed_notifs(engine, 2, 3)
        assert notif.unread_count(operator_ctx).data["unread"] == 3
        res = notif.mark_all_read(operator_ctx)
        assert res.ok and res.data["updated"] == 3
        assert notif.unread_count(operator_ctx).data["unread"] == 0

    def test_list_only_own(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        _seed_notifs(engine, 2, 2)
        _seed_notifs(engine, 1, 1)
        res = notif.list_notifications(operator_ctx)
        assert res.data["total"] == 2
        assert all(item["title"].startswith("Tiêu đề") for item in res.data["items"])

    def test_list_unread_only(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        ids = _seed_notifs(engine, 2, 2)
        assert notif.mark_read(operator_ctx, ids[0]).ok
        res = notif.list_notifications(operator_ctx, unread_only=True)
        assert res.data["total"] == 1
        assert res.data["items"][0]["id"] == ids[1]


class TestMarkDeleteOwnership:
    def test_mark_read_other_user_forbidden(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        ids = _seed_notifs(engine, 1, 1)
        res = notif.mark_read(operator_ctx, ids[0])
        assert not res.ok
        assert "không tìm thấy" in res.message.lower() or "không có quyền" in res.message.lower()

    def test_delete_only_own(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        own = _seed_notifs(engine, 2, 1)
        other = _seed_notifs(engine, 1, 1)
        assert not notif.delete_notification(operator_ctx, other[0]).ok
        assert notif.delete_notification(operator_ctx, own[0]).ok
        assert notif.list_notifications(operator_ctx).data["total"] == 0


class TestPrefs:
    def test_defaults_failures_on_done_off(self, _patch_engine, operator_ctx):
        res = notif.get_prefs(operator_ctx)
        assert res.ok, res.message
        prefs = res.data["prefs"]
        for t in ("RUN_FAILED", "REPORT_RUN_FAILED", "EXPORT_FAILED", "BATCH_FAILED", "WORKER_DOWN", "QUEUE_STUCK"):
            assert prefs[t] is True, t
        for t in ("RUN_DONE", "REPORT_RUN_DONE", "EXPORT_DONE", "BATCH_DONE"):
            assert prefs[t] is False, t

    def test_set_prefs_roundtrip_and_invalid(self, _patch_engine, operator_ctx):
        res = notif.set_prefs(operator_ctx, {"EXPORT_DONE": True, "RUN_FAILED": False})
        assert res.ok, res.message
        prefs = notif.get_prefs(operator_ctx).data["prefs"]
        assert prefs["EXPORT_DONE"] is True
        assert prefs["RUN_FAILED"] is False
        assert prefs["EXPORT_FAILED"] is True  # không đổi
        bad = notif.set_prefs(operator_ctx, {"KHONG_CO": True})
        assert not bad.ok

    def test_notify_respects_prefs(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        # Mặc định: RUN_FAILED tạo, EXPORT_DONE không.
        assert notif.notify_user(engine, "operator", "RUN_FAILED", "Lỗi", "Chi tiết") is True
        assert notif.notify_user(engine, "operator", "EXPORT_DONE", "Xong", "Chi tiết") is False
        assert notif.unread_count(operator_ctx).data["unread"] == 1
        # Bật EXPORT_DONE -> tạo; tắt RUN_FAILED -> không tạo.
        assert notif.set_prefs(operator_ctx, {"EXPORT_DONE": True, "RUN_FAILED": False}).ok
        assert notif.notify_user(engine, "operator", "EXPORT_DONE", "Xong", "Chi tiết") is True
        assert notif.notify_user(engine, "operator", "RUN_FAILED", "Lỗi", "Chi tiết") is False
        assert notif.unread_count(operator_ctx).data["unread"] == 2

    def test_notify_unknown_user_returns_false(self, _patch_engine):
        engine = _patch_engine["engine"]
        assert notif.notify_user(engine, "khong_co", "RUN_FAILED", "Lỗi", "Chi tiết") is False


class TestNotifyAdmins:
    def test_only_admins_receive_and_dedup(self, _patch_engine, admin_ctx, operator_ctx):
        engine = _patch_engine["engine"]
        n = notif.notify_admins(engine, "WORKER_DOWN", "Worker chết", "Không thấy nhịp tim", link="/queue-health")
        assert n == 1
        assert notif.unread_count(admin_ctx).data["unread"] == 1
        assert notif.unread_count(operator_ctx).data["unread"] == 0
        # Gọi lại trong 60 phút -> dedup, không tạo thêm.
        assert notif.notify_admins(engine, "WORKER_DOWN", "Worker chết", "Không thấy nhịp tim") == 0
        assert notif.unread_count(admin_ctx).data["unread"] == 1

    def test_admin_pref_off_blocks(self, _patch_engine, admin_ctx):
        engine = _patch_engine["engine"]
        assert notif.set_prefs(admin_ctx, {"WORKER_DOWN": False}).ok
        assert notif.notify_admins(engine, "WORKER_DOWN", "Worker chết", "Chi tiết") == 0
        assert notif.unread_count(admin_ctx).data["unread"] == 0


class TestNotifyForEntities:
    def test_notify_for_report_run(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        env = _patch_engine
        with engine.begin() as conn:
            res = conn.execute(
                text(
                    "INSERT INTO RECON_REPORT_RUN (REPORT_ID, TEMPLATE_ID, VERSION_ID, "
                    "PARAMS_JSON, STATUS, CREATED_BY, CREATED_AT) "
                    "VALUES (:r, :t, :v, '{}', 'FAILED', 'operator', :now)"
                ),
                {"r": env["report_id"], "t": env["sql_template_id"], "v": env["sql_version_id"], "now": _now()},
            )
            run_id = int(res.lastrowid)
        assert notif.notify_for_report_run(engine, run_id, "REPORT_RUN_FAILED", "Chạy báo cáo lỗi", "Lỗi SQL") is True
        items = notif.list_notifications(operator_ctx).data["items"]
        assert len(items) == 1
        assert items[0]["link"] == f"/reports/{env['report_id']}?run={run_id}"

    def test_notify_for_run(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        now = _now()
        with engine.begin() as conn:
            res = conn.execute(
                text(
                    "INSERT INTO RECON_RUN (TEMPLATE_ID, TEMPLATE_VERSION, PROFILE_CODE, "
                    "DATA_SOURCE_ID, P_FROM, P_TO, APPLY_RANGE_EXCEL, PROGRESS_PCT, STATUS, CREATED_BY, CREATED_AT) "
                    "VALUES (1, 1, 'P78', :ds, :now, :now, 'Y', 0, 'FAILED', 'operator', :now)"
                ),
                {"ds": _patch_engine["ds_id"], "now": now},
            )
            run_id = int(res.lastrowid)
        assert notif.notify_for_run(engine, run_id, "RUN_FAILED", "Run lỗi", "Chi tiết") is True
        items = notif.list_notifications(operator_ctx).data["items"]
        assert items[0]["link"] == f"/runs/{run_id}"

    def test_notify_for_export(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        env = _patch_engine
        with engine.begin() as conn:
            res = conn.execute(
                text(
                    "INSERT INTO RECON_REPORT_RUN (REPORT_ID, TEMPLATE_ID, VERSION_ID, "
                    "PARAMS_JSON, STATUS, CREATED_BY, CREATED_AT) "
                    "VALUES (:r, :t, :v, '{}', 'DONE', 'operator', :now)"
                ),
                {"r": env["report_id"], "t": env["sql_template_id"], "v": env["sql_version_id"], "now": _now()},
            )
            run_id = int(res.lastrowid)
            res = conn.execute(
                text(
                    "INSERT INTO RECON_RPT_EXPORT (RUN_ID, FORMAT, STATUS, PART_COUNT, "
                    "PROGRESS_PCT, CREATED_BY, CREATED_AT) "
                    "VALUES (:run, 'XLSX', 'FAILED', 1, 0, 'operator', :now)"
                ),
                {"run": run_id, "now": _now()},
            )
            export_id = int(res.lastrowid)
        assert notif.notify_for_export(engine, export_id, "EXPORT_FAILED", "Xuất lỗi", "Chi tiết") is True
        items = notif.list_notifications(operator_ctx).data["items"]
        assert items[0]["link"] == "/report-runs"

    def test_notify_for_batch(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        now = _now()
        with engine.begin() as conn:
            res = conn.execute(
                text(
                    "INSERT INTO RECON_BATCH_DEF (CODE, NAME, STATUS, MAX_PARALLEL_PER_DS, "
                    "OWNER_ID, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                    "VALUES ('B78', 'Bộ 78', 'DRAFT', 2, 2, 'SEED', :now, 'SEED', :now, 1)"
                ),
                {"now": now},
            )
            def_id = int(res.lastrowid)
            res = conn.execute(
                text(
                    "INSERT INTO RECON_BATCH_RUN (BATCH_DEF_ID, NAME, PERIOD, PERIOD_FROM, "
                    "PERIOD_TO, STATUS, INCLUDE_WARN, CNT_ITEMS, CNT_DONE, CNT_FAILED, "
                    "CNT_SKIPPED, CNT_NOT_RUN, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:d, 'Bộ 78 2026-11', '2026-11', :now, :now, 'PARTIAL', 'Y', "
                    "1, 0, 1, 0, 0, 'operator', :now, 'operator', :now, 1)"
                ),
                {"d": def_id, "now": now},
            )
            batch_id = int(res.lastrowid)
        assert notif.notify_for_batch(engine, batch_id, "BATCH_FAILED", "Chạy bộ lỗi", "1 mục lỗi") is True
        items = notif.list_notifications(operator_ctx).data["items"]
        assert items[0]["link"] == f"/batch-runs/{batch_id}/result"


class TestWorkerHealthNotify:
    def test_down_notifies_admin_once_per_hour(self, _patch_engine, admin_ctx, operator_ctx):
        engine = _patch_engine["engine"]
        # Chưa từng có nhịp tim -> worker "down".
        out = notif.maybe_notify_worker_health(engine)
        assert out["worker_down"] is True
        assert notif.unread_count(admin_ctx).data["unread"] == 1
        assert notif.unread_count(operator_ctx).data["unread"] == 0
        # Gọi lại -> dedup, không tạo thêm.
        out2 = notif.maybe_notify_worker_health(engine)
        assert out2["worker_down"] is True
        assert notif.unread_count(admin_ctx).data["unread"] == 1

    def test_alive_worker_no_notify(self, _patch_engine, admin_ctx):
        engine = _patch_engine["engine"]
        from app.services.worker_health import write_worker_heartbeat

        write_worker_heartbeat(engine, "w1", "recon")
        write_worker_heartbeat(engine, "w1", "export")
        out = notif.maybe_notify_worker_health(engine)
        assert out["worker_down"] is False
        assert notif.unread_count(admin_ctx).data["unread"] == 0

    def test_stuck_queue_notifies_admin(self, _patch_engine, admin_ctx):
        engine = _patch_engine["engine"]
        from app.services.worker_health import write_worker_heartbeat

        write_worker_heartbeat(engine, "w1", "recon")
        write_worker_heartbeat(engine, "w1", "export")
        old = _now() - timedelta(minutes=40)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO RECON_REPORT_RUN (REPORT_ID, TEMPLATE_ID, VERSION_ID, "
                    "PARAMS_JSON, STATUS, CREATED_BY, CREATED_AT) "
                    "VALUES (:r, :t, :v, '{}', 'QUEUED', 'operator', :now)"
                ),
                {
                    "r": _patch_engine["report_id"],
                    "t": _patch_engine["sql_template_id"],
                    "v": _patch_engine["sql_version_id"],
                    "now": old,
                },
            )
        out = notif.maybe_notify_worker_health(engine)
        assert out["queue_stuck"] is True
        assert out["worker_down"] is False
        items = notif.list_notifications(admin_ctx).data["items"]
        assert len(items) == 1
        assert items[0]["type"] == "QUEUE_STUCK"
        assert items[0]["link"] == "/queue-health"


class TestNeverRaises:
    def test_notify_user_broken_engine_returns_false(self):
        bad = create_engine("sqlite:////nonexistent_dir_xyz/db.sqlite")
        assert notif.notify_user(bad, "operator", "RUN_FAILED", "Lỗi", "Chi tiết") is False
        assert notif.notify_admins(bad, "WORKER_DOWN", "Worker chết", "Chi tiết") == 0
        assert notif.maybe_notify_worker_health(bad) == {"worker_down": False, "queue_stuck": False, "notified": 0}


class TestHeaderBell:
    def test_header_has_bell_with_unread_count(self, _patch_engine, operator_ctx, monkeypatch):
        import app.ui.layout.shell as shell

        engine = _patch_engine["engine"]
        monkeypatch.setattr(shell, "get_recon_engine", lambda: engine)
        _seed_notifs(engine, 2, 2)
        header = shell.create_header(operator_ctx, "dev", "/")
        dump = _dump(header)
        assert "app-notif-bell" in dump
        assert "app-notif-indicator" in dump
        indicator = _find_by_id(header, "app-notif-indicator")
        assert indicator is not None
        assert str(indicator.label) == "2"

    def test_header_bell_zero_unread(self, _patch_engine, operator_ctx, monkeypatch):
        import app.ui.layout.shell as shell

        engine = _patch_engine["engine"]
        monkeypatch.setattr(shell, "get_recon_engine", lambda: engine)
        header = shell.create_header(operator_ctx, "dev", "/")
        indicator = _find_by_id(header, "app-notif-indicator")
        assert indicator is not None
        assert str(indicator.label) in ("", "0")


class TestPanelItemClick:
    """Hồi quy task 78: bấm mục panel phải đánh dấu đọc + trả link.

    MenuItem có href + n_clicks thì click điều hướng ngay, n_clicks
    mất (chứng minh bằng debug live) — nên panel dùng MenuItem không
    href, callback tự điều hướng sau khi đánh dấu đọc.
    """

    def test_panel_item_marks_read_and_returns_link(self, _patch_engine, operator_ctx, monkeypatch):
        from app.ui.layout import shell

        engine = _patch_engine["engine"]
        monkeypatch.setattr(shell, "get_recon_engine", lambda: engine)
        _seed_notifs(engine, 2, 1)
        label, disabled, panel, href = shell.handle_panel_item_click(operator_ctx, 1)
        assert href == "/runs/1"
        assert label == "" and disabled is True
        assert notif.unread_count(operator_ctx).data["unread"] == 0
        assert "Tiêu đề 0" in str(panel)

    def test_panel_item_without_link_stays(self, _patch_engine, operator_ctx, monkeypatch):
        import dash

        from app.ui.layout import shell

        engine = _patch_engine["engine"]
        monkeypatch.setattr(shell, "get_recon_engine", lambda: engine)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO RECON_NOTIFICATION (USER_ID, TYPE, TITLE, MESSAGE, LINK, IS_READ, CREATED_AT) "
                    "VALUES (2, 'RUN_FAILED', 'Không link', '', NULL, 'N', :now)"
                ),
                {"now": _now()},
            )
        label, disabled, _panel, href = shell.handle_panel_item_click(operator_ctx, 1)
        assert href is dash.no_update
        assert label == "" and disabled is True


class TestNotificationsPage:
    def test_page_layout_lists_and_prefs(self, _patch_engine, operator_ctx, monkeypatch):
        import app.ui.pages.notifications as page

        engine = _patch_engine["engine"]
        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        _seed_notifs(engine, 2, 2)
        tree = page.layout()
        dump = _dump(tree)
        assert "Tiêu đề 0" in dump
        assert "Cài đặt thông báo" in dump
        assert "Run đối soát lỗi" in dump
