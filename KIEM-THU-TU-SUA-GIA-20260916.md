# Tự bổ sung giá mua ngày 07/09

Luồng cũ lưu được nhưng phải chuyển màn hình và đọc bảng quá dài. Luồng mới mở ngay tại Công nợ phải trả: hướng dẫn sửa Excel, chọn file, kiểm tra tổng, lưu và xem công nợ. File còn lỗi không bật nút lưu; lỗi giá chỉ rõ địa chỉ ô Excel và tên hàng.

## Kiểm thử thực tế

- Mở bản sao file khách ngày 07/09 bằng Microsoft Excel 16.0, sửa J7, J42, J166, J184, J254, J255, tính lại và lưu. Giá 10.000 ở sáu ô chỉ là dữ liệu thử, không phải giá khách xác nhận.
- Trình duyệt chạy với bản sao cơ sở dữ liệu production, cách ly mạng ra ngoài. Chọn file gốc: chỉ rõ đủ sáu ô, không cho lưu. Chọn file đã sửa: 307 dòng, không lỗi/cảnh báo, tổng thử 46.227.641đ.
- Bấm nút lưu trên giao diện, xác nhận cập nhật xong; tải lại trang vẫn đúng tổng. Nhấn đúp nút chỉ gửi một yêu cầu lưu.
- Chín bảng đơn bán, bảng kê, kho, phải thu và hóa đơn đã phát hành không thay đổi. Không nhập giá minh họa vào dữ liệu thật.
- Có ảnh từng bước, video trình duyệt và JSON kết quả tại thư mục riêng `D:/TDP_RAILWAY_PRIVATE/self_service_usability_20260916`.

Giới hạn: sáu giá mua thực tế ngày 07/09 vẫn cần khách điền. Kiểm thử chứng minh thao tác lưu/cập nhật, không xác nhận số tiền thử là công nợ thực tế.
