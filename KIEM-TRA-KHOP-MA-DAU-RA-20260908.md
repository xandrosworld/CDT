# Kiểm tra khớp mã đầu ra ngày 08/09/2026

Các dòng thiếu mã nguồn được nhận theo tên danh mục chuẩn và đơn vị. Tên hóa đơn dùng chung cho nhiều biến thể không còn che mất tên danh mục chuẩn duy nhất. Nếu tên nguồn viết ngắn khác danh mục, hệ thống dùng lựa chọn đã xác nhận có lịch sử kiểm chứng, cùng tên và đơn vị, nhất quán giữa các bên mua. Không đoán theo tên gần giống, không tự quy đổi khác đơn vị, không ghi đè lựa chọn riêng đã lưu.

Hóa đơn bị chặn do nguồn không hợp lệ hiển thị “Chờ kiểm tra HĐ”, lý do chặn và mã trên hóa đơn gốc. Không còn ô ghép mã trống khiến người dùng tưởng mã bị mất. Các khóa ghi kho giữ nguyên.

## Kiểm thử trước triển khai

- 86 kiểm thử đạt: khớp mã đầu ra 18, đồng bộ đầu ra 16, mapping 16, danh sách 12, ghi xuất hàng loạt 8, đọc portal 16.
- Trình duyệt Chrome: hiển thị mã đã ghép; lỗi mạng rồi thử lại; tải lại trang; tên trùng nhiều mã giữ chưa ghép; hóa đơn nguồn bị chặn hiện lý do; không gửi yêu cầu ghi kho.
- Bản sao dữ liệu thật mới nhất nhận thêm 53 dòng, gồm các trường hợp khách gửi: Quất, Sả, Thanh long đỏ, Cà chua, Cà rốt, Củ cải và Hành lá. Mọi snapshot mã mới có revision hợp lệ; chạy lại không đổi; tiền, dòng nguồn, mã đã chọn và sổ kho giữ nguyên. Đây là kết quả bản sao, cần đối chiếu kết quả thực tế sau triển khai vì khách vẫn đang làm việc.

## Hóa đơn 1C26TYY / 717

Đã đọc lại trực tiếp chi tiết M-Invoice bằng kết nối chỉ đọc: 11 dòng cộng trước thuế 1.938.000đ và thuế 155.040đ; đầu hóa đơn ghi trước thuế 2.058.000đ và thuế 164.640đ. Chênh 120.000đ trước thuế và 9.600đ thuế. Mã nguồn M000177, M000277, M000338 đã có trong dữ liệu tải về. Không sửa số tiền hoặc bỏ chặn để ép hóa đơn này qua bước ghi kho. Cần đối chiếu chứng từ nguồn cho khoản chênh.

Chứng cứ, bản sao và ảnh trình duyệt lưu riêng ngoài Git tại `D:/TDP_RAILWAY_PRIVATE/evidence/output-complete-*`. Đây là kiểm chứng phạm vi sửa lỗi khớp mã, không phải chứng nhận 100% mọi luồng toàn hệ thống.
