"""CLI quản trị cho ReconHub.

Các lệnh: create-admin, reset-password, purge-temp, migrate-metadata, seed.
"""
from __future__ import annotations

import argparse
import sys


def create_admin_cmd(args: argparse.Namespace) -> None:
    print("create-admin: Tính năng sẽ được kích hoạt ở task 01-auth-users.")


def reset_password_cmd(args: argparse.Namespace) -> None:
    print("reset-password: Tính năng sẽ được kích hoạt ở task 01-auth-users.")


def purge_temp_cmd(args: argparse.Namespace) -> None:
    print("purge-temp: Tính năng sẽ được kích hoạt ở task 07-run-queue-worker.")


def migrate_metadata_cmd(args: argparse.Namespace) -> None:
    print("migrate-metadata: Tính năng sẽ được kích hoạt ở task 13-metadata-migration.")


def seed_cmd(args: argparse.Namespace) -> None:
    print("seed: Khởi tạo dữ liệu mẫu tối thiểu.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="reconhub-cli", description="CLI quản trị ReconHub")
    subparsers = parser.add_subparsers(dest="subcommand", help="Lệnh quản trị")

    # create-admin
    p_admin = subparsers.add_parser("create-admin", help="Tạo tài khoản quản trị đầu tiên")
    p_admin.add_argument("--username", help="Tên đăng nhập")
    p_admin.add_argument("--force", action="store_true", help="Bắt buộc tạo lại")
    p_admin.set_defaults(func=create_admin_cmd)

    # reset-password
    p_reset = subparsers.add_parser("reset-password", help="Đặt lại mật khẩu người dùng")
    p_reset.add_argument("--username", required=False, help="Tên đăng nhập")
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

