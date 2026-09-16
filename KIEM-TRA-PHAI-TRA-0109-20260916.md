# Đối chiếu ảnh khách gửi ngày 16/09

File `Đơn hàng  01.09.2026.xlsx` trong thư mục `ĐƠN HÀNG T9-2026` có tổng sheet Đặt hàng 5.232.325đ. Phải trả đang hiệu lực trên production cũng là 5.232.325đ, 18 dòng. Ảnh khách gửi chụp màn Duyệt đơn, có tổng tiền mua 7.704.450đ từ 30 dòng đơn bán. Hai tổng lấy từ hai sheet khác nhau.

## Thay đổi

- Đổi tên số trên màn Duyệt đơn thành “Tiền mua theo sheet đơn hàng”, ghi rõ phải trả lấy từ sheet Đặt hàng. Thêm nút mở phải trả đúng ngày, bỏ bộ lọc nhà cung cấp cũ.
- Phát hiện thêm lỗi độc lập: trạng thái “Tất cả” cộng cả 30 dòng đã đảo vào tổng tiền và số lượng. Ngày 01/09 hiện 12.936.775đ thay vì 5.232.325đ. Sửa tổng theo bộ lọc chỉ cộng dòng còn hiệu lực; vẫn giữ nguyên các dòng đã đảo để tra cứu. Chọn riêng “Đã đảo” có tổng tài chính bằng 0.
- Không sửa giá, số lượng, công nợ nguồn hay hóa đơn thật.

## Kiểm thử

- 35 tests: payable ledger, export, payments, settlement đều qua. Kiểm tra tổng với đủ trạng thái chưa trả/trả một phần/đã trả/đã đảo; bản ghi lịch sử vẫn hiện nhưng không cộng vào tổng.
- Trình duyệt với bản sao production: chọn Tất cả ngày 01/09 ra 5.232.325đ; từ màn đơn hàng vẫn xem được tiền mua 7.704.450đ, bấm nút mới mở đúng phải trả ngày 01/09.
- Ảnh trước/sau và kết quả tại `D:/TDP_RAILWAY_PRIVATE/recheck_sep01_20260916`.

Ảnh hiện có giải thích được trường hợp 01/09, không phải bằng chứng tất cả file mới về sau đã khớp. Đủ dữ liệu không chỉ là không trống: còn phải hợp lệ và khớp số lượng, giá, thành tiền ở đúng sheet.
