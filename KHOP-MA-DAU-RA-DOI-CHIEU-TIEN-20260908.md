# Khớp mã đầu ra khi hóa đơn đang chờ đối chiếu tiền

Ảnh khách gửi đã là giao diện mới: đầu ra chỉ khớp mã, không yêu cầu quy đổi.

## Lỗi đã xác định và sửa

Chức năng tự khớp bỏ qua hóa đơn có cảnh báo tổng tiền, trong khi thao tác Lưu từng dòng đã cho phép khớp mã. Ngoài ra, nút Khớp mã danh mục chưa áp dụng lại các quy tắc đã ghi nhớ cho dòng còn trống mã.

Bản sửa dùng cùng điều kiện kiểm tra nguồn với thao tác Lưu. Hóa đơn chỉ có chênh lệch tổng tiền được khớp mã chính xác; cảnh báo tiền và chặn xuất kho vẫn giữ nguyên. Các quy tắc duy nhất, còn hiệu lực được áp dụng lại vào dòng chưa chọn mã. Mã đã chọn, quy tắc hết hạn hoặc xung đột không bị tự thay thế.

## Đối chiếu bản sao dữ liệu thật

Kỳ 01/08–31/08/2026: 89 hóa đơn, 1.953 dòng.

| Nội dung | Kết quả |
|---|---:|
| Dòng cần xử lý trước sửa | 40 |
| Dòng khớp thêm ở hóa đơn 716–717 | 29 |
| Trong đó áp dụng lại quy tắc đã lưu | 12 |
| Dòng cần xử lý còn lại | 11 |
| Dòng còn cảnh báo tên hàng khác mã kho | 9 |
| Dòng thuộc hóa đơn nguồn đã điều chỉnh | 2 |

29 dòng đều trùng mã nguồn với mã danh mục và có tên hàng khớp. Giữ nguyên tên, mã nguồn, đơn vị, số lượng, đơn giá và thành tiền. Tổng tiền dòng vẫn là **2.090.284.169 đ**; tổng thanh toán hóa đơn vẫn là **2.157.268.585 đ**. Không phát sinh xuất kho.

So sánh toàn bộ 85 bảng: 79 bảng giống hệt, bao gồm dữ liệu hóa đơn gốc, danh mục, đầu vào và sổ kho. Sáu bảng thay đổi chỉ liên quan đến kết quả ghép mã, quy tắc, phiên bản quy tắc, thống kê lần tải, nhật ký và bộ đếm ID. Chạy khớp lần hai không khớp thêm dòng nào.

## Những dòng cần khách xác minh mặt hàng

| Hóa đơn | Tên trên hóa đơn | Mã đang chọn | Tên trong danh mục |
|---|---|---|---|
| 703 và 718 | Đùi gà góc tư đông lạnh, Tip Top Poultry | B000331 | Đùi gà góc tư bỏ xương sống |
| 723 | Mì Kokomi tôm chua cay 30 gói × 65 g | G000039 | Mì tôm Kokomi (gói) |
| 723 | GVS BLESS YOU H.M/ALAVIE CUON*20 | M000118 | Giấy ăn gấp |
| 748 | Cá rô phi sơ chế, cắt gáy | D000079 | Cá rô phi sơ chế, bằng đầu |
| 753 | Bột chiên giòn a-asean nhãn b1kg | M000021 | Bột chiên giòn Thành Phát 1kg/gói |
| 753 | Giấy vệ sinh Watersilk 12 cuộn/túi | M000118 | Giấy ăn gấp |
| 765 | Súp Miso rong biển Marukome ăn liền 152g | M000353 | Hạt nêm cá |
| 767 | Mực trứng | E000017 | Mực ống 8–10 con/kg |

Không tự xác nhận các cặp này. Nếu khác mặt hàng, khách cần chọn đúng mã kho. Nếu chỉ khác cách gọi và khách xác nhận đúng cùng mặt hàng, bấm Lưu và xác nhận trong thông báo so sánh hai tên. Chỉ việc bỏ yêu cầu quy đổi không thể giải quyết chọn sai mặt hàng.

Hai hóa đơn 716–717 vẫn có cảnh báo tổng tiền riêng, kể cả sau khi các dòng khớp mã đã chuyển về màu đen. Hai dòng nguồn đã điều chỉnh thuộc hóa đơn 695–696 vẫn giữ chặn.

## Kiểm tra

- 68 kiểm tra đạt: mapping, tự khớp đầu ra, đồng bộ đầu ra và hóa đơn chờ đối chiếu tiền.
- Trình duyệt: nút Khớp mã khớp được dòng trong hóa đơn chờ đối chiếu tiền, dòng chuyển màu đen, không xuất hiện ô quy đổi; tiền nguồn và chặn kho còn nguyên.
- Kiểm tra trường hợp mã trùng nhưng khác hàng, tên trùng nhiều mã, quy tắc hết hạn/xung đột, dữ liệu nguồn thiếu, hóa đơn hủy/điều chỉnh, dữ liệu đã ghi kho và thao tác lặp lại.
