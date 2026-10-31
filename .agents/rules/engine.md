---
trigger: glob
globs: app/engine/**, tests/golden/**, tests/unit/engine/**
description: Quy tắc engine đối soát (hàm thuần, Polars, Decimal, SQL nguồn).
---

# Engine

- Hàm thuần: nhận DataFrame + cấu hình Pydantic, trả DataFrame + cảnh báo. Không gọi DB (trừ `fetch.py`/`catalog.py` nhận connection từ ngoài), không đọc biến môi trường, không log giá trị dữ liệu.
- Đọc Excel bằng Polars + calamine, mọi cột String. Không để thư viện tự đoán kiểu.
- Tiền, số lượng: `pl.Decimal(38,4)`, làm tròn ROUND_HALF_UP theo `round` của measure rồi mới so.
- Thứ tự ưu tiên trạng thái: Không hợp lệ > Trùng khóa > Không nhất quán > Thiếu trong DB / Thiếu trong Excel > Lệch giá trị > Khớp.
- SQL nguồn: định danh lấy từ whitelist `catalog.list_columns` và quote; giá trị luôn là bind. SQL tự viết qua `sql_guard.check_sql`.
- Golden test không cần Oracle: phía DB dùng `db.parquet` qua fetcher giả. Cập nhật expected bằng `uv run poe golden-update CASE=…`, giải thích trong decisions.md.
