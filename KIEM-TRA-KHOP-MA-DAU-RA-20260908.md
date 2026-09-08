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

## Kết quả trên web thật

Source `1036e0181be07cbf275...` được Railway triển khai thành công ở deployment `f45d7c98-770a-44d5-b2c2-934cc2d19ab4`. Một lần bấm Khớp mã danh mục tháng 8 đã ghép đúng 53 dòng, khớp toàn bộ danh sách đã duyệt trên bản sao. Đọc lại độc lập và mở trình duyệt xác nhận hóa đơn 715 các dòng 3/5/6 nhận I000127/I000042/J000030; hóa đơn 710 dòng 3/4 nhận I000014/I000018. 717 hiện lý do chặn và mã gốc M000177. Không lỗi JavaScript hoặc HTTP 5xx. Lần kiểm tra độc lập sau thao tác không gửi yêu cầu ghi dữ liệu.

Hai snapshot trước/sau có đủ 85 bảng, kiểm tra toàn vẹn đạt; 78 bảng giữ nguyên, bao gồm sổ kho và các dữ liệu nghiệp vụ ngoài mapping. Bảy bảng thay đổi đúng phần mã, trạng thái tổng hợp, revision/audit và bộ đếm. 548 đầu hóa đơn cùng 3.876 dòng nguồn giữ nguyên các trường nguồn, lượng, giá và tiền.

Số dòng cần xử lý tháng 8 giảm từ 136 xuống 83. Phần còn lại gồm 29 dòng chưa xác định mã an toàn, 16 dòng cần quy đổi đơn vị, 36 dòng thuộc hóa đơn 716/717 có tổng tiền nguồn không khớp, và 2 dòng của hóa đơn điều chỉnh 695/696 cần đối chiếu trạng thái. Không tự ép ghép hoặc bỏ khóa những trường hợp này.
