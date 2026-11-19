"""Mail Token Inspector Engine.

Cung cấp cơ chế Dynamic Token Introspection:
Tự động quét cấu trúc trường dữ liệu (fields) của các bảng từ SQLAlchemy Core Metadata
theo từng Màn hình/Phân hệ (Page / Menu), kết hợp với System Tokens và Mock Scenarios
phục vụ cho Mail Template Studio và các dịch vụ gửi email tự động.
"""

from __future__ import annotations

from typing import Any

from app.db.metadata import metadata as app_metadata

# Danh sách cột nhạy cảm cần loại trừ vì lý do an toàn thông tin
SENSITIVE_COLUMNS = {
    "PASSWORD_HASH",
    "SESSION_VERSION",
    "ROW_VERSION",
    "FAILED_COUNT",
    "TELEGRAM_LINK_CODE",
    "TELEGRAM_LINK_EXPIRES_AT",
    "CONN_STRING_ENC",
    "PASSWORD_ENC",
}

# Ánh xạ tên cột sang nhãn tiếng Việt thân thiện
COLUMN_LABELS: dict[str, str] = {
    "ID": "Mã ID hệ thống",
    "USERNAME": "Tên đăng nhập",
    "FULL_NAME": "Họ và tên",
    "EMAIL": "Địa chỉ email",
    "IS_ACTIVE": "Trạng thái hoạt động (Y/N)",
    "MUST_CHANGE_PW": "Yêu cầu đổi mật khẩu (Y/N)",
    "LOCKED_UNTIL": "Tạm khóa đến lúc",
    "LAST_LOGIN_AT": "Lần đăng nhập cuối",
    "PW_CHANGED_AT": "Lần đổi mật khẩu cuối",
    "CREATED_BY": "Người tạo",
    "CREATED_AT": "Thời điểm tạo",
    "UPDATED_AT": "Thời điểm cập nhật",
    "TELEGRAM_CHAT_ID": "ID Telegram kết nối",
    "CODE": "Mã định danh",
    "NAME": "Tên gọi",
    "DESCRIPTION": "Mô tả",
    "STATUS": "Trạng thái",
    "HOST": "Máy chủ (Host)",
    "PORT": "Cổng kết nối (Port)",
    "SERVICE_NAME": "Tên dịch vụ Oracle",
    "PERIOD": "Kỳ đối soát",
    "STARTED_AT": "Thời điểm bắt đầu",
    "COMPLETED_AT": "Thời điểm hoàn tất",
    "SUMMARY": "Tóm tắt kết quả",
}

# Cấu hình ánh xạ từng Màn hình (Page) -> Bảng chính (Table) và thuộc tính mở rộng
PAGE_CONFIG: dict[str, dict[str, Any]] = {
    "user": {
        "label": "Người dùng (/users)",
        "table_name": "RECON_USER",
        "prefix": "user",
        "page_url": "/users",
        "virtual_fields": [
            {
                "key": "roles",
                "label": "Vai trò phân quyền",
                "data_type": "string",
                "example": "Operator, Viewer",
                "description": "Danh sách các vai trò được cấp cho tài khoản",
            },
            {
                "key": "temp_password",
                "label": "Mật khẩu khởi tạo ban đầu",
                "data_type": "string",
                "example": "ReconHub@2026",
                "description": "Mật khẩu ban đầu được bàn giao (chỉ dùng khi gửi mật khẩu khởi tạo)",
            },
        ],
        "mock_defaults": {
            "username": "nguyenvana",
            "full_name": "Nguyễn Văn A",
            "email": "nguyenvana@reconhub.vn",
            "is_active": "Y",
            "must_change_pw": "Y",
            "roles": "Operator, Viewer",
            "temp_password": "ReconHub@2026",
            "created_at": "18/11/2026 14:30",
            "last_login_at": "18/11/2026 14:30",
        },
    },
    "template": {
        "label": "Mẫu đối soát (/templates)",
        "table_name": "RECON_TEMPLATE",
        "prefix": "template",
        "page_url": "/templates",
        "virtual_fields": [
            {
                "key": "items_count",
                "label": "Số lượng template",
                "data_type": "integer",
                "example": 15,
                "description": "Tổng số mẫu đối soát được kết xuất",
            },
            {
                "key": "files_list",
                "label": "Danh sách file đính kèm",
                "data_type": "array",
                "example": ["danh_sach_template.xlsx"],
                "description": "Tên các file báo cáo đính kèm",
            },
        ],
        "mock_defaults": {
            "code": "DTP_HOA_DON_TAC_NGHIEP",
            "name": "Hóa đơn tác nghiệp DTP",
            "status": "ACTIVE",
            "items_count": 15,
            "files_list": ["danh_sach_template.xlsx"],
            "created_at": "18/11/2026 14:30",
        },
    },
    "batch_run": {
        "label": "Bộ đối soát (/batch-runs)",
        "table_name": "RECON_BATCH_RUN",
        "prefix": "batch",
        "page_url": "/batch-runs",
        "virtual_fields": [
            {
                "key": "batch_name",
                "label": "Tên cấu hình bộ đối soát",
                "data_type": "string",
                "example": "Đối soát Doanh thu Cuối ngày",
                "description": "Tên bộ đối soát được thực thi",
            },
            {
                "key": "summary_total",
                "label": "Tổng số template",
                "data_type": "integer",
                "example": 20,
                "description": "Tổng số template chạy trong bộ",
            },
            {
                "key": "summary_success",
                "label": "Số template khớp",
                "data_type": "integer",
                "example": 18,
                "description": "Số template hoàn thành khớp",
            },
            {
                "key": "summary_failed",
                "label": "Số template có lệch/lỗi",
                "data_type": "integer",
                "example": 2,
                "description": "Số template có sai lệch hoặc lỗi",
            },
        ],
        "mock_defaults": {
            "batch_name": "Đối soát Doanh thu Cuối ngày",
            "period": "10/2026",
            "status": "COMPLETED",
            "summary_total": 20,
            "summary_success": 18,
            "summary_failed": 2,
            "created_at": "18/11/2026 14:30",
        },
    },
    "data_source": {
        "label": "Nguồn dữ liệu (/datasources)",
        "table_name": "RECON_DATA_SOURCE",
        "prefix": "datasource",
        "page_url": "/datasources",
        "virtual_fields": [],
        "mock_defaults": {
            "code": "ORACLE_BILLING_PROD",
            "name": "Hệ thống Tính cước Billing PROD",
            "host": "10.0.1.50",
            "port": 1521,
            "service_name": "BILLING_DB",
            "status": "ACTIVE",
            "created_at": "18/11/2026 14:30",
        },
    },
    "issue": {
        "label": "Xử lý chênh lệch (/issues)",
        "table_name": "RECON_ISSUE",
        "prefix": "issue",
        "page_url": "/issues",
        "virtual_fields": [
            {
                "key": "issue_count",
                "label": "Số lượng chênh lệch",
                "data_type": "integer",
                "example": 5,
                "description": "Số lượng issue phát hiện",
            }
        ],
        "mock_defaults": {
            "status": "OPEN",
            "issue_count": 5,
            "created_at": "18/11/2026 14:30",
        },
    },
    "common": {
        "label": "Chung / Hệ thống",
        "table_name": None,
        "prefix": "common",
        "page_url": "/",
        "virtual_fields": [
            {
                "key": "module_name",
                "label": "Tên phân hệ",
                "data_type": "string",
                "example": "Hệ thống ReconHub",
                "description": "Tên chức năng hoặc module gửi thư",
            },
            {
                "key": "items_count",
                "label": "Số lượng bản ghi",
                "data_type": "integer",
                "example": 50,
                "description": "Tổng số bản ghi liên quan",
            },
        ],
        "mock_defaults": {
            "module_name": "Hệ thống ReconHub",
            "items_count": 50,
            "created_at": "18/11/2026 14:30",
        },
    },
}

# Các Token hệ thống dùng chung luôn xuất hiện cho mọi trang
SYSTEM_TOKENS: list[dict[str, Any]] = [
    {
        "key": "actor.name",
        "label": "Người thực hiện",
        "data_type": "string",
        "example": "Quản trị viên",
        "description": "Họ và tên người dùng hoặc tiến trình thực hiện hành động",
    },
    {
        "key": "actor.username",
        "label": "Tài khoản thực hiện",
        "data_type": "string",
        "example": "admin",
        "description": "Username của người thực hiện hành động",
    },
    {
        "key": "created_at",
        "label": "Thời điểm phát sinh",
        "data_type": "string",
        "example": "18/11/2026 16:00",
        "description": "Thời gian phát sinh sự kiện hoặc kết xuất",
    },
    {
        "key": "system.app_name",
        "label": "Tên ứng dụng",
        "data_type": "string",
        "example": "ReconHub",
        "description": "Tên hệ thống ứng dụng đối soát",
    },
    {
        "key": "links.login",
        "label": "Liên kết đăng nhập",
        "data_type": "link_token",
        "example": "/login",
        "description": "Đường dẫn trang đăng nhập hệ thống",
    },
    {
        "key": "links.page",
        "label": "Liên kết trang nghiệp vụ",
        "data_type": "link_token",
        "example": "/users",
        "description": "Đường dẫn quay lại màn hình phát sinh thông báo",
    },
    {
        "key": "notes",
        "label": "Ghi chú / Lời nhắn",
        "data_type": "string",
        "example": "Thông báo tự động từ hệ thống.",
        "description": "Lời nhắn hoặc ghi chú kèm theo",
    },
]


def get_available_pages() -> list[dict[str, str]]:
    """Trả về danh sách các Page hỗ trợ kết nối Mail Template Studio."""
    return [
        {"value": code, "label": cfg["label"]}
        for code, cfg in PAGE_CONFIG.items()
    ]


def introspect_tokens_for_page(page_code: str) -> dict[str, list[dict[str, Any]]]:
    """Tự động quét cấu trúc trường của Bảng tương ứng với Page và trả về 2 nhóm:

    1. 'table_fields': Các trường dữ liệu từ database schema (bỏ các cột nhạy cảm) và virtual fields.
    2. 'system_fields': Các trường hệ thống chung.
    """
    cfg = PAGE_CONFIG.get(page_code, PAGE_CONFIG["common"])
    table_name = cfg.get("table_name")
    prefix = cfg.get("prefix", "data")
    virtual_fields = cfg.get("virtual_fields", [])

    table_tokens: list[dict[str, Any]] = []

    # 1. Quét từ SQLAlchemy Table metadata nếu có bảng
    if table_name and table_name in app_metadata.tables:
        table = app_metadata.tables[table_name]
        for col in table.columns:
            c_name = col.name
            if c_name.upper() in SENSITIVE_COLUMNS:
                continue

            low_name = c_name.lower()
            lbl = COLUMN_LABELS.get(c_name.upper(), f"Trường {c_name}")
            col_type = str(col.type).lower()
            data_type = "string"
            if "int" in col_type or "bigint" in col_type:
                data_type = "integer"
            elif "num" in col_type or "decimal" in col_type or "float" in col_type:
                data_type = "number"
            elif "date" in col_type or "time" in col_type:
                data_type = "string"

            # Cung cấp cả token có tiền tố (user.username) và token ngắn (username)
            table_tokens.append(
                {
                    "key": f"{prefix}.{low_name}",
                    "alias": low_name,
                    "label": f"{lbl} ({{{{{prefix}.{low_name}}}}})",
                    "data_type": data_type,
                    "category": "table",
                    "description": f"Cột {c_name} trong bảng {table_name}",
                    "example_value": cfg.get("mock_defaults", {}).get(low_name, f"[{lbl}]"),
                }
            )

    # 2. Thêm các virtual fields đặc thù của page (như roles, temp_password...)
    for vf in virtual_fields:
        k = vf["key"]
        table_tokens.append(
            {
                "key": f"{prefix}.{k}",
                "alias": k,
                "label": f"{vf['label']} ({{{{{prefix}.{k}}}}})",
                "data_type": vf.get("data_type", "string"),
                "category": "table",
                "description": vf.get("description", ""),
                "example_value": vf.get("example", cfg.get("mock_defaults", {}).get(k, "")),
            }
        )

    # 3. Chuẩn hóa System fields
    page_url = cfg.get("page_url", "/")
    sys_tokens: list[dict[str, Any]] = []
    for sf in SYSTEM_TOKENS:
        item = dict(sf)
        item["category"] = "system"
        if item["key"] == "links.page":
            item["example_value"] = page_url
        else:
            item["example_value"] = sf.get("example")
        sys_tokens.append(item)

    return {
        "table_fields": table_tokens,
        "system_fields": sys_tokens,
    }


def get_flat_tokens_for_page(page_code: str) -> list[dict[str, Any]]:
    """Trả về danh sách phẳng toàn bộ tokens của Page để nạp vào Badges hoặc Event Registry."""
    grouped = introspect_tokens_for_page(page_code)
    return grouped["table_fields"] + grouped["system_fields"]


def get_all_valid_tokens_set(
    page_code: str | None = None,
    event_code: str | None = None,
) -> set[str]:
    """Trả về tập hợp toàn bộ key token hợp lệ cho một trang và/hoặc sự kiện.

    Bao gồm:
    - Biến của trang cụ thể (cả tiền tố lẫn tên ngắn).
    - Biến hệ thống chung.
    - Biến sự kiện cứng từ EVENT_REGISTRY (nếu có).
    - Toàn bộ biến từ tất cả các trang đã đăng ký (user, template, batch_run, v.v.).
    """
    keys: set[str] = set()

    # 1. Thêm biến hệ thống
    for sf in SYSTEM_TOKENS:
        k = sf.get("key", "")
        if k:
            keys.add(k)
            if "." in k:
                keys.add(k.split(".", 1)[1])

    # 2. Thêm biến từ page_code cụ thể nếu được chỉ định
    target_pages = [page_code] if page_code and page_code in PAGE_CONFIG else list(PAGE_CONFIG.keys())
    for p_code in target_pages:
        grouped = introspect_tokens_for_page(p_code)
        for t in grouped.get("table_fields", []):
            k = t.get("key", "")
            if k:
                keys.add(k)
            alias = t.get("alias", "")
            if alias:
                keys.add(alias)
        for s in grouped.get("system_fields", []):
            k = s.get("key", "")
            if k:
                keys.add(k)
                if "." in k:
                    keys.add(k.split(".", 1)[1])

    # 3. Lấy biến từ EVENT_REGISTRY nếu có event_code
    if event_code:
        try:
            from app.engine.mail_event_registry import get_allowed_variable_keys

            evt_keys = get_allowed_variable_keys(event_code)
            keys.update(evt_keys)
        except Exception:
            pass

    return keys


def get_mock_payload_for_page(page_code: str, scenario: str = "success") -> dict[str, Any]:
    """Sinh payload dữ liệu thử nghiệm (Mock Scenario) cho Live Preview trên Canvas."""
    cfg = PAGE_CONFIG.get(page_code, PAGE_CONFIG["common"])
    prefix = cfg.get("prefix", "data")
    mock_base = dict(cfg.get("mock_defaults", {}))

    payload: dict[str, Any] = {}

    # Đưa vào payload cả 2 dạng: có prefix (user.username) và ngắn (username)
    for k, v in mock_base.items():
        payload[f"{prefix}.{k}"] = v
        payload[k] = v

    # System tokens
    payload["actor.name"] = "Quản trị viên"
    payload["actor.username"] = "admin"
    payload["created_at"] = mock_base.get("created_at", "18/11/2026 16:00")
    payload["system.app_name"] = "ReconHub"
    try:
        from app.services.smtp_settings import build_app_url

        payload["links.login"] = build_app_url("/login")
        payload["links.page"] = build_app_url(cfg.get("page_url", "/users"))
        payload["links.result"] = build_app_url("/batch-runs/preview")
        payload["links.download"] = build_app_url("/download/sample")
        payload["links.template"] = build_app_url("/templates")
    except Exception:
        payload["links.login"] = "http://127.0.0.1:8050/login"
        payload["links.page"] = f"http://127.0.0.1:8050{cfg.get('page_url', '/users')}"
        payload["links.result"] = "http://127.0.0.1:8050/batch-runs/preview"
        payload["links.download"] = "http://127.0.0.1:8050/download/sample"
        payload["links.template"] = "http://127.0.0.1:8050/templates"
    payload["notes"] = "Thông báo tự động từ hệ thống ReconHub."

    if scenario == "error":
        payload["notes"] = "Có lỗi phát sinh trong quá trình xử lý."
        if "summary_failed" in payload:
            payload["summary_failed"] = 5
        if "summary_success" in payload:
            payload["summary_success"] = 15
    elif scenario == "empty":
        payload["notes"] = "Không có bản ghi nào được tìm thấy."
        if "summary_total" in payload:
            payload["summary_total"] = 0
            payload["summary_success"] = 0
            payload["summary_failed"] = 0

    # Dữ liệu dạng mảng (Mock Items) cho Component Bảng dữ liệu (Table)
    if scenario == "empty":
        mock_items: list[dict[str, Any]] = []
    elif page_code == "user":
        mock_items = [
            {
                "username": "nguyenvana",
                "full_name": "Nguyễn Văn A",
                "email": "nguyenvana@reconhub.vn",
                "roles": "Operator",
                "is_active": "Kích hoạt",
                "created_at": "18/11/2026 14:30",
            },
            {
                "username": "tranthib",
                "full_name": "Trần Thị B",
                "email": "tranthib@reconhub.vn",
                "roles": "Viewer",
                "is_active": "Kích hoạt",
                "created_at": "18/11/2026 15:00",
            },
            {
                "username": "lequangc",
                "full_name": "Lê Quang C",
                "email": "lequangc@reconhub.vn",
                "roles": "Operator",
                "is_active": "Tạm khóa",
                "created_at": "17/11/2026 09:15",
            },
        ]
    elif page_code == "template":
        mock_items = [
            {
                "code": "DTP_HOA_DON_TAC_NGHIEP",
                "name": "Hóa đơn tác nghiệp DTP",
                "status": "ACTIVE",
                "created_at": "15/11/2026 10:00",
            },
            {
                "code": "DTP_CUOC_THUE_BAO",
                "name": "Cước thuê bao Viễn thông",
                "status": "ACTIVE",
                "created_at": "16/11/2026 11:30",
            },
            {
                "code": "DTP_PHI_HA_TANG",
                "name": "Phí hạ tầng dùng chung",
                "status": "DRAFT",
                "created_at": "17/11/2026 14:20",
            },
        ]
    elif page_code == "batch_run":
        mock_items = [
            {"name": "NGAN_HANG_B", "status": "Lỗi", "detail": "Mất kết nối Oracle timeout 300s"},
            {"name": "PHI_HA_TANG", "status": "Lệch", "detail": "Lệch 15 bản ghi (42.500.000 VNĐ)"},
            {"name": "HOA_DON_DTP", "status": "Khớp", "detail": "10.500 bản ghi khớp 100%"},
        ]
    else:
        mock_items = [
            {"name": "Mục đối soát 1", "status": "Hoàn tất", "detail": "Không có sai lệch"},
            {"name": "Mục đối soát 2", "status": "Chờ xử lý", "detail": "Đang đồng bộ dữ liệu"},
        ]

    payload["items"] = mock_items
    payload["rows"] = mock_items
    payload["data"] = mock_items
    payload["batch.items"] = mock_items

    return payload


def get_table_columns_options_for_page(page_code: str) -> list[tuple[str, str]]:
    """Trả về danh sách (col_key, col_label) các cột dữ liệu phù hợp hiển thị dạng bảng."""
    if page_code == "user":
        return [
            ("username", "Tên đăng nhập"),
            ("full_name", "Họ và tên"),
            ("email", "Địa chỉ email"),
            ("roles", "Vai trò"),
            ("is_active", "Trạng thái"),
            ("created_at", "Ngày tạo"),
        ]
    if page_code == "template":
        return [
            ("code", "Mã Template"),
            ("name", "Tên Template"),
            ("status", "Trạng thái"),
            ("created_at", "Ngày tạo"),
        ]
    if page_code == "batch_run":
        return [
            ("name", "Tên Template"),
            ("status", "Trạng thái"),
            ("detail", "Chi tiết"),
        ]

    # Fallback tự động quét từ introspect_tokens_for_page
    res = introspect_tokens_for_page(page_code)
    cols: list[tuple[str, str]] = []
    exclude_keys = {"id", "password_hash", "temp_password", "session_version", "telegram_chat_id"}
    for f in res.get("table_fields", []):
        raw_k = f.get("alias") or f.get("key", "").split(".", 1)[-1]
        lbl = f.get("label", raw_k)
        if raw_k not in exclude_keys and raw_k not in [c[0] for c in cols]:
            cols.append((raw_k, lbl))
    return cols or [("name", "Tên"), ("status", "Trạng thái"), ("detail", "Chi tiết")]
