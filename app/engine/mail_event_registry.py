"""Event Schema Registry for Mail Template Studio.

Định nghĩa danh mục sự kiện nghiệp vụ cứng, metadata biến và mock scenario datasets.
Module hàm thuần (pure engine), không phụ thuộc vào database hay UI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Regex bắt token biến dạng {{ variable }} hoặc {{ nested.property }}
TOKEN_REGEX = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


@dataclass(frozen=True)
class EventVariable:
    key: str
    label: str
    data_type: str  # "string", "integer", "number", "array", "link_token"
    category: str  # "actor", "source", "summary", "collection", "links", "system"
    description: str = ""
    example_value: Any = None


@dataclass(frozen=True)
class EventDefinition:
    code: str
    menu_code: str
    label: str
    description: str
    variables: list[EventVariable] = field(default_factory=list)
    scenarios: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def allowed_keys(self) -> set[str]:
        keys = set()
        for v in self.variables:
            keys.add(v.key)
            if "." in v.key:
                keys.add(v.key.split(".", 1)[1])
        return keys


# 1. Sự kiện Hoàn tất chạy bộ đối soát
EVENT_BATCH_RUN = EventDefinition(
    code="BATCH_RUN_COMPLETED",
    menu_code="batch_run",
    label="Hoàn tất chạy bộ đối soát",
    description="Sự kiện phát sinh sau khi worker hoàn tất thực hiện một phiên chạy bộ đối soát (Batch Run)",
    variables=[
        EventVariable(
            "actor.name", "Người thực hiện", "string", "actor", "Họ tên người bấm chạy hoặc Schedule", "Nguyễn Văn A"
        ),
        EventVariable(
            "batch.name",
            "Tên bộ đối soát",
            "string",
            "source",
            "Tên cấu hình bộ đối soát",
            "Đối soát Doanh thu Cuối ngày",
        ),
        EventVariable(
            "batch.period",
            "Kỳ đối soát",
            "string",
            "source",
            "Kỳ đối soát định dạng MM/YYYY hoặc YYYY-MM-DD",
            "10/2026",
        ),
        EventVariable(
            "batch.run_code",
            "Mã phiên chạy",
            "string",
            "source",
            "Mã định danh duy nhất của Batch Run",
            "BR-202610-0042",
        ),
        EventVariable("summary.total", "Tổng số template", "integer", "summary", "Tổng số template trong bộ", 20),
        EventVariable(
            "summary.success", "Số template thành công", "integer", "summary", "Số template khớp hoặc không lệch", 18
        ),
        EventVariable(
            "summary.failed", "Số template có lỗi", "integer", "summary", "Số template có lỗi hoặc lệch giá trị", 2
        ),
        EventVariable(
            "batch.items", "Danh sách template", "array", "collection", "Danh sách chi tiết các template và trạng thái"
        ),
        EventVariable(
            "links.result", "Liên kết kết quả", "link_token", "links", "Đích đến an toàn mở trang chi tiết Batch Run"
        ),
        EventVariable(
            "created_at",
            "Thời gian hoàn thành",
            "string",
            "system",
            "Thời điểm kết thúc phiên chạy",
            "18/11/2026 14:30",
        ),
    ],
    scenarios={
        "success": {
            "actor.name": "Nguyễn Văn A",
            "batch.name": "Đối soát Doanh thu Cuối ngày",
            "batch.period": "10/2026",
            "batch.run_code": "BR-202610-0042",
            "summary.total": 20,
            "summary.success": 20,
            "summary.failed": 0,
            "batch.items": [
                {"name": "DTP_HOA_DON_TAC_NGHIEP", "status": "Khớp", "detail": "100% khớp dữ liệu"},
                {"name": "DTP_DOANH_THU_THE", "status": "Khớp", "detail": "100% khớp dữ liệu"},
            ],
            "links.result": "/batch-runs/BR-202610-0042",
            "created_at": "18/11/2026 14:30",
        },
        "error": {
            "actor.name": "Nguyễn Văn A",
            "batch.name": "Đối soát Doanh thu Cuối ngày",
            "batch.period": "10/2026",
            "batch.run_code": "BR-202610-0042",
            "summary.total": 20,
            "summary.success": 18,
            "summary.failed": 2,
            "batch.items": [
                {"name": "NGAN_HANG_B", "status": "Lỗi", "detail": "Mất kết nối Oracle timeout 300s"},
                {"name": "PHI_HA_TANG", "status": "Lệch", "detail": "Lệch 15 bản ghi (42.500.000 VNĐ)"},
            ],
            "links.result": "/batch-runs/BR-202610-0042",
            "created_at": "18/11/2026 14:30",
        },
        "empty": {
            "actor.name": "Nguyễn Văn A",
            "batch.name": "Đối soát Doanh thu Cuối ngày",
            "batch.period": "10/2026",
            "batch.run_code": "BR-202610-0043",
            "summary.total": 0,
            "summary.success": 0,
            "summary.failed": 0,
            "batch.items": [],
            "links.result": "/batch-runs/BR-202610-0043",
            "created_at": "18/11/2026 14:30",
        },
    },
)

# 2. Sự kiện Hoàn tất kết xuất báo cáo
EVENT_REPORT_EXPORT = EventDefinition(
    code="REPORT_EXPORT_COMPLETED",
    menu_code="report",
    label="Hoàn tất kết xuất báo cáo",
    description="Sự kiện phát sinh sau khi tạo file báo cáo nền (XLSX, CSV, ZIP)",
    variables=[
        EventVariable(
            "actor.name", "Người xuất báo cáo", "string", "actor", "Họ tên người yêu cầu kết xuất", "Trần Thị B"
        ),
        EventVariable(
            "report.name", "Tên báo cáo", "string", "source", "Tên báo cáo được kết xuất", "Báo cáo tổng hợp chênh lệch"
        ),
        EventVariable(
            "export.filename",
            "Tên file kết xuất",
            "string",
            "source",
            "Tên tệp tin đã tạo",
            "BAO_CAO_CHENH_LECH_202610.xlsx",
        ),
        EventVariable("export.rows", "Số dòng dữ liệu", "integer", "summary", "Tổng số bản ghi trong file", 12458),
        EventVariable(
            "export.format", "Định dạng file", "string", "source", "Định dạng tệp tin (XLSX, CSV, ZIP)", "XLSX"
        ),
        EventVariable(
            "links.download",
            "Liên kết tải về",
            "link_token",
            "links",
            "Liên kết an toàn để tải file",
            "/downloads/report-001",
        ),
        EventVariable("created_at", "Thời gian kết xuất", "string", "system", "Thời điểm tạo file", "18/11/2026 15:00"),
    ],
    scenarios={
        "success": {
            "actor.name": "Trần Thị B",
            "report.name": "Báo cáo tổng hợp chênh lệch",
            "export.filename": "BAO_CAO_CHENH_LECH_202610.xlsx",
            "export.rows": 12458,
            "export.format": "XLSX",
            "links.download": "/downloads/report-001",
            "created_at": "18/11/2026 15:00",
        },
        "error": {
            "actor.name": "Trần Thị B",
            "report.name": "Báo cáo tổng hợp chênh lệch",
            "export.filename": "BAO_CAO_CHENH_LECH_202610.xlsx",
            "export.rows": 150,
            "export.format": "XLSX",
            "links.download": "/downloads/report-001",
            "created_at": "18/11/2026 15:00",
        },
        "empty": {
            "actor.name": "Trần Thị B",
            "report.name": "Báo cáo tổng hợp chênh lệch",
            "export.filename": "BAO_CAO_CHENH_LECH_202610.xlsx",
            "export.rows": 0,
            "export.format": "XLSX",
            "links.download": "/downloads/report-001",
            "created_at": "18/11/2026 15:00",
        },
    },
)

# 3. Sự kiện Xuất danh sách Template đối soát
EVENT_TEMPLATE_LIST = EventDefinition(
    code="TEMPLATE_LIST_EXPORT",
    menu_code="template",
    label="Xuất danh sách mẫu đối soát",
    description="Sự kiện gửi thư kèm danh sách cấu hình template từ trang Quản lý Template",
    variables=[
        EventVariable("actor.name", "Người gửi", "string", "actor", "Họ tên người gửi thư", "Lê Văn C"),
        EventVariable(
            "items_count", "Số lượng template", "integer", "summary", "Số lượng cấu hình template được xuất", 12
        ),
        EventVariable(
            "files_list", "Tệp đính kèm", "array", "source", "Danh sách tên các tệp đính kèm", ["templates_export.xlsx"]
        ),
        EventVariable(
            "filters_info", "Bộ lọc áp dụng", "string", "source", "Mô tả tiêu chí tìm kiếm", "Trạng thái: Hoạt động"
        ),
        EventVariable(
            "notes", "Ghi chú kèm theo", "string", "source", "Lời nhắn của người gửi", "Gửi anh chị danh sách cập nhật."
        ),
        EventVariable(
            "links.template",
            "Liên kết trang Template",
            "link_token",
            "links",
            "Liên kết mở trang Quản lý Template",
            "/templates",
        ),
        EventVariable("created_at", "Thời gian xuất", "string", "system", "Thời điểm kết xuất", "18/11/2026 15:30"),
    ],
    scenarios={
        "success": {
            "actor.name": "Lê Văn C",
            "items_count": 12,
            "files_list": ["templates_export.xlsx"],
            "filters_info": "Trạng thái: Hoạt động",
            "notes": "Gửi anh chị danh sách cấu hình template đối soát cập nhật mới nhất.",
            "links.template": "/templates",
            "created_at": "18/11/2026 15:30",
        },
        "error": {
            "actor.name": "Lê Văn C",
            "items_count": 1,
            "files_list": ["templates_export.xlsx"],
            "filters_info": "Bộ lọc lỗi",
            "notes": "Có 1 template bị vô hiệu hóa.",
            "links.template": "/templates",
            "created_at": "18/11/2026 15:30",
        },
        "empty": {
            "actor.name": "Lê Văn C",
            "items_count": 0,
            "files_list": [],
            "filters_info": "Không có bộ lọc",
            "notes": "",
            "links.template": "/templates",
            "created_at": "18/11/2026 15:30",
        },
    },
)

# 4. Sự kiện Xuất dữ liệu chung (Fallback cho User, Menu, Data Source...)
EVENT_GENERAL_EXPORT = EventDefinition(
    code="GENERAL_EXPORT",
    menu_code="common",
    label="Kết xuất dữ liệu chung (Fallback)",
    description="Sự kiện mặc định dùng cho mọi tính năng xuất dữ liệu chưa đăng ký mẫu riêng",
    variables=[
        EventVariable("actor.name", "Người gửi", "string", "actor", "Họ tên người gửi thư", "Quản trị viên"),
        EventVariable(
            "module_name", "Tên phân hệ", "string", "source", "Tên phân hệ xuất dữ liệu", "Danh sách người dùng"
        ),
        EventVariable("items_count", "Số lượng bản ghi", "integer", "summary", "Tổng số dòng/mục được xuất", 50),
        EventVariable(
            "files_list", "Tệp đính kèm", "array", "source", "Danh sách tệp tin đính kèm", ["export_data.xlsx"]
        ),
        EventVariable(
            "notes",
            "Ghi chú kèm theo",
            "string",
            "source",
            "Lời nhắn của người gửi",
            "Gửi dữ liệu kết xuất theo yêu cầu.",
        ),
        EventVariable(
            "links.download",
            "Liên kết tải về",
            "link_token",
            "links",
            "Liên kết an toàn để tải file",
            "/downloads/general-001",
        ),
        EventVariable("created_at", "Thời gian xuất", "string", "system", "Thời điểm kết xuất", "18/11/2026 16:00"),
    ],
    scenarios={
        "success": {
            "actor.name": "Quản trị viên",
            "module_name": "Danh sách người dùng",
            "items_count": 50,
            "files_list": ["users_export.xlsx"],
            "notes": "Gửi danh sách tài khoản theo yêu cầu rà soát bảo mật.",
            "links.download": "/downloads/general-001",
            "created_at": "18/11/2026 16:00",
        },
        "error": {
            "actor.name": "Quản trị viên",
            "module_name": "Danh sách người dùng",
            "items_count": 2,
            "files_list": ["users_export.xlsx"],
            "notes": "Có tài khoản cần lưu ý.",
            "links.download": "/downloads/general-001",
            "created_at": "18/11/2026 16:00",
        },
        "empty": {
            "actor.name": "Quản trị viên",
            "module_name": "Danh sách người dùng",
            "items_count": 0,
            "files_list": [],
            "notes": "",
            "links.download": "/downloads/general-001",
            "created_at": "18/11/2026 16:00",
        },
    },
)

# 5. Sự kiện Tạo mới người dùng (Welcome Email)
EVENT_USER_CREATED = EventDefinition(
    code="USER_CREATED",
    menu_code="user",
    label="Tạo mới người dùng",
    description="Sự kiện gửi thư thông tin tài khoản và chào mừng khi Quản trị viên tạo người dùng mới",
    variables=[
        EventVariable("user.username", "Tên đăng nhập", "string", "source", "Tên đăng nhập người dùng mới", "nguyenvana"),
        EventVariable("user.full_name", "Họ và tên", "string", "source", "Họ và tên đầy đủ", "Nguyễn Văn A"),
        EventVariable("user.email", "Địa chỉ email", "string", "source", "Email nhận thư", "nguyenvana@reconhub.vn"),
        EventVariable("user.roles", "Vai trò", "string", "source", "Các vai trò phân quyền", "Operator, Viewer"),
        EventVariable("user.temp_password", "Mật khẩu ban đầu", "string", "source", "Mật khẩu khởi tạo được cấp", "ReconHub@2026"),
        EventVariable("user.must_change_pw", "Yêu cầu đổi mật khẩu", "string", "source", "Trạng thái bắt buộc đổi mật khẩu", "Có"),
        EventVariable("user.is_active", "Trạng thái hoạt động", "string", "source", "Trạng thái kích hoạt tài khoản", "Y"),
        EventVariable("actor.name", "Quản trị viên tạo", "string", "actor", "Họ tên Admin tạo tài khoản", "Quản trị viên"),
        EventVariable("actor.username", "Username Admin", "string", "actor", "Tên đăng nhập Admin", "admin"),
        EventVariable("created_at", "Thời điểm tạo", "string", "system", "Thời gian tạo tài khoản", "18/11/2026 16:00"),
        EventVariable("system.app_name", "Tên ứng dụng", "string", "system", "Tên hệ thống", "ReconHub"),
        EventVariable("links.login", "Liên kết đăng nhập", "link_token", "links", "Liên kết mở trang đăng nhập", "/login"),
        EventVariable("links.page", "Liên kết trang Người dùng", "link_token", "links", "Liên kết mở trang Người dùng", "/users"),
    ],
    scenarios={
        "success": {
            "user.username": "nguyenvana",
            "username": "nguyenvana",
            "user.full_name": "Nguyễn Văn A",
            "full_name": "Nguyễn Văn A",
            "user.email": "nguyenvana@reconhub.vn",
            "email": "nguyenvana@reconhub.vn",
            "user.roles": "Operator, Viewer",
            "roles": "Operator, Viewer",
            "user.temp_password": "ReconHub@2026",
            "temp_password": "ReconHub@2026",
            "user.must_change_pw": "Có",
            "must_change_pw": "Có",
            "user.is_active": "Y",
            "is_active": "Y",
            "actor.name": "Quản trị viên",
            "actor.username": "admin",
            "created_at": "18/11/2026 16:00",
            "system.app_name": "ReconHub",
            "links.login": "/login",
            "links.page": "/users",
        },
        "error": {
            "user.username": "nguyenvana",
            "username": "nguyenvana",
            "user.full_name": "Nguyễn Văn A",
            "full_name": "Nguyễn Văn A",
            "user.email": "nguyenvana@reconhub.vn",
            "email": "nguyenvana@reconhub.vn",
            "user.roles": "Viewer",
            "roles": "Viewer",
            "user.temp_password": "ReconHub@2026",
            "temp_password": "ReconHub@2026",
            "user.must_change_pw": "Có",
            "must_change_pw": "Có",
            "user.is_active": "N",
            "is_active": "N",
            "actor.name": "Quản trị viên",
            "actor.username": "admin",
            "created_at": "18/11/2026 16:00",
            "system.app_name": "ReconHub",
            "links.login": "/login",
            "links.page": "/users",
        },
        "empty": {
            "user.username": "test_user",
            "username": "test_user",
            "user.full_name": "Người dùng thử nghiệm",
            "full_name": "Người dùng thử nghiệm",
            "user.email": "test@reconhub.vn",
            "email": "test@reconhub.vn",
            "user.roles": "Viewer",
            "roles": "Viewer",
            "user.temp_password": "ReconHub@2026",
            "temp_password": "ReconHub@2026",
            "user.must_change_pw": "Không",
            "must_change_pw": "Không",
            "user.is_active": "Y",
            "is_active": "Y",
            "actor.name": "Quản trị viên",
            "actor.username": "admin",
            "created_at": "18/11/2026 16:00",
            "system.app_name": "ReconHub",
            "links.login": "/login",
            "links.page": "/users",
        },
    },
)

# 6. Sự kiện Xuất danh sách người dùng
EVENT_USER_LIST = EventDefinition(
    code="USER_LIST_EXPORT",
    menu_code="user",
    label="Xuất danh sách người dùng",
    description="Sự kiện gửi thư đính kèm danh sách tài khoản người dùng từ trang Quản lý Người dùng",
    variables=[
        EventVariable("actor.name", "Người gửi", "string", "actor", "Họ tên người gửi thư", "Quản trị viên"),
        EventVariable("items_count", "Số lượng tài khoản", "integer", "summary", "Tổng số tài khoản được xuất", 25),
        EventVariable("files_list", "Tệp đính kèm", "array", "source", "Danh sách tệp tin đính kèm", ["danh_sach_nguoi_dung.xlsx"]),
        EventVariable("filters_info", "Bộ lọc áp dụng", "string", "source", "Mô tả tiêu chí tìm kiếm", "Vai trò: Tất cả"),
        EventVariable("notes", "Ghi chú kèm theo", "string", "source", "Lời nhắn của người gửi", "Gửi anh chị danh sách tài khoản cập nhật."),
        EventVariable("links.page", "Liên kết trang Người dùng", "link_token", "links", "Liên kết mở trang Người dùng", "/users"),
        EventVariable("created_at", "Thời gian xuất", "string", "system", "Thời điểm kết xuất", "18/11/2026 16:00"),
    ],
    scenarios={
        "success": {
            "actor.name": "Quản trị viên",
            "items_count": 25,
            "files_list": ["danh_sach_nguoi_dung.xlsx"],
            "filters_info": "Vai trò: Tất cả",
            "notes": "Gửi anh chị danh sách tài khoản người dùng cập nhật.",
            "links.page": "/users",
            "created_at": "18/11/2026 16:00",
        },
        "error": {
            "actor.name": "Quản trị viên",
            "items_count": 1,
            "files_list": ["danh_sach_nguoi_dung.xlsx"],
            "filters_info": "Trạng thái: Tạm khóa",
            "notes": "Có tài khoản bị tạm khóa cần xử lý.",
            "links.page": "/users",
            "created_at": "18/11/2026 16:00",
        },
        "empty": {
            "actor.name": "Quản trị viên",
            "items_count": 0,
            "files_list": [],
            "filters_info": "Không tìm thấy tài khoản",
            "notes": "",
            "links.page": "/users",
            "created_at": "18/11/2026 16:00",
        },
    },
)

# Registry ánh xạ mã sự kiện -> EventDefinition
EVENT_REGISTRY: dict[str, EventDefinition] = {
    EVENT_BATCH_RUN.code: EVENT_BATCH_RUN,
    EVENT_REPORT_EXPORT.code: EVENT_REPORT_EXPORT,
    EVENT_TEMPLATE_LIST.code: EVENT_TEMPLATE_LIST,
    EVENT_USER_CREATED.code: EVENT_USER_CREATED,
    EVENT_USER_LIST.code: EVENT_USER_LIST,
    EVENT_GENERAL_EXPORT.code: EVENT_GENERAL_EXPORT,
}


def get_event_definition(event_code: str) -> EventDefinition | None:
    """Lấy metadata của một sự kiện theo mã."""
    return EVENT_REGISTRY.get(event_code)


def list_event_definitions() -> list[EventDefinition]:
    """Danh sách tất cả các sự kiện nghiệp vụ được hỗ trợ."""
    return list(EVENT_REGISTRY.values())


def get_allowed_variable_keys(event_code: str) -> set[str]:
    """Tập hợp tất cả các key biến hợp lệ của một sự kiện."""
    event = get_event_definition(event_code)
    if not event:
        return set()
    return event.allowed_keys


def get_sample_payload(event_code: str, scenario: str = "success") -> dict[str, Any]:
    """Lấy dữ liệu mẫu cho Live Preview theo sự kiện và scenario (success/error/empty)."""
    event = get_event_definition(event_code)
    if not event:
        return {}
    if scenario in event.scenarios:
        return dict(event.scenarios[scenario])
    return dict(event.scenarios.get("success", {}))


def extract_variable_keys(text: str) -> list[str]:
    """Trích xuất tất cả các token dạng {{ variable }} từ chuỗi."""
    if not text:
        return []
    return [m.group(1).strip() for m in TOKEN_REGEX.finditer(text)]


def validate_text_variables(text: str, event_code: str) -> list[str]:
    """Kiểm tra xem chuỗi có chứa biến nào không thuộc schema của event không.

    Trả về danh sách các biến vi phạm.
    """
    allowed = get_allowed_variable_keys(event_code)
    used = extract_variable_keys(text)
    invalid = [k for k in used if k not in allowed]
    return list(dict.fromkeys(invalid))  # Giữ thứ tự và loại bỏ trùng lặp
