# Quyết định kiến trúc — TASK UI-02: Reports & Analytics

## 1. Giữ nguyên Dash component callbacks cho các bảng có inline action/link
- Trong `/` Dashboard, bảng 10 run gần nhất chứa `dcc.Link` và badge trạng thái; bảng tỷ lệ lệch chứa progress bar.
- Trong `/runs/<id>`, bảng kết quả chứa các action mở drawer và các callback tương tác.
- Giữ nguyên cấu trúc `dmc.Table` với sticky header 34px và `dmc.TableScrollContainer` bọc trong `dmc.Paper(style={"flex": 1, "minHeight": 0, "overflow": "hidden"})` để triệt tiêu toàn bộ page scroll, đảm bảo 100% callback tương thích mà không gây lỗi serialize dữ liệu.
