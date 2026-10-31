---
name: lam-task
description: Làm một task trong docs/tasks theo quy trình từng bước (plan, test trước, kiểm tra, cập nhật progress, dừng chờ duyệt). Dùng khi người dùng nói "làm task NN", "tiếp tục task", "continue" hoặc gọi /lam-task.
---

# Làm một task

Đầu vào: `NN-slug` (nếu chỉ nói "tiếp tục", lấy task đang 🔄 trong `docs/tasks/README.md`).

## Đọc
1. `docs/tasks/README.md` → `docs/tasks/NN-slug/task.md` → `progress.md` → `decisions.md`.
2. Chỉ các spec và thiết kế mà task.md liệt kê. Task có giao diện: đọc trang DMC của component sẽ dùng.
3. Bước đã ✅ không làm lại.

## Lập kế hoạch (khi chưa có plan.md)
Implementation Plan: mỗi bước ghi file tạo/sửa, test viết trước, lệnh kiểm tra, rủi ro; chỗ tự suy ra; câu hỏi; package cần cài thêm (phải hỏi). DỪNG chờ duyệt.

## Bắt đầu (sau khi duyệt)
- Chép nguyên văn kế hoạch vào `plan.md`; `git checkout -b feat/NN-slug`; đổi trạng thái 🔄 trong README và progress.

## Mỗi bước
1. Viết test hành vi trước, chạy thấy đỏ.
2. Code cho xanh, chỉ trong phạm vi bước.
3. Chạy đúng lệnh ở "Kiểm tra". Test Oracle bị skip vì thiếu biến môi trường: ghi rõ trong báo cáo và nhờ người dùng chạy `uv run poe test-oracle` khi có VPN.
4. Cập nhật `progress.md` (dòng của bước + nhật ký: đã làm, lệnh + kết quả, suy ra gì, việc người dùng làm tay).
5. Chạy `uv run poe tasks-dashboard`.
6. Báo cáo ngắn + đề xuất commit `NN-slug: step N — <mô tả>`; bước có giao diện đính ảnh chụp.
7. **DỪNG** chờ "continue". Chỉ commit khi được đồng ý.

## Khi có vấn đề
- Khác task.md/spec/thiết kế: ghi `decisions.md` (ngày, quyết định, lý do, ảnh hưởng spec).
- Mơ hồ hoặc mâu thuẫn: DỪNG và hỏi.

## Kết thúc task
Chạy skill `dong-task`.
