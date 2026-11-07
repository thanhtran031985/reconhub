# ReconHub — Prompt phong cách thiết kế cho AI

Cách dùng: ghép **Phần A (luật chung)** với **đúng 1 prompt ở Phần B**, rồi đặt vào `DESIGN_SYSTEM.md` hoặc `CLAUDE.md` / `AGENTS.md`. Mỗi task UI chỉ cần nhắc lại: *"Tuân thủ DESIGN_SYSTEM.md, không tự tạo style mới."*

---

## Phần A — Luật chung (dùng cho mọi phong cách)

```text
Bạn đang làm UI cho ReconHub, một ứng dụng nội bộ để đối soát dữ liệu và xem báo cáo (Oracle, Excel).
Mục tiêu: màn hình sạch, rõ ràng, mật độ thông tin cao, KHÔNG phải cuộn cả trang.

PHẠM VI
- Chỉ sửa giao diện (layout, CSS, markup trình bày). Không đổi logic, luồng, tên field, API, validate.
- Không thêm chức năng, màn hình hoặc nội dung ngoài task.
- Mọi màn hình mới phải dùng lại token và component đã có. Không tự đặt màu, cỡ chữ hay khoảng cách mới.

KHUNG MÀN HÌNH (desktop ≥ 1280px)
- html/body cao 100%, không cuộn trang. Chỉ grid, danh sách, panel cuộn bên trong khung của nó.
- Khung: Sidebar | (Topbar 44px + Content flex:1).
- Mỗi màn gồm 3 vùng: [Header trang 1 dòng] [Command bar / bộ lọc] [Vùng chính flex:1, min-height:0].
- Không dùng khối hero lớn. Tiêu đề và mô tả nằm chung một dòng.
- Nút hành động của wizard/form gắn ở chân panel (footer cố định), không nổi đè lên nội dung.
- Kiểm tra bắt buộc ở 1366×768: document.scrollHeight == innerHeight và không có cuộn ngang.
- Dưới 900px: cho phép cuộn trang, sidebar thành menu trượt, panel chia đôi chuyển thành xếp dọc.

MẬT ĐỘ (giới hạn tối đa)
- Chữ cơ bản 13px; nhãn và header bảng 12px; tiêu đề trang 18px; tiêu đề section 15px.
- Input, select, button: cao 30px; trong grid: 26px.
- Dòng bảng 32–34px; dòng danh sách 40px.
- Padding panel 12–16px; khoảng cách giữa các khối 8px.
- Không dùng card lớn cho danh sách. Danh sách dùng table/list.

COMPONENT CHUẨN (bắt buộc dùng lại)
- Button: primary | default | subtle | danger | icon (26px).
- Field: label 12px phía trên, input 30px, hint 11–12px phía dưới.
- Data grid: header sticky, số căn phải, tabular-nums, hover dòng, dòng chọn có vạch trái 3px.
- Tag/badge: bo 4px, chữ 11px. Màu chỉ dùng cho trạng thái: ok, warn, error, info.
- Stepper wizard: 1 hàng 34px. Bước đã xong có dấu ✓.
- Dialog: chỉ dùng cho xác nhận hoặc thông báo ngắn. Không dùng dialog làm form dài.
- Empty state, loading (skeleton), lỗi: mỗi vùng dữ liệu phải có đủ 3 trạng thái này.

TƯƠNG TÁC VÀ TRUY CẬP
- Focus-visible rõ ràng cho mọi control. Mỗi input có label hoặc aria-label.
- Chuyển động ≤ 150ms, chỉ dùng cho hover/press/mở dialog. Tôn trọng prefers-reduced-motion.
- Có theme sáng/tối bằng biến CSS. Không hardcode màu trong component.
- Thông báo động (kết quả, lỗi) dùng aria-live="polite".

NGHIỆM THU MỖI TASK UI
1. Chụp màn hình ở 1366×768, 1920×1080 và 390px; xem ảnh trước khi báo xong.
2. Chạy lại luồng chính của màn hình, không có lỗi console.
3. Liệt kê ngắn những gì đã đổi. Không đổi gì ngoài phạm vi.
```

---

## Phần B — Prompt theo từng phong cách (chọn 1)

### B1. Fluent Compact + Master–Detail (khuyến nghị — giống bản `preview-fluent.html`)

```text
PHONG CÁCH: Fluent Compact (giống Azure Portal / Microsoft 365 admin), kết hợp Master–Detail cho màn cấu hình.

TOKEN
- Light: bg #f5f5f5, panel #ffffff, panel-2 #fafafa, text #242424, muted #616161, line #e0e0e0,
  accent #0f6cbd, accent-soft #ebf3fc, ok #107c10, warn #bc4b09, error #c50f1f.
- Dark: bg #1f1f1f, panel #292929, text #f0f0f0, muted #adadad, line #3d3d3d, accent #479ef5.
- Font "Segoe UI"; mono Consolas. Bo góc: control 4px, panel 6px. Bóng: 0 1px 2px rgba(0,0,0,.12).
- Input kiểu Fluent: viền 1px, viền dưới đậm hơn; khi focus viền dưới 2px màu accent.

BỐ CỤC
- Sidebar 200px nền trắng, mục 32px, mục đang chọn có nền accent-soft và vạch trái 3px; có nút thu gọn về 48px (chỉ icon + tooltip).
- Topbar 44px: breadcrumb bên trái; theme, môi trường, user bên phải.
- Command bar phía trên grid: ô tìm kiếm, bộ lọc, nút Thêm / Xóa / Xuất.
- Màn danh sách: table full chiều cao còn lại, nhóm bằng dòng group header 28px.
- Màn cấu hình (tham số, LOV, cột, menu, phân quyền, template): MASTER–DETAIL.
  Trái = grid/danh sách (flex:1). Phải = panel chi tiết 320px, nền panel-2, viền trái, cuộn độc lập.
  Chọn dòng ở trái → chi tiết hiện ngay bên phải. Không mở dialog.
- Màn xem báo cáo: bộ lọc 1 hàng (auto-fill minmax 170px) + nút chạy; bảng kết quả chiếm phần còn lại.

KHÔNG LÀM: gradient, card nổi lớn, bo góc > 8px, icon màu sắc, chữ > 18px trong nội dung.
```

### B2. Linear Minimal

```text
PHONG CÁCH: Linear Minimal — gần như đơn sắc, đường kẻ mảnh, không dùng card.

TOKEN
- Light: bg #fbfbfb, panel #ffffff, text #1c1d1f, muted #6b6f76, line #ececed, line-strong #dcdcde,
  accent #5e6ad2 (CHỈ cho nút primary, focus, mục đang chọn).
- Dark: bg #0f1011, panel #151617, text #e6e6e7, muted #8a8f98, line #232427.
- Trạng thái: ok #26a269, warn #d9822b, error #e5484d, chỉ dùng dạng chấm 6px + chữ, không tô nền.
- Font Inter / "Segoe UI", 13px, weight 400/500 (không dùng 700). Bo góc 6px. Không đổ bóng.

BỐ CỤC
- Sidebar 220px cùng màu nền trang, không viền đậm; mục 28px, mục chọn nền line nhạt.
- Các vùng tách bằng đường kẻ 1px, KHÔNG dùng card/khung bao.
- Header trang: tiêu đề 15px weight 500 + đếm số lượng màu muted.
- Bảng không có viền dọc, dòng 32px, header chữ muted 12px không nền.
- Form cấu hình: 2 cột "nhãn trái 160px | control phải", mỗi dòng 36px, phân nhóm bằng tiêu đề nhỏ 11px muted.
- Nút primary duy nhất trên mỗi màn đặt ở góc phải header. Các nút khác là subtle (không viền).

LƯU Ý: phong cách dễ thiếu điểm nhấn → nút hành động chính luôn dùng accent và luôn ở cùng một vị trí.
KHÔNG LÀM: nền màu cho section, icon to, badge tô đậm, nhiều hơn 1 màu nhấn.
```

### B3. Master–Detail chia đôi (Outlook / Oracle Redwood) — dùng làm phong cách chính

```text
PHONG CÁCH: Master–Detail làm khung cho MỌI chức năng (giống Outlook, Oracle Redwood).

TOKEN
- Light: bg #f4f6f8, panel #ffffff, text #161513, muted #6f6c69, line #e3e1de,
  accent #227e9e, accent-soft #e6f2f6, ok #508223, warn #c74634 (cam đậm), error #b42318.
- Font "Segoe UI"; bo góc 6px; bóng rất nhẹ cho panel.

BỐ CỤC
- Sidebar 200px (thu gọn được) | Danh sách master 300–340px | Detail flex:1.
- Master: ô tìm kiếm + bộ lọc ở đầu; mỗi item 2 dòng (tên đậm 13px + phụ 12px muted), cao 52px; item chọn có nền accent-soft và vạch trái.
- Detail: header (tên + trạng thái + nút hành động) cao 48px, dưới là tab ngang 32px; nội dung tab cuộn độc lập.
- Áp dụng thống nhất:
  - Trung tâm báo cáo: master = danh sách báo cáo; detail = các tab template + bộ lọc + kết quả.
  - Quản trị báo cáo: master = template; detail tab = Thông tin | SQL | Tham số & LOV | Cột | Xem trước.
    (Thay wizard bằng tab; nút Lưu nháp / Kích hoạt ở header detail.)
  - Tham số / Cột / Menu / Phân quyền: bên trong detail lại chia grid trái + panel thuộc tính phải 300px.
- Detail khi chưa chọn gì: empty state nhỏ có hướng dẫn 1 dòng.

KHÔNG LÀM: dialog cho form sửa, mở trang mới để xem chi tiết, cuộn trang ngoài.
```

### B4. Console dạng tab (Excel / công cụ quản trị DB)

```text
PHONG CÁCH: Console — mật độ cao nhất, dành cho admin và người cấu hình thường xuyên.

TOKEN
- Light: bg #f3f3f3, panel #ffffff, text #1e1e1e, muted #6e6e6e, grid-line #d4d4d4,
  accent #0e639c, selection #cce4f7, ok #388a34, warn #bf8803, error #e51400.
- Dark: bg #1e1e1e, panel #252526, text #cccccc, grid-line #3c3c3c, accent #3794ff, selection #094771.
- Font "Segoe UI" 12px cho UI, Consolas 12px cho mã/SQL/field DB. Bo góc 2px. Không bóng.

BỐ CỤC
- Sidebar dạng activity bar 44px (chỉ icon) + explorer 220px (cây chức năng).
- Vùng làm việc có tab ngang 30px như editor (mở nhiều báo cáo/template cùng lúc, có nút đóng tab).
- Wizard → tab: Thông tin | SQL | Tham số | Cột | Xem trước; mỗi tab vừa khít màn hình.
- Grid sát mép, viền ô 1px, dòng 26px, sửa trực tiếp trên ô (inline edit), ô đang sửa viền accent.
- Toolbar icon 28px phía trên grid (có tooltip).
- Status bar 24px ở đáy: số dòng, tổng GRID_SPAN, số lỗi validate, môi trường.
- Panel thuộc tính bên phải 280px, có thể ẩn/hiện.

LƯU Ý: với màn người dùng chỉ xem báo cáo, tăng dòng bảng lên 30px và giữ bộ lọc dạng form thường.
KHÔNG LÀM: card, khoảng trắng lớn, chữ > 14px, animation trang trí.
```

---

## Có cần đưa 3 skill (taste-skill, gstack, emilkowalski/skills) vào prompt không?

**Không cần nhúng toàn bộ.** Nên dùng mỗi skill cho đúng một vai trò:

| Skill | Dùng khi nào | Cách đưa vào |
|---|---|---|
| taste-skill | 1 lần, lúc **chốt phong cách** | Không đưa vào prompt hằng ngày. Những gì nó chỉ dẫn đã được "đóng băng" thành token và luật ở Phần A/B. |
| gstack (design-review) | **Cuối mỗi milestone** để rà soát | Gọi như một bước review riêng: "Chạy design review theo DESIGN_SYSTEM.md, liệt kê lệch chuẩn, chưa sửa." |
| emilkowalski/skills | Khi **đánh bóng tương tác** | Chỉ giữ phần chuyển động ngắn, trạng thái nhấn, focus, reduced-motion (đã có trong Phần A). |

Lý do:
- Prompt cụ thể (màu hex, px, quy tắc bố cục) mới là thứ giữ được sự **đồng nhất**. Skill mang tính định hướng chung, và mỗi skill có "gu" riêng.
- Nạp cả 3 skill cùng lúc dễ làm AI tự sáng tạo thêm hiệu ứng, gradient, card lớn. Đó đúng là những thứ bạn muốn tránh.
- Khi các chỉ dẫn mâu thuẫn nhau, cần ghi rõ thứ tự ưu tiên: **DESIGN_SYSTEM.md > yêu cầu task > skill**.

Dòng nên thêm vào `CLAUDE.md` / `AGENTS.md`:

```text
Ưu tiên khi mâu thuẫn: DESIGN_SYSTEM.md > yêu cầu của task > hướng dẫn trong các skill.
Chỉ dùng skill design-review ở bước nghiệm thu milestone; không dùng skill để đổi phong cách đã chốt.
```
