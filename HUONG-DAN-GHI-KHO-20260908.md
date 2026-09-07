# Ghi kho, chuyển tháng và file M-Invoice

## Hóa đơn đã phát hành

Tại **Hóa đơn đầu vào + đầu ra → Hóa đơn đầu ra**, chọn ngày, tải hóa đơn và khớp mã. Bấm **Ghi xuất kho**, kiểm tra danh sách, lượng theo đơn vị và các hóa đơn bị giữ lại, rồi **Xác nhận xuất kho**.

Hệ thống kiểm tra đủ tồn theo ngày cho cả nhóm. Hóa đơn lỗi hoặc thiếu tồn được giữ lại; **Còn chưa xuất** hiển thị cả hóa đơn ngày cũ đến ngày kết thúc đã chọn. Ghi kho không gửi hoặc phát hành hóa đơn lên M-Invoice. Mất kết nối có thể thử lại cùng lựa chọn; không ghi trùng. Nếu dữ liệu đã thay đổi, đóng và mở lại bảng kiểm tra.

Đầu vào dùng **Nhập kho … hóa đơn → Xác nhận nhập kho**, phần chưa xong nằm trong **Còn chưa nhập**. Mỗi hóa đơn được ghi đủ các dòng hợp lệ, không ghi một phần hóa đơn.

## Lập file để phát hành hóa đơn mới

Bấm **Tạo file đưa lên M-Invoice** ở đầu bảng hóa đơn đầu ra, hoặc mở **Bảng kê & hóa đơn**. Chọn đơn hàng đã duyệt trên thanh trên. Tại **File đưa lên M-Invoice**, bấm **Tạo file tải hóa đơn**, sau đó **Tải ZIP vòng này**. Giải nén ZIP trên máy, nhập các file Excel vào M-Invoice để kiểm tra, ký và phát hành.

Nếu chưa có đơn, nạp và duyệt ở **Nhập & sửa đơn** trước. Tạo file chỉ lập dữ liệu của vòng đang xử lý; không tự ký/phát hành và không thay bước xác nhận ghi kho của hóa đơn đã tải về.

## Chuyển tồn tháng 8 sang tháng 9

Vào **Báo cáo vật tư hàng hóa → Chuyển tồn sang tháng sau**, chọn **08/2026**. Kiểm tra lượng, giá trị và hóa đơn chưa ghi kho. Các mã âm hoặc chưa đủ căn cứ được liệt kê trong hộp kiểm tra; cần đối chiếu trước khi chốt.

Sau khi đã kiểm tra, nhập tên người xác nhận rồi **Chốt tháng 08/2026 và chuyển sang 09/2026**. Hệ thống chuyển tồn cuối đã ghi sổ thành tồn đầu tháng 9, không cộng chồng. Nếu tháng 9 đã có tồn đầu, bảng xác nhận báo rõ việc thay thế. Để sửa tháng đã chốt, dùng **Mở lại tháng**, xử lý rồi chốt lại; giữ lịch sử thao tác.

Chốt tháng chỉ chuyển số liệu đã ghi kho. Các nút **Xử lý đầu vào còn chờ / Xử lý đầu ra còn chờ** mở đúng danh sách đến cuối tháng đó.

## Danh mục và kiểm thử

Danh mục tìm trên toàn bộ mã trước khi phân trang, nhận tên có hoặc không dấu. Thêm mã cần đủ mã, tên, đơn vị và thuế; thiếu trường sẽ báo **Chưa lưu**. Lưu thành công tự mở kết quả đúng mã vừa thêm. Mã trùng không ghi đè.

Đợt này không triển khai sửa báo cáo nhập–xuất–tồn trong Excel rồi tải ngược cập nhật kho.

Kiểm thử trước triển khai: 287 bài kiểm thử Python, 9 bộ kiểm thử trình duyệt; gồm các luồng đã sửa trước đó, đủ tồn cho cả nhóm, hủy, lỗi mạng/thử lại, dữ liệu thay đổi, chống ghi trùng, chốt/mở/chốt lại, các báo cáo toàn màn hình và trường hợp HT00245 tăng từ 1.255 lên 1.256 mã trên dữ liệu thử. Bốn mẫu Excel thuế được đối chiếu đúng hash bản đã chốt. Kiểm thử ghi kho/chốt tháng dùng cơ sở dữ liệu riêng.
