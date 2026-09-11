# Đối chiếu bảng kê, hóa đơn đã ký và tồn đầu vào

## Phản ánh và dữ liệu thật

- Khách chỉ lấy đơn đến hết 07/09/2026. Luồng cộng dồn cũ bỏ qua ngày đến và luôn lấy đến hôm nay; đã đổi thành ngày chọn rõ ràng trên form, mặc định ngày phiên đơn đang mở.
- Hóa đơn 1C26TYY/790 ngày 10/09 của ATV đã ghi nhận 27 bánh bao G000002 và 75,6 kg đậu phụ H000016. Trước lần sửa này, dữ liệu hiện tại đã đối trừ hai lượng này; bánh bao còn giữ 0,6 cái vì tồn đầu là 27,6. Không được diễn giải ảnh file cũ 27,6 là số đang xuất lại trên máy chủ.
- File khách `HATRAN_KKKNT_2026-09-01_2026-09-11.xlsx` chứa H000006 / Trứng cút sơ chế / 1.218 quả. Mã này không có tồn đầu hoặc đầu vào trong sổ hiện tại. Nguồn M-Invoice hiện ghi hóa đơn 794 ngày 11/09 đã phát hành đúng 1.218 quả; sổ còn -1.218. Không thay trạng thái, xóa hóa đơn hoặc tạo đầu vào giả để che số âm.
- Nguyên nhân cho lượng thiếu tồn vào file là ngoại lệ cũ áp dụng cho mọi mã KKKNT. Chỉ dẫn khách ngày 11/09 thay thế quy tắc đó: chỉ dòng có tên BK được ngoại lệ khi lập bảng kê xuất.
- Biên nhận có dòng C4 viết cứng tên công ty cũ khác C5. Đã lấy cùng tên pháp lý cấu hình cho cả hai dòng.

## Cách sửa

- Giới hạn ngày chỉ giới hạn ngày đơn; luôn đồng bộ hóa đơn đã ký đến hiện tại và trừ cả hóa đơn ký sau ngày đơn. Hóa đơn chưa ký không trừ.
- Chỉ tên hàng có từ BK riêng biệt được ngoại lệ; thuế KKKNT không cấp quyền âm kho. Không tự thêm BK vào tên hàng của khách.
- Làm mới lượng chờ cũng kiểm tra lại tồn của các dự thảo cũ, giảm/hủy phần giữ vượt tồn. Dự thảo đã lưu M-Invoice vẫn khóa và yêu cầu đối chiếu nếu xung đột; không âm thầm viết lại.
- Kg lấy 0,1; cái/quả/con/chiếc lấy số nguyên sau cộng cùng mã, cùng giá. Phần lẻ giữ chờ. Giá trên đơn không đổi.
- Khi một mã đã âm do hóa đơn phát hành trước đó, không cấp thêm lượng cho mã đó. Mã khác còn đủ tồn vẫn lập được bảng kê.

## Xác minh

Kiểm thử các lớp SourceScopeTests, WaitingTests, OrderInvoiceRangeTests, UnissuedTests, OutgoingReadinessTests, ReceiptExportTests: giới hạn ngày, đối trừ sau ngày đơn, tải lặp, ký một phần, không trừ hóa đơn nháp, không cấp trùng tồn giữa hai yêu cầu, thu hồi giữ chờ theo quy tắc cũ, không sửa dự thảo khóa và tên công ty trên biên nhận.

Đã chạy bản sửa trên bản sao SQLite trong bộ nhớ của dữ liệu Railway (nguồn mở chỉ đọc): không còn G000002 hoặc H000006 trong file xuất mới; mọi mã xuất mới đều không vượt tồn khả dụng. BIADAUVOI vẫn cần xác nhận I000090 ngày 06/09 ghi gói trong khi các ngày khác ghi kg.

Hóa đơn 794 đã phát hành trong dữ liệu nguồn là vấn đề chứng từ còn cần khách đối chiếu; bản sửa phần mềm ngăn xuất mới sai tồn, không giải quyết bằng cách sửa lịch sử đã ký.
