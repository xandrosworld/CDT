# Báo giá kỳ 2 tháng 9 — file khách ngày 15/09

File `BÁO GIÁ KỲ 2 T9.2026.xlsx` chứa 1.294 dòng, 7 cột nhà thầu và 50 mã lặp. Hai dòng 40–41 của A000045 có giá bán giống nhau ở 5 nhà thầu, nhưng giá mua từ hai NCC là 92.000 và 100.000. Kiểm tra cũ gộp cả giá mua vào xung đột báo giá bán nên chặn file.

## Hành vi sau sửa

- Theo từng cột nhà thầu, loại X/rỗng rồi gộp cùng mã, tên, ĐVT, thuế và giá bán. Giá bán khác nhau vẫn báo xung đột rõ dòng nguồn.
- Giá mua khác NCC không chặn xuất báo giá. Giữ toàn bộ dòng nguồn; khi định giá đơn, chọn giá mua đúng NCC. Nguồn mua còn mơ hồ yêu cầu giá mua thực tế, không chọn ngẫu nhiên.
- Các giá chữ `HM`, `Báo khi ăn`, `-` được xuất nguyên văn, không biến thành giá 0.
- Giữ thuế số 0 thành 0% khi nhập và xuất; hai mã muối M000183/M000184 không còn mất thuế thành ô trống.
- Mã được mô tả đầy đủ trong báo giá được giữ trong phiên bản báo giá dù chưa có trong danh mục kho; không tự tạo hay sửa danh mục. Điều này giải quyết C000029 và ba mã đã đánh X toàn bộ trong file mới.
- Lưu khoảng hiệu lực cho phiên bản: kỳ 2 này là 16–30/09/2026. Định giá đơn chọn phiên bản phù hợp ngày đơn; số đã lưu trong đơn cũ không bị viết lại. Báo giá cũ không có khoảng ngày tiếp tục có hiệu lực cả tháng như trước.
- Màn hình nạp cho chọn cả tháng, kỳ 1 hoặc kỳ 2. Bản gửi khách chỉ ghi `BẢNG BÁO GIÁ KỲ 2 THÁNG 9`, không in ngày hiệu lực. Khoảng ngày vẫn được hiển thị trong màn hình quản lý nội bộ.
- Báo giá tổng không kèm báo giá theo ngày của một đơn nằm ngoài khoảng hiệu lực.

## Kiểm chứng

Đối chiếu trực tiếp các cột Excel L/M/N/O/R/S/V với 7 file xuất, kiểm từng mã/tên/ĐVT/giá/thuế, không mã trùng, không còn X; 2.996 dòng đầu ra:

| Nhà thầu | Dòng |
|---|---:|
| ATV | 462 |
| HATRAN | 504 |
| BIADAUVOI | 393 |
| NGUYENGIA | 333 |
| SUPPY | 282 |
| TOYOTA | 516 |
| NHUAHAIPHONG | 506 |

Trên bản sao mới lấy từ production, nhập báo giá chỉ thay ba bảng phiên bản báo giá và audit; 102 bảng khác giữ nguyên. 64 tests qua trong quote_import (21), quote_export (4), quote_ui (2), round4_documents (27), selected_document_export (4), order_price_override (6). Bao gồm gộp sau X, khác giá mua theo NCC, mã mới, giá chữ, thuế 0%, biên ngày 15/16/30 và tháng sau, lọc đơn theo ngày khỏi bộ báo giá sai kỳ, đơn cũ, replay và rollback.
