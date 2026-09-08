# Sửa màu dòng và cảnh báo đối chiếu tiền — 08/09/2026

Khách phản ánh dòng đã lưu mã vẫn đỏ và cảnh báo lệch tiền lặp lại ở mọi dòng, khiến khó biết còn phải làm gì.

## Hành vi sau sửa

- Đầu ra: dòng thiếu mã, thiếu quy đổi hoặc cần xác nhận đúng mặt hàng vẫn đỏ và có lý do. Dòng hoàn tất mã/quy đổi trở về màu chữ bình thường, kể cả khi cả hóa đơn đang chờ đối chiếu tiền.
- Nút **Chỉ xem dòng đỏ** / **Xem tất cả dòng** dùng được trong màn toàn màn hình. Lưu vẫn giữ vị trí; không tự cuộn hoặc đảo vị trí dòng đang làm.
- Cảnh báo tiền nằm riêng phía trên bảng: số hóa đơn cần đối chiếu, bảng cộng chi tiết / tổng hóa đơn / chênh lệch, tách tiền hàng, thuế và tổng thanh toán. Lọc dòng đỏ không giấu cảnh báo tiền.
- Ghép mã và quy đổi được lưu trong lúc đối chiếu; hóa đơn còn lệch tổng vẫn bị chặn ghi xuất kho. Không thay đổi điều kiện xác nhận mặt hàng hay các trường tiền, lượng, sổ kho.

## Đối chiếu nguồn trực tiếp

Lấy lại chi tiết 716 và 717 từ M-Invoice bằng GET, đối chiếu với bản sao web thật cùng ngày:

| Hóa đơn | Khoản | Cộng chi tiết | Tổng hóa đơn | Tổng HĐ trừ chi tiết |
|---|---|---:|---:|---:|
| 1C26TYY / 716 | Tiền hàng, cũng là tổng thanh toán | 12.731.500 | 19.258.100 | 6.526.600 |
| 1C26TYY / 717 | Tiền hàng | 1.938.000 | 2.058.000 | 120.000 |
| 1C26TYY / 717 | Thuế | 155.040 | 164.640 | 9.600 |
| 1C26TYY / 717 | Tổng thanh toán | 2.093.040 | 2.222.640 | 129.600 |

Trong 89 hóa đơn đầu ra tháng 8, hai hóa đơn này có cảnh báo tổng tiền. Không kết luận tất cả hóa đơn sai, hoặc tự sửa số nguồn để làm hết cảnh báo. Hai hóa đơn khác 695/696 đang cần xử lý trạng thái điều chỉnh; giữ nguyên chặn nghiệp vụ.

Hóa đơn 771 không có cảnh báo tổng tiền. Dòng M000118 Giấy ăn gấp cần quy đổi Túi sang Kg; không tự đặt hệ số khi chưa có căn cứ.

## Kiểm tra

- 92 kiểm thử đạt: output_mapping_review (8), invoice_workbench_listing (12), invoice_output_sync (16), invoice_inventory (9), minvoice_portal (16), invoice_output_bulk (8), invoice_output_mapping (23).
- Trình duyệt dữ liệu thử: lưu mã/quy đổi, màu trước/sau lưu, tải lại, lọc đỏ trong toàn màn hình, chi tiết tiền, xác nhận đúng mặt hàng, lỗi mạng rồi thử lại; thêm kiểm tra luồng nhập/gộp hiện có.
- Dữ liệu thật: lấy bản sao để kiểm tra trạng thái, số tiền và số dòng; đọc lại nguồn 716/717. Không thử ghi sổ kho trên dữ liệu khách.
- Bằng chứng đầy đủ nằm trong thư mục evidence riêng, tiền tố `color-totals-`; không đưa thông tin đăng nhập vào kho mã.
