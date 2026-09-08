# Mã nguồn trùng mã kho nhưng khác mặt hàng — 08/09/2026

Hóa đơn 1C26TYY/781, dòng 7 (ID 7718), có tên nguồn “Bánh đa đỏ ướt (sợi nhỏ)”, 7 Kg, 129.500đ, nhưng nguồn gửi mã HT00233. Cơ chế tự ghép cũ tin mã trùng danh mục mà chưa đối chiếu tên, nên đã chọn HT00233 và yêu cầu quy đổi Kg sang Gói. Đây là thiếu sót của phần tự ghép. Trong danh mục hiện tại HT00233 là mì khô; HT00223 là bánh lương khô. Cả hai đều không phải mặt hàng bánh đa trên dòng này.

Đã đọc lại trên web thật và snapshot mới: hóa đơn chưa ghi xuất kho, không có bút toán xuất cho hóa đơn ID 546. Đối chiếu tên chuẩn xác nhận mã đúng G000007, đơn vị Kg. Đã thử sửa trên bản sao trước, rồi dùng API mapping có kiểm tra phiên bản dòng để sửa đúng một dòng trên production sang G000007, hệ số 1. Toàn bộ mã nguồn, tên nguồn, số lượng, giá, tiền và các dòng khác giữ nguyên; không gọi ghi kho.

## Chặn tái diễn

- Tự ghép theo mã nguồn phải khớp cả tên danh mục hoặc tên hóa đơn của chính mã đó. Mã trùng nhưng tên khác không được tự ghép.
- Các lựa chọn cũ có mã nguồn trùng mã kho nhưng tên khác phải xác nhận lại trước khi ghi kho. Chốt kiểm tra đặt ở bước xác thực snapshot ghi xuất, nên cả xuất một hóa đơn và xuất hàng loạt đều bị chặn. Danh sách/Excel thể hiện cần xử lý, không báo sẵn sàng.
- Không dùng lựa chọn đáng ngờ để tự ghép các dòng thiếu mã nguồn có cùng tên. Các lựa chọn viết tên khác nhưng đã được người dùng xác nhận rõ vẫn có thể dùng lại.
- Giữ các mã cũ để đối chiếu; hiển thị tên và đơn vị hàng trong kho ngay dưới ô mã. Khi giữ mã không khớp tên, nút Lưu yêu cầu xác nhận hai tên là cùng một mặt hàng; có thể hủy và chọn lại. Xác nhận có audit, gắn với mặt hàng/đơn vị hiện tại, thay đổi danh mục sẽ yêu cầu kiểm tra lại.

## Kiểm chứng

100 kiểm thử đạt: mapping đầu ra 23, mapping chung 16, đồng bộ đầu ra 16, danh sách 12, ghi kho 9, xuất hàng loạt 8, portal 16. Kiểm thử mới bao gồm mã sai mặt hàng nhưng cùng đơn vị, khóa ghi kho với mapping cũ, ngăn học lại lựa chọn sai, xác nhận rõ qua API, danh mục thay đổi hủy hiệu lực xác nhận, sửa sang mã đúng và bảo toàn nguồn.

Chrome fixture đạt: hiện đủ tên kho và cảnh báo; hủy xác nhận không ghi; chọn G000007 sửa đúng bánh đa; tải lại giữ mã; lỗi mạng và thử lại vẫn hoạt động; không có request ghi kho. Trên bản sao dữ liệu thật sau sửa 781, phát hiện 12 dòng khác cần kiểm tra tên, gồm một dòng đã học lại từ lựa chọn cũ. Tất cả dòng có mapping hoàn chỉnh trong nhóm này đều bị chốt mới từ chối ghi kho; không kết luận cả 12 dòng đều sai hàng khi chưa được khách xác nhận. Đọc toàn bộ 89 hóa đơn mất khoảng 0,12 giây trên bản sao.

Chứng cứ và dữ liệu riêng: `D:/TDP_RAILWAY_PRIVATE/evidence/output-wrong-code-01`, `output-wrong-code-before`, `identity-regression-*`, `output-identity-browser-01`.

## Xác nhận sau triển khai

Source `ac2f4b4198776ed961a88c40346b451f29daefb0`, deployment `75a4ec58-c9aa-4a39-ad27-558bb717a19a`, Railway SUCCESS. Trình duyệt web thật đã mở toàn màn hình: 781 dòng 7 hiện G000007, đúng tên bánh đa và đơn vị Kg. 12 dòng khác hiện cảnh báo tên không khớp; API GET chuẩn bị xuất kho loại toàn bộ 9 hóa đơn chứa các dòng đó khỏi danh sách được xuất. Không JavaScript exception, HTTP 5xx hay request ghi kho trong lần kiểm tra.

Snapshot trước/sau đủ 85 bảng, integrity OK, 78 bảng giữ nguyên, bao gồm sổ kho. Các bảng còn lại chỉ thay đổi mapping, revision/audit và trạng thái tổng hợp cho thao tác sửa mã. So từng trường: duy nhất dòng 7718 đổi snapshot ghép mã và đầu hóa đơn 546 đổi trạng thái; mã nguồn, tên nguồn, số lượng, đơn giá, tiền và toàn bộ dòng khác giữ nguyên. Hóa đơn 546 vẫn không có bút toán xuất kho. Không có thao tác tự xác nhận 12 dòng còn cần khách đối chiếu.
