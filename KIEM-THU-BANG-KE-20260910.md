# Bảng kê & hóa đơn — xử lý điều kiện chặn

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
