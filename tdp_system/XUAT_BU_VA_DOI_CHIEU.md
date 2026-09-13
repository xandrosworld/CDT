# Hàng chưa xuất và xuất bù từ đơn đã duyệt

Trong **Bảng kê & hóa đơn → Hàng chưa xuất hóa đơn · cộng dồn**, chọn nhà thầu và ngày đơn cần lấy đến.

- **Tải bảng chưa xuất theo mẫu:** ZIP tách theo nhà thầu và thuế, cùng 13 cột của mẫu hóa đơn. Giữ đúng lượng chưa xuất, giá trên đơn và phần lẻ; có cả hàng thiếu đầu vào để đối chiếu. Đây là bộ đối chiếu, không dùng nhập M-Invoice.
- **Tải file xuất bù đủ điều kiện:** cập nhật hóa đơn đã ký, trừ lượng đã phát hành rồi kiểm tra tồn và các dự thảo đang giữ. Chỉ file đủ điều kiện được đưa vào ZIP để nhập M-Invoice. Phần thiếu đầu vào, chưa rõ quy đổi hoặc chưa đủ lượng sau làm tròn vẫn giữ chờ và có trong hướng dẫn đi kèm.
- **Tải đối chiếu chi tiết:** bảng tổng hợp và các dòng đơn nguồn để truy lại số liệu.

Xuất bù dùng chính đơn cũ đã duyệt, không tạo hay duyệt thêm đơn, không cộng doanh thu/phải thu lần hai. Tải file chưa phải phát hành hóa đơn; chỉ khi hóa đơn đã ký được đồng bộ hoặc ghi nhận đúng số/ký hiệu/ngày thì lượng đó mới được trừ. Hóa đơn ký sau ngày đơn vẫn phải trừ khi xem lại đơn cũ. Ngày lọc là mốc đơn, không phải ngày phát hành hóa đơn.

KKKNT vẫn kiểm tra tồn. Ngoại lệ BK và việc nhập bảng kê bổ sung tiếp tục theo chính sách hiện hành; không tự giả định trọng lượng túi/hộp hay tạo đầu vào. Hồ sơ người mua cần có đúng mã số thuế để đối chiếu hóa đơn mới; hóa đơn chưa xác định được nguồn đơn phải được xử lý ở phần đối chiếu.

Khi tải cho nhiều nhà thầu, hệ thống giải phóng phần giữ của hóa đơn đã ký trước khi phân bổ tồn chung. Phần tồn nhả ra sau làm tròn được phân bổ xong trong cùng giao dịch, tránh thay đổi file chỉ vì bấm tải lại. Lỗi tạo file hoàn tác trong giao dịch; không trả file vượt tồn hoặc chứa lượng đã phát hành.

Kiểm thử: `test_catchup_exports` bao gồm mẫu 13 cột, giá/thuế/khuyến mại, lọc đơn đã duyệt, hóa đơn ký muộn, thiếu đầu vào, khác đơn vị, lỗi đồng bộ, chia tồn giữa nhà thầu, tải lại, hai lần xuất bù và xác nhận hóa đơn lặp không tăng doanh thu/phải thu. Chạy cùng các mô-đun `test_order_invoice_range`, `test_outgoing_unissued`, `test_outgoing_readiness`, `test_outgoing_waiting`, `test_outgoing_source_scope`, `test_receivable_ledger`, `test_invoice_tax_export`, `test_report_export`, `test_plain_print` bằng `qa_railway_acceptance` để cô lập dữ liệu và kết nối.
