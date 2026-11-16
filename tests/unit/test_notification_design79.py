"""Tests task 79 — trung tâm thông báo theo thiết kế (NOTIFICATION-01).

- Service: lọc q / event_type / time_range; detail từng loại entity
  (RUN / REPORT_RUN / EXPORT / BATCH) + fallback SYSTEM; công tắc
  tổng 'ALL' tắt thì không tạo thông báo; RELATED_* ghi đúng lúc emit.
- UI pure: giờ tương đối + nhóm theo ngày; panel chi tiết; popover
  tab Tất cả/Chưa đọc; menu Thông báo sang nhóm QUẢN TRỊ.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from dash.exceptions import PreventUpdate
from sqlalchemy import text

import app.services.notification as notif
import app.ui.pages.notifications as notif_page
from tests.unit.test_notifications78 import _patch_engine, _seed_notifs
from tests.unit.test_report_run_execute import admin_ctx, norole_ctx, operator_ctx, run_env

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx", "_patch_engine"]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _insert_notif_at(engine, user_id: int, created_at: datetime, **kw) -> int:
    """Chèn thẳng 1 thông báo với CREATED_AT chỉ định (test lọc thời gian)."""
    with engine.begin() as conn:
        res = conn.execute(
            text(
                "INSERT INTO RECON_NOTIFICATION (USER_ID, TYPE, TITLE, MESSAGE, LINK, "
                "IS_READ, CREATED_AT, RELATED_TYPE, RELATED_ID) "
                "VALUES (:u, :t, :ti, :m, :l, :r, :c, :rt, :ri)"
            ),
            {
                "u": user_id,
                "t": kw.get("event_type", "RUN_FAILED"),
                "ti": kw.get("title", "Tiêu đề"),
                "m": kw.get("message", "Nội dung"),
                "l": kw.get("link", ""),
                "r": "Y" if kw.get("is_read") else "N",
                "c": created_at,
                "rt": kw.get("related_type"),
                "ri": kw.get("related_id"),
            },
        )
        return int(res.lastrowid)


def _seed_run_tree(engine) -> dict[str, int]:
    """Template đối soát + bộ + lần chạy bộ + run lỗi (detail RUN)."""
    now = _now()
    with engine.begin() as conn:
        tpl = conn.execute(
            text(
                "INSERT INTO RECON_TEMPLATE (CODE, NAME, DESCRIPTION, OWNER, STATUS, "
                "CURRENT_VERSION, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                "VALUES ('TPL79', 'Doanh thu VTOS BDP', NULL, 'admin', 'ACTIVE', 1, :now, :now, 1)"
            ),
            {"now": now},
        ).lastrowid
        bdef = conn.execute(
            text(
                "INSERT INTO RECON_BATCH_DEF (CODE, NAME, DESCRIPTION, STATUS, "
                "MAX_PARALLEL_PER_DS, OWNER_ID, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES ('BDP79', 'Doanh thu cuối tháng', NULL, 'ACTIVE', 2, 1, 'SEED', :now, 'SEED', :now, 1)"
            ),
            {"now": now},
        ).lastrowid
        ds_id = int(conn.execute(text("SELECT ID FROM RECON_DATA_SOURCE")).scalar_one())
        brun = conn.execute(
            text(
                "INSERT INTO RECON_BATCH_RUN (BATCH_DEF_ID, NAME, PERIOD, PERIOD_FROM, PERIOD_TO, "
                "STATUS, INCLUDE_WARN, CNT_ITEMS, CNT_DONE, CNT_FAILED, CNT_SKIPPED, CNT_NOT_RUN, "
                "STARTED_AT, FINISHED_AT, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES (:d, 'Tháng 7/2026', '2026-07', :now, :now, 'PARTIAL', 'Y', 2, 1, 1, 0, 0, "
                ":now, :now, 'SEED', :now, 'SEED', :now, 1)"
            ),
            {"d": int(bdef), "now": now},
        ).lastrowid
        start = now - timedelta(minutes=3, seconds=41)
        run = conn.execute(
            text(
                "INSERT INTO RECON_RUN (TEMPLATE_ID, TEMPLATE_VERSION, PROFILE_CODE, DATA_SOURCE_ID, "
                "P_FROM, P_TO, APPLY_RANGE_EXCEL, STATUS, PROGRESS_PCT, ERROR_CODE, ERROR_MSG, BATCH_RUN_ID, "
                "CREATED_BY, CREATED_AT, STARTED_AT, FINISHED_AT) "
                "VALUES (:t, 1, 'VTOS', :ds, :now, :now, 'Y', 'FAILED', 0, 'ORA-12170', "
                "'ORA-12170: Kết nối Oracle quá thời gian chờ.', :b, 'operator', :now, :s, :now)"
            ),
            {"t": int(tpl), "ds": ds_id, "b": int(brun), "now": now, "s": start},
        ).lastrowid
    return {"tpl": int(tpl), "bdef": int(bdef), "brun": int(brun), "run": int(run)}


class TestListFilters:
    def test_search_title_and_message(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        _insert_notif_at(engine, 2, _now(), title="Run đối soát thất bại", message="ORA-12170")
        _insert_notif_at(engine, 2, _now(), title="Xuất báo cáo lỗi", message="hết dung lượng")
        res = notif.list_notifications(operator_ctx, q="ORA-12170")
        assert res.ok and res.data["total"] == 1
        assert res.data["items"][0]["title"].startswith("Run đối soát")
        res = notif.list_notifications(operator_ctx, q="báo cáo")
        assert res.data["total"] == 1
        res = notif.list_notifications(operator_ctx, q="không có gì")
        assert res.data["total"] == 0

    def test_event_type_filter(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        _seed_notifs(engine, 2, 3)  # RUN_FAILED, EXPORT_FAILED, RUN_FAILED
        res = notif.list_notifications(operator_ctx, event_type="EXPORT_FAILED")
        assert res.data["total"] == 1
        assert all(i["type"] == "EXPORT_FAILED" for i in res.data["items"])
        res = notif.list_notifications(operator_ctx, event_type="RUN_DONE")
        assert res.data["total"] == 0

    def test_invalid_event_type_errors(self, _patch_engine, operator_ctx):
        res = notif.list_notifications(operator_ctx, event_type="KHONG_CO")
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_time_range_filter(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        now = _now()
        _insert_notif_at(engine, 2, now - timedelta(days=1))
        _insert_notif_at(engine, 2, now - timedelta(days=10))
        _insert_notif_at(engine, 2, now - timedelta(days=40))
        assert notif.list_notifications(operator_ctx, time_range="7d").data["total"] == 1
        assert notif.list_notifications(operator_ctx, time_range="30d").data["total"] == 2
        assert notif.list_notifications(operator_ctx, time_range="all").data["total"] == 3

    def test_invalid_time_range_errors(self, _patch_engine, operator_ctx):
        res = notif.list_notifications(operator_ctx, time_range="1y")
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_combined_filters(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        _insert_notif_at(engine, 2, _now(), title="Run lỗi A", event_type="RUN_FAILED")
        _insert_notif_at(engine, 2, _now(), title="Run lỗi B", event_type="RUN_FAILED", is_read=True)
        _insert_notif_at(engine, 2, _now(), title="Xuất lỗi", event_type="EXPORT_FAILED")
        res = notif.list_notifications(operator_ctx, q="Run", event_type="RUN_FAILED", unread_only=True)
        assert res.data["total"] == 1
        assert res.data["items"][0]["title"] == "Run lỗi A"
        res = notif.list_notifications(operator_ctx, event_type="RUN_FAILED", read_only=True)
        assert res.data["total"] == 1
        assert res.data["items"][0]["title"] == "Run lỗi B"


class TestRelatedColumns:
    def test_insert_stores_related(self, _patch_engine):
        engine = _patch_engine["engine"]
        nid = notif.insert_notification(engine, 2, "RUN_FAILED", "T", "M", related_type="RUN", related_id=421)
        assert nid is not None
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT RELATED_TYPE, RELATED_ID FROM RECON_NOTIFICATION WHERE ID = :i"),
                {"i": nid},
            ).one()
        assert tuple(row) == ("RUN", 421)

    def test_notify_for_run_writes_related(self, _patch_engine):
        engine = _patch_engine["engine"]
        tree = _seed_run_tree(engine)
        assert notif.notify_for_run(engine, tree["run"], "RUN_FAILED", "Run lỗi", "msg")
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT RELATED_TYPE, RELATED_ID FROM RECON_NOTIFICATION WHERE USER_ID = 2 AND TYPE = 'RUN_FAILED'"
                )
            ).one()
        assert tuple(row) == ("RUN", tree["run"])

    def test_notify_admins_writes_system(self, _patch_engine):
        engine = _patch_engine["engine"]
        assert notif.notify_admins(engine, "WORKER_DOWN", "Worker chết", "msg") >= 1
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT RELATED_TYPE, RELATED_ID FROM RECON_NOTIFICATION WHERE TYPE = 'WORKER_DOWN'")
            ).one()
        assert tuple(row) == ("SYSTEM", None)


class TestMasterToggle:
    def test_master_off_blocks_all_types(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        assert notif.is_enabled(engine, 2, "RUN_FAILED") is True  # thiếu dòng = BẬT
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO RECON_NOTIFICATION_PREF (USER_ID, EVENT_TYPE, ENABLED, UPDATED_AT) "
                    "VALUES (2, 'ALL', 'N', :now)"
                ),
                {"now": _now()},
            )
        assert notif.is_enabled(engine, 2, "RUN_FAILED") is False
        assert notif.is_enabled(engine, 2, "REPORT_RUN_DONE") is False
        assert notif.notify_user(engine, "operator", "RUN_FAILED", "T", "M") is False
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM RECON_NOTIFICATION")).scalar() == 0
        # Công tắc tổng của ADMIN cũng tắt → notify_admins không tạo gì.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO RECON_NOTIFICATION_PREF (USER_ID, EVENT_TYPE, ENABLED, UPDATED_AT) "
                    "VALUES (1, 'ALL', 'N', :now)"
                ),
                {"now": _now()},
            )
        assert notif.notify_admins(engine, "WORKER_DOWN", "T", "M") == 0

    def test_master_on_restores(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO RECON_NOTIFICATION_PREF (USER_ID, EVENT_TYPE, ENABLED, UPDATED_AT) "
                    "VALUES (2, 'ALL', 'N', :now)"
                ),
                {"now": _now()},
            )
        res = notif.set_prefs(operator_ctx, {}, master=True)
        assert res.ok and res.data["master"] is True
        assert notif.is_enabled(engine, 2, "RUN_FAILED") is True

    def test_get_prefs_includes_master(self, _patch_engine, operator_ctx):
        res = notif.get_prefs(operator_ctx)
        assert res.ok and res.data["master"] is True  # mặc định BẬT
        res = notif.set_prefs(operator_ctx, {"RUN_DONE": True}, master=False)
        assert res.ok and res.data["master"] is False
        assert res.data["prefs"]["RUN_DONE"] is True
        res = notif.get_prefs(operator_ctx)
        assert res.data["master"] is False


class TestDetail:
    def test_detail_run(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        tree = _seed_run_tree(engine)
        nid = notif.insert_notification(
            engine,
            2,
            "RUN_FAILED",
            "Run đối soát thất bại",
            "ORA-12170",
            link=f"/runs/{tree['run']}",
            related_type="RUN",
            related_id=tree["run"],
        )
        res = notif.get_notification_detail(operator_ctx, nid)
        assert res.ok, res.message
        d = res.data
        assert d["code"] == f"RUN_{tree['run']:05d}"
        assert d["code_label"] == "Mã lần chạy"
        assert d["error"] == "ORA-12170: Kết nối Oracle quá thời gian chờ."
        assert d["open_label"] == "Mở kết quả Run"
        fields = {f["label"]: f["value"] for f in d["fields"]}
        assert fields["Bộ đối soát"] == "Doanh thu cuối tháng"
        assert fields["Template"] == "Doanh thu VTOS BDP"
        assert fields["Thời gian chạy"] == "03 phút 41 giây"

    def test_detail_report_run(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        now = _now()
        with engine.begin() as conn:
            tpl_id = int(conn.execute(text("SELECT ID FROM RECON_REPORT_TEMPLATE WHERE CODE='SQL1'")).scalar_one())
            ver_id = int(
                conn.execute(text("SELECT ID FROM RECON_RPT_TPL_VER WHERE TEMPLATE_ID=:t"), {"t": tpl_id}).scalar_one()
            )
            rep_id = int(conn.execute(text("SELECT ID FROM RECON_REPORT WHERE CODE='FIN_REVENUE'")).scalar_one())
            rrun = conn.execute(
                text(
                    "INSERT INTO RECON_REPORT_RUN (REPORT_ID, TEMPLATE_ID, VERSION_ID, PARAMS_JSON, "
                    "STATUS, ROW_COUNT, QUERY_MS, ERROR_CODE, ERROR_MESSAGE, CREATED_BY, CREATED_AT, FINISHED_AT) "
                    "VALUES (:r, :t, :v, '{}', 'FAILED', NULL, 1234, 'ORA-00942', 'ORA-00942: bảng không tồn tại', "
                    "'operator', :now, :now)"
                ),
                {"r": rep_id, "t": tpl_id, "v": ver_id, "now": now},
            ).lastrowid
        nid = notif.insert_notification(
            engine,
            2,
            "REPORT_RUN_FAILED",
            "Chạy báo cáo lỗi",
            "ORA-00942",
            related_type="REPORT_RUN",
            related_id=int(rrun),
        )
        res = notif.get_notification_detail(operator_ctx, nid)
        assert res.ok, res.message
        d = res.data
        assert d["code"] == f"RPT_{int(rrun):05d}"
        assert d["error"] == "ORA-00942: bảng không tồn tại"
        fields = {f["label"]: f["value"] for f in d["fields"]}
        assert fields["Báo cáo"] == "Doanh thu"
        assert fields["Template"] == "Mẫu SQL1"

    def test_detail_export(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        now = _now()
        with engine.begin() as conn:
            tpl_id = int(conn.execute(text("SELECT ID FROM RECON_REPORT_TEMPLATE WHERE CODE='SQL1'")).scalar_one())
            ver_id = int(
                conn.execute(text("SELECT ID FROM RECON_RPT_TPL_VER WHERE TEMPLATE_ID=:t"), {"t": tpl_id}).scalar_one()
            )
            rep_id = int(conn.execute(text("SELECT ID FROM RECON_REPORT WHERE CODE='FIN_REVENUE'")).scalar_one())
            rrun = conn.execute(
                text(
                    "INSERT INTO RECON_REPORT_RUN (REPORT_ID, TEMPLATE_ID, VERSION_ID, PARAMS_JSON, "
                    "STATUS, ROW_COUNT, CREATED_BY, CREATED_AT, FINISHED_AT) "
                    "VALUES (:r, :t, :v, '{}', 'DONE', 55, 'operator', :now, :now)"
                ),
                {"r": rep_id, "t": tpl_id, "v": ver_id, "now": now},
            ).lastrowid
            exp = conn.execute(
                text(
                    "INSERT INTO RECON_RPT_EXPORT (RUN_ID, FORMAT, STATUS, FILE_PATH, PART_COUNT, "
                    "PROGRESS_PCT, ROW_COUNT, CREATED_BY, CREATED_AT, FINISHED_AT, ERROR_MESSAGE) "
                    "VALUES (:r, 'XLSX', 'FAILED', '/tmp/xuat_202607.xlsx', 1, 0, NULL, 'operator', :now, :now, 'Hết dung lượng')"
                ),
                {"r": int(rrun), "now": now},
            ).lastrowid
        nid = notif.insert_notification(
            engine,
            2,
            "EXPORT_FAILED",
            "Xuất báo cáo lỗi",
            "Hết dung lượng",
            related_type="EXPORT",
            related_id=int(exp),
        )
        res = notif.get_notification_detail(operator_ctx, nid)
        assert res.ok, res.message
        d = res.data
        assert d["code"] == f"EXP_{int(exp):05d}"
        assert d["error"] == "Hết dung lượng"
        fields = {f["label"]: f["value"] for f in d["fields"]}
        assert fields["Báo cáo"] == "Doanh thu"
        assert fields["Tên file"] == "xuat_202607.xlsx"

    def test_detail_batch(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        tree = _seed_run_tree(engine)
        nid = notif.insert_notification(
            engine,
            2,
            "BATCH_FAILED",
            "Chạy bộ kết thúc có lỗi",
            "1 mục lỗi",
            related_type="BATCH",
            related_id=tree["brun"],
        )
        res = notif.get_notification_detail(operator_ctx, nid)
        assert res.ok, res.message
        d = res.data
        assert d["code"] == f"BATCH_{tree['brun']:05d}"
        fields = {f["label"]: f["value"] for f in d["fields"]}
        assert fields["Bộ đối soát"] == "Doanh thu cuối tháng"
        assert "1 mục xong" in fields["Số mục"] and "1 mục lỗi" in fields["Số mục"]

    def test_detail_system_fallback(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        nid = notif.insert_notification(
            engine,
            2,
            "WORKER_DOWN",
            "Worker ngừng hoạt động",
            "Mất heartbeat",
            related_type="SYSTEM",
            related_id=None,
        )
        res = notif.get_notification_detail(operator_ctx, nid)
        assert res.ok, res.message
        assert res.data["code"] is None
        assert res.data["fields"] == []
        assert res.data["error"] is None

    def test_detail_missing_entity_fallback(self, _patch_engine, operator_ctx):
        engine = _patch_engine["engine"]
        nid = notif.insert_notification(
            engine, 2, "RUN_FAILED", "Run lỗi", "msg", related_type="RUN", related_id=999999
        )
        res = notif.get_notification_detail(operator_ctx, nid)
        assert res.ok, res.message
        assert res.data["code"] == "RUN_999999"
        assert res.data["fields"] == []

    def test_detail_not_found_and_not_own(self, _patch_engine, operator_ctx, norole_ctx):
        engine = _patch_engine["engine"]
        nid = notif.insert_notification(engine, 2, "RUN_FAILED", "T", "M")
        assert not notif.get_notification_detail(operator_ctx, 999999).ok
        assert not notif.get_notification_detail(norole_ctx, nid).ok


class TestRelativeTime:
    def test_format_relative_time(self):
        from app.ui.pages.notifications import format_relative_time

        now = datetime(2026, 11, 12, 21, 16, 8)
        assert format_relative_time(now - timedelta(seconds=30), now) == "Vừa xong"
        assert format_relative_time(now - timedelta(minutes=2), now) == "2 phút"
        assert format_relative_time(now - timedelta(minutes=59), now) == "59 phút"
        assert format_relative_time(now - timedelta(hours=1), now) == "1 giờ"
        assert format_relative_time(now - timedelta(hours=5), now) == "5 giờ"
        assert format_relative_time(now - timedelta(days=1, hours=5), now) == "Hôm qua 16:16"
        assert format_relative_time(now - timedelta(days=2), now) == "10/11/2026 21:16"
        # Chuỗi ISO cũng dùng được (item từ service trả ISO).
        assert format_relative_time("2026-11-12T21:14:08", now) == "2 phút"

    def test_day_group_label(self):
        from app.ui.pages.notifications import day_group_label

        now = datetime(2026, 11, 12, 21, 16, 8)
        assert day_group_label(now, now) == "HÔM NAY"
        assert day_group_label(now - timedelta(days=1), now) == "HÔM QUA"
        assert day_group_label(now - timedelta(days=3), now) == "09/11/2026"


class TestPanelAndMenu:
    def test_panel_items_unread_only(self, _patch_engine, operator_ctx):
        from app.ui.layout.shell import _notif_panel_items

        engine = _patch_engine["engine"]
        _seed_notifs(engine, 2, 3)
        notif.mark_read(operator_ctx, 1)
        all_items = _notif_panel_items(operator_ctx)
        assert len(all_items) == 3
        unread_items = _notif_panel_items(operator_ctx, unread_only=True)
        assert len(unread_items) == 2

    def test_menu_notifications_in_quan_tri(self):
        from app.ui.menus import MENUS

        m = next(x for x in MENUS if x.code == "notifications")
        assert m.group == "QUAN_TRI"
        assert m.order == 70  # parent fix: 30 trùng menu_admin trong nhóm


class TestRowClassAndCopy:
    def test_selected_row_keeps_base_class(self):
        """Dòng được chọn giữ class notif-row + thêm notif-row-selected
        (hồi quy: trước đây class bị thay hẳn nên mất padding/cursor)."""
        from app.ui.pages.notifications import _notif_row

        now = datetime(2026, 11, 12, 21, 16, 8)
        item = {"id": 7, "title": "T", "message": "M", "type": "RUN_FAILED", "is_read": False, "created_at": now}
        selected = _notif_row(item, 7, now)
        assert selected.className == "notif-row notif-row-selected"
        plain = _notif_row(item, 9, now)
        assert plain.className == "notif-row"

    def test_copy_button_writes_store(self, _patch_engine, operator_ctx, monkeypatch):
        """Bấm sao chép mã -> copy-store có text = mã run (clientside
        ghi clipboard; không dùng dcc.Clipboard vì log cảnh báo React)."""
        engine = _patch_engine["engine"]
        tree = _seed_run_tree(engine)
        nid = notif.insert_notification(
            engine,
            2,
            "RUN_FAILED",
            "Run đối soát thất bại",
            "ORA-12170",
            link=f"/runs/{tree['run']}",
            related_type="RUN",
            related_id=tree["run"],
        )
        monkeypatch.setattr(notif_page, "get_current_ctx", lambda: operator_ctx)
        store, _toast = notif_page.handle_notif_copy(1, {"id": nid})
        assert store == {"text": f"RUN_{tree['run']:05d}"}

    def test_copy_without_selection_noop(self, _patch_engine, operator_ctx, monkeypatch):
        monkeypatch.setattr(notif_page, "get_current_ctx", lambda: operator_ctx)
        with pytest.raises(PreventUpdate):
            notif_page.handle_notif_copy(1, {"id": None})


class TestDetailActionButtons:
    def test_settings_cancel_closes_without_saving(self):
        """Hủy modal: đóng, không gọi set_prefs (không lưu)."""
        import app.ui.pages.notifications as page

        assert page.handle_notif_settings_cancel(1) is False
        with pytest.raises(PreventUpdate):
            page.handle_notif_settings_cancel(0)

    def test_system_detail_keeps_action_buttons(self, _patch_engine, operator_ctx):
        """Action buttons vẫn render nút Mở/Sao chép (ẩn) để callback
        list/copy không chết khi dòng chọn không có link/mã."""
        import app.ui.pages.notifications as page

        group = page._action_buttons(None, None, None, show_delete=True)

        ids: set[str] = set()

        def _walk(node):
            if isinstance(node, (list, tuple)):
                for child in node:
                    _walk(child)
                return
            node_id = getattr(node, "id", None)
            if isinstance(node_id, str):
                ids.add(node_id)
            children = getattr(node, "children", None)
            if children is not None:
                _walk(children)

        _walk(group)
        assert "notif-detail-open-btn" in ids
        assert "notif-detail-copy-btn" in ids

    def test_empty_detail_keeps_action_buttons(self, operator_ctx):
        """Action buttons trống (không chọn dòng / list rỗng) cũng phải có 2
        nút — nếu không, lọc ra 0 dòng xong callback list chết."""
        import app.ui.pages.notifications as page

        group = page._action_buttons(None, None, None, show_delete=False)
        ids: set[str] = set()

        def _walk(node):
            if isinstance(node, (list, tuple)):
                for child in node:
                    _walk(child)
                return
            node_id = getattr(node, "id", None)
            if isinstance(node_id, str):
                ids.add(node_id)
            children = getattr(node, "children", None)
            if children is not None:
                _walk(children)

        _walk(group)
        assert "notif-detail-open-btn" in ids
        assert "notif-detail-copy-btn" in ids


class TestParentFixes79:
    """Parent review task 79: icon đặc, nút sao chép có nhãn, menu
    không trùng order, khôi phục xóa (task 78 có, D11 bỏ nhầm)."""

    def test_status_icon_filled_like_design(self):
        """Icon trạng thái nền đặc (theo ảnh thiết kế), không nhạt."""
        import app.ui.pages.notifications as page

        icon = page._status_icon("RUN_FAILED")
        assert icon.variant == "filled"
        assert page._status_icon("WORKER_DOWN").color == "orange"

    def test_copy_button_is_action_icon_with_tooltip(self):
        """Nút sao chép là ActionIcon nằm trong Tooltip có nhãn 'Sao chép mã run'
        trên master bên trái (theo yêu cầu UI UX)."""
        import dash_mantine_components as dmc

        import app.ui.pages.notifications as page

        group = page._action_buttons("/runs/1", "RUN_00001", "Mở kết quả Run")
        found = [
            c
            for c in group.children
            if isinstance(c, dmc.Tooltip) and getattr(c.children, "id", None) == "notif-detail-copy-btn"
        ]
        assert len(found) == 1
        assert found[0].label == "Sao chép mã run"
        assert isinstance(found[0].children, dmc.ActionIcon)

    def test_menu_orders_unique_in_quan_tri(self):
        """Order menu trong nhóm QUẢN TRỊ không trùng (trước đây
        notifications trùng order 30 với menu_admin)."""
        from app.ui.menus import MENUS

        orders = [m.order for m in MENUS if m.group == "QUAN_TRI"]
        assert len(orders) == len(set(orders))
        notif = next(m for m in MENUS if m.code == "notifications")
        assert notif.order == 70

    def test_delete_button_present_in_master_actions(self, _patch_engine, operator_ctx):
        """Master actions có nút Xóa dạng ActionIcon kèm Tooltip."""
        import dash_mantine_components as dmc

        import app.ui.pages.notifications as page

        group = page._action_buttons(None, None, None, show_delete=True)
        found = [
            c
            for c in group.children
            if isinstance(c, dmc.Tooltip) and getattr(c.children, "id", None) == "notif-detail-delete-btn"
        ]
        assert len(found) == 1
        assert found[0].label == "Xóa thông báo"
        assert isinstance(found[0].children, dmc.ActionIcon)

    def test_delete_modal_open_close(self, monkeypatch):
        """Modal xác nhận xóa: bấm Xóa mở, Hủy/Xác nhận đóng."""
        from types import SimpleNamespace

        import dash

        import app.ui.pages.notifications as page

        monkeypatch.setattr(dash, "callback_context", SimpleNamespace(triggered_id="notif-detail-delete-btn"))
        assert page.handle_notif_delete_modal(1, None, None) is True
        monkeypatch.setattr(dash, "callback_context", SimpleNamespace(triggered_id="notif-delete-modal-cancel"))
        assert page.handle_notif_delete_modal(1, 1, None) is False
        monkeypatch.setattr(dash, "callback_context", SimpleNamespace(triggered_id="notif-delete-modal-confirm"))
        assert page.handle_notif_delete_modal(1, None, 1) is False

    def test_delete_modal_noop_on_remount(self, monkeypatch):
        """Nút Xóa bị vẽ lại (remount) khi danh sách đổi: Dash bắn
        callback với n_clicks=None — modal KHÔNG được tự mở (hồi
        quy live: modal tự mở che mất ô lọc sau mỗi lần tìm kiếm)."""
        from types import SimpleNamespace

        import dash

        import app.ui.pages.notifications as page

        monkeypatch.setattr(dash, "callback_context", SimpleNamespace(triggered_id="notif-detail-delete-btn"))
        with pytest.raises(PreventUpdate):
            page.handle_notif_delete_modal(None, None, None)

    def test_delete_confirm_removes_notification(self, _patch_engine, operator_ctx, monkeypatch):
        """Xác nhận xóa trong modal: dòng biến mất khỏi DB; dòng còn
        lại được tự chọn (panel luôn hiện 1 dòng khi list còn dữ
        liệu); toast thành công."""
        from types import SimpleNamespace

        import dash

        import app.ui.pages.notifications as page
        from app.ui.pages.notifications import DEFAULT_FILTERS

        engine = _patch_engine["engine"]
        keep = notif.insert_notification(engine, 2, "RUN_FAILED", "Giữ lại", "x")
        gone = notif.insert_notification(engine, 2, "RUN_FAILED", "Xóa đi", "x")
        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        monkeypatch.setattr(dash, "callback_context", SimpleNamespace(triggered_id="notif-delete-modal-confirm"))
        out = page.handle_notif_list_actions(
            {"page": 1},
            dict(DEFAULT_FILTERS),
            None,
            None,
            None,
            None,
            1,
            {"id": gone},
        )
        assert out[9] == {"id": keep}  # tự chọn dòng còn lại
        assert out[6] is not dash.no_update  # toast thành công
        res = notif.list_notifications(operator_ctx, page=1, page_size=20)
        assert res.ok
        assert [int(i["id"]) for i in res.data["items"]] == [keep]
