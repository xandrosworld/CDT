# Kiểm tra luồng xuất hóa đơn — 09/09/2026

Phạm vi: tạo file từ đơn hàng, ghi nhận số hóa đơn đã phát hành, và xem trước ghi xuất kho cho hóa đơn đã tải về. Chưa ký hoặc phát hành hóa đơn thật trên M-Invoice.

## Đã sửa

- Mỗi file theo nhà thầu và nhóm thuế có một dự thảo riêng để lưu đúng số hóa đơn. Dự thảo cũ chứa nhiều nhóm thuế yêu cầu tính lại trước khi tải.
- Các nút tải file, tính lại, hồ sơ người mua và ghi nhận số hóa đơn hiện ngay ở bảng dự thảo.
- Nhập ký hiệu, số và ngày hóa đơn trong một cửa sổ. Lỗi hiện tại chỗ, giữ nội dung đã nhập.
- Ngày mặc định theo giờ Việt Nam; tránh lùi một ngày sau nửa đêm.
- Danh sách theo đúng đơn đang chọn, không mất dự thảo do giới hạn 200 bản ghi toàn hệ thống.
- Gửi lại cùng số hóa đơn không ghi trùng; số khác báo xung đột.
- Hiện tồn âm và nút mở kho trước khi tạo file. Đơn chưa duyệt có nút mở đơn để sửa/duyệt.

## Bằng chứng kiểm tra

- 749 kiểm thử thuộc 95 nhóm đạt, không bỏ qua kiểm thử nào. Bốn nhóm ban đầu còn kiểm tra câu chữ/phiên bản tệp cũ hoặc quy đổi đầu ra theo yêu cầu cũ; đã cập nhật đúng yêu cầu hiện tại và chạy lại. Nhật ký ban đầu được giữ lại.
- Trình duyệt đã thử tạo hai file khác thuế, tải lại, tính lại không nhân đôi dự thảo, hủy, sửa hồ sơ người mua, lưu từng số hóa đơn và tải lại trang. Không có lỗi JavaScript; không dùng chuỗi hộp thoại trình duyệt.
- Kiểm tra thời điểm 00:30 Việt Nam hiển thị đúng ngày mới.
- Trên bản sao dữ liệu thật: đối chiếu 13 file, 124 dòng về mã, tên, đơn vị, lượng và tiền; ghi nhận riêng 13 số hóa đơn thử.
- Thử trên bản sao có ba giả định rõ ràng: sửa thuế dòng Khế chua theo danh mục; thêm một giao dịch tồn thử 1,5 kg Quả me tươi; điền hồ sơ người mua giả. Những thay đổi này chỉ có trong bản sao. Không được hiểu là dữ liệu thật đã đủ điều kiện.
- Hóa đơn nguồn giữ nguyên. Bước tạo file/ghi số hóa đơn không thêm bút toán kho.

## Dữ liệu thật còn vướng

Đơn 04/09/2026 có 320 dòng, chưa duyệt:

- Một dòng Khế chua (I000067) có thuế `INVALID`; danh mục ghi KKKNT.
- Quả me tươi (I000091) đang âm 1,5 kg.
- Chưa có hồ sơ người mua; 78 mã còn thiếu tồn cho lượng yêu cầu.

Hóa đơn đầu ra tháng 08/2026:

- 89 hóa đơn, 1.953 dòng; hai hóa đơn điều chỉnh thuế đã đối chiếu, không thay đổi kho.
- Xem trước trên bản sao: 43 hóa đơn đủ điều kiện ghi kho, 44 bị chặn (42 thiếu tồn theo ngày, 2 cần đối chiếu tiền).
- Không được báo khách rằng bấm Ghi xuất kho là hoàn tất toàn bộ.

Nhật ký, ảnh, bản sao và dữ liệu đối chiếu nằm trong thư mục bằng chứng riêng; không đưa dữ liệu khách hàng vào kho mã nguồn.
