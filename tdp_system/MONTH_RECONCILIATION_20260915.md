# Đối chiếu tháng 9 và tự bổ sung dữ liệu Đặt hàng

Ô Duyệt đơn – sửa đơn có bộ lọc từ/đến ngày và chọn ngày cần xem trong khoảng. Số doanh thu được ghi rõ chưa VAT; tổng tiền hàng gồm VAT hiển thị riêng. Không hiển thị số của ngày nằm ngoài khoảng đang chọn.

Khi sheet Excel dùng SUBTOTAL và đang lọc, kiểm tra riêng tổng các dòng hiện. Nếu tổng đó đúng, nhập toàn bộ dòng và cảnh báo rõ tổng cả ngày; vẫn chặn dòng tiền sai, tổng lưu cũ và công thức chỉ cộng thiếu phạm vi. File khách ngày 03/09, 10/09 thuộc trường hợp tổng đang lọc.

Kiểm tra cả cột Lợi nhuận từng dòng để phát hiện trường hợp giá mua được lấy dự phòng làm lệch giá vốn dù doanh thu vẫn khớp. Dung sai tối đa 1đ mỗi dòng cho phần lẻ VND của công thức Excel.

Phải trả thiếu nguồn/giá mua hiển thị dòng Excel, mã, tên hàng và nút mở đúng ngày Đặt hàng. Người dùng sửa file, lưu rồi nạp lại và xác nhận; không cần hoàn tác kho hay duyệt lại đơn bán. Chưa đủ giá vẫn báo thiếu, không tự suy đoán giá.

Kiểm tra: 71 tests thuộc daily_workbook_import (23), daily_payable_recovery (17), supplier_plan_source (10), daily_import_issues (3), daily_catalog_capture (12), order_price_override (6) đều qua. Trình duyệt thử đổi khoảng/ngày, số chưa VAT/gồm VAT, mở đúng ngày lỗi và nạp lại file. Bản sao DB thử sửa sáu giá bằng dữ liệu giả: hết lỗi, ghi nhận đúng tổng mới, nạp lại không trùng; đơn bán, phải thu, kho và nguồn hóa đơn giữ nguyên.

Đối chiếu riêng 16 file gốc tháng 9: 3.023 dòng đã nạp ngày 01–13/09. Bản khôi phục trên DB sao chép khớp doanh thu, giá vốn vận hành và tổng gồm VAT từng dòng. Ngày 04/09 sửa 19 giá mua; 07/09 sửa 3 giá bán và giá theo gói cho 0,5 kg bột tiêu (một gói 500g), giữ nguyên lượng kho. Chứng từ BK đã ghi và hóa đơn nguồn đã phát hành giữ nguyên snapshot; dự thảo nội bộ chưa gửi có giá thay đổi được tạo lại với cùng lượng. Đây là khôi phục có nhật ký, không phải cho phép ghi đè tự do đơn đã ghi kho.

Giới hạn dữ liệu: phải trả 07/09 còn sáu giá mua chưa hợp lệ; dữ liệu Đặt hàng được giữ để người dùng tự bổ sung. Các ngày 14–16 chưa được nạp/duyệt trên web; file 15/09 có một mã chưa có trong danh mục và file 16/09 có 135 dòng cần kiểm tra khi kiểm tra cả lợi nhuận (76 dòng ở bước kiểm tra trước đó). Không tự tạo đơn hoặc đoán giá từ các file đó. Lợi nhuận Excel có phần lẻ VND có thể lệch 1–2đ so với tổng làm tròn từng dòng. Doanh thu theo ngày giao hàng không đồng nghĩa tổng hóa đơn phát hành đúng ngày đó.

Chi tiết kiểm tra và script khôi phục: `D:/TDP_RAILWAY_PRIVATE/month09_reconcile_20260915`; không chứa trong repository các file dữ liệu gốc hoặc bản sao DB khách hàng.
