# Task 47 — decisions

- D1: Nút footer to lên = size sm / cao 36px / chữ 13px / padding 0 18px / icon 16; footer 20px → 48px. Lý do: 36px là chuẩn app (nút Xem task 42); footer 20px không chứa nổi nút 36px.
- D2: "Column cách nhau 8px" = padding ngang 4px mỗi ô (4+4=8px giữa nội dung 2 cột kề nhau), thống nhất body theo header (đã 6px 4px). Không dùng `horizontalSpacing` của Mantine Table (8px padding mỗi bên sẽ thành 16px).
- D3: STT canh giữa bằng `textAlign: center` trên Td; KHÔNG dùng `hideControls` (giữ nút tăng/giảm — bài học task 37/38).
- D4: Indicator chuyển dòng bằng Output pattern-ALL `style` trên chính `handle_p_select_click`, không re-render bảng (bảo toàn nhãn đang gõ dở — nhãn chỉ lưu ở Lưu nháp, task 38). Helper `_param_row_style(is_selected)` dùng chung render + callback.
- D5: Canvas cân đối = `repeat(12, minmax(0, 1fr))` + box `minWidth: 0` + nhóm Hàng/Cột wrap được. Không thu nhỏ NumberInput 46px (vẫn dùng được), card hẹp xếp Hàng trên Cột dưới.
- D6: Test cũ `test_wizard_footer_compact` (assert 20px/18px) phải cập nhật theo yêu cầu mới — kích thước cũ là yêu cầu cũ, không phải regression.
