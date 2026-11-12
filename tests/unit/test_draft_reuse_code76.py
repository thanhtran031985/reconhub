"""Tests task 76 — lưu nháp / lưu bước 1 dùng lại mã đã có (resume thay vì báo lỗi).

- Helper `_resolve_new_step1_codes`: mã báo cáo mới -> tạo; mã báo cáo
  có sẵn -> dùng lại (bỏ qua create_report); mã template có sẵn dưới
  báo cáo đó -> resume DRAFT version; template không có DRAFT -> lỗi
  như handle_open_edit ("không có version DRAFT").
- Handler lưu bước 1 (Tiếp theo) + lưu nháp ở bước 1, luồng tạo mới:
  gõ lại mã đã lưu nháp -> không CONFLICT, state nhận đúng ids của
  bản nháp; mã mới hoàn toàn -> tạo như cũ; mã báo cáo có sẵn nhưng
  template mới -> tạo template dưới báo cáo có sẵn.
- Nhánh D4 (đã chọn báo cáo qua Select task 75) giữ nguyên: dùng lại
  report_id, tạo template mới; mã template đã có thì mở lại template
  đó (D5), template không có DRAFT thì lỗi như handle_open_edit.
"""

from __future__ import annotations

from tests.unit.test_page_report_viewer import _dump
from tests.unit.test_report_run_execute import (
    admin_ctx,
    norole_ctx,
    operator_ctx,
    run_env,
)

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


def _report_payload(code: str = "RPT76", name: str = "Báo cáo 76") -> dict:
    return {
        "code": code,
        "name": name,
        "category_code": "FINANCE",
        "owner": "FIN",
        "description": None,
        "default_favorite": False,
        "is_visible": True,
    }


def _template_payload(code: str = "TPL76", name: str = "Mẫu 76") -> dict:
    return {
        "code": code,
        "name": name,
        "display_order": 10,
        "timeout_sec": 300,
        "preview_max_rows": 100,
        "export_max_rows": 1000000,
    }


def _tpl_id_by_code(admin_ctx, report_id: int, code: str) -> int:
    from app.services.report_template import list_templates

    res = list_templates(admin_ctx, report_id)
    assert res.ok, res.message
    for t in res.data:
        if t["code"] == code:
            return int(t["id"])
    raise AssertionError(f"không thấy template {code}")


def _save_step1(page, state, report_code, tpl_code, **overrides):
    args = {
        "report_name": f"Báo cáo {report_code}",
        "category_code": "FINANCE",
        "owner": "FIN",
        "description": "",
        "is_visible": True,
        "default_favorite": False,
        "tpl_name": f"Mẫu {tpl_code}",
        "display_order": 10,
        "timeout_sec": 300,
        "preview_max_rows": 100,
        "export_max_rows": 1000000,
    }
    args.update(overrides)
    return page.handle_save_step1(1, state, report_code, tpl_code=tpl_code, **args)


def _save_draft_step1(page, state, report_code, tpl_code, **overrides):
    args = {
        "report_name": f"Báo cáo {report_code}",
        "category_code": "FINANCE",
        "owner": "FIN",
        "description": "",
        "is_visible": True,
        "default_favorite": False,
        "tpl_name": f"Mẫu {tpl_code}",
        "display_order": 10,
        "timeout_sec": 300,
        "preview_max_rows": 100,
        "export_max_rows": 1000000,
        "s2_sql": None,
    }
    args.update(overrides)
    return page.handle_save_draft_click(1, state, report_code, tpl_code=tpl_code, **args)


class TestResolveNewStep1Codes:
    def test_helper_new_codes_create_both(self, run_env, admin_ctx):
        import app.ui.pages.report_admin as page

        result, err = page._resolve_new_step1_codes(admin_ctx, _report_payload(), _template_payload())
        assert err is None
        assert result is not None
        assert result["resumed"] is False
        assert result["report_reused"] is False
        assert result["report_id"]
        assert result["template_id"]
        assert result["version_id"]
        assert result["version_status"] == "DRAFT"

    def test_helper_existing_report_reuses(self, run_env, admin_ctx):
        import app.ui.pages.report_admin as page
        from app.services.report import create_report, list_reports

        rep = create_report(admin_ctx, _report_payload(code="RPT76_ORPHAN"))
        assert rep.ok, rep.message
        result, err = page._resolve_new_step1_codes(
            admin_ctx,
            _report_payload(code="RPT76_ORPHAN"),
            _template_payload(code="TPL76_NEW"),
        )
        assert err is None
        assert result is not None
        assert result["report_reused"] is True
        assert result["report_id"] == int(rep.data["id"])
        assert result["resumed"] is False
        assert [r["code"] for r in list_reports(admin_ctx).data].count("RPT76_ORPHAN") == 1

    def test_helper_existing_template_resumes_draft(self, run_env, admin_ctx):
        import app.ui.pages.report_admin as page

        draft_tpl_id = _tpl_id_by_code(admin_ctx, int(run_env["report_id"]), "DRAFT1")
        result, err = page._resolve_new_step1_codes(
            admin_ctx,
            _report_payload(code="FIN_REVENUE"),
            _template_payload(code="DRAFT1"),
        )
        assert err is None
        assert result is not None
        assert result["resumed"] is True
        assert result["report_id"] == int(run_env["report_id"])
        assert result["template_id"] == draft_tpl_id
        assert result["version_id"] == int(run_env["draft_version_id"])
        assert result["version_status"] == "DRAFT"

    def test_helper_existing_template_no_draft_errors(self, run_env, admin_ctx):
        import app.ui.pages.report_admin as page

        result, err = page._resolve_new_step1_codes(
            admin_ctx,
            _report_payload(code="FIN_REVENUE"),
            _template_payload(code="SQL1"),
        )
        assert result is None
        assert err is not None
        assert "không có version DRAFT" in _dump(err)

    def test_helper_invalid_report_code_still_errors(self, run_env, admin_ctx):
        import app.ui.pages.report_admin as page
        from app.services.report import list_reports

        before = len(list_reports(admin_ctx).data)
        result, err = page._resolve_new_step1_codes(
            admin_ctx,
            _report_payload(code="bad code!"),
            _template_payload(),
        )
        assert result is None
        assert err is not None
        assert "chữ hoa" in _dump(err)
        assert len(list_reports(admin_ctx).data) == before


class TestSaveStep1Resume:
    def test_save_step1_retypes_drafted_codes_resumes(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report_template import list_templates

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        first, alert = _save_step1(page, page._fresh_state(), "RPT76", "TPL76")
        assert alert is None or "Đã lưu" in _dump(alert)
        assert first["step"] == 2
        again, alert2 = _save_step1(page, page._fresh_state(), "RPT76", "TPL76")
        assert alert2 is None
        assert again["step"] == 2
        assert again["report_id"] == first["report_id"]
        assert again["template_id"] == first["template_id"]
        assert again["version_id"] == first["version_id"]
        assert len([t for t in list_templates(admin_ctx, first["report_id"]).data if t["code"] == "TPL76"]) == 1

    def test_save_step1_existing_report_new_template(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report import create_report, list_reports
        from app.services.report_template import list_templates

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        rep = create_report(admin_ctx, _report_payload(code="RPT76_ORPHAN"))
        assert rep.ok, rep.message
        state, alert = _save_step1(page, page._fresh_state(), "RPT76_ORPHAN", "TPL76_NEW")
        assert alert is None or "Đã lưu" in _dump(alert)
        assert state["step"] == 2
        assert state["report_id"] == int(rep.data["id"])
        assert [r["code"] for r in list_reports(admin_ctx).data].count("RPT76_ORPHAN") == 1
        assert "TPL76_NEW" in [t["code"] for t in list_templates(admin_ctx, int(rep.data["id"])).data]

    def test_save_step1_picked_report_d4_unchanged(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = page._fresh_state()
        state["report_id"] = int(run_env["report_id"])
        new_state, alert = _save_step1(page, state, "FIN_REVENUE", "TPL76_D4")
        assert new_state["step"] == 2
        assert new_state["report_id"] == int(run_env["report_id"])
        assert new_state["template_id"] is not None
        assert alert is None or "Đã lưu" in _dump(alert)

    def test_save_step1_picked_report_existing_template_resumes(self, run_env, admin_ctx, monkeypatch):
        """Task 76 D5: chọn báo cáo qua Select rồi gõ mã template đã có
        thì mở lại template đó (DRAFT) thay vì CONFLICT."""
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        draft_tpl_id = _tpl_id_by_code(admin_ctx, int(run_env["report_id"]), "DRAFT1")
        draft_ver = page._draft_version_of(admin_ctx, draft_tpl_id)
        assert draft_ver is not None
        state = page._fresh_state()
        state["report_id"] = int(run_env["report_id"])
        new_state, alert = _save_step1(page, state, "FIN_REVENUE", "DRAFT1", report_name="Doanh thu")
        assert new_state["step"] == 2
        assert new_state["template_id"] == draft_tpl_id
        assert new_state["version_id"] == int(draft_ver["id"])
        assert alert is None or "Đã lưu" in _dump(alert)
        assert "đã tồn tại" not in _dump(alert)

    def test_save_step1_picked_report_active_only_template_errors(self, run_env, admin_ctx, monkeypatch):
        """Task 76 D5: chọn báo cáo qua Select rồi gõ mã template chỉ có
        ACTIVE (không DRAFT) thì lỗi rõ, ở lại bước 1."""
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = page._fresh_state()
        state["report_id"] = int(run_env["report_id"])
        new_state, alert = _save_step1(page, state, "FIN_REVENUE", "SQL1")
        assert new_state["template_id"] is None
        assert alert is not None
        assert "không có version DRAFT" in _dump(alert)


class TestSaveDraftResume:
    def test_save_draft_retypes_codes_resumes(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        first, notif = _save_draft_step1(page, page._fresh_state(), "RPT76", "TPL76")
        assert notif is not None and "Đã tạo và lưu nháp" in _dump(notif)
        assert first["step"] == 1
        again, notif2 = _save_draft_step1(page, page._fresh_state(), "RPT76", "TPL76")
        assert notif2 is not None and "Đã lưu nháp" in _dump(notif2)
        assert "đã tồn tại" not in _dump(notif2)
        assert again["report_id"] == first["report_id"]
        assert again["template_id"] == first["template_id"]
        assert again["version_id"] == first["version_id"]

    def test_save_draft_existing_report_new_template(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report import create_report
        from app.services.report_template import list_templates

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        rep = create_report(admin_ctx, _report_payload(code="RPT76_ORPHAN"))
        assert rep.ok, rep.message
        state, notif = _save_draft_step1(page, page._fresh_state(), "RPT76_ORPHAN", "TPL76_NEW")
        assert notif is not None and "lưu nháp" in _dump(notif)
        assert state["report_id"] == int(rep.data["id"])
        assert state["template_id"] is not None
        assert "TPL76_NEW" in [t["code"] for t in list_templates(admin_ctx, int(rep.data["id"])).data]

    def test_save_draft_template_no_draft_errors(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state, notif = _save_draft_step1(page, page._fresh_state(), "FIN_REVENUE", "SQL1")
        assert state["report_id"] is None
        assert notif is not None
        assert "không có version DRAFT" in _dump(notif)

    def test_save_draft_picked_report_creates_template(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = page._fresh_state()
        state["report_id"] = int(run_env["report_id"])
        new_state, notif = _save_draft_step1(page, state, "FIN_REVENUE", "TPL76_D4")
        assert notif is not None and "lưu nháp" in _dump(notif)
        assert new_state["report_id"] == int(run_env["report_id"])
        assert new_state["template_id"] is not None
        assert new_state["step"] == 1

    def test_save_draft_picked_report_existing_template_resumes(self, run_env, admin_ctx, monkeypatch):
        """Task 76 D5: Lưu nháp với báo cáo đã chọn qua Select, gõ mã
        template đã có thì mở lại template đó thay vì CONFLICT."""
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        draft_tpl_id = _tpl_id_by_code(admin_ctx, int(run_env["report_id"]), "DRAFT1")
        draft_ver = page._draft_version_of(admin_ctx, draft_tpl_id)
        assert draft_ver is not None
        state = page._fresh_state()
        state["report_id"] = int(run_env["report_id"])
        new_state, notif = _save_draft_step1(page, state, "FIN_REVENUE", "DRAFT1", report_name="Doanh thu")
        assert notif is not None and "Đã lưu nháp" in _dump(notif)
        assert "đã tồn tại" not in _dump(notif)
        assert new_state["template_id"] == draft_tpl_id
        assert new_state["version_id"] == int(draft_ver["id"])
        assert new_state["step"] == 1
