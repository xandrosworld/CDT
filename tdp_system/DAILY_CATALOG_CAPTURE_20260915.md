# Mã mới trong danh mục đi cùng file đơn hàng

Khi khách thêm mã vào sheet `danh mục hh` rồi nạp file đơn hàng, luồng cũ chỉ nhập đơn và bỏ qua danh mục. Vì vậy mã không xuất hiện trên web; dòng đơn dùng mã đó có thể báo chưa có trong danh mục.

Luồng nhập ngày giờ nhận các mã mới từ sheet `danh mục hh`, `danh mục hàng hóa`, `danh mục hàng`. Preview dùng các mã hợp lệ để đối chiếu đơn nhưng chưa ghi dữ liệu. Khi lưu đơn hoặc riêng Đặt hàng của ngày đã khóa, mã mới được ghi trong cùng giao dịch. Nạp lại không thêm trùng; thông tin mã cũ, giá, NCC và dữ liệu CCCD không bị thay theo file. Muốn sửa mã cũ vẫn dùng màn hình Danh mục.

Mã mới cần mã, tên, ĐVT và thuế. Tên/ĐVT hóa đơn trống dùng giá trị kho theo luồng hiện hành. Trùng mã khác thông tin hoặc thiếu trường bắt buộc hiển thị sheet/dòng cần sửa, chặn lưu. Thay đổi danh mục sau preview bị chặn để tránh ghi dữ liệu cũ. Đọc cả mã sau khoảng trống định dạng, giới hạn 100.000 dòng vật lý và 10.000 dòng dữ liệu.

## Kiểm chứng

- 12 ca `test_daily_catalog_capture`: mã chưa dùng, mã có trong đơn, nạp lại, tên sheet, xung đột, thiếu ĐVT, hủy preview, stale state, rollback đơn/danh mục/audit, file cập nhật, khoảng trống 12.669 dòng, ngày đã khóa giữ đơn/kho.
- Hồi quy: daily workbook/reference import, payable recovery, catalogue invoice labels, order import idempotence.
- Ba file khách ngày 01–03/09: nhận đúng danh mục, không có lỗi mới.
- Trình duyệt thật trên hai bản sao SQLite: cùng bản sao file 01/09 thêm `ZZTEST1509`; mã không xuất hiện với code cũ, xuất hiện với code mới. Chỉ thêm mã thử vào bản sao, không thêm vào dữ liệu khách đang chạy.

Lỗi báo giá A00045 ở hai dòng 40–41 cần đúng file khách vừa nạp để đối chiếu giá, xử lý riêng.
