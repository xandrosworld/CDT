# Rà soát đổi mã kho và đối trừ hóa đơn

Phản ánh của khách liên quan đến chức năng Excel đổi mã trừ kho của hàng âm. Kiểm tra riêng `outgoing_substitution_actions` không đủ để xác định chức năng này đã được sử dụng hay chưa: lịch sử của nó nằm trong `inventory.output.remap`, `output_stock_remaps` và `output_stock_remap_parts`.

Đối chiếu bản sao nhất quán lấy trực tiếp từ Railway ngày 13/09 xác nhận 15 dòng thuộc 9 hóa đơn tháng 8 đã đổi cách trừ kho, trong đó 7 dòng đổi đơn vị. Dữ liệu hóa đơn lưu tại hệ thống vẫn khớp bản chụp trước thao tác ở cả 15 dòng. Tháng 8 đã chốt và đã chuyển tồn sang tháng 9. Đây là bằng chứng về thao tác đã ghi, không xác nhận các lựa chọn đổi hàng phù hợp với hàng thực tế bán.

Có 4 lần sửa ghép nhầm mã riêng trong tháng 9, có đối chiếu mã, lượng, giá với dòng đơn cụ thể và dữ liệu nguồn. Không gộp những lần sửa nhận diện này với thao tác chuyển phần tồn âm qua Excel. Báo cáo chi tiết và dữ liệu khách được lưu ngoài Git.

## Lỗi tái hiện và bản sửa

Ví dụ hóa đơn bán mặt hàng A số lượng 3, sau đó người dùng chuyển trừ kho nội bộ sang B. Trước bản sửa, đối trừ FIFO lấy sổ kho hiệu lực nên có thể ghi 3 đã xuất vào đơn bán B. Chuyển một phần có thể chia số đã xuất giữa A và B dù nội dung hóa đơn không thay đổi.

`outgoing_unissued.py` nhận diện những dòng đang còn hiệu lực từ lịch sử chuyển tồn âm qua Excel. Những hóa đơn này phải đối chiếu mặt hàng với đơn trước khi tự phân bổ phần đã xuất. Cảnh báo chỉ thuộc nhà thầu liên quan, không tự ghi thêm hóa đơn, sửa đơn, kho hoặc công nợ.

- Liên kết đơn đã xác nhận phát hành từ trước được giữ, đồng thời hiện cảnh báo đối chiếu.
- Hóa đơn trước kỳ đơn và hóa đơn thuộc phạm vi ngoài đơn tiếp tục theo quy tắc hiện có.
- Sửa ghép nhầm mã có loại nhật ký riêng tiếp tục được xử lý theo luồng đối chiếu hiện có.
- Hoàn về mã kho gốc và không còn phần chuyển sang mã khác thì không giữ cảnh báo này.
- Đây là kiểm soát đối trừ; không chứng thực lựa chọn mã kho hoặc mở chức năng đổi mặt hàng trên hóa đơn.

## Kiểm tra

- Tái hiện trước sửa: 3/6 ca kiểm tra không đạt (đối trừ toàn bộ, một phần và thiếu cảnh báo khi đã có liên kết đơn).
- Sau sửa: 8 ca chuyên biệt đạt, gồm phạm vi nhà thầu và lịch sử chuyển tiếp một phần đã tách.
- So sánh trực tiếp hàm trước/sau trên bản sao dữ liệu khách: kết quả cộng dồn tháng 9 giống nhau, 2.144 dòng đơn nguồn và 788 dòng còn chưa xuất. Các giao dịch chuyển tồn âm tháng 8 không tự làm chặn toàn bộ tháng 9.
- Sửa ca kiểm thử cũ còn mặc định KKKNT được xuất âm: kiểm tra KKKNT chưa đánh dấu BK phải bị chặn, sau khi đánh dấu BK rõ ràng mới áp dụng ngoại lệ của nghiệp vụ hiện có. Không nới quy tắc phần mềm để làm kiểm thử qua.

Các thao tác ghi tiền, sửa hàng, thay đổi đầu vào hoặc phát hành hóa đơn không được thực hiện trên Railway trong lượt rà soát. Việc sửa những lựa chọn hàng hóa lịch sử cần căn cứ chứng từ thực tế; không tự hoàn tác kỳ đã chốt để làm mất lịch sử.
