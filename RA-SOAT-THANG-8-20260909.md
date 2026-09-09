# Rà soát tháng 8 — 09/09/2026

Chưa hoàn tất kho tháng 8. Không yêu cầu khách điền giá ngày 29/8 với lời hứa rằng việc đó sẽ giải quyết toàn bộ tháng.

## Đã kiểm tra

- Web: 43 hóa đơn đã ghi kho, 42 hóa đơn chưa đủ tồn, 2 hóa đơn lệch tiền và 2 hóa đơn điều chỉnh thuế không đổi kho. Hiện không có hóa đơn nào trong nhóm còn lại vượt qua bước kiểm tra ghi kho.
- Đã tải lại trực tiếp hóa đơn 716 và 717: chênh lệch tổng thanh toán vẫn lần lượt là 6.526.600 đ và 129.600 đ. Chưa có căn cứ sửa số tiền hay tự thêm dòng hàng.
- Đọc 5.177 dòng trong 18 trang đơn ngày 12–29/8.
- Phát hiện thêm 6.269 dòng ngày 1–28/8 trong trang **Công nợ tổng** của cùng file `Đơn hàng 29.08.xlsx`. Trang này có lượng thực tế, giá mua và thành tiền. Không cần xin lại dữ liệu ngày 1–11 chỉ vì không có trang đơn riêng.
- Đối chiếu theo ngày, mã, đơn vị và nhà cung cấp, cộng các bếp trước khi so sánh: 1.960 nhóm bằng nhau, 289 nhóm khác lượng. Ví dụ đá viên ngày 12/8: đơn 12 túi, Công nợ tổng 10 túi. Không tự chọn nguồn khi khách trước đó xác nhận lượng theo đơn.
- Tên trùng duy nhất trong danh mục được ưu tiên trước tên thay thế; không ghép gần đúng, không đổi đơn vị tự động.

## Phần đã chuẩn bị, chưa ghi vào kho thật

- Bảng kê ngày 29/8: 104 dòng, 6.995.705 đ theo quy tắc đang cấu hình. Đơn vẫn còn 25 dòng lỗi giá ngoài phần bảng kê.
- Từ Công nợ tổng: 2.403 dòng qua kiểm tra mã, đơn vị, giá và phép tính, tổng 299.739.377 đ. Đây là dự thảo theo nguồn Công nợ tổng, **chưa phải xác nhận lượng nhập kho**, vì còn phải chốt ưu tiên nguồn khi khác đơn hàng.
- Các dòng có hóa đơn nhập cùng mã, khác đơn vị, nghi trùng hoặc thiếu dữ liệu được giữ lại để đối chiếu; hàng lấy từ kho không được tự biến thành mua mới.
- Chạy thử trên bản sao mới tải: bổ sung dự thảo Công nợ tổng và bảng kê 29/8 vẫn chưa làm trọn vẹn thêm hóa đơn nào trong nhóm 42. Phần nguồn mua còn thiếu/chưa rõ và hóa đơn lệch tiền cần xử lý tiếp. Không cộng đồng thời các trang đơn và Công nợ tổng cho cùng lần mua.
- Không tạo nhập/xuất kho thật, không phát hành hóa đơn trong lần rà soát này.

## Sửa phần mềm

- Khi duyệt đơn, kiểm tra cả bảng kê đã nhập cùng mã/ngày, bên cạnh hóa đơn nhập. Phải xác nhận đó là lần mua riêng trước khi ghi thêm.
- Bảng kê phát sinh sau lúc mở xác nhận làm hết hiệu lực bản xem trước; thao tác cũ bị chặn.
- Bảng kê đúng nguồn đã nhập từ Excel vẫn được nhận lại theo cơ chế chống trùng hiện có.
- Hướng dẫn màu ghi rõ: màu đen là đã khớp mã; bấm Ghi xuất kho để kiểm tra tồn và ghi kho. Không ẩn chức năng.
- Kiểm chứng: 40 kiểm thử bảng kê/duyệt đơn và 12 kiểm thử danh sách hóa đơn đạt; JavaScript qua kiểm tra cú pháp.

## Một ý cần khách chốt

“Chị xác nhận giúp em: số lượng nhập kho tháng 8 lấy theo cột SL thực tế trong trang Công nợ tổng hay theo số lượng trong các trang đơn hàng? Hai phần đang có chỗ khác nhau, em sẽ tự đối chiếu phần còn lại.”

Sau khi có câu trả lời, dùng đúng nguồn đã chốt để hoàn thiện dự thảo, kiểm tra lại chống trùng và tồn theo ngày trước khi ghi kho. Các hóa đơn 716/717 vẫn cần nguồn chi tiết khớp tổng; không bỏ chặn để báo hoàn tất.
