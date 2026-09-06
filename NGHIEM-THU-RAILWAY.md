# Kiểm tra nghiệm thu trên Railway

Ứng dụng: https://tdp.up.railway.app/login

Khi đổi domain Railway, cập nhật `TDP_TRUSTED_HOSTS` thành hostname mới (không kèm `https://` hoặc đường dẫn), triển khai lại rồi kiểm tra đăng nhập. Đổi phần Public Networking riêng lẻ chưa cập nhật cấu hình của tiến trình đang chạy.

Checklist khách hàng: https://docs.google.com/spreadsheets/d/1c1C4Imexri4VRolrNSSmWmSnpmM0hgj0TCCbm9if3D8/edit?gid=1127847104

Ngày kiểm tra: 05/09/2026. Kết quả kỹ thuật dưới đây không thay cho xác nhận của khách trong Google Sheet. Tài khoản đăng nhập được bàn giao riêng; tài liệu này không chứa mật khẩu hoặc khóa kết nối.

## Trình tự khách kiểm tra

Các thao tác ghi tiền, ghi kho, chốt kỳ cần dùng bộ dữ liệu thử riêng hoặc dữ liệu nghiệp vụ đã được người phụ trách xác nhận. Kiểm thử tự động đã dùng cơ sở dữ liệu riêng.

| Mục | Thao tác và tiêu chí kiểm tra | Bằng chứng kỹ thuật |
|---|---|---|
| 1. Đơn hàng | Lọc dòng lỗi, tìm hàng, cuộn bảng. Tiêu đề giữ vị trí; tổng phản ánh đúng các dòng đang lọc. | Kiểm thử nghiệp vụ và trình duyệt lượt 2. |
| 2. Nhà cung cấp | Chọn NCC, sao chép đơn, kiểm tra đánh dấu đã đặt sau khi sao chép thành công; mở lại khi cần. | Lượt 2; kiểm tra thêm file đặt hàng 03/09 trên bản sao DB. |
| 3. Menu | Chuyển các màn hình đang sử dụng; không còn menu thừa đã thống nhất. Dữ liệu cũ không bị xóa. | Lượt 5; kiểm tra các bảng nghiệp vụ trước/sau triển khai. |
| 4. Xem chứng từ | Mở phiếu giao, bảng kê/biên nhận, báo giá, hồ sơ thanh toán. Xem trực tiếp, đổi sheet, cuộn và thu/phóng. | Lượt 4; xuất Excel và PDF phiếu giao thật trên Railway. |
| 5. Chọn và in nhiều | Lọc bếp/ngày, chọn một hoặc nhiều phiếu, bỏ chọn, xem trước và in. Chỉ những sheet được chọn mới xuất. | Lượt 4; kiểm tra riêng bộ chuyển PDF Linux. |
| 6. Nội dung phiếu | Đối chiếu đơn vị, thông tin đơn vị mua/bán, địa chỉ, người nhận, chữ ký và tổng tiền làm tròn. | Kiểm thử mẫu chứng từ; PDF A4 và ảnh từng trang. |
| 7. Hóa đơn đầu vào | Chọn 01–31/08/2026, tải nguồn. Mã khớp duy nhất được tự ghép; phần cần chọn mã/quy đổi nằm đầu bảng, tiếp theo là xác nhận ghi kho, phần đã xong nằm dưới. | Đã áp dụng tự ghép trên Railway: 941/1.104 dòng, 171 hóa đơn đủ mã, còn 163 dòng. Tổng 266 hóa đơn và tiền nguồn giữ nguyên. |
| 8. Hóa đơn đầu ra | Dùng tài khoản hiện tại theo lựa chọn của chủ dự án ngày 06/09, chọn đúng kỳ, tải M-Invoice; khi báo còn dữ liệu, tải tiếp. Chỉ xác nhận xuất kho khi hóa đơn đủ điều kiện. | Phân trang, trạng thái và chống trùng đạt trên dữ liệu thử. Tài khoản hiện tại được cho phép sử dụng; hệ thống vẫn hiển thị đúng môi trường nhà cung cấp. |
| 9. Tồn hóa đơn | Với bộ thử thiếu hàng: phân bổ phần có, giữ phần thiếu cho vòng sau, kiểm tra không âm tồn. | Lượt 1 và các bài kiểm thử kho/phân bổ. |
| 10. Chốt tháng | Chốt, kiểm tra tồn chuyển kỳ sau; mở lại rồi chốt lại. Không sinh bản chuyển tồn trùng. | Lượt 1; kiểm thử chốt/mở/chốt và khóa kỳ. |
| 11. Báo cáo tháng | Lọc tháng, nhà thầu, bếp; thêm bếp ở dữ liệu thử rồi đối chiếu tổng và cột động. | Lượt 3 và kiểm thử báo cáo. |
| 12. Phải trả NCC | Kiểm tra bảng 14 cột, xuất file, ghi trả một phần/đủ, hoàn tác; kiểm tra số dư và lịch sử. | Lượt 3; các bài kiểm thử sổ phải trả và phân bổ thanh toán. |
| 13. Phải thu | Lọc nhà thầu/bếp/tháng, kiểm tra tổng, ghi nhận thu và lịch sử trên bộ thử. | Lượt 3; kiểm thử sổ phải thu và chống ghi trùng. |
| 14. Lưu và sao lưu | Lưu thay đổi, tải lại trang, kiểm tra trạng thái sao lưu; tải bản sao lưu và kiểm tra khả năng đọc. | Lượt 5; sao lưu SQLite thật trước/sau triển khai đều kiểm tra toàn vẹn đạt. |

## Nạp bản đầu và cập nhật đơn trong ngày

1. Vào **Nhập & sửa đơn**, chọn file đầu ngày hoặc file chuẩn bị tối hôm trước. Hệ thống dùng ngày nghiệp vụ xác định trong file; bản đầu còn thiếu được lưu nháp và hiện lỗi.
2. Chọn **Nạp bản mới** hoặc **Chọn file đơn hàng khác** để tải bản hoàn thiện của cùng ngày. Bản hợp lệ cập nhật dữ liệu đang dùng, kể cả ô đã sửa trên web. File sai ngày, lỗi bắt buộc hoặc vướng chứng từ sẽ có thông báo và giữ dữ liệu cũ.
3. Có thể lặp nhiều lần. Nạp cùng file không nhân đôi; nạp mới không tự duyệt/chốt giao. Khi đủ dữ liệu, đóng bảng rồi dùng nút duyệt/chốt tương ứng.
4. Mở **Sửa nhanh cả bảng** hoặc **Mở bảng Excel · tự lưu**: chọn ô, sửa rồi Enter/Tab; có thể dán nhiều ô. Đợi **Đã lưu**. Sửa giá bán cần người sửa và lý do ở thanh trên.
5. Mạng lỗi: giữ bảng đang mở, bấm **Thử lưu lại**. Nếu người khác đã sửa cùng dòng, dùng **Đọc lại / đối chiếu** để tải phần chưa lưu rồi mở bản mới nhất. X chỉ đóng sau khi lưu được.
6. Bảng báo cáo có nút xem toàn màn hình và X quay lại. Đơn hàng và nhập–xuất–tồn lấy toàn bộ dòng trong phạm vi; bảng khác ghi **phần đang hiển thị**, cần chọn bộ lọc/trang ở màn gốc. Ghi kho, thanh toán, duyệt, chốt và in vẫn dùng màn nghiệp vụ.
7. Số lượng nhận dấu phẩy hoặc dấu chấm thập phân, ví dụ **0,855** hoặc **0.855**. Khi dán nhiều dòng cũng giữ lượng lẻ. Đợi **Đã lưu** rồi đối chiếu lại dòng nếu vừa nhập lượng quan trọng.
8. **Chỉ dòng có lỗi được tô đỏ cả dòng**, áp dụng chung cho các file. Bấm **Tới dòng lỗi** để đến vị trí cần sửa. Sau khi lưu xác nhận đã hết lỗi, dòng tự hết đỏ; dòng chỉ có cảnh báo vẫn hiện nội dung cảnh báo riêng và không tô đỏ.

Tại **Báo cáo vật tư hàng hóa**, bấm số ĐVT trên thẻ tổng lượng hoặc dòng tổng cố định để xem lượng tách theo đơn vị. File kho có nhiều ĐVT cũng có sheet **Tổng ĐVT**. Ô **CẦN KIỂM TRA** phải được đối chiếu trước khi chốt; không tự thay số âm thành 0.

Kết quả đối chiếu số liệu từng màn/file và phần dữ liệu còn mở ngày 06/09: [DOI-CHIEU-SO-LIEU-20260906.md](DOI-CHIEU-SO-LIEU-20260906.md).

## Dùng bản web trên máy tính

- Tại **In giấy tờ**, chọn phiếu rồi bấm **In phần đã chọn**. Chọn máy in và số bản trong hộp thoại của trình duyệt/PDF. Nếu hộp thoại chưa bật, dùng nút máy in trên PDF hoặc tải PDF về máy để in.
- Dữ liệu nằm trên hệ thống trực tuyến. Đóng trình duyệt không dừng lịch sao lưu của dịch vụ đang chạy. Mở cùng địa chỉ và đăng nhập trên máy tính khác để tiếp tục.
- Kết quả rà từng màn, lỗi tìm được và giới hạn kiểm chứng được lưu tại [KIEM-TRA-MAY-TINH-20260906.md](KIEM-TRA-MAY-TINH-20260906.md). Các thao tác ghi nghiệp vụ trong đợt rà dùng dữ liệu thử riêng.

## Hồ sơ người bán Đoàn Văn Giang

Theo xác nhận khách ngày 06/09, mở lại **Đoàn Văn Giang** trong lựa chọn người bán và bảng kê/biên nhận; **Nguyễn Văn Toại vẫn bị loại** khỏi chứng từ mới. Trạng thái triển khai và bằng chứng tại [README-new-2.md, mục 13.25](README-new-2.md#1325-mở-lại-đoàn-văn-giang-theo-hồ-sơ-khách-xác-nhận--06092026).

Chọn Giang ở dòng cần lập bảng kê, mở **Xem bảng kê và biên nhận**, rồi chọn sheet biên nhận để đối chiếu hồ sơ. Giữ số giấy tờ có số 0 đầu, ngày cấp 28/05/2018, nơi cấp Cục cảnh sát và địa chỉ đúng hồ sơ Giang. Bộ có cả Toại chỉ lập phần hợp lệ và báo phần bị loại; dữ liệu lịch sử của Toại vẫn còn. Giá mua, lượng và các điều kiện chứng từ khác vẫn phải hợp lệ.

## Ghép mã hóa đơn đầu vào tháng 8

1. Vào **Hóa đơn đầu vào + đầu ra**, chọn **Hóa đơn đầu vào**, từ ngày 01/08/2026 đến 31/08/2026.
2. Khi **Tải/tiếp tục đầu vào**, hệ thống tự ghép tên duy nhất và cùng ĐVT; không hỏi xác nhận lại mã khớp chắc chắn.
3. Nếu có bảng kê nhập cũ: mở **Tự ghép mã từ bảng kê nhập cũ**, chọn file rồi bấm **Tự ghép từ file cũ**. Hệ thống đối chiếu MST, số hóa đơn, tên, lượng, tiền, mã và ĐVT; lưu phần đủ căn cứ rồi ghép tiếp theo danh mục trong cùng lần xử lý. Các mã/quy đổi đã chọn được giữ nguyên.
4. **Tự ghép mã trùng khớp** dùng khi muốn xử lý tiếp sau khi bổ sung danh mục. Bấm lại không tạo thêm mapping hay lịch sử nếu không có gì mới. Các quy tắc được nhớ cho cùng NCC/mã nguồn/tên/ĐVT ở những kỳ chưa ghi kho.
5. Chỉ phần không khớp duy nhất, thiếu mã hoặc cần hệ số quy đổi mới để người dùng xử lý trên đầu bảng. Tiếp theo là hóa đơn đủ mã chờ **Xác nhận nhập cả hóa đơn**; phần đã xử lý xong nằm dưới. Xác nhận nhập kho là bước ghi sổ riêng, không phải xác nhận lại từng mã đã tự ghép.

Ngày 06/09 đã áp dụng trên Railway: **941/1.104 dòng đã ghép, 171/264 hóa đơn sẵn sàng, còn 163 dòng thuộc 93 hóa đơn cần xử lý**. Khách không phải chạy lại phần này. 111 quy tắc đã ghép tổng cộng 9.193 dòng cùng nguồn ở các kỳ chưa ghi kho. Có sao lưu trước/sau, kết quả mapping khớp bản sao đã kiểm chứng; tổng 266 hóa đơn và 919.234.874 đồng giữ nguyên. Chưa ghi kho trong lượt tự ghép.

## Lập hồ sơ thanh toán từ hóa đơn VAT

1. Vào **Chứng từ**, chọn nhà thầu, từ ngày và đến ngày độc lập với đơn đang mở.
2. Mở **Hồ sơ người mua**, nhập đúng tên pháp lý, MST và địa chỉ; lưu. Không cần tạo dự thảo hóa đơn để khai báo hồ sơ.
3. Kiểm tra thông tin công ty, người đề nghị và tài khoản nhận tiền trong cấu hình chứng từ.
4. Tải hóa đơn đầu ra đúng kỳ ở màn hình hóa đơn. Các lượt tải còn dữ liệu được tiếp tục từ vị trí đã lưu.
5. Bấm **Xem và tải bảng kê**. Hệ thống đối chiếu số/ký hiệu/ngày, MST, trạng thái nguồn, chi tiết và tổng tiền trước khi cho xuất.
6. Với hóa đơn chưa liên kết ngày giao/bếp, file là **bảng kê hóa đơn VAT**. Chứng từ không tự tạo lịch sử giao nhận. Hóa đơn bị hủy, thay thế, điều chỉnh hoặc sai tổng phải được đối chiếu trước.

## Dữ liệu cần người phụ trách xác nhận

- **Quyết định ngày 06/09: chủ dự án chỉ dùng tài khoản M-Invoice hiện tại.** Giữ nguyên URL/tài khoản, cho phép sử dụng qua `MINVOICE_ALLOW_TEST_ENVIRONMENT=true`; không còn yêu cầu đổi tài khoản như điều kiện bàn giao. Máy chủ `0106026495-999.minvoice.site` vẫn được nhận diện là môi trường kiểm thử của nhà cung cấp; lựa chọn này không thay đổi môi trường thực tế hoặc tự xác nhận tính hợp lệ của từng hóa đơn.
- File `Đơn hàng  03.09.2026.xlsx`: đã chốt hai khoản mua hộ do hàng hỏng **117.000 + 90.000 = 207.000 đồng trừ công nợ Phong**, doanh thu/lượng bán giữ nguyên. Xem hướng dẫn phần Phong bên dưới; không còn chờ xác nhận cách tính hai khoản này.
- **Tổng đủ 266 hóa đơn đầu vào**, gồm **171 đủ mã, 93 còn cần xử lý và 2 không nhập tồn**. Trong 1.107 dòng hàng, 941 dòng đã tự ghép, 163 dòng còn thiếu căn cứ và 3 dòng không nhập tồn. Phần còn lại được đưa lên đầu bảng; không yêu cầu khách xác nhận lại 941 mã đã tự ghép.
- Bản production tại lúc kiểm tra chưa có hồ sơ MST bên mua và chưa có hóa đơn đầu ra đã đồng bộ. Form hồ sơ độc lập đã được bổ sung; không tự đoán MST hoặc liên kết hóa đơn với nhà thầu.
- Không thực hiện ký/phát hành hóa đơn thật hoặc ghi thanh toán thật trong lượt kiểm thử này.

## Bằng chứng và tái kiểm tra

Tại **Báo cáo vật tư hàng hóa → Chi tiết Nhập – Xuất – Tồn**, bấm **Xem bằng Excel · toàn màn hình** ngay cạnh tiêu đề để xem bảng rộng. Dòng **TỔNG** vẫn cố định khi cuộn; bấm nút số **ĐVT** để xem tổng tồn đầu, nhập, xuất, tồn cuối theo từng đơn vị. Tổng tiền nằm trên một dòng. Nút tải Excel theo kỳ vẫn ở phần đầu màn hình.

Chi tiết sửa và kết quả mới nhất ở mục **13.24 của README-new-2.md**. Bằng chứng riêng nằm trong `D:\TDP_RAILWAY_PRIVATE\evidence`; không đưa dữ liệu hóa đơn, bản sao DB hoặc thông tin đăng nhập vào Git.

```powershell
python -m tdp_system.qa_railway_acceptance --output THU_MUC_MOI
python -m tdp_system.qa_browser_rounds --output THU_MUC_MOI
```

Khách đánh dấu kết quả thực tế ở checklist sau khi thử từng mục. Các điểm phụ thuộc dữ liệu phía trên cần được giải quyết trước khi xác nhận nghiệm thu toàn bộ.

## Trừ tiền mua hộ cho Phong ngày 03/09

1. Nạp đơn ngày 03/09 tại **Công việc hằng ngày**. Chế độ nhập liên tục nhận phần đơn bán; phần mua được xử lý riêng bên dưới.
2. Chọn phiên 03/09, vào **Đặt hàng nhà cung cấp → Chỉnh số lượng và giá mua bằng Excel → Chọn file đã chỉnh**, chọn đúng file khách `Đơn hàng  03.09.2026.xlsx` rồi xác nhận phần mua sau khi hết lỗi.
3. Hai dòng dưa hấu/nhãn đã chốt được nhận thành **Trừ tiền mua hộ do hàng hỏng**: lượng 0, tiền −117.000 và −90.000 đồng. Thiếu mã ở khoản tiền nhãn không tạo hàng tồn hoặc tự sinh mã mới. Các dòng âm khác vẫn bị kiểm tra như trước.
4. Sau khi đơn được duyệt, vào **Công nợ → Phải trả**, lọc 03/09–03/09 và NCC **phong**. Trên bản sao đúng file khách: tiền hàng 997.040đ, trừ 207.000đ, còn 790.040đ. Excel phải trả giữ 14 cột và cùng tổng tiền. Khoản trừ không phải khoản thanh toán; không chọn nó để ghi trả tiền.
5. Nạp lại cùng file không trừ thêm. File NCC tải ra giữ khoản trừ bằng số tiền trực tiếp và cột **Loại dòng**; nếu chỉnh khoản tiền này, giữ lượng/giá/các cột điều chỉnh bằng 0 và nhập thành tiền âm. Giữ nguyên lịch sử các lần sửa.

Lượt triển khai chức năng không tự nạp hoặc duyệt đơn 03/09 lên production. Số 790.040đ là kết quả kiểm chứng trên bản sao, chưa phải số dư Phong đã ghi trên Railway. Bốn mã tồn đầu âm tiếp tục chờ khách chốt.
