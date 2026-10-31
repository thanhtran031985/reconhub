"""CLI quản trị cho ReconHub.

Các lệnh: create-admin, reset-password, purge-temp, migrate-metadata, seed.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.core.audit import write_audit_log
from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.crypto import encrypt_secret
from app.core.session import invalidate_user_session_cache
from app.db.engine import get_recon_engine
from app.db.metadata import recon_data_source, recon_user, recon_user_role
from app.services.data_source import sync_current_metadata_source


def create_admin_cmd(args: argparse.Namespace) -> None:
    """Tạo tài khoản quản trị đầu tiên (từ chối nếu đã có Admin trừ --force)."""
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        # Kiểm tra Admin hiện có
        existing_admins = (
            conn.execute(
                select(recon_user.c.ID)
                .join(recon_user_role, recon_user.c.ID == recon_user_role.c.USER_ID)
                .where(recon_user_role.c.ROLE == "ADMIN")
            )
            .scalars()
            .all()
        )

        if existing_admins and not getattr(args, "force", False):
            print(
                "Lỗi: Hệ thống đã có tài khoản Quản trị viên. Dùng --force nếu muốn tạo thêm.",
                file=sys.stderr,
            )
            sys.exit(1)

        username = getattr(args, "username", None)
        if not username:
            username = input("Tên đăng nhập quản trị: ").strip()

        full_name = getattr(args, "full_name", None)
        if not full_name:
            full_name = input("Họ và tên: ").strip() or "Quản Trị Viên"

        password = getattr(args, "password", None)
        if not password:
            password = getpass.getpass("Mật khẩu: ")

        norm_username = username.strip().lower()
        pw_hash = hash_password(password)

        # Kiểm tra nếu user đã tồn tại
        user_row = conn.execute(
            select(recon_user.c.ID).where(recon_user.c.USERNAME == norm_username)
        ).scalar_one_or_none()

        if user_row is not None:
            user_id = user_row
            # Cập nhật mật khẩu và gán role ADMIN
            conn.execute(
                update(recon_user)
                .where(recon_user.c.ID == user_id)
                .values(
                    FULL_NAME=full_name,
                    PASSWORD_HASH=pw_hash,
                    IS_ACTIVE="Y",
                    MUST_CHANGE_PW="N",
                    SESSION_VERSION=recon_user.c.SESSION_VERSION + 1,
                    UPDATED_AT=now,
                )
            )
        else:
            ins_res = conn.execute(
                recon_user.insert().values(
                    USERNAME=norm_username,
                    FULL_NAME=full_name,
                    PASSWORD_HASH=pw_hash,
                    IS_ACTIVE="Y",
                    MUST_CHANGE_PW="N",
                    FAILED_COUNT=0,
                    SESSION_VERSION=1,
                    CREATED_BY="CLI",
                    CREATED_AT=now,
                    UPDATED_AT=now,
                )
            )
            if ins_res.inserted_primary_key is None:
                print("Lỗi: Không lấy được ID người dùng vừa tạo.", file=sys.stderr)
                sys.exit(1)
            user_id = int(ins_res.inserted_primary_key[0])

        # Đảm bảo có role ADMIN
        has_admin_role = conn.execute(
            select(recon_user_role.c.ROLE)
            .where(recon_user_role.c.USER_ID == user_id)
            .where(recon_user_role.c.ROLE == "ADMIN")
        ).scalar_one_or_none()

        if not has_admin_role:
            conn.execute(
                recon_user_role.insert().values(
                    USER_ID=user_id,
                    ROLE="ADMIN",
                    CREATED_AT=now,
                )
            )

        invalidate_user_session_cache(user_id)

        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=user_id,
            action="CLI_CREATE_ADMIN",
            actor="CLI",
            new_data={"username": norm_username, "role": "ADMIN", "password_hash": "***"},
            now=now,
        )

        print(f"Thành công: Đã tạo/cập nhật tài khoản quản trị '{norm_username}'.")


def reset_password_cmd(args: argparse.Namespace) -> None:
    """Đặt lại mật khẩu cho người dùng khi quên mật khẩu."""
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    username = getattr(args, "username", None)
    if not username:
        username = input("Tên đăng nhập cần đặt lại mật khẩu: ").strip()

    password = getattr(args, "password", None)
    if not password:
        password = getpass.getpass("Mật khẩu mới: ")

    norm_username = username.strip().lower()
    pw_hash = hash_password(password)

    with engine.begin() as conn:
        user_row = conn.execute(select(recon_user).where(recon_user.c.USERNAME == norm_username)).mappings().first()

        if user_row is None:
            print(f"Lỗi: Không tìm thấy người dùng '{norm_username}'.", file=sys.stderr)
            sys.exit(1)

        user_id = int(user_row["ID"])

        conn.execute(
            update(recon_user)
            .where(recon_user.c.ID == user_id)
            .values(
                PASSWORD_HASH=pw_hash,
                MUST_CHANGE_PW="Y",
                PW_CHANGED_AT=now,
                FAILED_COUNT=0,
                LOCKED_UNTIL=None,
                SESSION_VERSION=int(user_row["SESSION_VERSION"] or 1) + 1,
                UPDATED_AT=now,
            )
        )

        invalidate_user_session_cache(user_id)

        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=user_id,
            action="CLI_RESET_PASSWORD",
            actor="CLI",
            new_data={"username": norm_username, "password_hash": "***", "must_change_pw": "Y"},
            now=now,
        )

        print(f"Thành công: Đã đặt lại mật khẩu cho '{norm_username}'.")


def purge_temp_cmd(args: argparse.Namespace) -> None:
    print("purge-temp: Tính năng sẽ được kích hoạt ở task 07-run-queue-worker.")


def migrate_metadata_cmd(args: argparse.Namespace) -> None:
    print("migrate-metadata: Tính năng sẽ được kích hoạt ở task 13-metadata-migration.")


def seed_cmd(args: argparse.Namespace) -> None:
    """Khởi tạo 4 tài khoản mẫu đại diện cho 4 vai trò (idempotent)."""
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    seed_users = [
        ("admin", "Quản Trị Viên", "admin123", ["ADMIN"]),
        ("owner", "Chủ Sở Hữu Template", "owner123", ["TEMPLATE_OWNER"]),
        ("operator", "Chuyên Viên Đối Soát", "operator123", ["OPERATOR"]),
        ("viewer", "Người Xem Báo Cáo", "viewer123", ["VIEWER"]),
    ]

    with engine.begin() as conn:
        created_count = 0
        for username, full_name, password, roles in seed_users:
            existing = conn.execute(
                select(recon_user.c.ID).where(recon_user.c.USERNAME == username)
            ).scalar_one_or_none()

            if existing is not None:
                continue

            pw_hash = hash_password(password)
            ins_res = conn.execute(
                recon_user.insert().values(
                    USERNAME=username,
                    FULL_NAME=full_name,
                    PASSWORD_HASH=pw_hash,
                    IS_ACTIVE="Y",
                    MUST_CHANGE_PW="N",
                    FAILED_COUNT=0,
                    SESSION_VERSION=1,
                    CREATED_BY="SEED",
                    CREATED_AT=now,
                    UPDATED_AT=now,
                )
            )
            if ins_res.inserted_primary_key is None:
                continue
            user_id = int(ins_res.inserted_primary_key[0])

            for role in roles:
                conn.execute(
                    recon_user_role.insert().values(
                        USER_ID=user_id,
                        ROLE=role,
                        CREATED_AT=now,
                    )
                )

            write_audit_log(
                conn=conn,
                entity="USER",
                entity_id=user_id,
                action="SEED_USER",
                actor="SEED",
                new_data={"username": username, "roles": roles, "password_hash": "***"},
                now=now,
            )
            created_count += 1

        print(f"Hoàn tất: Đã nạp {created_count} người dùng mẫu mới (tổng 4 người dùng mẫu).")

    # 2. Đồng bộ nguồn metadata hiện tại
    sync_current_metadata_source(engine)

    # 3. Nạp data source mẫu ORACLE_TEST nếu có cấu hình trong môi trường
    settings = get_settings()
    if settings.ORACLE_TEST_HOST and settings.ORACLE_TEST_SERVICE and settings.ORACLE_TEST_USER:
        env_val = (settings.APP_ENV or "DEV").upper()
        with engine.begin() as conn:
            existing_ds = conn.execute(
                select(recon_data_source.c.ID)
                .where(recon_data_source.c.NAME == "ORACLE_TEST")
                .where(recon_data_source.c.ENV == env_val)
            ).scalar_one_or_none()

            if existing_ds is None:
                pw_enc = encrypt_secret(settings.ORACLE_TEST_PASSWORD) if settings.ORACLE_TEST_PASSWORD else None
                conn.execute(
                    recon_data_source.insert().values(
                        NAME="ORACLE_TEST",
                        ENV=env_val,
                        PURPOSE="SOURCE",
                        DB_TYPE="ORACLE",
                        HOST=settings.ORACLE_TEST_HOST,
                        PORT=int(settings.ORACLE_TEST_PORT or 1521),
                        SERVICE_NAME=settings.ORACLE_TEST_SERVICE,
                        USERNAME=settings.ORACLE_TEST_USER,
                        PASSWORD_ENC=pw_enc,
                        DEFAULT_SCHEMA=settings.ORACLE_TEST_SRC_SCHEMA or None,
                        CALL_TIMEOUT_S=600,
                        MAX_ROWS=1000000,
                        IS_ACTIVE="Y",
                        IS_CURRENT_METADATA="N",
                        CREATED_BY="SEED",
                        CREATED_AT=now,
                        UPDATED_AT=now,
                    )
                )
                print(f"Hoàn tất: Đã nạp nguồn dữ liệu mẫu 'ORACLE_TEST' ({env_val}).")


def main() -> None:
    if sys.platform == "win32":
        try:
            reconfig_out = getattr(sys.stdout, "reconfigure", None)
            if callable(reconfig_out):
                reconfig_out(encoding="utf-8")
            reconfig_err = getattr(sys.stderr, "reconfigure", None)
            if callable(reconfig_err):
                reconfig_err(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(prog="reconhub-cli", description="CLI quản trị ReconHub")
    subparsers = parser.add_subparsers(dest="subcommand", help="Lệnh quản trị")

    # create-admin
    p_admin = subparsers.add_parser("create-admin", help="Tạo tài khoản quản trị đầu tiên")
    p_admin.add_argument("--username", help="Tên đăng nhập")
    p_admin.add_argument("--full-name", help="Họ và tên")
    p_admin.add_argument("--password", help="Mật khẩu khởi tạo")
    p_admin.add_argument("--force", action="store_true", help="Bắt buộc tạo lại")
    p_admin.set_defaults(func=create_admin_cmd)

    # reset-password
    p_reset = subparsers.add_parser("reset-password", help="Đặt lại mật khẩu người dùng")
    p_reset.add_argument("--username", required=False, help="Tên đăng nhập")
    p_reset.add_argument("--password", required=False, help="Mật khẩu mới")
    p_reset.set_defaults(func=reset_password_cmd)

    # purge-temp
    p_purge = subparsers.add_parser("purge-temp", help="Dọn dẹp dữ liệu tạm theo yêu cầu")
    p_purge.set_defaults(func=purge_temp_cmd)

    # migrate-metadata
    p_mig = subparsers.add_parser("migrate-metadata", help="Chuyển metadata RECON_APP sang Oracle")
    p_mig.set_defaults(func=migrate_metadata_cmd)

    # seed
    p_seed = subparsers.add_parser("seed", help="Nạp dữ liệu mẫu ban đầu")
    p_seed.set_defaults(func=seed_cmd)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
