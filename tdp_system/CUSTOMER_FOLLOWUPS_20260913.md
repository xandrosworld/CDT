# Công nợ, giá bảng kê bổ sung và ghi chú NCC

- Công nợ phải thu: thay nhà thầu, bếp hoặc trạng thái là cập nhật bảng và đường dẫn tải ngay. Phản hồi chậm của bộ lọc cũ không thay thế bộ lọc mới. Nút Lọc danh sách vẫn dùng để tải lại.
- Công nợ phải trả: chọn NCC/trạng thái tự cập nhật. Cả hai sổ có bảng xem trực tiếp và nút **Xem toàn màn hình**; tải Excel là lựa chọn riêng.
- Bảng kê bổ sung từ tồn âm: gợi ý đơn giá bằng 95% giá bán, làm tròn đến đồng. Ưu tiên dòng giao hàng đã duyệt gần nhất đến ngày đối chiếu, cùng mã và ĐVT. Nếu không có, dùng hóa đơn bán đã ký, đã ghi kho, ghép mã hợp lệ và cùng ĐVT với hệ số 1. Hiện ngày và nguồn giá dưới ô; người dùng được sửa giá. Không có nguồn phù hợp thì để trống kèm lý do. Không lấy giá của ngày sau, đơn nháp, hàng trả hết hoặc tự quy đổi túi/kg/lít.
- Đặt NCC: nút **Ghi chú NCC** mở từng dòng nguồn để nhập lời dặn. Lưu riêng với chứng từ mua/bán, không sửa số lượng, giá, kho hay công nợ. Đơn NCC đã gửi có ghi chú thay đổi sẽ mở lại. Lưu từ tab cũ bị từ chối nếu nguồn đã thay đổi. File mới có ghi chú nguồn khác được ưu tiên để không mang lời dặn cũ sang dòng mới.
- Ảnh NCC luôn có cột Ghi chú, kể cả trống. Nội dung đã lưu được đưa vào cả ảnh và Excel đơn NCC.

## Kiểm tra

`qa_customer_followups.cjs` chạy với bản sao dữ liệu khách tại `http://127.0.0.1:5094`, hoặc với `https://tdp.up.railway.app`.
Đặt `TDP_PLAYWRIGHT_MODULE` tới module Playwright. Đăng nhập Railway dùng file riêng `D:/TDP_RAILWAY_PRIVATE/access.json`.
Trên bản sao, script thử phản hồi đến muộn, lưu/sửa/khôi phục ghi chú và sửa giá thủ công. Trên Railway chỉ đọc, tải file, xem bản in và lưu lại ghi chú hiện có với kết quả `changed=0`; không ghi lời dặn thử hoặc nhập kho giả vào dữ liệu khách.

Kiểm thử Python liên quan: `test_bk_draft`, `test_bk_import`, `test_supplier_notes`, `test_supplier_plan_source`, `test_supplier_order_checklist`, `test_daily_workbook_import`, `test_date_range_workflows`, `test_receivable_ledger`, `test_receivable_export`, `test_receivable_ui`, `test_payable_ledger`, `test_payable_payments`, `test_payable_export`, `test_purchase_order_roundtrip`, `test_purchase_sales_boundary`, `test_customer_purchase_layout`, `test_round3_documents`, `test_round4_documents`, `test_print_layout_regressions`. Ảnh và file đối chiếu được lưu riêng trong `exports`.
