# samples/

| File | Nội dung |
|---|---|
| dtp_sample_200.xlsx | Dữ liệu **tổng hợp** theo đúng cấu trúc sheet "BÁO CÁO DTP" (19 cột, dòng tổng "Tổng tiền" ở cuối): 200 dòng, 190 hóa đơn (10 hóa đơn có 2 dòng), ngày 01–05/02/2026, Số lượng 220, Thành tiền 366.732.000. Tên khách hàng và người lập là giả. Dùng cho golden test, seed, e2e. |
| templates/DTP_HOA_DON_TAC_NGHIEP.json | Cấu hình template mẫu (spec 03), nguồn kind=table trên RECON_SRC.SRC_FACT_INVOICE_DTP. |
| private/ | Đặt file thật ở đây (không commit). Golden G05 dùng `private/dtp_full.xlsx` nếu có để kiểm control total 24.114.547.250 trên 12.445 dòng. |

Dữ liệu nguồn test tương ứng trên Oracle: `scripts/oracle/02_seed_src_test.sql` (cùng sample, có 3 HĐ lệch tiền, 1 HĐ lệch ngày, 2 HĐ thiếu trong DB, 2 HĐ thiếu trong Excel → golden G01).
