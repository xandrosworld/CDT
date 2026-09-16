# Làm tròn công nợ phải trả theo tổng sheet Đặt hàng

Các dòng có phần lẻ đồng trước đây được làm tròn riêng, nên cộng lên cao hơn tổng Excel 1đ ở ngày 03, 04, 05, 09, 11/09. Ngày 08/09 thực tế đã khớp 54.246.470đ; kết quả kiểm tra ban đầu bị nhiễu biểu diễn số thập phân ở ngưỡng 0,5đ.

## Quy tắc

- Tính bằng Decimal, loại nhiễu dưới một phần triệu đồng; làm tròn tổng sheet/ngày đến đồng.
- Phân bổ phần chênh vào các dòng có phần lẻ, ưu tiên sai số làm tròn lớn nhất, thứ tự dòng nguồn ổn định. Không đổi số lượng, giá mua hay số tiền nguồn Excel.
- Cùng cách tính ở xem trước, sổ công nợ, số dư và xuất Excel. Dòng điều chỉnh có ghi chú trên web và comment trong Excel; tổng theo NCC cộng lại đúng tổng ngày.
- Hàng trả lại, khoản trừ tiền giữ nguyên ý nghĩa âm. Dòng đã phân bổ thanh toán vẫn được bảo vệ bởi kiểm tra thay đổi nguồn hiện có. Nạp lại cùng file không cộng trùng hay điều chỉnh lặp.

## Bằng chứng

Trên bản sao production, chỉ 5 dòng NCC kho thay đổi -1đ: ngày 03 dòng114, 04 dòng104, 05 dòng81, 09 dòng135, 11 dòng104. Chạy đồng bộ lần hai không thay đổi dòng nào. 12 ngày đủ dữ liệu từ 01–13/09 có tổng sổ, tổng xuất Excel và tổng Excel nguồn bằng nhau đến đồng. Ngày07 vẫn chờ 6 giá thật.

81 bài kiểm thử đã qua: làm tròn, preview/import, sổ nợ, thanh toán, xuất file, hàng trả và khoản trừ. Có kiểm tra phần lẻ âm, ngưỡng 0,5, lỗi số nhị phân, thứ tự dòng, lịch sử và nạp lại. Trình duyệt đã kiểm tra sáu ngày gồm ngày08 không cần đổi; nạp lại file03 trên bản sao vẫn ra47.699.831đ.

13 bảng đơn bán, nguồn Excel, thanh toán, kho, phải thu, bảng kê và hóa đơn giữ nguyên khi đồng bộ trên bản sao. Đã sao lưu production trước triển khai: `/data/manual_backups/before_payable_rounding_20260916_141558.sqlite3`.

Bằng chứng kiểm thử và kết quả: `D:/TDP_RAILWAY_PRIVATE/payable_rounding_20260916`.
