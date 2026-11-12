# Task 70 — Plan: cỡ trang dạng badge, chế độ xuất dạng switch

## Hiện trạng (đã đọc code)

- `app/ui/pages/report_viewer.py`: header kết quả có 2 Select:
  - `viewer-page-size` (Select, data 50/100/200 "dòng/trang", value "50")
    — đọc qua `State("viewer-page-size", "value")` (dòng 536) và
    `Input("viewer-page-size", "value")` (dòng 601, 622).
  - `viewer-export-mode` (Select, "Xuất ngay"/"now" và "Chạy ngầm"/
    "background", value "now") — đọc qua `State("viewer-export-mode",
    "value")` (dòng 763) trong `handle_export_click`, tham số `mode`.

## Các bước

1. **Cỡ trang → badge**: `dmc.Select` → `dmc.SegmentedControl`
   (dạng pill/badge bấm chọn), giữ nguyên id `viewer-page-size`,
   giữ nguyên 3 value chuỗi "50"/"100"/"200" và nhãn "50 dòng/trang" /
   "100 dòng/trang" / "200 dòng/trang", value mặc định "50".
   SegmentedControl cũng expose prop `value` nên 3 callback đọc
   `viewer-page-size` KHÔNG cần đổi.
2. **Chế độ xuất → switch**: `dmc.Select` → `dmc.Switch` label
   "Chạy ngầm", `checked=False` mặc định (= Xuất ngay), giữ nguyên id
   `viewer-export-mode`. Callback xuất đổi State từ
   `"viewer-export-mode", "value"` sang `"viewer-export-mode",
   "checked"` và map `checked → "background"`, không checked → `"now"`.
   Logic xuất ngay/ngầm trong `handle_export_click` giữ nguyên.
3. **Tests**: test unit cho mapping switch (checked → background,
   không checked → now) + test callback đổi cỡ trang vẫn về trang 1
   qua SegmentedControl; chạy các test viewer liên quan cho xanh.
4. **Check live** `~/workspace/check-70-viewer-badge-switch.py`
   (port 8120, DB/storage riêng `/run/pytest-tmp/check70.*`): mở
   /reports/<id> — thấy 3 badge cỡ trang, bấm 100 thì lưới đổi cỡ
   trang; switch mặc định tắt (Xuất ngay), bật lên rồi bấm Xuất Excel
   thì chạy ngầm (run QUEUED + thông báo/link Lịch sử, không tải ngay);
   quét CẢ console error VÀ pageerror.
5. **Parent**: review diff → chạy lại targeted tests → chạy lại check
   live → typecheck + ruff → full suite CHUNG với task 69 (chỉ chạy 1
   lần, sau khi cả 2 task xong — KHÔNG chạy 2 bộ pytest cùng lúc) →
   commit 1 commit `70-viewer-badge-pagesize-switch: ...` (trên commit
   task 69) → export patch `~/workspace/reconhub-task70.patch` → verify
   `git am` sạch trên worktree ở commit task 69 → cập nhật MEMORY.md →
   giao patch (áp sau patch 69, KHÔNG cần db-migrate, chỉ khởi động lại
   app).

## Quyết định

- D1: cỡ trang dùng `dmc.SegmentedControl` (pill/badge) thay vì Badge
  bấm tay — giữ prop `value` nên không đổi callback.
- D2: switch xuất dùng label "Chạy ngầm", tắt = Xuất ngay (mặc định như
  cũ), bật = Chạy ngầm (mẫu switch task 67).
- D3: giữ nguyên id 2 control (`viewer-page-size`, `viewer-export-mode`)
  để không vỡ test/callback khác.
