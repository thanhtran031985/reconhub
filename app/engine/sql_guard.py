from __future__ import annotations

import re

DISALLOWED_KEYWORDS = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "DROP",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "BEGIN",
    "DECLARE",
    "EXECUTE",
    "EXEC",
    "CALL",
    "COMMIT",
    "ROLLBACK",
    "LOCK",
]


def strip_comments_and_literals(sql: str) -> str:
    """Loại bỏ các chú thích (-- và /* */) và chuỗi ký tự nháy đơn khỏi câu lệnh SQL."""
    res: list[str] = []
    i = 0
    n = len(sql)
    in_single_quote = False
    in_line_comment = False
    in_block_comment = False

    while i < n:
        if in_single_quote:
            if sql[i] == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    i += 2
                    continue
                in_single_quote = False
            i += 1
            continue

        if in_line_comment:
            if sql[i] == "\n":
                in_line_comment = False
                res.append("\n")
            i += 1
            continue

        if in_block_comment:
            if sql[i : i + 2] == "*/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        # Trạng thái văn bản SQL thông thường
        if sql[i] == "'":
            in_single_quote = True
            res.append(" 'LITERAL' ")
            i += 1
            continue

        if sql[i : i + 2] == "--":
            in_line_comment = True
            i += 2
            continue

        if sql[i : i + 2] == "/*":
            in_block_comment = True
            i += 2
            continue

        res.append(sql[i])
        i += 1

    return "".join(res)


def check_sql(sql: str, allowed_params: list[str]) -> tuple[bool, str | None]:
    """Kiểm tra độ an toàn của câu lệnh SQL tùy biến (SQL guard).

    Trả về (True, None) nếu hợp lệ, hoặc (False, lý do tiếng Việt) nếu vi phạm.
    """
    if not sql or not sql.strip():
        return False, "Câu lệnh SQL không được để trống."

    cleaned = strip_comments_and_literals(sql).strip()
    if not cleaned:
        return False, "Câu lệnh SQL không được để trống sau khi loại bỏ chú thích."

    # 1. Kiểm tra dấu chấm phẩy
    if ";" in cleaned:
        return False, "Câu lệnh SQL không được chứa dấu chấm phẩy (;)."

    # 2. Kiểm tra từ khóa bắt đầu (SELECT hoặc WITH)
    first_token = cleaned.split()[0].upper()
    if first_token not in ("SELECT", "WITH"):
        return False, "Câu lệnh SQL phải bắt đầu bằng SELECT hoặc WITH."

    # 3. Kiểm tra FOR UPDATE
    if re.search(r"\bFOR\s+UPDATE\b", cleaned, re.IGNORECASE):
        return False, "Không cho phép sử dụng mệnh đề FOR UPDATE."

    # 4. Kiểm tra các từ khóa DML/DDL/DCL/PL-SQL nguy hiểm
    for kw in DISALLOWED_KEYWORDS:
        if re.search(rf"\b{kw}\b", cleaned, re.IGNORECASE):
            return False, f"Không cho phép sử dụng câu lệnh hoặc từ khóa nguy hiểm '{kw}'."

    # 5. Kiểm tra Database link (@)
    if "@" in cleaned:
        return False, "Không cho phép sử dụng liên kết cơ sở dữ liệu (@ - Database Link)."

    # 6. Kiểm tra Package hệ thống DBMS_ và UTL_
    if re.search(r"\bDBMS_[A-Z0-9_]*", cleaned, re.IGNORECASE):
        return False, "Không cho phép gọi các package hệ thống DBMS_."
    if re.search(r"\bUTL_[A-Z0-9_]*", cleaned, re.IGNORECASE):
        return False, "Không cho phép gọi các package hệ thống UTL_."

    # 7. Kiểm tra bind parameters
    # Tìm tất cả :param_name (không nằm trong literal vì literal đã bị loại bỏ)
    binds = set(re.findall(r":([a-zA-Z0-9_]+)", cleaned))
    allowed_set = set(allowed_params)

    unknown = binds - allowed_set
    if unknown:
        unknown_param = sorted(unknown)[0]
        return False, f"Biến bind ':{unknown_param}' không nằm trong danh sách tham số được phép."

    # Bắt buộc phải có :p_from và :p_to
    if "p_from" not in binds:
        return False, "Câu lệnh SQL bắt buộc phải sử dụng tham số lọc thời gian :p_from."
    if "p_to" not in binds:
        return False, "Câu lệnh SQL bắt buộc phải sử dụng tham số lọc thời gian :p_to."

    return True, None
