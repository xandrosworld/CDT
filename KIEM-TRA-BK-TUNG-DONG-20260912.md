# Bổ sung rà soát trách nhiệm xử lý bảng kê

## Căn cứ từ file gốc và nguồn hóa đơn

- File `Đơn hàng 06.09.2026.xlsx`, sheet `06.09`, hàng 105: BIADAUVOI / I000090 / Măng trúc / 15 gói. Cột R có tiêu đề `Bảng kê`, giá trị `bk`. Danh mục hàng ghi kg nhưng danh mục nhà cung cấp và báo giá ghi gói. Không có hệ số để tự đổi 15 gói thành kg.
- Dữ liệu nhập giữ dấu này tại `orders.purchase_list=1`. Các dòng trứng cút sơ chế H000006 đều có `purchase_list=0`. Việc chỉ tìm BK trong tên hàng ở bản sửa trước đã bỏ sót dấu BK hợp lệ trong cột Bảng kê.
- Hai dòng M000318 ngày 07/09 cũng khác đơn vị: đơn HATRAN ghi 1 hộp, NHUAHAIPHONG ghi 5 hộp, danh mục kho ghi chai. Giữ riêng ba dòng chưa xác định đơn vị; không chặn các dòng hợp lệ của nhà thầu.
- Nguồn hóa đơn 794 có `dateSign=2026-09-11T23:17:29.829761+07:00`, trạng thái cổng M-Invoice `invoiceStatus=0`, `sendTaxStatus=4`. Đây là hóa đơn đã ký, không phải nháp bị nhận nhầm. Sổ không có đầu vào H000006; không tạo chứng từ bù hoặc sửa/xóa trạng thái đã ký.

## Thay đổi

- Nhận dấu BK trên từng dòng đơn và giữ căn cứ qua các dòng phân bổ vào dự thảo. Không suy BK từ thuế KKKNT hoặc sao quyền từ danh mục sang dòng không đánh dấu.
- Kiểm tra đơn vị tại bước giữ chờ, tạo dự thảo, gộp file, tải file và xác nhận. Thu hồi phần giữ có đơn vị không khớp; phần hợp lệ của BIADAUVOI vẫn xuất được.
- Ghi rõ dòng giữ riêng và lý do trong giao diện, file bảng chưa xuất và hướng dẫn kèm ZIP.
- Thêm mục đối chiếu hóa đơn đã ký với sổ âm: số hóa đơn, ngày ký, mã hàng, lượng đã ký, tồn đầu, đầu vào và tồn hiện tại. Mục này chỉ đọc và không cản các mã hợp lệ.
- Đường tải dự thảo cũ cũng cập nhật nguồn M-Invoice khi kết nối và kiểm tra lượng đã ký chưa đối trừ. Cả trường hợp xuất một phần thấp hơn tổng lượng đơn cũng bị chặn nếu phần giữ chưa cập nhật.
- Điều kiện BK của phần giữ chờ được tính theo dòng nguồn của từng nhà thầu, tránh dòng không BK của nhà thầu khác vô hiệu hóa ngoại lệ hợp lệ.
- Khi tải lặp trên web thật, phát hiện tám dòng kg thay đổi 0,1 do sai số số thực tại ngưỡng làm tròn xuống. Chỉ loại sai số nhỏ hơn 0,000000001 trước khi lấy số lượng xuất: 0,7999999999999999 thành 0,8; 0,799999 vẫn lấy 0,7; bánh bao 27,6 vẫn lấy 27. Có kiểm thử tái hiện lỗi trước sửa, đối chiếu lượng và tiền trong file sau sửa, và tải lặp không đổi dữ liệu giữ chờ.

## Xác minh

138 kiểm thử qua: phạm vi đơn, hóa đơn đã ký/nháp, lượng giữ chờ, tồn chuẩn, dấu BK qua dự thảo và giữa các nhà thầu, đơn vị khác danh mục, sai số số thực sát ngưỡng xuất, xuất lại không thay số lượng, đường tải cũ và biên nhận.

Chạy bản sửa trên bản sao dữ liệu thật trong bộ nhớ: BIADAUVOI có các dòng hợp lệ để xuất, không còn nhà thầu bị lỗi gộp đơn vị; G000002 và H000006 không vào file mới. Mã có dấu BK được ngoại lệ theo đúng dòng nguồn, còn dòng không BK vẫn chịu giới hạn tồn.

Hóa đơn 794 và ba dòng đơn vị chưa xác định được trình bày thành hồ sơ đối chiếu cụ thể. Đây là dữ liệu/chứng từ còn cần quyết định dựa trên nguồn thực tế, không được tự đặt giá trị để làm mất cảnh báo.
