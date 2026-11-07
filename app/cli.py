"""CLI quản trị cho ReconHub.

Các lệnh: create-admin, reset-password, purge-temp, migrate-metadata, seed.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Connection, select, update

from app.core.audit import write_audit_log
from app.core.auth import hash_password
from app.core.config import PROJECT_ROOT, get_settings
from app.core.context import Ctx, Role
from app.core.crypto import encrypt_secret
from app.core.session import invalidate_user_session_cache
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_data_source,
    recon_menu,
    recon_role,
    recon_role_menu,
    recon_template,
    recon_template_version,
    recon_user,
    recon_user_role,
)
from app.schemas.run import PurgeFilter
from app.services.data_source import sync_current_metadata_source
from app.services.metadata_migration import precheck, start_migration
from app.services.temp_data import preview, purge_filter, purge_runs, usage


def _ensure_role(conn: Connection, code: str, name: str, is_system: str, now: datetime) -> int:
    """Trả về ID vai trò, tự tạo nếu chưa có (DB mới chưa chạy migration 0003)."""
    role_id = conn.execute(select(recon_role.c.ID).where(recon_role.c.CODE == code)).scalar_one_or_none()
    if role_id is not None:
        return int(role_id)
    res = conn.execute(
        recon_role.insert().values(
            CODE=code,
            NAME=name,
            IS_SYSTEM=is_system,
            IS_ACTIVE="Y",
            CREATED_BY="CLI",
            CREATED_AT=now,
            UPDATED_BY="CLI",
            UPDATED_AT=now,
            ROW_VERSION=1,
        )
    )
    assert res.inserted_primary_key is not None
    return int(res.inserted_primary_key[0])


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
                .join(recon_role, recon_user_role.c.ROLE_ID == recon_role.c.ID)
                .where(recon_role.c.CODE == "ADMIN")
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

        # Đảm bảo có role ADMIN (tự tạo nếu DB mới chưa chạy migration 0003)
        admin_role_id = _ensure_role(conn, "ADMIN", "Quản trị viên", "Y", now)
        has_admin_role = None
        if admin_role_id is not None:
            has_admin_role = conn.execute(
                select(recon_user_role.c.ROLE_ID)
                .where(recon_user_role.c.USER_ID == user_id)
                .where(recon_user_role.c.ROLE_ID == admin_role_id)
            ).scalar_one_or_none()

        if admin_role_id is not None and not has_admin_role:
            conn.execute(
                recon_user_role.insert().values(
                    USER_ID=user_id,
                    ROLE_ID=admin_role_id,
                    ASSIGNED_BY="CLI",
                    ASSIGNED_AT=now,
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
    ctx = Ctx(user_id=1, username="cli_admin", full_name="Quản trị viên CLI", roles=[Role.ADMIN])
    run_id = getattr(args, "run", None)
    checked_before_str = getattr(args, "checked_before", None)
    is_dry_run = getattr(args, "dry_run", False)

    if run_id is not None:
        if is_dry_run:
            print(f"[DRY-RUN] Xem trước: Dữ liệu tạm của run #{run_id} sẽ được xóa.")
            return
        res = purge_runs(ctx, [run_id])
        if res.ok and res.data:
            print(
                f"Thành công: Đã xóa dữ liệu tạm của run #{run_id} (giải phóng {res.data.get('bytes_freed', 0):,} bytes)."
            )
        else:
            print(f"Lỗi: {res.message}", file=sys.stderr)
            sys.exit(1)
        return

    if checked_before_str is not None:
        try:
            dt = datetime.strptime(checked_before_str.strip(), "%Y-%m-%d")
        except ValueError:
            print("Lỗi: Định dạng ngày --checked-before phải là YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)

        flt = PurgeFilter(before_date=dt, only_checked=True)
        prev = preview(ctx, flt)
        if not prev.ok or not prev.data:
            print(f"Lỗi preview: {prev.message}", file=sys.stderr)
            sys.exit(1)

        run_count = prev.data["run_count"]
        est_rows = prev.data["rows_estimated"]
        est_bytes = prev.data["bytes_estimated"]

        print(
            f"Tìm thấy {run_count} run đã kiểm tra trước ngày {checked_before_str} ({est_rows:,} dòng, ước tính ~{est_bytes / (1024 * 1024):.1f} MB)."
        )

        if is_dry_run:
            print("[DRY-RUN] Kết thúc chế độ xem trước (không có dữ liệu nào bị xóa).")
            return

        if run_count == 0:
            print("Không có run nào thỏa mãn điều kiện để xóa.")
            return

        res = purge_filter(ctx, flt, confirm_text="XOA")
        if res.ok and res.data:
            print(
                f"Thành công: Đã xóa dữ liệu tạm của {res.data['runs_purged']} run ({res.data['rows_deleted']:,} dòng)."
            )
        else:
            print(f"Lỗi: {res.message}", file=sys.stderr)
            sys.exit(1)
        return

    # Nếu không truyền tham số, in thông tin usage
    u = usage(ctx)
    if u.ok and u.data:
        d = u.data
        total_mb = d["total_bytes"] / (1024 * 1024)
        print("=== BÁO CÁO DỮ LIỆU TẠM RECONHUB ===")
        print(f"- Tổng dung lượng dữ liệu tạm: {total_mb:.2f} MB (~{d['total_bytes']:,} bytes)")
        print(f"- Số dòng Excel tạm: {d['excel_rows_count']:,} dòng")
        print(f"- Số run chưa kiểm tra: {d['runs_unchecked_count']}")
        print(f"- Số run giữ dữ liệu tạm chưa xóa: {d['runs_unpurged_count']}")
        print(f"- Số run giữ dữ liệu tạm quá {d['warn_days']} ngày: {d['runs_overdue_count']}")
        if d["is_warning"]:
            print(f"CẢNH BÁO: {d['warning_message']}")
        else:
            print("Trạng thái: Dung lượng nằm trong ngưỡng an toàn.")
    else:
        print("Lỗi khi kiểm tra dung lượng dữ liệu tạm.", file=sys.stderr)


def migrate_metadata_cmd(args: argparse.Namespace) -> None:
    """Chuyển metadata RECON_APP từ SQLite sang Oracle qua CLI."""
    ctx = Ctx(user_id=1, username="cli_admin", full_name="Quản trị viên CLI", roles=[Role.ADMIN])
    target_ds_id = getattr(args, "target_ds", None)
    mode = getattr(args, "mode", "NO_TEMP")
    is_dry_run = getattr(args, "dry_run", False)
    force = getattr(args, "force", False)

    if not target_ds_id:
        print("Lỗi: Cần cung cấp ID của Data Source Oracle đích qua --target-ds.", file=sys.stderr)
        sys.exit(1)

    print(f"=== BẮT ĐẦU KIỂM TRA TRƯỚC (PRECHECK) CHO DATA SOURCE #{target_ds_id} (MODE: {mode}) ===")
    pre_res = precheck(ctx, target_ds_id=target_ds_id, mode=mode)
    if not pre_res.ok or not pre_res.data:
        print(f"Lỗi precheck: {pre_res.message}", file=sys.stderr)
        sys.exit(1)

    data = pre_res.data
    print(f"Data Source đích: {data['target_name']} (ENV: {data['target_env']})")
    print(f"Tổng số bảng cần chuyển: {len(data['tables'])}")
    print(f"Tổng số bản ghi ước tính: {data['total_rows']:,}")
    print(f"Tổng dung lượng ước tính: {data['total_bytes_est'] / (1024 * 1024):.2f} MB")
    print("\nChi tiết các bảng:")
    for t in data["tables"]:
        print(f"  - {t['table']:<25}: {t['rows']:>8,} dòng (~{t['bytes_est'] / 1024:>7.1f} KB)")

    if is_dry_run:
        print("\n[DRY-RUN] Precheck thành công! Không thực hiện chuyển dữ liệu.")
        return

    if not force:
        confirm = input(
            f"\nBạn có chắc chắn muốn chuyển dữ liệu RECON_APP sang Data Source #{target_ds_id}? "
            "Hệ thống sẽ kích hoạt chế độ bảo trì trong khi chuyển. [y/N]: "
        )
        if confirm.strip().lower() not in ("y", "yes"):
            print("Đã hủy thao tác chuyển metadata.")
            return

    print("\n=== ĐANG THỰC HIỆN CHUYỂN DỮ LIỆU SANG ORACLE... ===")
    mig_res = start_migration(ctx, target_ds_id=target_ds_id, mode=mode)
    if not mig_res.ok or not mig_res.data:
        print(f"Lỗi khi chuyển metadata: {mig_res.message}", file=sys.stderr)
        sys.exit(1)

    m_data = mig_res.data
    print("\n=== CHUYỂN DỮ LIỆU THÀNH CÔNG! ===")
    print(f"Phiên chuyển ID: {m_data['migration_id']}")
    print(f"Bản lưu SQLite cũ tại: {m_data['old_sqlite_path']}")
    print("\nCác bước tiếp theo cần thực hiện:")
    for step in m_data.get("next_steps", []):
        print(f"  {step}")


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
                role_id = _ensure_role(
                    conn,
                    role,
                    {
                        "ADMIN": "Quản trị viên",
                        "TEMPLATE_OWNER": "Chủ sở hữu Template",
                        "OPERATOR": "Chuyên viên đối soát",
                        "VIEWER": "Người xem báo cáo",
                    }.get(role, role),
                    "Y" if role == "ADMIN" else "N",
                    now,
                )
                # Gán menu seed cho vai trò (chỉ khi menu đã đồng bộ vào DB)
                from app.ui.menus import ROLE_MENUS_SEED

                for menu_code in ROLE_MENUS_SEED.get(role, []):
                    menu_exists = conn.execute(
                        select(recon_menu.c.CODE).where(recon_menu.c.CODE == menu_code)
                    ).scalar_one_or_none()
                    granted = conn.execute(
                        select(recon_role_menu.c.MENU_CODE)
                        .where(recon_role_menu.c.ROLE_ID == role_id)
                        .where(recon_role_menu.c.MENU_CODE == menu_code)
                    ).scalar_one_or_none()
                    if menu_exists is not None and granted is None:
                        conn.execute(
                            recon_role_menu.insert().values(
                                ROLE_ID=role_id,
                                MENU_CODE=menu_code,
                                GRANTED_BY="SEED",
                                GRANTED_AT=now,
                            )
                        )
                conn.execute(
                    recon_user_role.insert().values(
                        USER_ID=user_id,
                        ROLE_ID=int(role_id),
                        ASSIGNED_BY="SEED",
                        ASSIGNED_AT=now,
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

    # 4. Nạp template mẫu DTP_HOA_DON_TAC_NGHIEP
    sample_tmpl_file = PROJECT_ROOT / "samples" / "templates" / "DTP_HOA_DON_TAC_NGHIEP.json"
    if sample_tmpl_file.exists():
        with open(sample_tmpl_file, "r", encoding="utf-8") as f:
            tmpl_data = json.load(f)

        tmpl_code = "DTP_HOA_DON_TAC_NGHIEP"
        with engine.begin() as conn:
            existing_tmpl = conn.execute(
                select(recon_template.c.ID).where(recon_template.c.CODE == tmpl_code)
            ).scalar_one_or_none()

            if existing_tmpl is None:
                oracle_ds_id = (
                    conn.execute(select(recon_data_source.c.ID).where(recon_data_source.c.NAME == "ORACLE_TEST"))
                    .scalars()
                    .first()
                )

                ins_tmpl = conn.execute(
                    recon_template.insert().values(
                        CODE=tmpl_code,
                        NAME="Đối soát hóa đơn tác nghiệp DTP",
                        DESCRIPTION="Template mẫu đối soát hóa đơn tác nghiệp DTP với CSDL Oracle",
                        OWNER="admin",
                        STATUS="DRAFT",
                        CURRENT_VERSION=1,
                        CREATED_AT=now,
                        UPDATED_AT=now,
                        ROW_VERSION=1,
                    )
                )
                if ins_tmpl.inserted_primary_key:
                    tmpl_id = int(ins_tmpl.inserted_primary_key[0])

                    conn.execute(
                        recon_template_version.insert().values(
                            TEMPLATE_ID=tmpl_id,
                            VERSION=1,
                            STATUS="DRAFT",
                            CONFIG_JSON=tmpl_data,
                            DATA_SOURCE_ID=oracle_ds_id,
                            DRY_RUN_OK="N",
                            CREATED_BY="SEED",
                            CREATED_AT=now,
                        )
                    )

                    write_audit_log(
                        conn=conn,
                        entity="TEMPLATE",
                        entity_id=tmpl_id,
                        action="SEED_TEMPLATE",
                        actor="SEED",
                        new_data={"code": tmpl_code, "version": 1},
                        now=now,
                    )
                    print(f"Hoàn tất: Đã nạp template mẫu '{tmpl_code}'.")


def backup_cmd(args: argparse.Namespace) -> None:
    """Tạo bản sao lưu SQLite database (VACUUM INTO) và xoay vòng giữ tối đa 14 bản."""
    settings = get_settings()
    db_url = settings.RECON_DB_URL

    if not db_url.startswith("sqlite"):
        print(f"Chú ý: Cơ sở dữ liệu RECON_APP hiện tại ({db_url.split('://')[0]}) không phải SQLite.")
        print("Bản sao lưu cho Oracle được quản lý tự động bởi DBA thông qua RMAN hoặc Data Pump.")
        return

    dest_dir = getattr(args, "dest", None)
    if dest_dir:
        backup_dir = Path(dest_dir)
    else:
        backup_dir = settings.PROJECT_ROOT / "backup"

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"recon_app_{timestamp}.db"

    engine = get_recon_engine()
    print(f"Đang thực hiện sao lưu cơ sở dữ liệu SQLite vào '{backup_file}'...")

    try:
        with engine.connect() as conn:
            try:
                conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
            clean_path = str(backup_file.resolve()).replace("\\", "/")
            conn.exec_driver_sql(f"VACUUM INTO '{clean_path}'")
    finally:
        engine.dispose()

    file_size = backup_file.stat().st_size
    print(f"Thành công: Đã tạo bản sao lưu '{backup_file.name}' ({file_size:,} bytes).")

    keep_count = getattr(args, "keep", 14) or 14
    existing_backups = sorted(
        backup_dir.glob("recon_app_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if len(existing_backups) > keep_count:
        to_delete = existing_backups[keep_count:]
        print(f"Đang dọn dẹp các bản sao lưu cũ hơn (giữ lại {keep_count} bản gần nhất):")
        for old_b in to_delete:
            try:
                old_b.unlink()
                print(f"  - Đã xóa: {old_b.name}")
            except Exception as e:
                print(f"  ! Không thể xóa {old_b.name}: {e}", file=sys.stderr)

    remaining = len(list(backup_dir.glob("recon_app_*.db")))
    print(f"Tổng số bản sao lưu hiện có: {remaining}/{keep_count}.")


def restore_cmd(args: argparse.Namespace) -> None:
    """Khôi phục cơ sở dữ liệu SQLite từ file backup."""
    settings = get_settings()
    db_url = settings.RECON_DB_URL

    if not db_url.startswith("sqlite"):
        print("Lỗi: Lệnh restore chỉ áp dụng cho SQLite database.", file=sys.stderr)
        sys.exit(1)

    backup_file_path = getattr(args, "file", None)
    if not backup_file_path:
        print("Lỗi: Vui lòng chỉ định file sao lưu qua --file <path>.", file=sys.stderr)
        sys.exit(1)

    backup_path = Path(backup_file_path)
    if not backup_path.exists():
        print(f"Lỗi: Không tìm thấy file sao lưu '{backup_path}'.", file=sys.stderr)
        sys.exit(1)

    prefix = "sqlite:///"
    if db_url.startswith(prefix):
        raw_db_path = db_url[len(prefix) :]
    else:
        raw_db_path = "data/recon_app.db"

    target_db = Path(raw_db_path)
    if not target_db.is_absolute():
        target_db = settings.PROJECT_ROOT / target_db

    target_db.parent.mkdir(parents=True, exist_ok=True)

    engine = get_recon_engine()
    try:
        with engine.connect() as conn:
            try:
                conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
    except Exception:
        pass
    finally:
        engine.dispose()

    import gc

    gc.collect()

    if target_db.exists():
        safety_bak = target_db.with_suffix(".db.pre_restore_bak")
        import shutil

        shutil.copy2(target_db, safety_bak)
        print(f"Đã tạo bản lưu dự phòng cơ sở dữ liệu hiện tại tại '{safety_bak.name}'.")

    import shutil

    shutil.copy2(backup_path, target_db)

    # Xóa file WAL và SHM cũ nếu có để tránh phục hồi trạng thái cũ
    for suffix in ["-wal", "-shm"]:
        companion = target_db.with_name(target_db.name + suffix)
        if companion.exists():
            try:
                companion.unlink()
            except Exception:
                pass

    print(f"Thành công: Đã khôi phục cơ sở dữ liệu từ '{backup_path.name}' vào '{target_db}'.")


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
    p_purge.add_argument("--run", type=int, help="ID của run cần xóa dữ liệu tạm")
    p_purge.add_argument("--checked-before", help="Xóa các run đã kiểm tra trước ngày này (YYYY-MM-DD)")
    p_purge.add_argument("--dry-run", action="store_true", help="Chỉ xem trước số run và dung lượng mà không xóa thật")
    p_purge.set_defaults(func=purge_temp_cmd)

    # migrate-metadata
    p_mig = subparsers.add_parser("migrate-metadata", help="Chuyển metadata RECON_APP sang Oracle")
    p_mig.add_argument("--target-ds", type=int, help="ID của Data Source Oracle đích")
    p_mig.add_argument(
        "--mode",
        choices=["NO_TEMP", "FULL", "CONFIG_ONLY"],
        default="NO_TEMP",
        help="Chế độ chuyển dữ liệu (mặc định: NO_TEMP)",
    )
    p_mig.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ kiểm tra trước (precheck) mà không thực hiện chuyển",
    )
    p_mig.add_argument("--force", action="store_true", help="Bỏ qua câu hỏi xác nhận")
    p_mig.set_defaults(func=migrate_metadata_cmd)

    # seed
    p_seed = subparsers.add_parser("seed", help="Nạp dữ liệu mẫu ban đầu")
    p_seed.set_defaults(func=seed_cmd)

    # backup
    p_backup = subparsers.add_parser("backup", help="Sao lưu cơ sở dữ liệu SQLite (VACUUM INTO)")
    p_backup.add_argument("--dest", help="Thư mục lưu trữ bản backup (mặc định: backup/)")
    p_backup.add_argument("--keep", type=int, default=14, help="Số lượng bản sao lưu tối đa giữ lại (mặc định: 14)")
    p_backup.set_defaults(func=backup_cmd)

    # restore
    p_restore = subparsers.add_parser("restore", help="Khôi phục cơ sở dữ liệu SQLite từ file backup")
    p_restore.add_argument("--file", required=True, help="Đường dẫn file sao lưu .db")
    p_restore.set_defaults(func=restore_cmd)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
