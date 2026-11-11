# Quyết định — Task 64

## D1 — Running item suy ra từ dòng chờ đầu tiên, không thêm trạng thái "running"
Theo plan. `running_item(step)` trả dòng chờ đầu tiên của bước; người gọi
chỉ dùng cho bước đang chạy. Lý do: bảng chép theo đúng thứ tự nên dòng chờ
đầu tiên chính là item đang làm; không đổi data model, không thêm cột.

## D2 — Báo cáo đối chiếu + next steps nằm trong detail của bước 6 khi xong
Theo plan. Không thêm vùng thứ 3 dưới 2 card. `_render_mig_detail` gọi
`_render_mig_report` khi `idx == 5` và `overall_status == "done"`.

## D3 — Store `ds-mig-state` thay `ds-mig-fake-store`
Task 63 có 2 store giữ state checklist theo mode (fake-store cho fake,
last-checklist-store raw JSON cho real). Task 64 cần một nơi duy nhất để
callback bấm bước đọc state hiện tại để vẽ detail — nếu đọc 2 store cũ sẽ
gặp trạng thái cũ khi đổi mode trong cùng phiên modal (fake xong rồi chạy
thật, hoặc mở lại modal khi có phiên PROCESSING). Vì vậy thêm store
`ds-mig-state` làm nguồn sự thật duy nhất cho việc vẽ; mọi callback đổi
state (mở modal, bắt đầu, tick fake, poll real) đều ghi nó. `ds-mig-fake-store`
bị xóa khỏi layout; `ds-mig-last-checklist-store` giữ lại chỉ để real tick
so sánh raw JSON tránh vẽ lại khi checklist không đổi.

## D4 — Bước chọn giữ nguyên lựa chọn của user (sticky)
Tick/poll KHÔNG đổi bước chọn theo bước đang chạy (tránh giật detail khỏi
tay user lúc họ đang xem bước khác). Chỉ đổi bước chọn ở 3 thời điểm: mở
modal (về bước đang chạy), bấm "Bắt đầu" (về bước đang chạy), chạy xong
(về bước 6 Hoàn tất để thấy báo cáo) / lỗi (về bước lỗi để thấy lỗi).

## D5 — Alert (lỗi/từ chối/cảnh báo) hiện trong card detail
`ds-mig-modal-result` bị xóa theo layout 2 card. `_render_mig_detail` nhận
thêm tham số `alert` tùy chọn, vẽ alert_box ở đầu card detail. Các callback
trước đây trả alert vào modal-result nay truyền qua `alert` (precheck lỗi,
không phải ADMIN, chưa chọn đích, phiên đang chạy, thread chết, timeout
30s, FAILED với ERROR_MSG).

## D6 — `running_step_index` bỏ qua bước chưa có dòng con
`step_status` trả "pending" cho bước 0 item (theo task 63). Bước đối chiếu
(verify) chưa có item trước khi biết top-3 bảng sẽ bị coi là "bước chờ đầu
tiên" dù không có việc gì để làm — sai bước chọn mặc định trong state
tổng hợp (vd test all-done với top_tables=[]). Fix: `running_step_index`
bỏ qua bước 0 item khi tìm bước chờ. Không đổi `step_status` (giữ ngữ
nghĩa task 63).

## D7 — Modal size 1100px + cao 88vh
Mockup đã duyệt rộng ~1020px; `size="xl"` của Mantine (~780px) quá hẹp
cho 2 card (stepper 330px + detail). Dùng `size="1100px"` và
`styles` content/body để modal cao 88vh dạng flex cột. Dùng px ở đây theo
đúng mockup đã duyệt, nhất quán với px đã có sẵn trong file này (vòng
tròn 28px, ScrollArea h=380 cũ).
