# Sáu mục cuối trong note khách

Phạm vi đã thống nhất ngày 13/09/2026: 7, 9, 11, 12, 13, 15.

| Mục | Cách sử dụng sau thay đổi |
| --- | --- |
| 7 | Công nợ → Phải thu: tổng nhà thầu và phát sinh từng bếp chung một màn. |
| 9 | Hai nút Phải thu / Phải trả thay danh mục và tiêu đề lặp; lọc bằng khoảng ngày ngay trong công nợ. |
| 11 | Đối chiếu số thực tế từ đơn đã duyệt, đầu kỳ, điều chỉnh và tiền đã thu; tải Excel đối chiếu theo kỳ. |
| 12 | Bỏ bốn ô thống kê thừa; chi tiết mặt hàng và lịch sử sửa chỉ mở khi cần. Giữ các nút tải trong chế độ toàn màn hình. |
| 13 | Bảng kê & hóa đơn giữ bảng đưa lên M-Invoice, phần chưa xuất và ZIP. Đề nghị thanh toán nằm trong Công nợ; quản lý dự thảo nằm trong Hóa đơn đầu vào + đầu ra. |
| 15 | Bỏ tab In giấy tờ. In giao hàng / bảng kê / biên nhận từ Đơn hàng - bảng kê, in đơn NCC tại từng ngày đặt hàng, in báo cáo tại Báo cáo tổng hợp. |

Mục 11 thực hiện đúng note gốc: đối chiếu và chốt số thực tế. Không có yêu cầu khóa/mở kỳ; không bổ sung cơ chế đó.

Khoản thu thuộc tài khoản nhà thầu. Lọc một bếp chỉ thu hẹp phát sinh và chi tiết bếp, không phân bổ lại khoản đã thu cho từng bếp. Bảng tổng luôn gồm các dòng hiệu lực của mọi bếp của nhà thầu. Không hiển thị số 0 thay cho số liệu chưa tải xong.

Một đơn nguồn có thể nằm trong dự thảo gộp của ngày sau. Nút ZIP phải trỏ tới ngày sở hữu dự thảo, đồng thời ghi rõ ngày trên nút. Mỗi ZIP chứa các dự thảo chưa phát hành của ngày đó; không tạo thêm dự thảo khi tải.

## Kiểm tra lại

Các script trình duyệt dùng snapshot khách tháng 09/2026: ATV, LSVINA, đơn nguồn 04/09 (batch 2), đơn NCC 13/09 (batch 9). Chỉ dùng bản sao riêng tại `http://127.0.0.1:5094` cho các ca thu tiền / hoàn tác và thử tạo file hóa đơn. Đặt connector của bản sao ở chế độ offline.

- `qa_final_workspaces.cjs`: cả sáu màn hình, Excel/ZIP, thu và hoàn tác trên bản sao, đề nghị thanh toán từ hóa đơn đã phát hành, biên nhận.
- `qa_final_workspaces_edges.cjs`: chỉ chạy bản sao; đối chiếu mọi nhà thầu, tổng các bếp, lịch sử sửa, hồ sơ người mua, phản hồi chậm khi đổi bộ lọc/chuyển màn, ZIP dự thảo gộp.
- `qa_final_workspaces_printing.cjs`: in NCC đúng ngày và in báo cáo đúng khoảng ngày.

Hai script đầu/cuối có tham số URL: mặc định bản sao; `https://tdp.up.railway.app` chạy kiểm tra và tải chứng từ có thật, không tạo khoản thu hay hóa đơn thử. Script `edges` cố định localhost.

Cài Playwright hoặc đặt `TDP_PLAYWRIGHT_MODULE` tới module đã cài; cần Microsoft Edge. `TDP_QA_PRIVATE_ROOT` trỏ thư mục riêng chứa `access.json` gồm username/password khi chạy Railway. Không đưa thông tin đăng nhập hoặc snapshot vào Git. Kết quả và ảnh ghi vào thư mục riêng đó.

Kiểm thử Python dùng `python -m tdp_system.qa_railway_acceptance --module TEN_MODULE --output THU_MUC_RIENG`. Các module liên quan: receivable_ledger, receivable_export, receivable_ui, round3_documents, invoice_payment_scope, invoice_payment_documents, outgoing_unissued, outgoing_waiting, outgoing_readiness, print_layout_regressions, receipt_print_sheets, date_range_workflows, round4_documents (đều có tiền tố `test_`).

Minh chứng Railway được đóng gói riêng sau khi xác nhận deployment và so sánh dữ liệu nghiệp vụ trước/sau.
