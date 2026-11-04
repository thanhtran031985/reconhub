from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import recon_excel_load, recon_excel_row, recon_file, recon_template_version
from app.engine.control_total import check_control_total
from app.engine.filters import apply_row_filters
from app.engine.mapping import resolve_columns
from app.engine.normalize import derive, normalize
from app.engine.reader import read_sheet
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import TemplateConfig
from app.services import service


def _serialize_row_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Chuyển đổi các kiểu dữ liệu Decimal và datetime sang chuỗi để lưu JsonText."""
    res: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, Decimal):
            res[k] = str(v)
        elif isinstance(v, (datetime, date)):
            res[k] = v.isoformat()
        else:
            res[k] = v
    return res


def _reused_response(existing: Any, file_id: int, template_id: int, template_version: int) -> dict[str, Any]:
    """Trả về thông tin của một bản nạp đang hoạt động, không nạp lại."""
    rows_read = int(existing["ROWS_READ"])
    rows_invalid = int(existing["ROWS_INVALID"])
    ex_ct_file = existing["CONTROL_TOTAL_FILE"]
    ex_ct_calc = existing["CONTROL_TOTAL_CALC"]
    ex_ct_matched = ex_ct_file is not None and ex_ct_file == ex_ct_calc
    return {
        "load_id": int(existing["ID"]),
        "file_id": file_id,
        "sheet_name": str(existing["SHEET_NAME"]),
        "template_id": template_id,
        "template_version": template_version,
        "rows_read": rows_read,
        "rows_valid": rows_read - rows_invalid,
        "rows_invalid": rows_invalid,
        "control_total_file": Decimal(str(ex_ct_file)) if ex_ct_file is not None else None,
        "control_total_calc": Decimal(str(ex_ct_calc)) if ex_ct_calc is not None else None,
        "control_total_matched": ex_ct_matched,
        "is_reused": True,
    }


@service
def load_excel_to_temp(
    ctx: Ctx,
    file_id: int,
    template_id: int,
    template_version: int,
    sheet_name: str | None = None,
) -> dict[str, Any]:
    """Nạp dữ liệu từ file Excel đã upload vào bảng tạm RECON_EXCEL_LOAD và RECON_EXCEL_ROW."""
    require_role(ctx, Role.OPERATOR, Role.TEMPLATE_OWNER, Role.ADMIN)

    engine = get_recon_engine()

    # 1. Kiểm tra xem đã có bản ghi RECON_EXCEL_LOAD đang hoạt động chưa
    with engine.connect() as conn:
        stmt = select(recon_excel_load).where(
            recon_excel_load.c.FILE_ID == file_id,
            recon_excel_load.c.TEMPLATE_ID == template_id,
            recon_excel_load.c.TEMPLATE_VERSION == template_version,
            recon_excel_load.c.PURGED_AT.is_(None),
        )
        if sheet_name:
            stmt = stmt.where(recon_excel_load.c.SHEET_NAME == sheet_name)
        existing = conn.execute(stmt).mappings().first()

    if existing:
        return _reused_response(existing, file_id, template_id, template_version)

    # 2. Đọc thông tin file và cấu hình template
    with engine.connect() as conn:
        f_rec = conn.execute(select(recon_file).where(recon_file.c.ID == file_id)).mappings().first()
        if not f_rec:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy file với id {file_id}.")
        if f_rec["PURGED_AT"] is not None or not f_rec["STORAGE_PATH"]:
            raise ServiceError(ErrorCode.TEMP_DATA_PURGED, "File Excel đã bị xóa theo yêu cầu.")

        storage_path = Path(str(f_rec["STORAGE_PATH"]))
        if not storage_path.exists():
            raise ServiceError(ErrorCode.TEMP_DATA_PURGED, "File vật lý không còn tồn tại trên ổ cứng.")

        tv_rec = (
            conn.execute(
                select(recon_template_version).where(
                    recon_template_version.c.TEMPLATE_ID == template_id,
                    recon_template_version.c.VERSION == template_version,
                )
            )
            .mappings()
            .first()
        )
        if not tv_rec:
            raise ServiceError(
                ErrorCode.NOT_FOUND,
                f"Không tìm thấy phiên bản {template_version} của template {template_id}.",
            )

        raw_cfg = tv_rec["CONFIG_JSON"]
        if isinstance(raw_cfg, dict):
            config = TemplateConfig.model_validate(raw_cfg)
        else:
            config = TemplateConfig.model_validate(json.loads(str(raw_cfg)))
    selected_sheet = sheet_name or config.file.sheet

    # 1b. Bản nạp đã bị xóa dữ liệu tạm (PURGED_AT khác None) vẫn chiếm
    # khóa duy nhất (FILE_ID, SHEET_NAME, TEMPLATE_ID, TEMPLATE_VERSION)
    # vì unique constraint không trừ PURGED_AT. Nạp lại mà INSERT mới sẽ
    # lỗi UNIQUE constraint, nên ghi lại ngay trên bản nạp cũ đó.
    purged_load_id: int | None = None
    with engine.connect() as conn:
        purged = (
            conn.execute(
                select(recon_excel_load).where(
                    recon_excel_load.c.FILE_ID == file_id,
                    recon_excel_load.c.SHEET_NAME == selected_sheet,
                    recon_excel_load.c.TEMPLATE_ID == template_id,
                    recon_excel_load.c.TEMPLATE_VERSION == template_version,
                    recon_excel_load.c.PURGED_AT.is_not(None),
                )
            )
            .mappings()
            .first()
        )
        if purged:
            purged_load_id = int(purged["ID"])

    # 3. Thực thi Pipeline đọc và chuẩn hóa dữ liệu
    raw_df, _ = read_sheet(storage_path, config.file)
    filtered_df = apply_row_filters(raw_df, config.file.row_filters)
    mapped_df, _ = resolve_columns(filtered_df, config.fields)
    valid_df, invalid_df = normalize(
        mapped_df,
        config.fields,
        thousand_sep=config.file.thousand_sep,
        decimal_sep=config.file.decimal_sep,
    )

    if config.derived:
        valid_df = derive(valid_df, config.derived)

    ct_file: Decimal | None = None
    ct_calc: Decimal | None = None
    ct_matched: bool = True

    if config.control_total:
        ct_res = check_control_total(
            raw_df=raw_df,
            valid_df=valid_df,
            spec=config.control_total,
            fields=config.fields,
            thousand_sep=config.file.thousand_sep,
            decimal_sep=config.file.decimal_sep,
        )
        ct_file = ct_res.file_total
        ct_calc = ct_res.calc_total
        ct_matched = ct_res.is_matched

    # 4. Ghi nhận vào DB trong cùng transaction
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bytes_est = len(raw_df) * 200

    # Chuẩn bị dữ liệu ghi lô 5.000 dòng (dùng chung cho cả INSERT mới
    # và ghi lại trên bản nạp đã bị purge).
    row_records: list[dict[str, Any]] = []

    def _build_row_records(load_id_value: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for r in valid_df.to_dicts():
            r_copy = dict(r)
            row_no = r_copy.pop("__row_no", 0)
            records.append(
                {
                    "LOAD_ID": load_id_value,
                    "EXCEL_ROW_NO": int(row_no),
                    "DATA_JSON": _serialize_row_dict(r_copy),
                    "IS_VALID": "Y",
                }
            )
        for inv in invalid_df.to_dicts():
            row_no = inv.get("__row_no", 0)
            data_json = {
                "raw_data": _serialize_row_dict(inv.get("__raw_data") or {}),
                "reasons": inv.get("__invalid_reasons") or {},
            }
            records.append(
                {
                    "LOAD_ID": load_id_value,
                    "EXCEL_ROW_NO": int(row_no),
                    "DATA_JSON": data_json,
                    "IS_VALID": "N",
                }
            )
        return records

    if purged_load_id is not None:
        # Ghi lại trên bản nạp cũ: xóa dòng cũ (lẽ ra đã bị xóa khi
        # purge, nhưng xóa lại cho chắc), cập nhật lại số liệu và mở
        # lại PURGED_AT. Không xóa bản nạp vì các run cũ vẫn FK tới nó.
        load_id = purged_load_id
        with engine.begin() as conn:
            conn.execute(delete(recon_excel_row).where(recon_excel_row.c.LOAD_ID == load_id))
            conn.execute(
                update(recon_excel_load)
                .where(recon_excel_load.c.ID == load_id)
                .values(
                    ROWS_READ=len(raw_df),
                    ROWS_INVALID=len(invalid_df),
                    BYTES_EST=bytes_est,
                    CONTROL_TOTAL_FILE=ct_file,
                    CONTROL_TOTAL_CALC=ct_calc,
                    LOADED_AT=now,
                    PURGED_AT=None,
                )
            )
            row_records = _build_row_records(load_id)
            chunk_size = 5000
            for i in range(0, len(row_records), chunk_size):
                conn.execute(recon_excel_row.insert(), row_records[i : i + chunk_size])
    else:
        try:
            with engine.begin() as conn:
                stmt_load = (
                    recon_excel_load.insert()
                    .values(
                        FILE_ID=file_id,
                        SHEET_NAME=selected_sheet,
                        TEMPLATE_ID=template_id,
                        TEMPLATE_VERSION=template_version,
                        ROWS_READ=len(raw_df),
                        ROWS_INVALID=len(invalid_df),
                        BYTES_EST=bytes_est,
                        CONTROL_TOTAL_FILE=ct_file,
                        CONTROL_TOTAL_CALC=ct_calc,
                        LOADED_AT=now,
                        PURGED_AT=None,
                    )
                    .returning(recon_excel_load.c.ID)
                )
                load_id = conn.scalar(stmt_load)
                row_records = _build_row_records(int(load_id) if load_id else 0)
                chunk_size = 5000
                for i in range(0, len(row_records), chunk_size):
                    conn.execute(recon_excel_row.insert(), row_records[i : i + chunk_size])
        except IntegrityError:
            # Đua với một lần nạp khác: bước kiểm tra ở đầu hàm chưa
            # thấy bản nạp, nhưng trong lúc đọc/chuẩn hóa Excel (vài
            # giây với file lớn) bên kia đã nạp xong và commit. Lúc
            # này bản nạp của bên kia đã đầy đủ dòng, dùng lại nó
            # thay vì báo lỗi UNIQUE constraint ra UI.
            with engine.connect() as conn:
                raced = (
                    conn.execute(
                        select(recon_excel_load).where(
                            recon_excel_load.c.FILE_ID == file_id,
                            recon_excel_load.c.SHEET_NAME == selected_sheet,
                            recon_excel_load.c.TEMPLATE_ID == template_id,
                            recon_excel_load.c.TEMPLATE_VERSION == template_version,
                            recon_excel_load.c.PURGED_AT.is_(None),
                        )
                    )
                    .mappings()
                    .first()
                )
            if raced:
                return _reused_response(raced, file_id, template_id, template_version)
            raise

    return {
        "load_id": int(load_id) if load_id else 0,
        "file_id": file_id,
        "sheet_name": selected_sheet,
        "template_id": template_id,
        "template_version": template_version,
        "rows_read": len(raw_df),
        "rows_valid": len(valid_df),
        "rows_invalid": len(invalid_df),
        "control_total_file": ct_file,
        "control_total_calc": ct_calc,
        "control_total_matched": ct_matched,
        "is_reused": False,
    }
