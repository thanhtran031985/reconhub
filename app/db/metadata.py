from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine

# Naming convention tường minh
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=naming_convention)


class DecimalText(TypeDecorator[Decimal]):
    """Kiểu Decimal lưu chuỗi TEXT trên SQLite và NUMBER(38,4) trên Oracle."""

    impl = String(60)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "oracle":
            return dialect.type_descriptor(Numeric(38, 4))
        return dialect.type_descriptor(String(60))

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if value is None:
            return None
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        if dialect.name == "oracle":
            return value
        return str(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))


class JsonText(TypeDecorator[Any]):
    """Kiểu JSON lưu TEXT trên SQLite và CLOB trên Oracle, tự parse dict/list."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return str(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)


def pk_id_column() -> Column[int]:
    """Cột ID khóa chính tương thích SQLite và Oracle."""
    return Column(
        "ID",
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


# 1. Người dùng, phân quyền, hệ thống
recon_user = Table(
    "RECON_USER",
    metadata,
    pk_id_column(),
    Column("USERNAME", String(60), nullable=False, unique=True),
    Column("FULL_NAME", String(200), nullable=False),
    Column("EMAIL", String(200), nullable=True),
    Column("PASSWORD_HASH", String(255), nullable=False),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
    Column("MUST_CHANGE_PW", String(1), nullable=False, default="N"),
    Column("FAILED_COUNT", Integer, nullable=False, default=0),
    Column("LOCKED_UNTIL", DateTime, nullable=True),
    Column("SESSION_VERSION", Integer, nullable=False, default=1),
    Column("LAST_LOGIN_AT", DateTime, nullable=True),
    Column("PW_CHANGED_AT", DateTime, nullable=True),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    # Task 94: liên kết Telegram — chat_id sau khi nhắn /start <mã>.
    Column("TELEGRAM_CHAT_ID", String(64), nullable=True),
    Column("TELEGRAM_LINK_CODE", String(32), nullable=True),
    Column("TELEGRAM_LINK_EXPIRES_AT", DateTime, nullable=True),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
)

recon_user_role = Table(
    "RECON_USER_ROLE",
    metadata,
    Column("USER_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_USER.ID"), primary_key=True),
    Column("ROLE_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_ROLE.ID"), primary_key=True),
    Column("ASSIGNED_BY", String(60), nullable=True),
    Column("ASSIGNED_AT", DateTime, nullable=True),
    Column("CREATED_AT", DateTime, nullable=False),
)

# 1b. Menu, vai trò, phân quyền (task 19, spec 11/11a)
recon_menu_group = Table(
    "RECON_MENU_GROUP",
    metadata,
    Column("CODE", String(40), primary_key=True),
    Column("SOURCE_LABEL", String(100), nullable=False),
    Column("SOURCE_ORDER", Integer, nullable=False),
    Column("DISPLAY_LABEL", String(100), nullable=True),
    Column("DISPLAY_ORDER", Integer, nullable=True),
    Column("IS_REMOVED", String(1), nullable=False, default="N"),
    Column("SYNCED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
)

recon_menu = Table(
    "RECON_MENU",
    metadata,
    Column("CODE", String(40), primary_key=True),
    Column("PATH", String(200), nullable=False),
    Column("ICON", String(60), nullable=True),
    Column("SOURCE_LABEL", String(100), nullable=False),
    Column("SOURCE_GROUP", String(40), ForeignKey("RECON_MENU_GROUP.CODE"), nullable=False),
    Column("SOURCE_ORDER", Integer, nullable=False),
    Column("DISPLAY_LABEL", String(100), nullable=True),
    Column("DISPLAY_GROUP", String(40), ForeignKey("RECON_MENU_GROUP.CODE"), nullable=True),
    Column("DISPLAY_ORDER", Integer, nullable=True),
    Column("IS_HIDEABLE", String(1), nullable=False, default="Y"),
    Column("IS_HIDDEN", String(1), nullable=False, default="N"),
    Column("HIDDEN_REASON", String(300), nullable=True),
    Column("HIDDEN_BY", String(60), nullable=True),
    Column("HIDDEN_AT", DateTime, nullable=True),
    Column("IS_NEW", String(1), nullable=False, default="Y"),
    Column("IS_REMOVED", String(1), nullable=False, default="N"),
    Column("SYNCED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
    CheckConstraint("IS_HIDDEN = 'N' OR IS_HIDEABLE = 'Y'", name="ck_recon_menu_hideable"),
    CheckConstraint("IS_HIDDEN = 'N' OR HIDDEN_REASON IS NOT NULL", name="ck_recon_menu_hidden_reason"),
)

recon_role = Table(
    "RECON_ROLE",
    metadata,
    Column("ID", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("CODE", String(30), nullable=False, unique=True),
    Column("NAME", String(100), nullable=False),
    Column("DESCRIPTION", String(300), nullable=True),
    Column("IS_SYSTEM", String(1), nullable=False, default="N"),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
)

recon_role_menu = Table(
    "RECON_ROLE_MENU",
    metadata,
    Column(
        "ROLE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_ROLE.ID", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("MENU_CODE", String(40), ForeignKey("RECON_MENU.CODE"), primary_key=True),
    Column("GRANTED_BY", String(60), nullable=False),
    Column("GRANTED_AT", DateTime, nullable=False),
)

recon_login_log = Table(
    "RECON_LOGIN_LOG",
    metadata,
    pk_id_column(),
    Column("USERNAME", String(60), nullable=False),
    Column("USER_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=True),
    Column("SUCCESS", String(1), nullable=False),
    Column("REASON", String(40), nullable=True),
    Column("IP", String(60), nullable=True),
    Column("CREATED_AT", DateTime, nullable=False),
    Index("ix_recon_login_log_username_created_at", "USERNAME", "CREATED_AT"),
)

recon_password_reset_token = Table(
    "RECON_PASSWORD_RESET_TOKEN",
    metadata,
    pk_id_column(),
    Column("USER_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_USER.ID"), nullable=False),
    Column("TOKEN_HASH", String(64), nullable=False),
    Column("EXPIRES_AT", DateTime, nullable=False),
    Column("IS_USED", String(1), nullable=False, default="N"),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("CREATED_IP", String(60), nullable=True),
    Index("ix_recon_pwd_reset_token_hash", "TOKEN_HASH"),
    Index("ix_recon_pwd_reset_user_expires", "USER_ID", "EXPIRES_AT"),
)

recon_sso_provider = Table(
    "RECON_SSO_PROVIDER",
    metadata,
    pk_id_column(),
    Column("CODE", String(40), nullable=False),
    Column("NAME", String(120), nullable=False),
    Column("PROVIDER_TYPE", String(20), nullable=False, default="OIDC"),
    Column("ICON", String(60), nullable=True),
    Column("DISCOVERY_URL", String(500), nullable=True),
    Column("ISSUER", String(500), nullable=True),
    Column("AUTH_URL", String(500), nullable=True),
    Column("TOKEN_URL", String(500), nullable=True),
    Column("USERINFO_URL", String(500), nullable=True),
    Column("JWKS_URI", String(500), nullable=True),
    Column("CLIENT_ID", String(255), nullable=True),
    Column("CLIENT_SECRET_ENC", String(1000), nullable=True),
    Column("SCOPES", String(300), nullable=False, default="openid profile email"),
    Column("ALLOWED_DOMAINS", String(500), nullable=True),
    Column("JIT_ENABLED", String(1), nullable=False, default="Y"),
    Column("AUTO_LINK_EMAIL", String(1), nullable=False, default="Y"),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
    Column("SORT_ORDER", Integer, nullable=False, default=10),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
    UniqueConstraint("CODE", name="uq_recon_sso_prov_code"),
    CheckConstraint("PROVIDER_TYPE IN ('INTERNAL', 'OIDC')", name="ck_recon_sso_prov_type"),
    CheckConstraint("JIT_ENABLED IN ('Y', 'N')", name="ck_recon_sso_prov_jit"),
    CheckConstraint("AUTO_LINK_EMAIL IN ('Y', 'N')", name="ck_recon_sso_prov_autolink"),
    CheckConstraint("IS_ACTIVE IN ('Y', 'N')", name="ck_recon_sso_prov_active"),
)

recon_user_identity = Table(
    "RECON_USER_IDENTITY",
    metadata,
    pk_id_column(),
    Column("USER_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_USER.ID"), nullable=False),
    Column("PROVIDER_CODE", String(40), nullable=False),
    Column("SUBJECT", String(255), nullable=False),
    Column("EMAIL_AT_PROVIDER", String(200), nullable=True),
    Column("LAST_LOGIN_AT", DateTime, nullable=True),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    UniqueConstraint("PROVIDER_CODE", "SUBJECT", name="uq_recon_sso_prov_sub"),
    Index("ix_recon_user_id_user", "USER_ID"),
)

recon_audit_log = Table(
    "RECON_AUDIT_LOG",
    metadata,
    pk_id_column(),
    Column("ENTITY", String(40), nullable=False),
    Column("ENTITY_ID", String(60), nullable=False),
    Column("ACTION", String(40), nullable=False),
    Column("OLD_JSON", JsonText, nullable=True),
    Column("NEW_JSON", JsonText, nullable=True),
    Column("ACTOR", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Index("ix_recon_audit_log_entity_id_created_at", "ENTITY", "ENTITY_ID", "CREATED_AT"),
)

recon_app_setting = Table(
    "RECON_APP_SETTING",
    metadata,
    Column("KEY", String(60), primary_key=True),
    Column("VALUE", String(400), nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
)

# 1c. Thông báo trong app (task 78): chuông + danh sách lưu DB.
recon_notification = Table(
    "RECON_NOTIFICATION",
    metadata,
    pk_id_column(),
    Column("USER_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_USER.ID"), nullable=False),
    Column("TYPE", String(40), nullable=False),
    Column("TITLE", String(200), nullable=False),
    Column("MESSAGE", String(1000), nullable=True),
    Column("LINK", String(500), nullable=True),
    Column("IS_READ", String(1), nullable=False, default="N"),
    Column("CREATED_AT", DateTime, nullable=False),
    # Task 79: tham chiếu entity gốc cho panel chi tiết.
    Column("RELATED_TYPE", String(40), nullable=True),
    Column("RELATED_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=True),
    Index("ix_recon_notification_user_read_created", "USER_ID", "IS_READ", "CREATED_AT"),
)

# Cài đặt nhận thông báo theo user (task 78): thiếu dòng = dùng mặc định
# (lỗi BẬT, DONE TẮT — quyết định task 52).
recon_notification_pref = Table(
    "RECON_NOTIFICATION_PREF",
    metadata,
    Column("USER_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_USER.ID"), primary_key=True),
    Column("EVENT_TYPE", String(40), primary_key=True),
    Column("ENABLED", String(1), nullable=False, default="Y"),
    Column("UPDATED_AT", DateTime, nullable=False),
)

# 2. Data Source
recon_data_source = Table(
    "RECON_DATA_SOURCE",
    metadata,
    pk_id_column(),
    Column("NAME", String(60), nullable=False),
    Column("ENV", String(10), nullable=False),
    Column("PURPOSE", String(10), nullable=False),
    Column("DB_TYPE", String(10), nullable=False),
    Column("HOST", String(200), nullable=True),
    Column("PORT", Integer, nullable=True),
    Column("SERVICE_NAME", String(100), nullable=True),
    Column("FILE_PATH", String(400), nullable=True),
    Column("USERNAME", String(60), nullable=True),
    Column("PASSWORD_ENC", String(1000), nullable=True),
    Column("DEFAULT_SCHEMA", String(60), nullable=True),
    Column("CALL_TIMEOUT_S", Integer, nullable=False, default=600),
    Column("MAX_ROWS", Integer, nullable=False, default=1000000),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
    Column("IS_CURRENT_METADATA", String(1), nullable=False, default="N"),
    Column("LAST_TEST_AT", DateTime, nullable=True),
    Column("LAST_TEST_OK", String(1), nullable=True),
    Column("LAST_TEST_MSG", String(400), nullable=True),
    Column("LAST_TEST_MS", Integer, nullable=True),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    UniqueConstraint("NAME", "ENV", name="uq_recon_data_source_name_env"),
)

# 3. Template
recon_template = Table(
    "RECON_TEMPLATE",
    metadata,
    pk_id_column(),
    Column("CODE", String(60), nullable=False, unique=True),
    Column("NAME", String(200), nullable=False),
    Column("DESCRIPTION", String(1000), nullable=True),
    Column("OWNER", String(60), nullable=False),
    Column("STATUS", String(10), nullable=False, default="DRAFT"),
    Column("CURRENT_VERSION", Integer, nullable=True),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
)

recon_template_version = Table(
    "RECON_TEMPLATE_VERSION",
    metadata,
    Column(
        "TEMPLATE_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_TEMPLATE.ID"), primary_key=True
    ),
    Column("VERSION", Integer, primary_key=True),
    Column("STATUS", String(10), nullable=False, default="DRAFT"),
    Column("CONFIG_JSON", JsonText, nullable=False),
    Column(
        "DATA_SOURCE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_DATA_SOURCE.ID"),
        nullable=True,
    ),
    Column("SAMPLE_FILE_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=True),
    Column("DRY_RUN_OK", String(1), nullable=True),
    Column("DRY_RUN_JSON", JsonText, nullable=True),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("ACTIVATED_AT", DateTime, nullable=True),
)

# 4. File, dữ liệu Excel tạm, Run
recon_file = Table(
    "RECON_FILE",
    metadata,
    pk_id_column(),
    Column("SHA256", String(64), nullable=False),
    Column("ORIGINAL_NAME", String(400), nullable=False),
    Column("SIZE_BYTES", BigInteger, nullable=False),
    Column("STORAGE_PATH", String(400), nullable=True),
    Column("SHEETS_JSON", JsonText, nullable=True),
    Column("UPLOADED_BY", String(60), nullable=False),
    Column("UPLOADED_AT", DateTime, nullable=False),
    Column("PURGED_AT", DateTime, nullable=True),
    Index("ix_recon_file_sha256", "SHA256"),
)

recon_excel_load = Table(
    "RECON_EXCEL_LOAD",
    metadata,
    pk_id_column(),
    Column("FILE_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_FILE.ID"), nullable=False),
    Column("SHEET_NAME", String(200), nullable=False),
    Column("TEMPLATE_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=False),
    Column("TEMPLATE_VERSION", Integer, nullable=False),
    Column("ROWS_READ", Integer, nullable=False),
    Column("ROWS_INVALID", Integer, nullable=False, default=0),
    Column("BYTES_EST", BigInteger, nullable=False, default=0),
    Column("CONTROL_TOTAL_FILE", DecimalText, nullable=True),
    Column("CONTROL_TOTAL_CALC", DecimalText, nullable=True),
    Column("LOADED_AT", DateTime, nullable=False),
    Column("PURGED_AT", DateTime, nullable=True),
    # Task 18 (spec 10a §6): UQ đổi sang FILE_SET_HASH; FILE_ID giữ lại
    # = file đầu tiên. 1 file: FILE_SET_HASH = sha256(SHA256 của file).
    Column("FILE_SET_HASH", String(64), nullable=False),
    Column("SOURCE_FILES_JSON", JsonText, nullable=True),
    UniqueConstraint(
        "FILE_SET_HASH",
        "SHEET_NAME",
        "TEMPLATE_ID",
        "TEMPLATE_VERSION",
        name="uq_recon_excel_load_fileset_sheet_tmpl_ver",
    ),
)

recon_excel_row = Table(
    "RECON_EXCEL_ROW",
    metadata,
    Column(
        "LOAD_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_EXCEL_LOAD.ID"), primary_key=True
    ),
    Column(
        "SOURCE_FILE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_FILE.ID"),
        primary_key=True,
    ),
    Column("EXCEL_ROW_NO", Integer, primary_key=True),
    Column("DATA_JSON", JsonText, nullable=False),
    Column("IS_VALID", String(1), nullable=False, default="Y"),
)

recon_run = Table(
    "RECON_RUN",
    metadata,
    pk_id_column(),
    Column("TEMPLATE_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=False),
    Column("TEMPLATE_VERSION", Integer, nullable=False),
    Column("PROFILE_CODE", String(60), nullable=False),
    Column("PROFILE_OVERRIDE", JsonText, nullable=True),
    Column("FILE_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_FILE.ID"), nullable=True),
    Column(
        "EXCEL_LOAD_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_EXCEL_LOAD.ID"), nullable=True
    ),
    Column("SHEET_NAME", String(200), nullable=True),
    Column(
        "DATA_SOURCE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_DATA_SOURCE.ID"),
        nullable=False,
    ),
    Column("P_FROM", DateTime, nullable=False),
    Column("P_TO", DateTime, nullable=False),
    Column("PARAMS_JSON", JsonText, nullable=True),
    Column("APPLY_RANGE_EXCEL", String(1), nullable=False, default="Y"),
    Column("STATUS", String(10), nullable=False, default="QUEUED"),
    Column("STAGE", String(30), nullable=True),
    Column("PROGRESS_PCT", Integer, nullable=False, default=0),
    Column("ERROR_CODE", String(60), nullable=True),
    Column("ERROR_MSG", String(2000), nullable=True),
    Column("CHECKED_BY", String(60), nullable=True),
    Column("CHECKED_AT", DateTime, nullable=True),
    Column("TEMP_PURGED_AT", DateTime, nullable=True),
    Column("TEMP_PURGED_BY", String(60), nullable=True),
    # Task 18 (spec 10a §6): run con của một lần chạy bộ.
    Column(
        "BATCH_RUN_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_BATCH_RUN.ID"),
        nullable=True,
    ),
    Column(
        "BATCH_RUN_ITEM_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_BATCH_RUN_ITEM.ID"),
        nullable=True,
    ),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("STARTED_AT", DateTime, nullable=True),
    Column("FINISHED_AT", DateTime, nullable=True),
    CheckConstraint("P_FROM <= P_TO", name="ck_recon_run_time_range"),
    Index("ix_recon_run_batch", "BATCH_RUN_ID", "STATUS"),
)

recon_run_queue = Table(
    "RECON_RUN_QUEUE",
    metadata,
    Column("RUN_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_RUN.ID"), primary_key=True),
    Column("STATUS", String(12), nullable=False, default="READY"),
    Column("LOCKED_BY", String(100), nullable=True),
    Column("LOCKED_AT", DateTime, nullable=True),
    Column("HEARTBEAT_AT", DateTime, nullable=True),
    Column("RETRY_COUNT", Integer, nullable=False, default=0),
    Column("ENQUEUED_AT", DateTime, nullable=False),
)


def _audit_columns() -> list[Column[Any]]:
    return [
        Column("CREATED_BY", String(60), nullable=False),
        Column("CREATED_AT", DateTime, nullable=False),
        Column("UPDATED_BY", String(60), nullable=False),
        Column("UPDATED_AT", DateTime, nullable=False),
        Column("ROW_VERSION", Integer, nullable=False, default=1),
    ]


# 4b. Bộ đối soát và chạy theo bộ (task 18, spec 10/10a)
recon_batch_def = Table(
    "RECON_BATCH_DEF",
    metadata,
    pk_id_column(),
    Column("CODE", String(60), nullable=False, unique=True),
    Column("NAME", String(200), nullable=False),
    Column("DESCRIPTION", String(1000), nullable=True),
    Column("STATUS", String(10), nullable=False, default="DRAFT"),
    Column("MAX_PARALLEL_PER_DS", Integer, nullable=False, default=2),
    Column("OWNER_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_USER.ID"), nullable=False),
    *_audit_columns(),
    CheckConstraint("STATUS IN ('DRAFT', 'ACTIVE', 'ARCHIVED')", name="ck_recon_batch_def_status"),
    CheckConstraint("MAX_PARALLEL_PER_DS BETWEEN 1 AND 4", name="ck_recon_batch_def_max_parallel"),
    Index("ix_recon_batch_def_status", "STATUS"),
)

recon_batch_def_item = Table(
    "RECON_BATCH_DEF_ITEM",
    metadata,
    pk_id_column(),
    Column(
        "BATCH_DEF_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_BATCH_DEF.ID"),
        nullable=False,
    ),
    Column(
        "TEMPLATE_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_TEMPLATE.ID"), nullable=False
    ),
    Column("SEQ_NO", Integer, nullable=False),
    Column("PRIORITY", Integer, nullable=False, default=100),
    Column("PROFILE_CODE", String(60), nullable=True),
    Column(
        "DATA_SOURCE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_DATA_SOURCE.ID"),
        nullable=True,
    ),
    Column("FILE_PATTERN", String(400), nullable=False),
    Column("MULTI_FILE", String(1), nullable=False, default="N"),
    Column("IS_REQUIRED", String(1), nullable=False, default="Y"),
    Column("PARAMS_OVERRIDE_JSON", JsonText, nullable=True),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
    *_audit_columns(),
    UniqueConstraint("BATCH_DEF_ID", "TEMPLATE_ID", name="uq_recon_batch_def_item_def_tpl"),
    CheckConstraint("SEQ_NO >= 1", name="ck_recon_batch_def_item_seq_no"),
    Index("ix_recon_batch_def_item_def", "BATCH_DEF_ID", "IS_ACTIVE", "SEQ_NO"),
)

recon_batch_run = Table(
    "RECON_BATCH_RUN",
    metadata,
    pk_id_column(),
    Column(
        "BATCH_DEF_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_BATCH_DEF.ID"),
        nullable=False,
    ),
    Column("NAME", String(200), nullable=False),
    Column("PERIOD", String(7), nullable=False),
    Column("PERIOD_FROM", DateTime, nullable=False),
    Column("PERIOD_TO", DateTime, nullable=False),
    Column("STATUS", String(12), nullable=False, default="DRAFT"),
    Column("INCLUDE_WARN", String(1), nullable=False, default="Y"),
    Column("PROD_CONFIRMED_BY", String(60), nullable=True),
    Column("CNT_ITEMS", Integer, nullable=False, default=0),
    Column("CNT_DONE", Integer, nullable=False, default=0),
    Column("CNT_FAILED", Integer, nullable=False, default=0),
    Column("CNT_SKIPPED", Integer, nullable=False, default=0),
    Column("CNT_NOT_RUN", Integer, nullable=False, default=0),
    Column("ZIP_PATH", String(400), nullable=True),
    Column("ZIP_RUN_SET_HASH", String(64), nullable=True),
    Column("STARTED_AT", DateTime, nullable=True),
    Column("FINISHED_AT", DateTime, nullable=True),
    *_audit_columns(),
    CheckConstraint("STATUS IN ('DRAFT', 'RUNNING', 'DONE', 'PARTIAL', 'CANCELLED')", name="ck_recon_batch_run_status"),
    CheckConstraint("PERIOD_FROM <= PERIOD_TO", name="ck_recon_batch_run_period_range"),
    Index("ix_recon_batch_run_def_period", "BATCH_DEF_ID", "PERIOD", "CREATED_AT"),
    Index("ix_recon_batch_run_status", "STATUS", "CREATED_AT"),
)

recon_batch_run_item = Table(
    "RECON_BATCH_RUN_ITEM",
    metadata,
    pk_id_column(),
    Column(
        "BATCH_RUN_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_BATCH_RUN.ID"),
        nullable=False,
    ),
    Column(
        "BATCH_DEF_ITEM_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_BATCH_DEF_ITEM.ID"),
        nullable=False,
    ),
    Column("TEMPLATE_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=False),
    Column("TEMPLATE_VERSION", Integer, nullable=True),
    Column("PROFILE_CODE", String(60), nullable=False),
    Column(
        "DATA_SOURCE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_DATA_SOURCE.ID"),
        nullable=False,
    ),
    Column("SEQ_NO", Integer, nullable=False),
    Column("PRIORITY", Integer, nullable=False),
    Column("MULTI_FILE", String(1), nullable=False),
    Column("IS_REQUIRED", String(1), nullable=False),
    Column("STATUS", String(12), nullable=False, default="PENDING"),
    Column("SKIP_REASON", String(30), nullable=True),
    Column("SKIPPED_BY", String(60), nullable=True),
    Column("PARAMS_RUN_OVERRIDE_JSON", JsonText, nullable=True),
    Column("PARAMS_RESOLVED_JSON", JsonText, nullable=True),
    Column("PRECHECK_JSON", JsonText, nullable=True),
    Column("PRECHECK_AT", DateTime, nullable=True),
    # KHÔNG khai báo FK (decisions.md 04/11): tránh tham chiếu vòng
    # RECON_RUN <-> RECON_BATCH_RUN_ITEM khi tạo/chép; service đảm bảo
    # CURRENT_RUN_ID luôn trỏ tới run có BATCH_RUN_ITEM_ID = chính item.
    Column("CURRENT_RUN_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=True),
    Column("ATTEMPT_NO", Integer, nullable=False, default=0),
    Column("ERROR_CODE", String(60), nullable=True),
    Column("ERROR_MSG", String(2000), nullable=True),
    *_audit_columns(),
    UniqueConstraint("BATCH_RUN_ID", "BATCH_DEF_ITEM_ID", name="uq_recon_batch_run_item_run_defitem"),
    CheckConstraint(
        "STATUS IN ('PENDING', 'READY', 'WARN', 'ERROR', 'SKIPPED', 'NOT_RUN', 'QUEUED', 'RUNNING', 'DONE', 'FAILED')",
        name="ck_recon_batch_run_item_status",
    ),
    Index("ix_recon_batch_run_item_run", "BATCH_RUN_ID", "STATUS", "SEQ_NO"),
)

recon_batch_run_file = Table(
    "RECON_BATCH_RUN_FILE",
    metadata,
    pk_id_column(),
    Column(
        "BATCH_RUN_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_BATCH_RUN.ID"),
        nullable=False,
    ),
    Column("FILE_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_FILE.ID"), nullable=False),
    Column("ORIGINAL_NAME", String(400), nullable=False),
    Column("NORMALIZED_NAME", String(400), nullable=False),
    Column(
        "FROM_ZIP_FILE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_FILE.ID"),
        nullable=True,
    ),
    Column(
        "BATCH_RUN_ITEM_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_BATCH_RUN_ITEM.ID"),
        nullable=True,
    ),
    Column("MATCH_STATE", String(12), nullable=False, default="UNMATCHED"),
    Column("MATCH_BY", String(10), nullable=True),
    Column("CANDIDATE_ITEM_IDS", JsonText, nullable=True),
    Column("SHEET_NAME", String(200), nullable=True),
    Column("SEQ_IN_ITEM", Integer, nullable=True),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    UniqueConstraint("BATCH_RUN_ID", "ORIGINAL_NAME", name="uq_recon_batch_run_file_run_name"),
    CheckConstraint(
        "MATCH_STATE IN ('MATCHED', 'AMBIGUOUS', 'UNMATCHED', 'IGNORED', 'REPLACED')",
        name="ck_recon_batch_run_file_match_state",
    ),
    CheckConstraint(
        "MATCH_BY IS NULL OR MATCH_BY IN ('PATTERN', 'HEADER', 'MANUAL')",
        name="ck_recon_batch_run_file_match_by",
    ),
    Index("ix_recon_batch_run_file_item", "BATCH_RUN_ITEM_ID", "MATCH_STATE"),
    Index("ix_recon_batch_run_file_hash", "BATCH_RUN_ID", "FILE_ID"),
)

recon_run_summary = Table(
    "RECON_RUN_SUMMARY",
    metadata,
    Column("RUN_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_RUN.ID"), primary_key=True),
    Column("EXCEL_ROWS_READ", Integer, nullable=False, default=0),
    Column("EXCEL_ROWS_OUT_OF_RANGE", Integer, nullable=False, default=0),
    Column("EXCEL_ROWS_INVALID", Integer, nullable=False, default=0),
    Column("EXCEL_GROUPS", Integer, nullable=False, default=0),
    Column("DB_ROWS", Integer, nullable=False, default=0),
    Column("DB_GROUPS", Integer, nullable=False, default=0),
    Column("CNT_MATCHED", Integer, nullable=False, default=0),
    Column("CNT_MISMATCH", Integer, nullable=False, default=0),
    Column("CNT_MISSING_IN_DB", Integer, nullable=False, default=0),
    Column("CNT_MISSING_IN_EXCEL", Integer, nullable=False, default=0),
    Column("CNT_INCONSISTENT", Integer, nullable=False, default=0),
    Column("CNT_DUPLICATE", Integer, nullable=False, default=0),
    Column("CONTROL_TOTAL_FILE", DecimalText, nullable=True),
    Column("CONTROL_TOTAL_CALC", DecimalText, nullable=True),
    Column("CONTROL_TOTAL_OK", String(1), nullable=True),
    Column("MEASURE_TOTALS_JSON", JsonText, nullable=True),
    Column("STATUS_AMOUNTS_JSON", JsonText, nullable=True),
    Column("COLUMNS_JSON", JsonText, nullable=True),
    Column("SOURCE_SQL", Text, nullable=True),
    Column("DURATION_MS", Integer, nullable=False, default=0),
)

# 5. Kết quả
recon_result_row = Table(
    "RECON_RESULT_ROW",
    metadata,
    Column("RUN_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_RUN.ID"), primary_key=True),
    Column("ROW_NO", Integer, primary_key=True),
    Column("KEY_TEXT", String(1000), nullable=False),
    Column("KEY_HASH", String(64), nullable=False),
    Column("STATUS", String(20), nullable=False),
    Column("KEY_JSON", JsonText, nullable=False),
    Column("EXCEL_JSON", JsonText, nullable=True),
    Column("DB_JSON", JsonText, nullable=True),
    Column("DIFF_JSON", JsonText, nullable=True),
    Column("EXCEL_ROW_NOS", Text, nullable=True),
    Column("ABS_DIFF_MAIN", DecimalText, nullable=True),
    Column("ABS_DIFF_SORT", Float, nullable=True),
    Index("ix_recon_result_row_run_status_row", "RUN_ID", "STATUS", "ROW_NO"),
    Index("ix_recon_result_row_run_key_hash", "RUN_ID", "KEY_HASH"),
)

recon_result_diff = Table(
    "RECON_RESULT_DIFF",
    metadata,
    Column("RUN_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_RUN.ID"), primary_key=True),
    Column("ROW_NO", Integer, primary_key=True),
    Column("MEASURE", String(60), primary_key=True),
    Column("EXCEL_VAL", String(400), nullable=True),
    Column("DB_VAL", String(400), nullable=True),
    Column("DIFF_ABS", DecimalText, nullable=True),
    Column("DIFF_PCT", DecimalText, nullable=True),
)

recon_invalid_row = Table(
    "RECON_INVALID_ROW",
    metadata,
    Column("RUN_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_RUN.ID"), primary_key=True),
    Column("EXCEL_ROW_NO", Integer, primary_key=True),
    Column("FIELD", String(60), nullable=True),
    Column("RAW_VALUE", String(1000), nullable=True),
    Column("REASON_CODE", String(40), primary_key=True),
)

# 6. Xử lý chênh lệch [GĐ3]
recon_issue_reason = Table(
    "RECON_ISSUE_REASON",
    metadata,
    Column("CODE", String(40), primary_key=True),
    Column("LABEL", String(200), nullable=False),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
)

recon_issue = Table(
    "RECON_ISSUE",
    metadata,
    pk_id_column(),
    Column("TEMPLATE_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=False),
    Column("PROFILE_CODE", String(60), nullable=False),
    Column("KEY_TEXT", String(1000), nullable=False),
    Column("KEY_HASH", String(64), nullable=False),
    Column("FIRST_RUN_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=False),
    Column("LAST_RUN_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=False),
    Column("STATUS", String(20), nullable=False, default="OPEN"),
    Column("REASON_CODE", String(40), ForeignKey("RECON_ISSUE_REASON.CODE"), nullable=True),
    Column("ASSIGNEE_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_USER.ID"), nullable=True),
    Column("NOTE", String(2000), nullable=True),
    Column("UPDATED_BY", String(60), nullable=True),
    Column("UPDATED_AT", DateTime, nullable=True),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
    UniqueConstraint("TEMPLATE_ID", "PROFILE_CODE", "KEY_HASH", name="uq_recon_issue_tmpl_profile_key"),
)

# 7. Lookup Code — Danh mục dùng chung [GĐ3]
recon_lookup_type = Table(
    "RECON_LOOKUP_TYPE",
    metadata,
    Column("LOOKUP_TYPE", String(50), primary_key=True),
    Column("TYPE_NAME", String(200), nullable=False),
    Column("DESCRIPTION", String(500), nullable=True),
    Column("IS_SYSTEM", String(1), nullable=False, default="N"),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
)

recon_lookup_code = Table(
    "RECON_LOOKUP_CODE",
    metadata,
    Column("LOOKUP_TYPE", String(50), ForeignKey("RECON_LOOKUP_TYPE.LOOKUP_TYPE"), primary_key=True),
    Column("LOOKUP_CODE", String(50), primary_key=True),
    Column("MEANING", String(200), nullable=False),
    Column("DESCRIPTION", String(500), nullable=True),
    Column("DISPLAY_ORDER", Integer, nullable=False, default=0),
    Column("COLOR_BADGE", String(30), nullable=True),
    Column("ICON_NAME", String(60), nullable=True),
    Column("IS_DEFAULT", String(1), nullable=False, default="N"),
    Column("IS_SYSTEM", String(1), nullable=False, default="N"),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
)

# 8. Xóa dữ liệu tạm và chuyển metadata
recon_purge_log = Table(
    "RECON_PURGE_LOG",
    metadata,
    pk_id_column(),
    Column("SCOPE", String(20), nullable=False),
    Column("FILTER_JSON", JsonText, nullable=True),
    Column("RUN_COUNT", Integer, nullable=False),
    Column("ROWS_DELETED", Integer, nullable=False),
    Column("BYTES_FREED", BigInteger, nullable=False),
    Column("ACTOR", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
)

recon_metadata_migration = Table(
    "RECON_METADATA_MIGRATION",
    metadata,
    pk_id_column(),
    Column("SOURCE_DS_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=False),
    Column("TARGET_DS_ID", BigInteger().with_variant(Integer, "sqlite"), nullable=False),
    Column("STATUS", String(20), nullable=False, default="QUEUED"),
    Column("MODE", String(20), nullable=False, default="NO_TEMP"),
    Column("STAGE", String(30), nullable=True),
    Column("PROGRESS_PCT", Integer, nullable=False, default=0),
    Column("REPORT_JSON", JsonText, nullable=True),
    # Task 63: tiến độ checklist từng bước con của phiên migration (JSON).
    Column("CHECKLIST_JSON", JsonText, nullable=True),
    Column("OLD_SQLITE_PATH", String(400), nullable=True),
    Column("OLD_SQLITE_DELETED_AT", DateTime, nullable=True),
    Column("ERROR_MSG", Text, nullable=True),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("FINISHED_AT", DateTime, nullable=True),
)

# 9. Dynamic Reporting (task 21, spec 12a). Tên bảng/cột HOA, ≤ 30 ký tự.
# RECON_REPORT_TEMPLATE.ACTIVE_VERSION_ID trỏ tới RECON_RPT_TPL_VER:
# vòng FK hai chiều, create_all tự xử lý bằng ALTER TABLE.
recon_report = Table(
    "RECON_REPORT",
    metadata,
    pk_id_column(),
    Column("CODE", String(60), nullable=False, unique=True),
    Column("NAME", String(200), nullable=False),
    Column("CATEGORY_CODE", String(60), nullable=True),
    Column("OWNER", String(60), nullable=False),
    Column("DESCRIPTION", String(500), nullable=True),
    Column("DEFAULT_FAVORITE", String(1), nullable=False, default="N"),
    Column("IS_VISIBLE", String(1), nullable=False, default="Y"),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
)

recon_report_template = Table(
    "RECON_REPORT_TEMPLATE",
    metadata,
    pk_id_column(),
    Column("REPORT_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_REPORT.ID"), nullable=False),
    Column("CODE", String(60), nullable=False),
    Column("NAME", String(200), nullable=False),
    Column("DISPLAY_ORDER", Integer, nullable=False, default=10),
    Column(
        "ACTIVE_VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_TPL_VER.ID"),
        nullable=True,
    ),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
    UniqueConstraint("REPORT_ID", "CODE", name="uq_recon_report_template_report_code"),
)

recon_rpt_tpl_ver = Table(
    "RECON_RPT_TPL_VER",
    metadata,
    pk_id_column(),
    Column(
        "TEMPLATE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_REPORT_TEMPLATE.ID"),
        nullable=False,
    ),
    Column("VERSION_NO", Integer, nullable=False),
    Column("STATUS", String(20), nullable=False, default="DRAFT"),
    Column(
        "DATA_SOURCE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_DATA_SOURCE.ID"),
        nullable=True,
    ),
    Column(
        "MODEL_VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_VER.ID", name="fk_recon_rpt_tpl_ver_model_ver"),
        nullable=True,
    ),
    Column("SOURCE_TYPE", String(20), nullable=True),
    Column("SQL_TEXT", Text, nullable=True),
    Column("SOURCE_OWNER", String(60), nullable=True),
    Column("SOURCE_OBJECT", String(128), nullable=True),
    Column("TIMEOUT_SEC", Integer, nullable=False, default=300),
    Column("PREVIEW_MAX_ROWS", Integer, nullable=False, default=100),
    Column("EXPORT_MAX_ROWS", Integer, nullable=False, default=1000000),
    Column("SQL_HASH", String(64), nullable=True),
    Column("ACTIVATED_BY", String(60), nullable=True),
    Column("ACTIVATED_AT", DateTime, nullable=True),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
    UniqueConstraint("TEMPLATE_ID", "VERSION_NO", name="uq_recon_rpt_tpl_ver_template_version"),
    CheckConstraint(
        "STATUS IN ('DRAFT', 'DRY_RUN_OK', 'ACTIVE', 'ARCHIVED')",
        name="ck_recon_rpt_tpl_ver_status",
    ),
    CheckConstraint(
        "SOURCE_TYPE IS NULL OR SOURCE_TYPE IN ('CUSTOM_SQL', 'VIEW', 'TABLE', 'SEMANTIC_MODEL')",
        name="ck_recon_rpt_tpl_ver_source_type",
    ),
)

recon_rpt_param = Table(
    "RECON_RPT_PARAM",
    metadata,
    pk_id_column(),
    Column(
        "VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_TPL_VER.ID"),
        nullable=False,
    ),
    Column("CODE", String(60), nullable=False),
    Column("LABEL", String(200), nullable=False),
    Column("DATA_TYPE", String(30), nullable=False),
    Column("CONTROL_TYPE", String(30), nullable=False),
    Column("REQUIRED", String(1), nullable=False, default="N"),
    Column("DEFAULT_TYPE", String(20), nullable=True),
    Column("DEFAULT_VALUE", String(500), nullable=True),
    Column("DISPLAY_ROW", Integer, nullable=False, default=1),
    Column("DISPLAY_ORDER", Integer, nullable=False, default=10),
    Column("GRID_SPAN", Integer, nullable=False, default=6),
    Column("FILTER_COLUMN", String(128), nullable=True),
    Column("FILTER_OPERATOR", String(20), nullable=True),
    Column("IS_VISIBLE", String(1), nullable=False, default="Y"),
    UniqueConstraint("VERSION_ID", "CODE", name="uq_recon_rpt_param_version_code"),
    CheckConstraint("GRID_SPAN BETWEEN 1 AND 12", name="ck_recon_rpt_param_grid_span"),
    CheckConstraint("DISPLAY_ROW >= 1", name="ck_recon_rpt_param_display_row"),
    CheckConstraint(
        "FILTER_OPERATOR IS NULL OR FILTER_OPERATOR IN ('=', '>=', '<=', 'BETWEEN', 'IN', 'LIKE_PREFIX', 'IS_NULL')",
        name="ck_recon_rpt_param_filter_operator",
    ),
)

recon_rpt_param_lov = Table(
    "RECON_RPT_PARAM_LOV",
    metadata,
    Column(
        "PARAM_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_PARAM.ID", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("LOV_TYPE", String(20), nullable=False, default="NONE"),
    Column(
        "DATA_SOURCE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_DATA_SOURCE.ID"),
        nullable=True,
    ),
    Column("SQL_TEXT", Text, nullable=True),
    Column("LOOKUP_TYPE", String(60), nullable=True),
    Column("STATIC_JSON", JsonText, nullable=True),
    Column("CACHE_SECONDS", Integer, nullable=False, default=300),
    Column("MAX_ROWS", Integer, nullable=False, default=5000),
    CheckConstraint(
        "LOV_TYPE IN ('NONE', 'STATIC', 'SQL', 'LOOKUP')",
        name="ck_recon_rpt_param_lov_type",
    ),
    CheckConstraint("CACHE_SECONDS BETWEEN 0 AND 3600", name="ck_recon_rpt_param_lov_cache"),
    CheckConstraint("MAX_ROWS > 0", name="ck_recon_rpt_param_lov_max_rows"),
)

recon_rpt_column = Table(
    "RECON_RPT_COLUMN",
    metadata,
    pk_id_column(),
    Column(
        "VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_TPL_VER.ID"),
        nullable=False,
    ),
    Column("FIELD_NAME", String(128), nullable=False),
    Column("LABEL", String(200), nullable=False),
    Column("DATA_TYPE", String(30), nullable=False),
    Column("DISPLAY_ORDER", Integer, nullable=False, default=10),
    Column("WEB_VISIBLE", String(1), nullable=False, default="Y"),
    Column("EXCEL_VISIBLE", String(1), nullable=False, default="Y"),
    Column("FORMAT_MASK", String(100), nullable=True),
    Column("ALIGNMENT", String(10), nullable=False, default="LEFT"),
    Column("WIDTH", Integer, nullable=True),
    Column("IS_TOTAL", String(1), nullable=False, default="N"),
    UniqueConstraint("VERSION_ID", "FIELD_NAME", name="uq_recon_rpt_column_version_field"),
    CheckConstraint(
        "ALIGNMENT IN ('LEFT', 'CENTER', 'RIGHT')",
        name="ck_recon_rpt_column_alignment",
    ),
)

recon_report_run = Table(
    "RECON_REPORT_RUN",
    metadata,
    pk_id_column(),
    Column("REPORT_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_REPORT.ID"), nullable=False),
    Column(
        "TEMPLATE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_REPORT_TEMPLATE.ID"),
        nullable=False,
    ),
    Column(
        "VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_TPL_VER.ID"),
        nullable=False,
    ),
    Column(
        "VISUAL_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_VISUAL.ID", name="fk_recon_report_run_visual"),
        nullable=True,
    ),
    Column("QUERY_SPEC_JSON", JsonText, nullable=True),
    Column("PARAMS_JSON", JsonText, nullable=False),
    Column("STATUS", String(30), nullable=False, default="QUEUED"),
    Column("ROW_COUNT", Integer, nullable=True),
    Column("QUERY_MS", Integer, nullable=True),
    Column("ERROR_CODE", String(60), nullable=True),
    Column("ERROR_MESSAGE", String(500), nullable=True),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("FINISHED_AT", DateTime, nullable=True),
    CheckConstraint(
        "STATUS IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED', 'CANCELLED')",
        name="ck_recon_report_run_status",
    ),
)

recon_rpt_export = Table(
    "RECON_RPT_EXPORT",
    metadata,
    pk_id_column(),
    Column("RUN_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_REPORT_RUN.ID"), nullable=False),
    Column("FORMAT", String(10), nullable=False),
    Column("STATUS", String(30), nullable=False, default="QUEUED"),
    Column("FILE_PATH", String(500), nullable=True),
    Column("FILE_SIZE", BigInteger, nullable=True),
    Column("FILE_HASH", String(128), nullable=True),
    Column("PART_COUNT", Integer, nullable=False, default=1),
    Column("ROW_COUNT", Integer, nullable=True),
    # Task 40 (migration 0007): tiến độ export % thật + bước hiện tại.
    Column("PROGRESS_PCT", Integer, nullable=False, default=0),
    Column("PROGRESS_STEP", String(200), nullable=True),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("FINISHED_AT", DateTime, nullable=True),
    Column("ERROR_MESSAGE", String(500), nullable=True),
    # Task 26 (migration 0005): worker claim nguyên tử + heartbeat.
    Column("LOCKED_BY", String(60), nullable=True),
    Column("LOCKED_AT", DateTime, nullable=True),
    Column("HEARTBEAT_AT", DateTime, nullable=True),
    CheckConstraint("FORMAT IN ('XLSX', 'CSV', 'ZIP')", name="ck_recon_rpt_export_format"),
    CheckConstraint(
        "STATUS IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED', 'CANCELLED')",
        name="ck_recon_rpt_export_status",
    ),
)

recon_rpt_favorite = Table(
    "RECON_RPT_FAVORITE",
    metadata,
    Column("USER_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_USER.ID"), primary_key=True),
    Column("REPORT_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_REPORT.ID"), primary_key=True),
    Column("CREATED_AT", DateTime, nullable=False),
)

recon_rpt_preset = Table(
    "RECON_RPT_PRESET",
    metadata,
    pk_id_column(),
    Column("USER_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_USER.ID"), nullable=False),
    Column("REPORT_ID", BigInteger().with_variant(Integer, "sqlite"), ForeignKey("RECON_REPORT.ID"), nullable=False),
    Column(
        "TEMPLATE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_REPORT_TEMPLATE.ID"),
        nullable=False,
    ),
    Column("NAME", String(200), nullable=False),
    Column("PARAMS_JSON", JsonText, nullable=False),
    Column("IS_DEFAULT", String(1), nullable=False, default="N"),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
)

recon_rpt_lov_cache = Table(
    "RECON_RPT_LOV_CACHE",
    metadata,
    Column("CACHE_KEY", String(200), primary_key=True),
    Column("PAYLOAD_JSON", JsonText, nullable=False),
    Column("ROW_COUNT", Integer, nullable=False, default=0),
    Column("EXPIRES_AT", DateTime, nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
)

recon_email_template = Table(
    "RECON_EMAIL_TEMPLATE",
    metadata,
    Column("TEMPLATE_CODE", String(60), primary_key=True),
    Column("NAME", String(200), nullable=False),
    Column("FUNCTION_CODE", String(60), nullable=False, index=True),
    Column("SUBJECT_PATTERN", String(500), nullable=False),
    Column("BODY_HTML", Text, nullable=False),
    Column("AVAILABLE_TOKENS", JsonText, nullable=False),
    Column("IS_DEFAULT", String(1), nullable=False, default="N"),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
)

# Task 98: Mail Template Studio (No-Code Email Builder & Multi-Version Engine)
recon_mail_template = Table(
    "RECON_MAIL_TEMPLATE",
    metadata,
    pk_id_column(),
    Column("CODE", String(64), nullable=False, unique=True),
    Column("NAME", String(255), nullable=False),
    Column("DESCRIPTION", String(500), nullable=True),
    Column("MENU_CODE", String(64), nullable=False),
    Column("EVENT_CODE", String(64), nullable=False),
    Column(
        "CURRENT_ACTIVE_VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_MAIL_TPL_VERSION.ID", use_alter=True, name="fk_recon_mail_template_active_ver"),
        nullable=True,
    ),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
    Index("ix_recon_mail_template_event", "EVENT_CODE"),
    Index("ix_recon_mail_template_menu", "MENU_CODE"),
)

recon_mail_tpl_version = Table(
    "RECON_MAIL_TPL_VERSION",
    metadata,
    pk_id_column(),
    Column(
        "TEMPLATE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_MAIL_TEMPLATE.ID"),
        nullable=False,
    ),
    Column("VERSION_NO", Integer, nullable=False),
    Column("STATUS", String(20), nullable=False, default="DRAFT"),
    Column("EVENT_SCHEMA_VERSION", Integer, nullable=False, default=1),
    Column("SUBJECT_TEMPLATE", String(255), nullable=False),
    Column("PREHEADER_TEMPLATE", String(150), nullable=True),
    Column("DESIGN_JSON", JsonText, nullable=False),
    Column("RENDERED_HTML", Text, nullable=True),
    Column("PLAIN_TEXT", Text, nullable=True),
    Column("DESIGN_HASH", String(64), nullable=True),
    Column("RENDERER_VERSION", String(20), nullable=True),
    Column("VALIDATION_JSON", JsonText, nullable=True),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("ACTIVATED_BY", String(60), nullable=True),
    Column("ACTIVATED_AT", DateTime, nullable=True),
    Column("ARCHIVED_AT", DateTime, nullable=True),
    UniqueConstraint("TEMPLATE_ID", "VERSION_NO", name="uq_recon_mail_tpl_version_no"),
    CheckConstraint(
        "STATUS IN ('DRAFT', 'ACTIVE', 'ARCHIVED', 'INVALID')",
        name="ck_recon_mail_tpl_version_status",
    ),
    Index("ix_recon_mail_tpl_ver_tmpl_status", "TEMPLATE_ID", "STATUS"),
)

recon_mail_rule_binding = Table(
    "RECON_MAIL_RULE_BINDING",
    metadata,
    Column("RULE_ID", String(64), primary_key=True),
    Column(
        "TEMPLATE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_MAIL_TEMPLATE.ID"),
        nullable=False,
    ),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
)

# Task 106 (REPORT-STUDIO-01A): Semantic Model Core
recon_rpt_model = Table(
    "RECON_RPT_MODEL",
    metadata,
    pk_id_column(),
    Column("CODE", String(60), nullable=False),
    Column("NAME", String(200), nullable=False),
    Column("DESCRIPTION", String(500), nullable=True),
    Column(
        "DATA_SOURCE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_DATA_SOURCE.ID", name="fk_recon_rpt_model_ds"),
        nullable=False,
    ),
    Column(
        "ACTIVE_VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_VER.ID", use_alter=True, name="fk_recon_rpt_model_active_ver"),
        nullable=True,
    ),
    Column("IS_ARCHIVED", String(1), nullable=False, default="N"),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
    UniqueConstraint("CODE", name="uq_recon_rpt_model_code"),
    CheckConstraint("IS_ARCHIVED IN ('Y', 'N')", name="ck_recon_rpt_model_archived"),
)

recon_rpt_model_ver = Table(
    "RECON_RPT_MODEL_VER",
    metadata,
    pk_id_column(),
    Column(
        "MODEL_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL.ID", name="fk_recon_rpt_model_ver_model"),
        nullable=False,
    ),
    Column("VERSION_NO", Integer, nullable=False),
    Column("STATUS", String(20), nullable=False, default="DRAFT"),
    Column("CHANGE_NOTE", String(500), nullable=True),
    Column("VALIDATION_JSON", JsonText, nullable=True),
    Column("PUBLISHED_BY", String(60), nullable=True),
    Column("PUBLISHED_AT", DateTime, nullable=True),
    Column("CREATED_BY", String(60), nullable=False),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_BY", String(60), nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
    UniqueConstraint("MODEL_ID", "VERSION_NO", name="uq_recon_rpt_model_ver_no"),
    CheckConstraint(
        "STATUS IN ('DRAFT', 'VALIDATED', 'ACTIVE', 'ARCHIVED')",
        name="ck_recon_rpt_model_ver_status",
    ),
    Index("ix_recon_rpt_model_ver_status", "MODEL_ID", "STATUS"),
)

recon_rpt_model_table = Table(
    "RECON_RPT_MODEL_TABLE",
    metadata,
    pk_id_column(),
    Column(
        "MODEL_VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_VER.ID", name="fk_recon_rpt_model_tbl_ver"),
        nullable=False,
    ),
    Column("SOURCE_OWNER", String(60), nullable=True),
    Column("SOURCE_OBJECT", String(128), nullable=False),
    Column("OBJECT_TYPE", String(20), nullable=False, default="TABLE"),
    Column("ALIAS", String(60), nullable=False),
    Column("DISPLAY_NAME", String(200), nullable=False),
    Column("TABLE_ROLE", String(20), nullable=False, default="UNCLASSIFIED"),
    Column("GRAIN_DESC", String(500), nullable=True),
    Column("GRAIN_KEYS_JSON", JsonText, nullable=True),
    Column("DEFAULT_DATE_FIELD", String(128), nullable=True),
    Column("IS_HIDDEN", String(1), nullable=False, default="N"),
    Column("POS_X", Integer, nullable=False, default=0),
    Column("POS_Y", Integer, nullable=False, default=0),
    Column("ROW_ESTIMATE", BigInteger().with_variant(Integer, "sqlite"), nullable=True),
    Column("DESCRIPTION", String(500), nullable=True),
    UniqueConstraint("MODEL_VERSION_ID", "ALIAS", name="uq_recon_rpt_model_tbl_alias"),
    UniqueConstraint("MODEL_VERSION_ID", "SOURCE_OWNER", "SOURCE_OBJECT", name="uq_recon_rpt_model_tbl_src"),
    CheckConstraint("OBJECT_TYPE IN ('TABLE', 'VIEW')", name="ck_recon_rpt_model_tbl_obj_type"),
    CheckConstraint(
        "TABLE_ROLE IN ('FACT', 'DIMENSION', 'BRIDGE', 'UNCLASSIFIED')",
        name="ck_recon_rpt_model_tbl_role",
    ),
    CheckConstraint("IS_HIDDEN IN ('Y', 'N')", name="ck_recon_rpt_model_tbl_hidden"),
    Index("ix_recon_rpt_model_tbl_ver", "MODEL_VERSION_ID"),
)

recon_rpt_model_rel = Table(
    "RECON_RPT_MODEL_REL",
    metadata,
    pk_id_column(),
    Column(
        "MODEL_VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_VER.ID", name="fk_recon_rpt_model_rel_ver"),
        nullable=False,
    ),
    Column("NAME", String(120), nullable=False),
    Column(
        "FROM_TABLE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_TABLE.ID", name="fk_recon_rpt_model_rel_from"),
        nullable=False,
    ),
    Column("FROM_COLUMN", String(128), nullable=False),
    Column(
        "TO_TABLE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_TABLE.ID", name="fk_recon_rpt_model_rel_to"),
        nullable=False,
    ),
    Column("TO_COLUMN", String(128), nullable=False),
    Column("CARDINALITY", String(20), nullable=False, default="MANY_TO_ONE"),
    Column("JOIN_TYPE", String(20), nullable=False, default="LEFT_OUTER"),
    Column("CROSS_FILTER", String(20), nullable=False, default="SINGLE"),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
    Column("VALIDATION_STATUS", String(20), nullable=True),
    Column("VALIDATION_JSON", JsonText, nullable=True),
    CheckConstraint("CARDINALITY IN ('MANY_TO_ONE', 'ONE_TO_ONE')", name="ck_recon_rpt_model_rel_card"),
    CheckConstraint("JOIN_TYPE IN ('LEFT_OUTER', 'INNER')", name="ck_recon_rpt_model_rel_join"),
    CheckConstraint("CROSS_FILTER IN ('SINGLE')", name="ck_recon_rpt_model_rel_cf"),
    CheckConstraint("IS_ACTIVE IN ('Y', 'N')", name="ck_recon_rpt_model_rel_active"),
    Index("ix_recon_rpt_model_rel_ver", "MODEL_VERSION_ID"),
)

recon_rpt_model_field = Table(
    "RECON_RPT_MODEL_FIELD",
    metadata,
    pk_id_column(),
    Column(
        "TABLE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_TABLE.ID", name="fk_recon_rpt_model_fld_tbl"),
        nullable=False,
    ),
    Column("SOURCE_COLUMN", String(128), nullable=False),
    Column("FIELD_CODE", String(128), nullable=False),
    Column("DISPLAY_NAME", String(200), nullable=False),
    Column("DESCRIPTION", String(500), nullable=True),
    Column("DATA_TYPE", String(30), nullable=False),
    Column("FIELD_ROLE", String(30), nullable=False, default="DIMENSION"),
    Column("DEFAULT_AGG", String(20), nullable=False, default="NONE"),
    Column("FORMAT_MASK", String(100), nullable=True),
    Column("IS_VISIBLE", String(1), nullable=False, default="Y"),
    Column("IS_FILTERABLE", String(1), nullable=False, default="Y"),
    Column("IS_PK", String(1), nullable=False, default="N"),
    Column("IS_FK", String(1), nullable=False, default="N"),
    Column(
        "SORT_BY_FIELD_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_FIELD.ID", name="fk_recon_rpt_model_fld_sort"),
        nullable=True,
    ),
    Column("FOLDER", String(100), nullable=True),
    Column("ENABLE_DATE_HIERARCHY", String(1), nullable=False, default="N"),
    Column("SENSITIVITY", String(20), nullable=False, default="NORMAL"),
    Column("DISPLAY_ORDER", Integer, nullable=False, default=10),
    UniqueConstraint("TABLE_ID", "FIELD_CODE", name="uq_recon_rpt_model_fld_code"),
    UniqueConstraint("TABLE_ID", "SOURCE_COLUMN", name="uq_recon_rpt_model_fld_col"),
    CheckConstraint(
        "FIELD_ROLE IN ('DIMENSION', 'MEASURE_CANDIDATE', 'KEY', 'HIDDEN')",
        name="ck_recon_rpt_model_fld_role",
    ),
    CheckConstraint(
        "DEFAULT_AGG IN ('NONE', 'SUM', 'AVG', 'MIN', 'MAX', 'COUNT', 'COUNT_DISTINCT')",
        name="ck_recon_rpt_model_fld_agg",
    ),
    CheckConstraint("IS_VISIBLE IN ('Y', 'N')", name="ck_recon_rpt_model_fld_vis"),
    CheckConstraint("IS_FILTERABLE IN ('Y', 'N')", name="ck_recon_rpt_model_fld_flt"),
    CheckConstraint("IS_PK IN ('Y', 'N')", name="ck_recon_rpt_model_fld_pk"),
    CheckConstraint("IS_FK IN ('Y', 'N')", name="ck_recon_rpt_model_fld_fk"),
    CheckConstraint("ENABLE_DATE_HIERARCHY IN ('Y', 'N')", name="ck_recon_rpt_model_fld_dh"),
    CheckConstraint(
        "SENSITIVITY IN ('NORMAL', 'INTERNAL', 'RESTRICTED')",
        name="ck_recon_rpt_model_fld_sens",
    ),
    Index("ix_recon_rpt_model_fld_tbl", "TABLE_ID"),
)

recon_rpt_model_measure = Table(
    "RECON_RPT_MODEL_MEASURE",
    metadata,
    pk_id_column(),
    Column(
        "MODEL_VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_VER.ID", name="fk_recon_rpt_model_meas_ver"),
        nullable=False,
    ),
    Column(
        "TABLE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_TABLE.ID", name="fk_recon_rpt_model_meas_tbl"),
        nullable=True,
    ),
    Column("CODE", String(60), nullable=False),
    Column("NAME", String(200), nullable=False),
    Column("MEASURE_TYPE", String(20), nullable=False, default="SIMPLE"),
    Column(
        "BASE_FIELD_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_FIELD.ID", name="fk_recon_rpt_model_meas_fld"),
        nullable=True,
    ),
    Column("AGGREGATION", String(20), nullable=True),
    Column("EXPR_JSON", JsonText, nullable=True),
    Column("FORMAT_MASK", String(100), nullable=True),
    Column("FOLDER", String(100), nullable=True),
    Column("DESCRIPTION", String(500), nullable=True),
    UniqueConstraint("MODEL_VERSION_ID", "CODE", name="uq_recon_rpt_model_meas_code"),
    UniqueConstraint("MODEL_VERSION_ID", "NAME", name="uq_recon_rpt_model_meas_name"),
    CheckConstraint("MEASURE_TYPE IN ('SIMPLE', 'CALCULATED')", name="ck_recon_rpt_model_meas_type"),
    CheckConstraint(
        "AGGREGATION IS NULL OR AGGREGATION IN ('SUM', 'AVG', 'MIN', 'MAX', 'COUNT', 'COUNT_DISTINCT')",
        name="ck_recon_rpt_model_meas_agg",
    ),
    Index("ix_recon_rpt_model_meas_ver", "MODEL_VERSION_ID"),
)

recon_rpt_model_rls = Table(
    "RECON_RPT_MODEL_RLS",
    metadata,
    pk_id_column(),
    Column(
        "MODEL_VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_VER.ID", name="fk_recon_rpt_model_rls_ver"),
        nullable=False,
    ),
    Column(
        "TABLE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_TABLE.ID", name="fk_recon_rpt_model_rls_tbl"),
        nullable=False,
    ),
    Column("COLUMN_NAME", String(128), nullable=False),
    Column("POLICY_TYPE", String(30), nullable=False, default="OWNER_USERNAME"),
    Column("SCOPE_ATTR", String(60), nullable=True),
    Column("ADMIN_BYPASS", String(1), nullable=False, default="Y"),
    Column("IS_ACTIVE", String(1), nullable=False, default="Y"),
    Column("DESCRIPTION", String(500), nullable=True),
    UniqueConstraint("MODEL_VERSION_ID", "TABLE_ID", "COLUMN_NAME", name="uq_recon_rpt_model_rls_col"),
    CheckConstraint(
        "POLICY_TYPE IN ('OWNER_USERNAME', 'ROLE_LIST', 'ORG_SCOPE_HOOK')",
        name="ck_recon_rpt_model_rls_type",
    ),
    CheckConstraint("ADMIN_BYPASS IN ('Y', 'N')", name="ck_recon_rpt_model_rls_bypass"),
    CheckConstraint("IS_ACTIVE IN ('Y', 'N')", name="ck_recon_rpt_model_rls_active"),
    Index("ix_recon_rpt_model_rls_ver", "MODEL_VERSION_ID"),
)

# Report Studio (task 109): visual thuộc một phiên bản template báo cáo
# (RECON_RPT_TPL_VER, SOURCE_TYPE='SEMANTIC_MODEL'); field/measure trong
# visual trỏ sang RECON_RPT_MODEL_FIELD / RECON_RPT_MODEL_MEASURE của
# MODEL_VERSION_ID mà version đó pin.
recon_rpt_visual = Table(
    "RECON_RPT_VISUAL",
    metadata,
    pk_id_column(),
    Column(
        "VERSION_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_TPL_VER.ID", name="fk_recon_rpt_visual_ver"),
        nullable=False,
    ),
    Column("CODE", String(60), nullable=False),
    Column("TITLE", String(200), nullable=False),
    Column("VISUAL_TYPE", String(20), nullable=False),
    Column("DISPLAY_ORDER", Integer, nullable=False, default=10),
    Column("GRID_SPAN", Integer, nullable=False, default=12),
    Column("HEIGHT_SIZE", String(10), nullable=False, default="M"),
    Column("CONFIG_JSON", JsonText, nullable=True),
    Column("CREATED_AT", DateTime, nullable=False),
    Column("UPDATED_AT", DateTime, nullable=False),
    Column("ROW_VERSION", Integer, nullable=False, default=1),
    UniqueConstraint("VERSION_ID", "CODE", name="uq_recon_rpt_visual_ver_code"),
    CheckConstraint(
        "VISUAL_TYPE IN ('TABLE', 'MATRIX', 'KPI', 'BAR', 'LINE')",
        name="ck_recon_rpt_visual_type",
    ),
    CheckConstraint("GRID_SPAN IN (3, 4, 6, 8, 12)", name="ck_recon_rpt_visual_grid_span"),
    CheckConstraint("HEIGHT_SIZE IN ('S', 'M', 'L')", name="ck_recon_rpt_visual_height"),
    Index("ix_recon_rpt_visual_ver", "VERSION_ID"),
)

recon_rpt_visual_field = Table(
    "RECON_RPT_VISUAL_FIELD",
    metadata,
    pk_id_column(),
    Column(
        "VISUAL_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_VISUAL.ID", name="fk_recon_rpt_visual_field_visual", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("WELL_ROLE", String(20), nullable=False),
    Column(
        "FIELD_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_FIELD.ID", name="fk_recon_rpt_visual_field_field"),
        nullable=True,
    ),
    Column(
        "MEASURE_ID",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("RECON_RPT_MODEL_MEASURE.ID", name="fk_recon_rpt_visual_field_measure"),
        nullable=True,
    ),
    Column("AGGREGATION", String(20), nullable=True),
    Column("DATE_PART", String(20), nullable=True),
    Column("ALIAS", String(128), nullable=True),
    Column("LABEL_OVERRIDE", String(200), nullable=True),
    Column("FORMAT_MASK", String(100), nullable=True),
    Column("SORT_DIRECTION", String(10), nullable=True),
    Column("DISPLAY_ORDER", Integer, nullable=False, default=10),
    CheckConstraint(
        "AGGREGATION IS NULL OR AGGREGATION IN ('NONE', 'SUM', 'AVG', 'MIN', 'MAX', 'COUNT', 'COUNT_DISTINCT')",
        name="ck_recon_rpt_visual_field_agg",
    ),
    CheckConstraint(
        "DATE_PART IS NULL OR DATE_PART IN ('DAY', 'MONTH', 'QUARTER', 'YEAR')",
        name="ck_recon_rpt_visual_field_date_part",
    ),
    CheckConstraint(
        "SORT_DIRECTION IS NULL OR SORT_DIRECTION IN ('ASC', 'DESC')",
        name="ck_recon_rpt_visual_field_sort",
    ),
    Index("ix_recon_rpt_visual_field_vis", "VISUAL_ID"),
)
