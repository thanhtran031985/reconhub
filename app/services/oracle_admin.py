from __future__ import annotations


def generate_target_user_sql(schema_name: str = "RECON_APP", password: str = "<mật khẩu>") -> str:
    """Sinh script SQL tạo user/schema đích trên Oracle để lưu trữ RECON_APP."""
    return f"""-- Tạo schema Oracle làm đích lưu trữ RECON_APP (chạy bằng tài khoản DBA)
CREATE USER {schema_name} IDENTIFIED BY "{password}"
  DEFAULT TABLESPACE USERS QUOTA UNLIMITED ON USERS;

GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE, CREATE VIEW TO {schema_name};
"""

