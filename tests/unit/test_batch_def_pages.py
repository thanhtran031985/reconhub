"""Tests cho hàm render thuần của màn Bộ đối soát — Bước 8 task 18.

Kiểm tra nội dung dựng ra (mã bộ, template, cảnh báo) mà không cần
trình duyệt.
"""

from __future__ import annotations

import json


def _dump(component) -> str:
    return json.dumps(component.to_plotly_json(), ensure_ascii=False, default=str)


def test_render_batch_defs_content_lists_defs():
    from app.ui.pages.batch_defs import render_batch_defs_content

    items = [
        {
            "id": 1,
            "code": "DOANH_THU",
            "name": "Doanh thu cuối tháng",
            "description": "Bộ doanh thu",
            "status": "ACTIVE",
            "max_parallel_per_ds": 2,
            "cnt_items": 3,
        },
        {
            "id": 2,
            "code": "CHI_PHI",
            "name": "Chi phí",
            "description": "",
            "status": "DRAFT",
            "max_parallel_per_ds": 1,
            "cnt_items": 0,
        },
    ]
    out = _dump(render_batch_defs_content(items, can_write=True))
    assert "DOANH_THU" in out
    assert "Doanh thu cuối tháng" in out
    assert "CHI_PHI" in out
    assert "/batches/1" in out
    assert "/batches/2" in out


def test_render_batch_defs_content_empty_and_error():
    from app.ui.pages.batch_defs import render_batch_defs_content

    assert "Chưa có bộ đối soát nào" in _dump(render_batch_defs_content([]))
    assert "Không thể tải" in _dump(render_batch_defs_content(None, error="Lỗi mạng"))


def test_render_def_items_table_archived_warning():
    from app.ui.pages.batch_def_edit import render_def_items_table

    items = [
        {
            "id": 10,
            "template_id": 5,
            "template_code": "DTP_TMPL",
            "template_name": "DTP hóa đơn",
            "template_status": "ARCHIVED",
            "template_version": 1,
            "seq_no": 1,
            "priority": 100,
            "profile_code": "BY_INVOICE",
            "data_source_id": None,
            "file_pattern": "*DTP*",
            "multi_file": True,
            "is_required": True,
            "params_override": {"p_ky": "{ky.thang}"},
        },
        {
            "id": 11,
            "template_id": 6,
            "template_code": "KHAC_TMPL",
            "template_name": "Khác",
            "template_status": "ACTIVE",
            "template_version": 2,
            "seq_no": 2,
            "priority": 200,
            "profile_code": None,
            "data_source_id": 3,
            "file_pattern": "*KHAC*",
            "multi_file": False,
            "is_required": False,
            "params_override": {},
        },
    ]
    out = _dump(render_def_items_table(items, can_write=True))
    assert "DTP_TMPL" in out
    assert "Đã lưu trữ" in out
    assert "KHAC_TMPL" in out
    assert "DS #3" in out
    assert "Mặc định template" in out


def test_render_preview_result_errors():
    from app.ui.pages.batch_def_edit import render_preview_result

    preview = {
        "def_id": 1,
        "period": "2026-02",
        "items": [
            {
                "item_id": 10,
                "template_code": "DTP_TMPL",
                "params": {"p_from": "2026-02-01T00:00:00", "p_ky": "202602"},
                "errors": [],
            },
            {
                "item_id": 11,
                "template_code": "KHAC_TMPL",
                "params": {},
                "errors": [{"code": "BATCH_PARAM_REQUIRED", "message": "Tham số p_ky là bắt buộc."}],
            },
        ],
    }
    out = _dump(render_preview_result(preview))
    assert "DTP_TMPL" in out
    assert "202602" in out
    assert "Tham số p_ky là bắt buộc." in out


def test_render_addable_list_reasons():
    from app.ui.pages.batch_def_edit import render_addable_list

    templates = [
        {
            "template_id": 1,
            "code": "DTP_TMPL",
            "name": "DTP",
            "status": "ACTIVE",
            "version": 1,
            "addable": True,
            "reason": None,
        },
        {
            "template_id": 2,
            "code": "OLD_TMPL",
            "name": "Cũ",
            "status": "ARCHIVED",
            "version": 1,
            "addable": False,
            "reason": "Template đã lưu trữ",
        },
    ]
    out = _dump(render_addable_list(templates))
    assert "DTP_TMPL" in out
    assert "Template đã lưu trữ" in out

    out_focused = _dump(render_addable_list(templates, focused_id=2))
    assert "OLD_TMPL" in out_focused
    assert "Cấu hình này thuộc template" in out_focused


def _find_id(comp, target_id):
    """Tìm component theo id trong cây layout (dump JSON làm phẳng con)."""
    if getattr(comp, "id", None) == target_id:
        return comp
    children = getattr(comp, "children", None)
    if isinstance(children, (list, tuple)):
        for c in children:
            found = _find_id(c, target_id)
            if found is not None:
                return found
    elif children is not None:
        return _find_id(children, target_id)
    return None


def _texts(comp) -> list[str]:
    """Lấy mọi chuỗi lá trong cây component (dump JSON cắt ngắn text lồng)."""
    if isinstance(comp, str):
        return [comp]
    if isinstance(comp, (list, tuple)):
        out: list[str] = []
        for c in comp:
            out.extend(_texts(c))
        return out
    if hasattr(comp, "children"):
        return _texts(comp.children)
    return []


def test_delete_modal_warns_runs_deleted_together(monkeypatch):
    """Task 86: modal Xóa phải cảnh báo các lần chạy của bộ cũng bị xóa cùng,
    và không còn câu cũ '(chỉ xóa được khi chưa có lần chạy nào)'."""
    from types import SimpleNamespace

    import app.ui.pages.batch_defs as bdefs

    monkeypatch.setattr(bdefs, "get_current_ctx", lambda: SimpleNamespace(user_id=1, username="admin", roles=["ADMIN"]))
    modal = _find_id(bdefs.layout(), "bdef-delete-modal")
    assert modal is not None
    text = " ".join(_texts(modal))
    assert "các lần chạy của bộ sẽ bị xóa hoàn toàn khỏi hệ thống" in text
    assert "vẫn còn trong Lịch sử" in text
    assert "chỉ xóa được khi chưa có lần chạy nào" not in text


def _run_delete_confirm(monkeypatch, deleted_runs: int):
    """Gọi trực tiếp _run_list_action như khi bấm Xác nhận ở modal Xóa."""
    from types import SimpleNamespace

    import dash

    import app.ui.pages.batch_defs as bdefs
    from app.schemas.errors import ServiceResult

    admin = SimpleNamespace(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])
    monkeypatch.setattr(bdefs, "get_current_ctx", lambda: admin)
    monkeypatch.setattr(
        bdefs,
        "delete_batch_def",
        lambda _ctx, _did: ServiceResult(
            ok=True, data={"id": 1, "code": "DOANH_THU", "deleted": True, "deleted_runs": deleted_runs}
        ),
    )
    monkeypatch.setattr(bdefs, "_load_list", lambda _a, _b: [])
    monkeypatch.setattr(
        dash,
        "callback_context",
        SimpleNamespace(
            triggered=[{"prop_id": "bdef-delete-modal-confirm.n_clicks", "value": 1}],
            triggered_id="bdef-delete-modal-confirm",
        ),
    )
    return bdefs._run_list_action(None, 1, [], {"action": "delete", "id": 1})


def test_delete_confirm_toast_has_run_count(monkeypatch):
    """Task 86: xác nhận xóa bộ có 3 lần chạy → toast báo rõ số lần chạy."""
    _store, notif, _arch, _del = _run_delete_confirm(monkeypatch, deleted_runs=3)
    assert "cùng 3 lần chạy" in _dump(notif)


def test_delete_confirm_toast_no_runs_keeps_old_message(monkeypatch):
    """Task 86: xóa bộ 0 lần chạy → toast giữ câu cũ."""
    _store, notif, _arch, _del = _run_delete_confirm(monkeypatch, deleted_runs=0)
    assert "Đã xóa bộ đối soát thành công." in _dump(notif)
