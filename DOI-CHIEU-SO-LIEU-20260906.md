# Đối chiếu số liệu màn hình và file — 06/09/2026

Đối chiếu trên bản sao nhất quán tải từ Railway tại `numeric-audit-before`. Mọi lần gọi API thử, tạo chứng từ và xuất file trong bộ kiểm tra dùng DB sao chép riêng, connector offline. Kỳ kiểm tra: tháng 8 và 01–06/09/2026; đơn đang có là 29/08, 233 dòng. Không suy ra dữ liệu nguồn đã được khách xác nhận chỉ vì màn hình và file khớp nhau.

## Các lỗi sửa trong lượt này

- Bảng Excel trên web tô đỏ **toàn bộ ô của dòng có lỗi hoặc cảnh báo**, gồm cả cột tính toán. Chỉ hết đỏ khi phản hồi đã lưu/đồng bộ xác nhận dòng không còn vấn đề; lỗi lưu không được tự xóa cảnh báo. Nút tới dòng cần sửa bao gồm cả cảnh báo.
- Bảng Excel NXT giữ dấu hiệu cần kiểm tra. Viewer bảng HTML giữ màu cảnh báo khi chuyển sang Excel chỉ xem.
- Thẻ tổng lượng NXT thu gọn thành nút mở bảng theo ĐVT; không còn chuỗi 21 đơn vị kéo thẻ dài hết màn hình. Footer vẫn cố định một hàng.
- Các file Tồn đầu/Nhập/Xuất/NXT không còn cộng chung kg, cái, chai… thành một tổng lượng. Ô tổng nhiều đơn vị dẫn tới sheet **Tổng ĐVT**, có đủ bốn cột đầu/nhập/xuất/cuối theo từng đơn vị.
- Tổng NXT không ghi **KHỚP** khi còn mã cần kiểm tra. Tiền và đơn giá trong bốn file kho dùng định dạng nguyên đồng `#,##0`; giữ giá trị tính gốc và lượng lẻ, không sửa dữ liệu sổ kho.

## Phạm vi số liệu đã đối chiếu

| Phần | Đối chiếu thực hiện | Kết quả / giới hạn dữ liệu |
|---|---|---|
| Đơn / tổng quan theo đơn | 233 dòng API so DB; tính lại giao ròng, nhận ròng, tiền bán/mua/thuế/lãi bằng Decimal; so tổng | Bán trước thuế 34.367.900; mua 30.715.357; lãi 3.652.543; thanh toán 35.130.404 đồng. Đơn vẫn nháp, còn lỗi/cảnh báo |
| NCC | 233 dòng mã/NCC/lượng; tính lại cộng/trừ điều chỉnh và công thức tiền trong Excel | Khớp nguồn kế hoạch đặt hàng hiện có |
| Phiếu giao | 233 dòng tên/lượng/ĐVT so giao ròng; 20 dòng có giá kiểm tra lại thành tiền | Khớp dữ liệu hiện lưu; không đồng nghĩa đơn đã được duyệt |
| Đầu vào | Tập ID DB/API; từng dòng tên/ĐVT/lượng/tiền/mã/giá trị quy đổi so Excel; tổng tiền dòng và hóa đơn tách riêng | Tháng 8: 266 hóa đơn, 1.107 dòng; tổng hóa đơn 919.234.874 đồng. Tháng 9 đang trống |
| Đầu ra | Cùng phép đối chiếu trên tập nguồn đầu ra | Tháng 8: 251 hóa đơn, 1.163 dòng; tổng hóa đơn 174.950.392 đồng. Đây là tài khoản đã chọn, nhiều nguồn chưa đủ điều kiện ghi kho |
| NXT / bốn file kho | 334 mã, 8 trường lượng/tiền mỗi mã; đầu + nhập − xuất = cuối; tổng từng ĐVT; trạng thái đối chiếu | Hai kỳ đều 2.419.360.717,75 đồng giá trị gốc, hiển thị 2.419.360.718 đồng. Có 4 mã tồn đầu âm; chưa có phát sinh từ hóa đơn đã ghi kho |
| Báo cáo tháng | Mọi ô của 26 dòng API so Excel; kiểm tra không đưa đơn nháp vào báo cáo đã duyệt | Tháng 8/9 tổng 0 vì chưa có đơn đã duyệt trong kỳ; tháng 8 báo 1 phiên nháp |
| Phải thu chi tiết | 233 dòng lịch sử và bộ lọc hiệu lực; lượng/giá/trước thuế/thuế/thành tiền theo ID so Excel | 233 dòng đã đảo tổng lịch sử 35.130.404 đồng; bộ lọc hiệu lực 0 dòng. Không cộng lịch sử đã đảo thành nợ mới |
| Phải trả chi tiết | 233 dòng lịch sử so Excel đủ 14 cột; kiểm tra lượng × giá; bộ lọc còn phải trả | Tổng lịch sử 30.715.357 đồng, 233 dòng đã đảo; không có dòng phát sinh còn nợ trong kỳ đang xét |
| Công nợ tổng | Từng đối tượng: đầu kỳ + phát sinh + điều chỉnh − đã thu/trả = cuối kỳ; đối chiếu 5 cột tiền Excel | Vẫn có 2.327.247.387 đồng phải trả đầu kỳ từ dữ liệu lịch sử. **Không được hiểu bộ lọc chi tiết kỳ này 0 dòng thành toàn bộ NCC đã hết nợ** |
| Báo giá | Rà 9 nhà thầu; giá tham chiếu so bảng giá DB; dòng được xuất so Excel; xác nhận chặn kỳ chưa chốt | 7 báo giá tháng chưa có phiên bản xác nhận nên bị chặn xuất. Báo giá ngày GIANHAPTAY có 32 dòng khớp; YLKHAN không có dòng trong đơn đang chọn |
| Chứng từ xem/in | So nội dung từng ô hiển thị và ô gộp của bản xem với chính Excel tải xuống, theo từng sheet được chọn | Phiếu giao, NCC, báo cáo, bảng kê đầu ra; không coi tải file thành công là kiểm chứng mọi nghiệp vụ |
| Bảng kê mua/biên nhận | Gọi phạm vi thực tế và rà lý do chặn; hồi quy mẫu/người bán trên DB thử | Nguồn hiện có thiếu giá mua ở một số dòng và thiếu hồ sơ người bán ở dòng nguồn 173; không xuất chứng từ chính thức bằng dữ liệu đoán |
| Hồ sơ thanh toán VAT | Kiểm tra phạm vi tháng 8 của 9 nhà thầu | Chưa có tập hóa đơn hợp lệ cho các hồ sơ đã khai báo (`issued_invoice_scope_empty`); chưa có hồ sơ thanh toán thật để chứng minh khớp tiền |
| Kho thực tế | Kiểm tra trạng thái chưa khai tồn và phép tính tồn nếu có nguồn đầu kỳ | 1.253 mã chưa khai tồn đầu: API trả chưa xác định, không được báo là tồn thực tế bằng 0 |
| Danh mục / sao lưu / đăng nhập | Giữ kiểm thử dữ liệu danh mục, nâng cấp, backup/khôi phục và truy cập từ bộ hồi quy; kiểm tra hosted riêng | Không dùng số test hoặc DB toàn vẹn thay đối chiếu số liệu nghiệp vụ |

## Các việc dữ liệu còn mở

1. Đơn 29/08: **45 dòng lỗi, 15 dòng cảnh báo**. Cần sửa đúng giá/mã/người bán theo nguồn; chưa tự duyệt.
2. Đầu vào: **1.104 dòng cần xử lý**, chưa xác nhận ghép mã/ghi kho trên production trong đợt này.
3. Đầu ra: **232 hóa đơn cần kiểm tra, 18 cần ghép mã, 1 không nhập tồn**. Tập dữ liệu hiện lưu khớp Excel không có nghĩa đã khớp sổ thuế.
4. Tồn đầu âm ở các mã **D000056, I000084, I000091, N000009**. Giữ nguyên dấu âm và cảnh báo; chưa có căn cứ tự điều chỉnh tồn.
5. Chốt đúng phiên bản báo giá tháng, bổ sung dữ liệu bảng kê/người bán và hồ sơ VAT trước khi lập chứng từ chính thức. Chưa khai tồn thực tế.

Các thao tác ghi/hoàn tác, ghi kho/chuyển kỳ, đối chiếu mẫu và lỗi mạng vẫn được kiểm tra trên dữ liệu thử có đủ tình huống. Các phần nguồn thực chưa sẵn sàng phía trên **chưa được ghi là nghiệm thu**.

## Kiểm thử và bằng chứng

- `numeric-regression-01`: 576/576 test đạt trước thay đổi mới ở file kho.
- `numeric-inventory-export-01`: 6/6 đạt, có tình huống nhiều ĐVT, lượng âm, tổng cần kiểm tra và giữ tiền gốc. `numeric-affected-01`: định giá 6/6, chốt kỳ 8/8, chứng từ 22/22 đạt sau sửa file kho. Không cộng các lượt trùng thành số test độc lập.
- `numeric-red-worksheet-03`: browser đạt; kiểm tra màu pixel của dòng lỗi và dòng chỉ có cảnh báo, hết đỏ sau xác nhận sửa; gõ/dán lượng lẻ, mạng lỗi, thử lại, xung đột, mở/đóng không tự ghi. Đã xem ảnh trực tiếp.
- `numeric-inventory-browser-01`: browser nghiệp vụ hóa đơn/kho và tổng cố định đạt.
- Bộ đối chiếu tái chạy: `python -m tdp_system.qa_numeric_reconciliation --snapshot BAN_SAO.sqlite3 --output THU_MUC_MOI`. Báo cáo ghi riêng phép so đạt và phạm vi bị chặn do dữ liệu. Không dùng HTTP 409/422 như bằng chứng đã xuất được chứng từ.
- Các lượt `numeric-real-copy-01` đến `05` giữ nguyên chẩn đoán: sửa cách bộ kiểm tra đọc thuế dạng 0,08, tên trạng thái phải trả, điều kiện phiên bản giá và lựa chọn bếp. Phép so bản xem so nội dung ô/ô gộp, không so nguyên chuỗi CSS có thể đổi sau vòng lưu XML. Các lần này không phải thay đổi dữ liệu nghiệp vụ.

Bằng chứng chi tiết và file có dữ liệu khách nằm riêng tại `D:\TDP_RAILWAY_PRIVATE\evidence`, không đưa vào Git. Trạng thái triển khai và kết quả đối chiếu production sau lượt kiểm tra được ghi tại README mục 13.21.
