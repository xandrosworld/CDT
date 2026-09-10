# Gộp nhiều ngày, mã hàng và giá bình quân cho M-Invoice

Một ZIP cho toàn bộ khoảng ngày đã chọn, không chia thư mục ngày. Mỗi nhà thầu/thuế có một Excel. Cùng mã, đơn vị và tính chất cộng lượng thành một dòng, giá bình quân có trọng số; hàng khuyến mại giữ riêng tính chất và giá 0. Khác đơn vị của cùng mã bị chặn để đối chiếu.

Kg làm tròn xuống theo 0,1 Kg sau khi cộng mã, tiền tính theo lượng xuất; phần lẻ trả lại lượng chưa phân bổ. Số lượng nguyên bản trên đơn giữ nguyên. Đơn giá bình quân giữ phần thập phân để số lượng × đơn giá khớp thành tiền làm tròn đồng. Tôm 7 + 6,3 = 13,3 Kg, 130.000đ/Kg, 1.729.000đ. Rau răm 0,432 Kg → 0,4 Kg × 20.000 = 8.000đ.

Tạo một dự thảo consolidated cho mỗi nhà thầu/thuế; hủy các dự thảo cục bộ thay thế và nhả đúng giữ kho cũ trong cùng giao dịch. Không thay dự thảo đã lưu M-Invoice/đã phát hành. Giữ bảng phân bổ từng dòng gộp về đơn nguồn, giá nguồn và phạm vi ngày (kể cả ngày chỉ còn phần lẻ). Tải lặp giữ nguyên dự thảo/giá/lượng. Không được lấy thiếu ngày của một dự thảo đã gộp. Dự thảo chung hiển thị ở các ngày nguồn; ghi nhận một hóa đơn chung cập nhật phân bổ các ngày, hủy thì nhả tất cả. Đơn nguồn được khóa ở tất cả ngày khi có dự thảo chung. Hồ sơ thanh toán dùng phân bổ để giữ ngày giao, kiểm tra tổng theo dòng hóa đơn đã gộp.

91 kiểm thử PASS: phân bổ theo tồn, ngoại lệ KKKNT, gộp nhiều ngày, giá bình quân, lượng Kg, giữ mã/thuế, tải lặp, ngày bị làm tròn hết không làm trôi giá, hủy/ghi nhận hóa đơn chung, phần nguồn nhiều ngày, hồ sơ thanh toán, lỗi file rollback, tồn giảm chặn xuất lại. Kiểm thử giao diện bản sao khách: ATV 01–03/09 còn 2 Excel (KKKNT 61 dòng, VAT8 2 dòng), 36 dòng còn phần chưa xuất gồm thiếu tồn/phần lẻ, không lỗi JavaScript.

Ảnh/file tiền tố BAN_SAO chỉ dùng kiểm thử. HE_THONG_THAT trong `tdp_system/exports/consolidation_test` là bằng chứng sau triển khai. Bộ gộp thay bộ tách ngày chưa phát hành; khách không nhập cả hai bộ để tránh lập trùng.
