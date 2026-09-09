# Bảng kê & hóa đơn — xử lý điều kiện chặn

## Bổ sung: đối chiếu đơn gốc và duyệt toàn đơn

Đối chiếu 553 dòng với hai file Excel có trên máy: 233 dòng ngày 29/08 và 320 dòng ngày 04/09. Không thiếu hoặc thêm dòng. Mã hàng, tên, nhà thầu, bếp và lượng đặt khớp; 320 giá bán ngày 04/09 khớp. Ngày 29/08 có 40 ô giá bán là chữ “Kiểm tra giá bán”: 19 đã bổ sung có nhật ký sửa, 21 còn thiếu; các giá bán số trong nguồn đều khớp. 11 khác biệt đơn vị chỉ là chữ hoa/thường. File 29/08 có SHA-256 khớp nhật ký nhập; file 04/09 đang có khác SHA-256, nên kết luận đối chiếu chỉ áp dụng cho các trường của sheet ngày đã kiểm tra, không khẳng định hai file giống hệt nhau.

Dòng 90 / ID 321 ngày 04/09, Khế chua I000067, bếp HESTRAXC có thuế nguồn #N/A và thuế đang lưu INVALID. Ngoài 7 mã âm, đây là điều kiện đang chặn duyệt đơn thật. Dòng 65 cùng mã từng được sửa sang KKKNT, có nhật ký 601; không tự sao chép lựa chọn đó sang dòng 90.

Đã sửa các lỗi phần mềm tìm được:

- Thuế không hợp lệ không hiển thị hoặc tự chọn thành 0% khi mở sửa. Biểu mẫu buộc người dùng chọn thuế.
- Readiness trả các dòng đơn cần sửa, kèm mã/bếp/dòng Excel; tab bảng kê có nút mở đúng dòng.
- Kiểm tra lại dữ liệu đơn trước khi tạo dự thảo; thuế INVALID/#N/A/rỗng/NaN/không hỗ trợ không thể âm thầm thành 0 trong file xuất.
- Nạp lại đơn vô hiệu hóa kết quả tính cũ; phản hồi cũ không ghi đè kết quả của phiên/lần tải mới. Quay lại bảng kê sau sửa tự cập nhật trạng thái.

Thử trên bản sao SQLite trong RAM của dữ liệu thật: lần duyệt nguyên trạng bị từ chối đúng lỗi dòng đơn. Giả lập chọn KKKNT cho dòng 321, chạy hàm API duyệt thực sự với xác nhận bảng kê: thành công, bảng kê mua vào 159 dòng không có lỗi/nhập trùng. Sau đó bổ sung đủ lượng giả lập cho toàn bộ nhu cầu: xuất 14 file Excel, đủ 320 dòng, tiền hàng 61.204.350đ, thuế trong kịch bản giả lập 610.264đ. Từng mã/lượng ròng/giá khớp đơn. Các sửa đổi và xác nhận chỉ diễn ra trên bản sao RAM, không thay đổi dữ liệu thật.

Kiểm thử bổ sung: nhóm 69 kiểm thử readiness/tax/substitution/worksheet và nhóm 59 kiểm thử import/giá/duyệt/bảng kê/M-Invoice client đều qua (có ca chủ động gây lỗi để kiểm tra rollback). Bài thử trình duyệt bổ sung thuế INVALID → mở đúng dòng → bắt buộc chọn thuế → lưu → quay lại tự hết lỗi → xử lý 7 mã âm → duyệt → tải hai nhóm thuế → tính lại → hủy tất cả/nhả tồn → tạo lại. Mẫu nhập M-Invoice tiếp tục dùng mã -2 cho KKKNT đúng định dạng.

Bảng đối chiếu chi tiết: `tdp_system/exports/doi_chieu_don_goc/Doi_chieu_553_dong_don_goc.xlsx`.

## Phần điều hướng đã triển khai trước đó

Khi phiên có mã tồn âm, màn hình nêu số mã, lượng âm và nút xử lý từng mã. Tổng lượng tách theo đơn vị; “Phần đủ lượng” không còn được trình bày như lời khẳng định có thể lập ngay khi chưa duyệt hoặc còn lỗi chặn.

Hộp xử lý hiển thị nguồn tồn đầu và lịch sử nhập/xuất. Có thể sửa tồn đầu đã đối chiếu bằng cơ chế kiểm tra phiên bản hiện có, kể cả khi có phát sinh sau tồn đầu. Các dòng nhập/xuất có nút mở ngày hóa đơn nguồn và làm nổi bật dòng liên quan; có nút quay lại bảng kê để kiểm tra lại. Người dùng có thể mở hóa đơn đầu vào để đối chiếu phần còn thiếu. Không tự bù tồn, đổi mặt hàng, sửa hóa đơn đã phát hành hoặc bỏ chặn tồn âm.

Lỗi tạo/tải file giữ thông báo trên màn hình cùng nút kiểm tra lại và mở đơn. Không có phần đủ lượng hoặc không tính được trạng thái thì không mở nút tạo mới.

## Kiểm chứng

- 50 kiểm thử backend qua: outgoing readiness, invoice tax export, outgoing substitution, invoice delivery statement. Bao gồm đường dẫn tới hóa đơn nguồn theo ngày hóa đơn khi ngày ghi kho khác ngày hóa đơn; đọc lịch sử không đổi dữ liệu; giữ giá/nguồn khi sửa tồn đầu; từ chối cửa sổ sửa cũ.
- Browser fixture dùng SQLite tạm, không mở dữ liệu vận hành. Chạy `python -m tdp_system.browser_fixture_documents_resolution`, rồi `node tdp_system/browser_smoke_documents_resolution.cjs` (có thể đặt `TDP_PLAYWRIGHT_PATH`).
- Qua giao diện: 7 mã âm → mở đúng dòng hóa đơn và quay lại → sửa 7 số tồn đầu giả lập đã đối chiếu (một mã có phát sinh) → hết chặn → duyệt đơn → tạo dự thảo → tải ZIP → tính lại → hủy/nhả tồn → tạo lại.
- Thử lỗi tải HTTP 409 rồi kiểm tra lại và tải thành công. Không gọi dịch vụ phát hành hóa đơn.
- Đọc Excel tải được: 7 mã riêng biệt, mỗi mã lượng 2, giá bán 20, tổng tiền hàng 280; không thiếu hoặc lặp dòng. Trình duyệt không có lỗi JavaScript.
- Lượt rà soát trước còn đối chiếu bản sao dữ liệu 04/09 và 29/08: giả lập đủ điều kiện trong RAM, 21 file/120 dòng khớp dự thảo, giữ nhóm nhà thầu/thuế/vòng và lượng chưa đủ.

## Giới hạn nghiệp vụ

Bảy mã âm trên dữ liệu thật chưa được chỉnh. Chức năng đổi mặt hàng trừ kho theo yêu cầu “luân chuyển” vẫn chờ khách xác nhận phạm vi. Mở nguồn hóa đơn tuân theo quyền và trạng thái sửa/ghi kho hiện có, không mở quyền sửa trực tiếp hóa đơn đã phát hành. Khi khách đối chiếu và sửa đúng nguyên nhân, bấm kiểm tra lại; hết điều kiện chặn và đã duyệt thì có thể tạo dự thảo/tải file. Ký và phát hành trên M-Invoice không nằm trong bài thử này.
