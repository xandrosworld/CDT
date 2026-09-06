# Rà soát bản web trên máy tính — 06/09/2026

Phạm vi theo chỉ đạo mới: máy tính, cửa sổ rộng 1024/1366/1440/1680px. Không triển khai thay đổi điện thoại trong lượt này. Kiểm tra giao diện bằng Chrome; bảng sửa đơn được kiểm tra thêm trên Edge. Các thao tác nhập/sửa, thanh toán, ghi kho và chốt kỳ dùng DB thử riêng. Kiểm tra Railway chỉ xem, tải chứng từ và đối chiếu dữ liệu.

## Lỗi phát hiện và cách sửa

1. **Số lượng `0,855` trong bảng Excel bị lưu thành `855`.** Đã tái hiện trên DB thử bằng thao tác gõ ô. Bộ đọc số tiếng Anh của thư viện hiểu dấu phẩy là phân cách hàng nghìn trước khi dữ liệu đến hàm kiểm tra. Đã giữ nguyên nội dung nhập ở các cột số lượng để bộ đọc thập phân của ứng dụng xử lý; tiền vẫn theo định dạng tiền đã chốt. Kiểm tra gõ `0,855`, `0.0056`, dán `0,625`/`2,5`, đối chiếu giá trị API đã lưu. Không sửa số lượng có sẵn trong DB production theo phỏng đoán.
2. **Màn in trên Railway còn hiện máy in Windows của máy chủ.** Bản hosted dùng luồng chọn phiếu → PDF → hộp thoại in trên máy tính người dùng. Đã bỏ các nút gửi máy in Windows khỏi giao diện hosted, giữ lịch sử in cũ để tra cứu.
3. **Hướng dẫn sao lưu còn nói phải mở máy chính/cùng Wi-Fi.** Đã phân biệt bản hosted và bản cục bộ. Bản web nói rõ dữ liệu trực tuyến và lịch sao lưu vẫn chạy khi đóng trình duyệt.
4. **Dòng tổng NXT cố định quá cao, che dữ liệu.** Giữ footer 52px, tiền trên một dòng; lượng nhiều đơn vị hiện nút mở bảng tổng theo ĐVT. Nút **Xem bằng Excel · toàn màn hình** ở ngay tiêu đề chi tiết. Browser kiểm tra 240 mã/24 ĐVT, tổng tiền 2,4 tỷ, cuộn giữa/cuối và ngang tại 1680/1366/1024px; tổng lượng trong hộp chi tiết được đối chiếu từng ô. Không thay nguồn số liệu hay cách xuất Excel.

Các bài browser cũ về hộp sửa đơn, xác nhận báo giá và nhãn giá sửa tay còn kỳ vọng giao diện trước đây. Đã cập nhật theo hành vi hiện tại, giữ đối chiếu dữ liệu, tiền, lịch sử và file tải; không đổi sản phẩm để đáp ứng nhãn cũ.

## Phạm vi kiểm tra từng màn

“Đạt trên DB thử” chỉ áp dụng các tình huống được liệt kê. Cột cuối ghi nguồn kiểm tra, không thay thế việc khách xác nhận dữ liệu nghiệp vụ.

| Màn | Chức năng/tình huống đã kiểm tra | Nguồn bằng chứng |
|---|---|---|
| Công việc hằng ngày | Mở phiên đơn, liên kết đơn/phiếu giao, giữ đường nghiệp vụ sau khi ẩn menu cũ | Browser lượt 2, 5; Railway |
| Nhập & sửa đơn | Lọc lỗi/cảnh báo/tìm kiếm/tổng, tiêu đề/cuộn; nạp bản đầu và nhiều bản sau; chống trùng/khóa chứng từ; sửa giá có lịch sử; bảng Excel gõ/dán/lưu, lượng lẻ, mạng lỗi, phản hồi chậm, xung đột hai người, đóng khi chưa lưu, mở/đóng không tự ghi | Backend nhập đơn và worksheet; browser lượt 2, worksheet và order_price; Railway xem bảng |
| Đặt hàng NCC | Đủ các bếp trong ảnh; sao chép lỗi không đánh dấu, thành công mới đã đặt; sắp xếp/mở lại; bảo toàn NCC đã chọn | Browser lượt 2; kiểm thử workbook/NCC; Railway xem |
| Kho thực tế | Chưa khai tồn thì báo thiếu; khai tồn/nhập/điều chỉnh, trừ theo đơn, sửa/hủy/khách trả, chốt giao/mở lại không trừ hai lần, mở đơn nguồn | Browser lượt 2; 14 kiểm thử kho thực tế; viewer chỉ xem |
| Báo giá | File xung đột bị chặn; file hợp lệ tự lưu; chọn kỳ/nhà thầu, giá 0 giữ lại, X/rỗng loại đúng; lịch sử, Excel từng nhà thầu và ZIP, tải lại trang còn dữ liệu | Browser quote_ui; kiểm thử nhập/xuất báo giá; Railway trạng thái kỳ chưa có giá |
| Báo cáo tổng hợp | Bếp động, kỳ rỗng, tổng theo tháng; phản hồi tháng cũ tới muộn và tải lỗi; bảng/Excel cùng số liệu | Browser lượt 3; kiểm thử báo cáo; Railway |
| Công nợ | Ba phần phải thu bếp/tổng/phải trả; lọc/ngày/phân trang/tổng ĐVT, trả một phần/đủ, thu/trả/hoàn tác và lịch sử; chống ghi lặp/đồng thời; Excel phải trả 14 cột | Browser lượt 3; kiểm thử phải thu/phải trả; Railway mở ba phần |
| Bảng kê & hóa đơn | Cần 10/tồn 7 chỉ lập 7 và giữ thiếu 3; giữ tồn, bổ sung đầu vào xử lý tiếp; rollback/chặn âm; nguồn VAT đồng bộ, hồ sơ người mua và kỳ độc lập | Browser outgoing_readiness; kiểm thử phân bổ, đầu ra và hồ sơ VAT; Railway xem |
| Báo cáo vật tư hàng hóa | Xem NXT, lượng/tiền, liên kết nguồn; chốt/mở/chốt lại/chuyển kỳ, cảnh báo số âm; tải lại không cộng trùng | Browser lượt 1; kiểm thử kho/định giá/xuất/chốt kỳ; Railway viewer |
| Hóa đơn đầu vào + đầu ra | Lọc Việt Nam/rìa kỳ, dòng lỗi lên đầu, tổng và Excel; mã sai bị chặn, ghép/quy đổi/xác nhận ghi và mở chi tiết; trạng thái hợp lệ, chống đồng bộ/ghi trùng | Browser lượt 1; kiểm thử hóa đơn/mapping; Railway 266 đầu vào/251 đầu ra |
| In giấy tờ | Lọc/chọn một/nhiều/tất cả, xem trong màn, đổi sheet/thu phóng, chỉ in phần chọn; hủy/chậm/đổi phiếu không mở PDF nhầm, không tải tự động | Browser lượt 4; kiểm thử chứng từ/PDF; Railway phiếu giao Excel/PDF |
| Danh mục & sao lưu | Kiểm thử nhập danh mục/thông tin người bán; loại hai hồ sơ theo quyết định, cập nhật dữ liệu cũ; backup thành công/lỗi, khôi phục bản thử, lịch/giữ phiên; hướng dẫn hosted | Kiểm thử danh mục và lượt 5; browser lượt 5; snapshot Railway |
| Đăng nhập/đăng xuất | Chặn chưa đăng nhập, phiên xác thực, CSRF/host/hạn chế thử mật khẩu, đăng xuất chặn API lại | Kiểm thử cloud; Chrome Railway |

## Kết quả và vị trí bằng chứng

Tất cả thư mục sau nằm tại `D:\TDP_RAILWAY_PRIVATE\evidence`, ngoài Git:

- `full-audit-regression-01`: **576/576**, không lỗi/không bỏ qua; chạy trên source trước các sửa mới trong lượt rà này.
- `full-audit-browser-01`: lượt 1, 3, 4, 5 đạt. Lượt 2 dừng vì tìm hộp sửa cũ; cập nhật rồi `full-audit-browser-02/round2` đạt.
- `full-audit-extra-02/order_price` và `outgoing_readiness` đạt; `full-audit-quote-03/quote_ui` đạt. Các lượt trước lưu nguyên kết quả không đạt do kỳ vọng UI cũ.
- `full-audit-worksheet-02`: bằng chứng tái hiện lỗi `0,855 → 855`. `full-audit-worksheet-04`: đạt sau sửa, gồm nhập/dán lượng lẻ và các tình huống mạng/xung đột; không có JavaScript exception. Lượt 03 qua phần số lượng nhưng dừng do công cụ bấm nút đúng lúc màn gốc đang vẽ lại; đã sửa cách chờ/bấm trong cùng bước.
- `full-audit-hosted-ui-02/round5`: kiểm tra giao diện hosted trên DB thử, có hướng dẫn backup đúng và không hiện điều khiển máy in Windows.
- `full-audit-worksheet-edge-01`: bảng sửa đơn đạt trên Edge, gồm các tình huống lưu/xung đột và lượng lẻ.
- `full-audit-targeted-03`: **135/135** bài chịu ảnh hưởng đạt sau sửa giao diện hosted và nhập lượng.
- `inventory-footer-browser-02`: đạt toàn lượt hóa đơn/kho và tình huống 240 mã/24 ĐVT của footer; `inventory-footer-tests-01`: **45/45** bài kho/xuất file/hợp đồng UI đạt. Không cộng các lần chạy lại thành số bài độc lập.
- `full-audit-hosted-before`: snapshot trước rà; toàn vẹn SQLite đạt. Lượt hosted ban đầu `full-audit-hosted-01` không có yêu cầu ghi ngoài ý định hay lỗi máy chủ; chưa dùng lượt này để xác nhận bản sửa mới đã triển khai.

Kết quả triển khai và đối chiếu cuối lượt được bổ sung sau khi kiểm tra xong.

## Điều chưa được chứng minh bằng lượt rà này

- Không cam kết mọi tình huống tương lai đều không lỗi. Đã rà các màn và các tình huống nêu trên; không ký/phát hành hóa đơn, ghi thu/trả tiền hoặc chạy máy in vật lý của khách để thử.
- Production vẫn có dữ liệu chưa xử lý: 45 dòng lỗi trong đơn cũ; 1.104 dòng đầu vào cần ghép/xử lý; đầu ra 232 hóa đơn cần kiểm tra và 18 cần ghép mã. Màn kho báo 4 mã tồn cuối âm/cần kiểm tra từ dữ liệu hiện có. Lượt này giữ nguyên dữ liệu và cơ chế chặn, không tạo tồn bù hoặc đoán mapping.
- 576 bài đạt không chứng minh đã khớp toàn bộ sổ thuế thật. Nguồn đầu ra vẫn là tài khoản chủ dự án đã chọn tại README mục 13.16. Các giấy tờ thiếu điều kiện phải hiển thị lý do và chờ xử lý đúng dữ liệu.
- Viewer chung của các bảng là phần đang hiển thị; cần chọn bộ lọc/trang ở màn gốc. Orders và NXT có nguồn đầy đủ trong phạm vi riêng. Không coi viewer chung là trình sửa mọi báo cáo.
