# Kiểm tra tiền hóa đơn đầu ra — 09/09/2026

Mỗi hóa đơn lệch tiền có nút **Kiểm tra hóa đơn** ngay trong bảng cảnh báo. Khách xem chênh lệch, kiểm tra lại đúng hóa đơn từ M-Invoice và tải hồ sơ Excel tại chỗ. Không có thông báo giả “đã gửi hỗ trợ”; file cần được khách gửi cho người hỗ trợ.

**Cập nhật hóa đơn** luôn hiện, chỉ bật sau khi kiểm tra nguồn mới đã khớp tổng và còn trạng thái phát hành hợp lệ. Cập nhật lấy dữ liệu nguồn, không cho sửa tổng tiền tùy ý, không ghi xuất kho. Khôi phục các quy tắc ghép mã đã lưu bằng quy trình hiện có. Kiểm tra lại cả phiên bản nguồn và dữ liệu/mã hàng tại thời điểm lưu; nguồn thay đổi, người khác vừa sửa hoặc hóa đơn đã ghi kho đều bị chặn. Lỗi giữa chừng hoàn tác toàn bộ giao dịch.

Chỉ đánh dấu dòng cần đối chiếu phép tính khi có số liệu chứng minh. Không suy ra một dòng bị thiếu chỉ từ khoản chênh tổng. File Excel có số hóa đơn, ngày, khách hàng, tổng đối chiếu và toàn bộ dòng hàng; tiền chênh màu đỏ, cố định tiêu đề, cỡ chữ 13. Không xuất thông tin đăng nhập hay toàn bộ dữ liệu kết nối.

Đã đọc lại trực tiếp hai hóa đơn 716 và 717 từ M-Invoice: vẫn lần lượt 25 và 11 dòng, không thay đổi so với dữ liệu đã tải. Chênh tổng gồm thuế vẫn 6.526.600 đ và 129.600 đ. Chưa thấy lệch phép tính số lượng × đơn giá ở 36 dòng đó. Chưa đủ căn cứ xác định dòng bị thiếu hoặc kết luận hóa đơn gốc sai; hai hóa đơn vẫn chờ đối chiếu.

Kiểm thử: 121 bài trong 10 nhóm liên quan đến portal, tải hóa đơn, ghép mã, ghi kho, điều chỉnh và hỗ trợ đối chiếu đều đạt. Trình duyệt với dữ liệu giả kiểm tra mở/đóng, đọc lại, mất kết nối, tải Excel và cập nhật có chủ ý: đạt; không tạo bút toán kho. Dữ liệu nguồn lỗi, định danh khác, phiên bản cũ, sửa đồng thời và hoàn tác khi lỗi sau cập nhật đều có kiểm thử.

Không sửa dữ liệu nghiệp vụ thật trong đợt kiểm tra này.
