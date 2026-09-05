# GHI CHÚ NGHIỆP VỤ TĐP – PHẠM VI HỢP ĐỒNG ĐÃ CHỐT

> Trạng thái: **ĐÃ HOÀN TẤT PHẠM VI HỢP ĐỒNG HIỆN TẠI; source, kiểm thử, QC, browser, smoke source/EXE và gói portable cuối đã đạt; xem bằng chứng phát hành tại mục 27. Lịch sử phân tích bên dưới được giữ để truy vết**.
>
> File này là nguồn ghi nhớ nghiệp vụ đã đối soát cho đợt triển khai hiện tại. Các kết luận mới hơn, đặc biệt mục 26, có quyền đính chính những giả định thận trọng trước đó; không được biến giả định cũ thành câu hỏi bắt khách trả lời lại.

Nguồn đã phân tích:

- `File 1 (253 Phu Thuong Doan Lane 6.m4a)`
- `File 2 (253 Phu Thuong Doan Lane 7.m4a)`
- Bản chép lời: `C:\Users\DELL\.codex\attachments\c6da20bf-9ecf-499d-bdd8-db75c9f057f1\pasted-text.txt`

## 1. Ranh giới nguồn dữ liệu đã làm rõ

| Nghiệp vụ | Nguồn dữ liệu đúng theo cuộc trao đổi |
|---|---|
| Công nợ phải thu để chốt/đối soát vận hành với khách | Đơn hàng khách theo ngày, cộng dồn theo từng nhà thầu |
| Đề nghị thanh toán và phải thu thể hiện trên giấy tờ chính thức | Hóa đơn đỏ đầu ra đã phát hành |
| Công nợ phải trả nhà cung cấp | Số lượng đặt/mua thực tế × giá mua đã chốt |
| Phiếu giao và doanh thu vận hành | Đơn hàng và lượng thực giao |
| Trừ kho hóa đơn/sổ sách | Hóa đơn đỏ đầu ra, không trừ trực tiếp theo đơn giao |
| Nhập kho hóa đơn/sổ sách | Hóa đơn đầu vào sau ghép mã và xử lý đơn vị tính |
| Giá bán khi dùng hàng thay thế | Giá bán đúng kỳ/bảng báo giá, không lấy giá nhập trong kho |

Lưu ý chống hiểu nhầm:

- Ban đầu khách có nói phải thu ở “bảng đặt hàng”, nhưng phần giải thích sau đã chốt phải thu vận hành lấy từ **đơn hàng khách**; phải trả mới lấy từ **đặt hàng NCC**.
- Công nợ vận hành và đề nghị thanh toán chính thức là hai góc nhìn khác nhau, không được trộn nguồn.
- “Triệt tiêu” công nợ đã trả có nghĩa là loại khỏi danh sách đang còn phải trả nhưng vẫn giữ lịch sử, không xóa chứng từ.

## 2. Luồng dữ liệu hai lần mỗi ngày

### Lần thứ nhất – tối hôm trước

Nạp dữ liệu để:

1. Soạn hàng.
2. In phiếu giao.
3. Tạo danh sách đặt NCC.

### Lần thứ hai – ngày hôm sau

Sau khi có đủ giá mua, giá bán và số lượng thực tế, nạp/chốt lại để:

1. Chốt doanh thu.
2. Chốt giá vốn và lợi nhuận.
3. Chốt phải thu vận hành.
4. Chốt phải trả NCC.
5. Cộng dồn dữ liệu vào sổ tháng.

Yêu cầu an toàn:

- Lần nạp sau phải cập nhật đúng ngày/batch cũ, không tạo dữ liệu trùng.
- File đặt NCC lần hai không được tự ý sửa đơn khách, lượng giao, doanh thu hoặc phải thu.
- Nếu cần cập nhật giá bán/doanh thu từ workbook ngày hoàn chỉnh thì nên có luồng “chốt dữ liệu ngày” riêng; file đặt NCC chỉ chốt phần mua và phải trả.

Điểm này cần tiếp tục nghe phần hội thoại sau để xác định chính xác khách muốn nạp lại toàn bộ file `Em Thành` hay chỉ file đặt NCC đã xuất từ hệ thống.

## 3. Báo giá

- Cần luồng/nút nạp báo giá riêng, không phụ thuộc file đơn hàng hằng ngày.
- Có thể nạp báo giá tại một ngày bất kỳ.
- Thông thường ngày 25 đã phải chuẩn bị báo giá cho kỳ/tháng sau, trong khi đơn hàng ngày 25 vẫn dùng giá của tháng hiện tại.
- Báo giá phải có kỳ hiệu lực và phiên bản điều chỉnh.
- Từ bảng báo giá tổng phải tạo được báo giá riêng theo từng nhà thầu/nhánh.
- Giá mua có sẵn từ báo giá được ưu tiên; giá còn thiếu được bổ sung khi có dữ liệu mua thực tế.

## 4. Đặt hàng nhà cung cấp

- Người dùng vẫn tự kiểm tra tồn tủ/kho vật lý và tự sửa lượng cần mua thực tế.
- Danh sách đặt hàng phải theo từng NCC; cách gộp phải giữ đúng quy tắc đã chốt.
- Ảnh gửi NCC chỉ nên có các thông tin thật sự cần để đặt hàng; không đưa các cột nội bộ dễ gây hiểu nhầm.
- Khách không muốn ảnh gửi NCC hiện dòng “tổng cần mua sau trừ tồn” hoặc dữ liệu thừa.
- Màn hình phải phân biệt rõ NCC nào chưa xử lý, NCC nào đã đặt xong để tránh bỏ sót.
- Khi đánh dấu nhầm phải hoàn tác được; không được làm dữ liệu biến mất vĩnh viễn.
- Có thể dùng tư duy checklist/đã xử lý/chưa xử lý tương đương cách khách đang bôi màu và lọc thủ công.

Đây là yêu cầu rủi ro vận hành rất cao: khách nói sót một mặt hàng có thể gây thêm chuyến xe, phải mua lẻ giá cao, chậm sản xuất và có nguy cơ bị phạt 25% đơn hàng.

## 5. Công nợ phải trả

- Phải xem theo từng NCC.
- Có chi tiết theo ngày, bếp, mặt hàng, số lượng, đơn giá và thành tiền để kế toán đối chiếu từng dòng.
- Có tổng hợp cả tháng và bảng/sheet chi tiết riêng từng NCC.
- Không chỉ hiển thị một con số tổng.
- Cần thao tác `Đã thanh toán` kèm ngày thanh toán và lịch sử.
- Khoản đã thanh toán được ẩn khỏi góc nhìn “còn phải trả”, nhưng vẫn phải tra cứu lại được để trả lời đã thanh toán ngày nào.
- Cần tiếp tục chốt việc thanh toán toàn bộ hay một phần, phạm vi theo ngày, phương thức và mã tham chiếu.

## 6. Công nợ phải thu và đề nghị thanh toán

- Phải thu vận hành lấy từ đơn hàng khách, theo từng nhà thầu và cộng dồn theo ngày/tháng.
- Dữ liệu dùng để chốt thực tế với khách có thể khác số liệu trên hóa đơn do xuất hóa đơn nhiều đợt hoặc thiếu đầu vào.
- Đề nghị thanh toán và giấy tờ gửi khách phải dựa trên hóa đơn đỏ đầu ra đã phát hành.
- Không dùng file đặt NCC để sửa phải thu.

## 7. Phiếu giao

- Tách phiếu theo từng bếp.
- Chữ phải đủ lớn để dùng thực tế.
- Riêng bếp Nhựa thể hiện giá bán.
- Các bếp còn lại không thể hiện giá bán, chỉ giữ thông tin giao hàng cần thiết.
- Cần xác định chính xác mã/tên bếp Nhựa để không áp dụng theo so khớp tên mơ hồ.

## 8. Giá bán chỉnh nhanh

- Giá bán phải sửa trực tiếp được trên bảng khi chỉ phát sinh một vài dòng.
- Ví dụ hàng không đủ chất lượng thì giá thực tế có thể giảm so với bảng báo giá.
- Không bắt người dùng sửa và nạp lại toàn bộ bảng báo giá chỉ vì một hoặc hai dòng ngoại lệ.
- Thay đổi phải có nguồn gốc/audit và không được ghi ngược làm sai bảng giá chuẩn của cả kỳ nếu đây chỉ là giá ngoại lệ của một giao dịch.

## 9. Hóa đơn đầu vào và quy đổi đơn vị

- Hóa đơn đầu vào phải có mã hàng hoặc được ghép mã trước khi vào kho.
- Phải so sánh đơn vị tính trên hóa đơn với đơn vị nhỏ nhất trong danh mục nội bộ.
- Ví dụ NCC xuất `1 thùng` nhưng kho quản lý `gói`; người dùng cần quy đổi như `1 thùng = 30 gói`.
- Cần cho phép người dùng sửa/nhập hệ số quy đổi và tính lại số lượng, đơn giá kho.
- Không tự đoán hệ số quy đổi.
- Việc quy đổi phải lưu dấu vết để kiểm tra lại.

## 10. Hóa đơn đầu ra nhiều đợt

- Nguồn dự kiến xuất hóa đơn vẫn bắt đầu từ đơn hàng/lượng thực giao.
- Dòng nào đủ tồn hóa đơn thì đưa vào bảng dự kiến xuất.
- Dòng chưa đủ tồn tiếp tục để lại chờ hóa đơn đầu vào.
- Cho phép xuất một phần: cần 10 nhưng kho có 7 thì được lập vòng đầu 7; phần 3 còn lại chờ vòng sau.
- Mẫu tải hóa đơn cũ được khách nói là sai và khách đã gửi lại mẫu; cần xác định đúng file mới trước khi sửa.
- Hệ thống chỉ tạo dữ liệu/draft; không tự ký hoặc phát hành.

## 11. Hàng thay thế khi thiếu đầu vào

- Hệ thống có thể xuất danh sách mặt hàng chưa có đầu vào và giá trị đang thiếu.
- Người dùng tự chọn mặt hàng thay thế từ kho/danh mục, có mã hàng rõ ràng.
- Không tự động suy đoán rau muống phải thay bằng bắp cải hoặc một mặt hàng cụ thể khác.
- Mặt hàng thay thế dùng giá bán đúng kỳ/nhà thầu; giá trong kho chỉ là giá nhập, không phải giá bán.
- Cần lưu lựa chọn và xác nhận của người dùng cho từng lần thay thế.

## 12. Chứng từ chính thức và kho hóa đơn

- Đề nghị thanh toán, bảng kê và chứng từ chính thức phải chạy từ hóa đơn đỏ đầu ra.
- Kho hóa đơn/sổ sách cũng phải trừ theo hóa đơn đỏ đã phát hành.
- Không trừ kho hóa đơn chỉ vì đã có đơn đặt, đơn giao hoặc draft chưa phát hành.
- Cần duy trì ranh giới rõ giữa vận hành thực giao và kế toán/hóa đơn.

## 13. Dùng nhiều máy và hosting

- Hiện hệ thống local/LAN không tự trở thành hệ thống dùng từ xa chỉ vì dữ liệu nằm trong Google Drive.
- Google Drive không phải mạng LAN và không nên chứa file SQLite đang được nhiều máy mở trực tiếp.
- Nếu máy kho/chợ và máy văn phòng không cùng LAN, cần máy chủ/hosting tập trung.
- Trước khi triển khai phải chốt người dùng, vai trò, phân quyền, domain, HTTPS, backup, phục hồi, chi phí và trách nhiệm vận hành.
- Câu nói “đầu tư luôn” trong hội thoại mới chỉ là đồng ý về ý tưởng/chi phí sơ bộ, chưa đủ thông tin kỹ thuật để tự triển khai.

## 14. AI và tự động hóa

- In một nút, tạo file và tạo draft hóa đơn là tự động hóa thông thường, không phải AI.
- AI nếu làm sau chủ yếu phục vụ đọc tin nhắn/ảnh đơn hàng từ Zalo và hỗ trợ nhận diện dữ liệu.
- Không tự gửi Zalo, tự thay mặt hàng, tự ký hoặc tự phát hành hóa đơn khi chưa có phạm vi và xác nhận riêng.

## 15. Đối chiếu sơ bộ với source tại thời điểm trước triển khai (lịch sử)

Các phần hiện đã cùng hướng với yêu cầu mới:

- Round-trip file đặt NCC 13 cột.
- Người dùng tự sửa tồn tủ, lượng mua, NCC và giá mua.
- File đặt NCC không sửa đơn khách/doanh thu/phải thu.
- Công nợ NCC theo lượng mua thực tế và giá mua chốt.
- Xuất hóa đơn nhiều vòng theo tồn.
- mSMI, ghép mã và draft hóa đơn an toàn.
- Máy in A4/A5 đã nghiệm thu.
- Kho vật lý vẫn do người dùng tự kiểm tra.

Tại thời điểm ghi nhận ban đầu, các phần dưới đây từng cần tiếp tục kiểm tra; trạng thái hiện hành đã được thay thế bởi các mục 24–27:

1. Luồng chốt/nạp dữ liệu ngày lần hai.
2. Báo giá độc lập theo kỳ, phiên bản và nhà thầu.
3. Công nợ NCC chi tiết và trạng thái thanh toán có lịch sử.
4. Checklist NCC đã đặt/chưa đặt và khả năng hoàn tác.
5. Quy đổi đơn vị hóa đơn đầu vào.
6. Quy tắc phiếu giao riêng cho bếp Nhựa.
7. Ranh giới chứng từ vận hành và chứng từ theo hóa đơn đỏ.
8. Kiến trúc dùng từ xa/hosting.

## 16. Quy tắc cập nhật file này

- Khi có phần hội thoại tiếp theo, đọc hết rồi bổ sung vào file này.
- Phân biệt rõ: khách đã chốt, khách đang nêu ví dụ, người triển khai đang đề xuất và nội dung còn mâu thuẫn.
- Nội dung mới hơn và lời xác nhận rõ ràng hơn được ưu tiên, nhưng không xóa lịch sử mâu thuẫn; phải ghi chú cách hiểu cuối.
- Lệnh triển khai đã được người dùng ban hành sau phần thu thập; xem trạng thái hiện hành ở cuối file.

## 17. Bổ sung từ `Note công việc.docx` ngày 02/09/2026

Nguồn mới:

- File: `C:\Users\DELL\Downloads\Note công việc.docx`.
- Thời điểm sửa file: 02/09/2026 09:40:37.
- Đã đọc đủ 19 đoạn yêu cầu và 15 ảnh nhúng.
- Đây là tài liệu khách tự viết sau buổi trao đổi nên được coi là nguồn chốt có trọng lượng cao hơn các câu trao đổi miệng còn mơ hồ. Tuy vậy, các chỗ phụ thuộc ảnh bị cắt tiêu đề hoặc câu chữ chưa rõ vẫn phải đánh dấu cần xác nhận, không tự suy diễn.

### 17.1. Báo giá

Khách yêu cầu cụ thể:

1. Có nút tải báo giá lên riêng.
2. Tách báo giá theo từng nhà thầu và đúng mẫu khách đã gửi.
3. Bỏ các dòng có dấu `X` hoặc dòng không được xuất.
4. Các dòng trùng phải xử lý theo mã hàng, tránh xuất trùng; câu “trùng nhau thì chỉ lấy mã” cần đối chiếu file mẫu để chốt chính xác cách gộp.
5. Sắp xếp mã hàng theo thứ tự A–Z.
6. Hết mỗi nhóm hàng phải có một dòng tên nhóm màu xanh như ảnh mẫu `GIA CẦM`.
7. Báo giá phải có giá/trạng thái theo đúng nhà thầu; không lấy nhầm cột giá của nhà thầu khác.

Ảnh khách gửi cho thấy màn `Báo giá theo nhà thầu`, nút `Xuất báo giá <nhà thầu>`, cột mã hàng, thuế và giá/trạng thái. Mẫu Excel có dòng phân nhóm nền xanh.

### 17.2. Phiếu giao

- Phiếu giao phải theo đúng mẫu trong file `Thành` vì bếp đã duyệt mẫu đó.
- Ảnh mẫu là `PHIẾU GIAO HÀNG (Kiêm phiếu xuất kho)`, có thông tin bên bán, đơn vị mua, địa chỉ giao, ngày, danh sách hàng, số lượng, đơn vị, đơn giá, thành tiền, ghi chú, tổng tiền và các vị trí ký.
- Cần giữ quy tắc đã nghe trong cuộc gọi: riêng bếp/nhà thầu Nhựa có giá bán; các bếp còn lại không hiện giá. Phải chốt bằng mã nhà thầu/bếp, không dò tên gần đúng.
- Yêu cầu “đúng mẫu đã duyệt” có ưu tiên cao hơn việc tự thiết kế lại giao diện hoặc mẫu in.

### 17.3. Đặt hàng NCC và chống bỏ sót

- Phải dùng phương pháp loại trừ/checklist: nhà nào đã đặt thì chuyển trạng thái rõ ràng, phần còn lại được sắp xếp để người dùng nhìn ngay các NCC chưa xử lý.
- Trạng thái đã đặt phải hoàn tác được nếu bấm nhầm; không xóa dữ liệu.
- Quy tắc dồn được khách ghi lại bằng văn bản:
  - Hoài: chỉ dồn mặt hàng `Cà rốt`.
  - Thu, Kỳ, Tân, Phượng, Dung và Kho: dồn các dòng có tên hàng giống nhau thành một dòng, số lượng bằng tổng các dòng.
  - Không tự mở rộng quy tắc dồn sang NCC khác.
- Ảnh/nội dung gửi Zalo cho NCC chỉ lấy đến cột `Ghi chú` theo ảnh mẫu, gồm tối thiểu: mã bếp, ngày, tên hàng, số lượng, ĐVT, NCC và ghi chú.
- Không đưa tồn tủ, giá mua, thành tiền hay các cột kiểm soát nội bộ vào ảnh gửi NCC nếu mẫu khách không yêu cầu.

### 17.4. Công nợ phải thu – cấu trúc file Excel

- Công nợ phải thu thực tế chốt với khách theo ngày.
- Phải tách theo từng nhà thầu và từng bếp.
- Cho phép kết xuất Excel tại bất kỳ thời điểm người dùng cần gửi đối soát.
- Mỗi file của một nhà thầu có cấu trúc:
  1. Sheet đầu tiên: công nợ tổng của nhà thầu.
  2. Các sheet liền kề: công nợ từng bếp thuộc nhà thầu đó.
- Không gộp dữ liệu nhiều nhà thầu vào một file đối soát nếu khách yêu cầu tách riêng.
- Phần này là công nợ vận hành từ đơn hàng/thực giao, không thay thế đề nghị thanh toán theo hóa đơn đỏ.

### 17.5. Công nợ phải trả – cấu trúc và thanh toán

- Phải chi tiết từng dòng, mặt hàng, ngày và NCC, đúng file mẫu khách gửi.
- Sheet `đặt hàng` trong file `Thành` là nguồn công nợ hằng ngày; mỗi lần chốt phải cộng dồn thành dữ liệu tháng và năm.
- Khi thanh toán được một NCC, khoản đó không còn xuất hiện trong bảng “còn phải trả”, nhưng vẫn giữ lịch sử thanh toán.
- Ảnh chỉ rõ màn `Báo cáo & công nợ`, vùng `Ghi nhận thu/chi`, nút `Lưu thanh toán` và bảng `Công nợ phải trả`.
- Không dùng thao tác xóa để “triệt tiêu”; phải dùng trạng thái/giao dịch thanh toán có ngày, số tiền, nội dung và audit.
- Nhận định “cần chốt thêm” ở thời điểm đọc Word đã được giải quyết: hệ thống cho chọn phạm vi, phân bổ thủ công từng dòng, trả một phần/toàn phần, lưu tham chiếu và hoàn tác có audit.

### 17.6. Dòng `BK`

- Các dòng có chữ `(bk)` được khách coi là mặc định có thể xuất.
- `BK` đồng thời là **đầu vào của Thành Đạt Phát**: đây là hàng mua vào theo bảng kê không có hóa đơn, tách khỏi hóa đơn đầu vào mSMI nhưng khi người dùng xác nhận import thì phải ghi tăng kho TĐP theo đúng mã hàng.
- Cờ nguồn đã xác định: sheet `BÁO GIÁ` dùng cột `bk` (cột H, kèm `Tên làm bảng kê` ở cột I); sheet ngày mang cột `Bảng kê` tương ứng. Giá trị `bk` là cờ chọn dòng, không phải một loại chứng từ còn phải hỏi lại.
- **Hệ thống phải cấp file mẫu BK để người dùng tải xuống và nạp lại**; câu “chị xin file mẫu” không có nghĩa khách còn nợ dự án một file BK thực tế.
- Giá nhập mặc định của dòng BK bằng **95% giá bán của chính dòng/kỳ tương ứng**. Người dùng vẫn phải được xem lại trước khi xác nhận; nếu không có giá bán hợp lệ thì chặn dòng đó thay vì tự bịa giá.
- Import phải bắt buộc mã TĐP, số lượng và nguồn tham chiếu; chống nhập trùng, có audit và chỉ ghi kho sau xác nhận rõ. Cờ `bk` không tự ký/phát hành hóa đơn và không được bỏ qua cổng không âm kho.

### 17.7. Hóa đơn đầu ra theo từng nhà thầu

- Nguồn chạy từ sheet đơn hàng ngày, khách dẫn ví dụ sheet ngày `28.07` trong file `Thành`.
- Phải tạo đúng mẫu tải hóa đơn khách gửi: thuế 8%, KKKNT, thuế 10% và các mẫu liên quan của cơ quan thuế.
- Tuyệt đối không âm kho.
- Mặt hàng còn bao nhiêu tồn hợp lệ thì được lập bấy nhiêu; phần chưa đủ tồn phải để lại.
- Phần chưa xuất được phải tách theo từng nhà thầu để vài ngày người dùng chạy lại; cuối tháng phần còn thiếu được tổng hợp để gửi khách xin luân chuyển/thay thế.
- Không gộp tất cả nhà thầu vì hóa đơn, bảng kê thuế và phần chưa xuất đều thuộc từng nhà thầu riêng.
- Đầu ra bắt buộc có mã hàng để ghi giảm kho chính xác.
- Cách hiểu này xác nhận luồng xuất hóa đơn nhiều vòng đang có trong source, nhưng bổ sung yêu cầu file/bảng chờ riêng từng nhà thầu và đúng mẫu thuế.

### 17.8. Kho hóa đơn, TĐK–NXT và giá bình quân

- Kho không được trừ theo bảng kê hoặc đơn giao.
- Khách yêu cầu trừ theo hóa đơn đỏ đã phát hành và kéo/đối chiếu từ hệ thống hóa đơn/cơ quan thuế: `Tồn + Nhập − hàng hóa trên hóa đơn đỏ`.
- Tên/màn kho khách muốn đổi thành `TĐK–NXT`. Golden chính thức cho hệ cột và hình thức là `_HANDOFF/EXTERNAL_INPUTS/TĐK T8-2026.xlsx thụy.xlsx`, sheet `Ton 7 (2)`; không cần đòi thêm một workbook có tên NXT.
- Phải có đủ:
  - File tồn đầu kỳ.
  - File nhập trong kỳ.
  - File xuất trong kỳ.
  - File NXT tổng hợp trong kỳ.
- Bốn file là một bộ chính thức dùng cùng kỳ, cùng danh mục/mã và cùng hợp đồng đối chiếu. File NXT được suy ra từ golden TĐK và sổ phát sinh, giữ các trường nhận diện `MÃ TĐP`, `TÊN TDP`, `Tên trên HĐ`, `MÃ KHO`, `T/Suất`, `ĐVT` cùng các khối số lượng–đơn giá–thành tiền.
- Bắt buộc đối chiếu từng mã và toàn bộ kỳ: `Tồn đầu + Nhập − Xuất = Tồn cuối`; Nhập/Xuất phải truy ngược được dòng nguồn, không trộn kho vận hành hoặc giá bán vào giá vốn.
- Giá trị kho/NXT dùng giá bình quân.
- Khi lấy hàng trong kho để xuất cho khách, giá bán phải lấy theo đúng thời điểm và đúng nhà thầu; không dùng giá vốn bình quân làm giá bán.
- Nguồn vận hành đã chốt là mSMI cho đầu vào và M-Invoice cho đầu ra. Adapter M-Invoice chỉ-read, phân loại trạng thái phát hành/nháp/hủy/thay thế/điều chỉnh, paging/cursor, idempotency và cổng ghi kho fail-closed đã được triển khai và kiểm chứng kỹ thuật; không hỏi khách lại về nguồn hay mẫu NXT.

### 17.9. Hóa đơn đầu vào mSMI – thao tác ghép mã

- Dòng chưa có mã phải được tô màu nổi bật để dễ phát hiện.
- Ô tìm/ghép mã phải dùng được bàn phím và phím `Enter`; không bắt buộc dùng chuột.
- Có filter để gom các dòng lỗi/chưa ghép/khác đơn vị lên cùng nhau.
- So sánh ĐVT hóa đơn đầu vào với ĐVT trong báo giá/danh mục.
- Dòng khác ĐVT phải được tô màu để người dùng chủ động quy đổi.
- Áp dụng kiểm tra cả với dòng khuyến mại.
- Đồng bộ hóa đơn phải chọn được khoảng `từ ngày – đến ngày`.
- Mapping và quy đổi đã sửa phải được ghi nhớ; khi đồng bộ lại cùng khoảng ngày, người dùng không phải sửa lần thứ hai.
- Không tự đoán mã hoặc hệ số quy đổi.

### 17.10. Đính chính phạm vi Xưởng cơm/PO và Chấm công/lương

Trong tài liệu Word, ảnh đi kèm câu “2 phần này không cần làm nữa” nằm cạnh hai menu `Xưởng cơm / PO` và `Chấm công & lương`, nên lần phân tích đầu đã hiểu rằng khách muốn tạm hoãn hai module này.

Ngày 02/09/2026, chủ dự án đính chính rõ: **cả `Xưởng cơm / PO` và `Chấm công & lương` vẫn phải có**.

Kết luận ưu tiên mới nhất:

- Hai module vẫn nằm trong phạm vi vận hành bắt buộc.
- Không ẩn, bỏ, xóa code hoặc ngừng duy trì hai module.
- Trong phạm vi hiện tại không cần xác định lại cụm “2 phần”: giữ đầy đủ Xưởng cơm/PO và Chấm công/lương; riêng `Phần làm thêm.docx` để sau.
- Không cần hỏi thêm “2 phần” trong phạm vi nghiệm thu hiện tại: bảo toàn đầy đủ Xưởng cơm/PO và Chấm công/lương; riêng nội dung `Phần làm thêm.docx` được chủ dự án yêu cầu để sau.

### 17.11. Báo cáo tổng hợp và đề nghị thanh toán

- Khách muốn báo cáo tổng hợp chạy theo nhà thầu và tên bếp.
- Khi có bếp mới, báo cáo phải tự động đưa bếp mới vào, không cần sửa công thức Excel thủ công.
- Khách đang gửi ảnh mẫu thay cho việc yêu cầu sao chép các công thức cũ.
- Ảnh mẫu là sheet `báo cáo tổng hợp`, có phân cấp nhà thầu/bếp và các dòng tổng nhóm, tổng tháng nền xanh.
- Nhận định thiếu tiêu đề/mẫu ở thời điểm ảnh chụp đã được thay thế bởi workbook đầy đủ `Đề nghị Thanh toán TĐP (T04.26).xlsx` và các golden local đã khóa tại mục 25.
- Đề nghị thanh toán theo từng nhà thầu đã có golden và đã được triển khai; không còn là đầu vào phải xin thêm.

## 18. Mức độ ưu tiên sau tài liệu Word

### Nhóm đã được khách ghi rõ bằng văn bản

1. Nạp/tách báo giá đúng mẫu và theo từng nhà thầu.
2. Phiếu giao đúng mẫu đã được bếp duyệt.
3. Checklist chống sót đặt NCC và quy tắc dồn chính xác.
4. Phải thu Excel theo nhà thầu → tổng nhà thầu → từng bếp.
5. Phải trả chi tiết và lưu trạng thái thanh toán.
6. Hóa đơn/kho/tồn tách tuyệt đối theo nhà thầu, không âm kho, cho xuất nhiều vòng.
7. NXT giá bình quân và giá bán đúng kỳ/nhà thầu.
8. Ghép mã mSMI bằng bàn phím, filter lỗi, kiểm tra ĐVT và ghi nhớ mapping/quy đổi.

### Nhóm được xác nhận vẫn phải giữ

- Xưởng cơm/PO.
- Chấm công/lương.

Đây là lời đính chính trực tiếp của chủ dự án ngày 02/09/2026 và ưu tiên hơn suy luận từ vị trí ảnh trong tài liệu Word.

### Nhóm đã được nguồn local/đính chính mới khóa, không hỏi lại khách

- BK: cờ `bk`, là đầu vào TĐP; hệ thống cấp mẫu; giá mặc định 95% giá bán và chỉ ghi kho sau xác nhận.
- NXT: xuất bộ bốn file chính thức từ golden TĐK đã có; không cần một file NXT riêng.

### Nhóm từng cần xác minh và nay đã được xử lý trong source

- Báo giá, phiếu giao, công nợ phải thu/phải trả, thanh toán một phần và hồ sơ đề nghị thanh toán đều đã có contract, golden/fixture và regression tương ứng.
- Connector M-Invoice đầu ra đã được kiểm chứng theo chế độ chỉ-read; chỉ trạng thái hợp lệ và dòng đã ghép mã mới được ghi canonical ledger, còn trạng thái không rõ/hủy/thay thế/điều chỉnh đều bị chặn hoặc đưa vào đối chiếu.

## 19. Nguyên tắc triển khai

- Nội dung từ `Note công việc.docx` đã được chủ dự án yêu cầu đưa vào đợt triển khai hợp đồng hiện tại, trừ riêng `Phần làm thêm.docx`.
- Đã có lệnh triển khai; mọi thay đổi phải đi qua source, test/QC và gói phát hành mới. Không sửa database thật, không làm mất thay đổi local và không coi EXE/gói cũ là đã mang các đính chính mới.
- Khi triển khai phải ưu tiên tài liệu Word này ở những điểm nó chốt rõ hơn hội thoại, đồng thời giữ các ranh giới an toàn về kho, công nợ, ký/phát hành hóa đơn và dữ liệu khách.

## 20. Đối chiếu các file Excel được nhắc trong tài liệu Word

### 20.1. Workbook chính “file Thành”

Đã xác định chắc chắn là file gốc:

- `Em Thành.xlsx`

Ngày 02/09/2026, chủ dự án xác nhận thêm: **toàn bộ nội dung và các biểu mẫu trong `Em Thành.xlsx` là mẫu chuẩn để hệ thống bám theo**. Nếu biểu mẫu hệ thống hiện tại khác file này thì phần sai là hệ thống hiện tại, không phải workbook `Em Thành.xlsx`.

Tên sheet thực tế trong file:

`CCCD`, `T.chiếu`, `danh mục hàng hóa`, `BÁO GIÁ`, `danh mục nhà cc`, `gộp đơn`, `đơn hàng27.08  `, `đặt hàng`, `đơn hàng đi giao`, `bảng kê tổng`, `biên nhận`, `báo cáo tổng hợp`.

Các tên sheet này trùng trực tiếp với nội dung và ảnh khách tham chiếu, nên có thể ánh xạ:

- Báo giá: sheet `BÁO GIÁ`.
- Danh mục NCC: sheet `danh mục nhà cc`.
- Đơn khách theo ngày: sheet `đơn hàng27.08  ` và các sheet ngày tương tự khi vận hành.
- Công nợ phải trả hằng ngày/nguồn đặt NCC: sheet `đặt hàng`.
- Phiếu giao mẫu đã được duyệt: sheet `đơn hàng đi giao`.
- Bảng kê: sheet `bảng kê tổng`.
- Biên nhận: sheet `biên nhận`.
- Mẫu báo cáo theo nhà thầu/bếp: sheet `báo cáo tổng hợp`.

### 20.2. Các mẫu thuế khách nhắc

Các câu “thuế 8, KKKNT, thuế 10…” tương ứng với bộ file trong `bosung.30.8.26`:

- `thue 8.xlsx`.
- `thue 0.xlsx`: mẫu KKKNT, trong source/QC được giữ mã thuế `-2`, không được hiểu thành VAT 0%.
- `thue 10.xlsx`.
- `thue 10 có khuyến mại.xlsx`.

### 20.3. Công nợ phải trả lịch sử

File phù hợp với câu “đúng file mẫu chị gửi” là:

- `bosung.30.8.26/Công nợ phải trả Thành Đạt Phát.xlsx`.

File này đã được QC trước đó theo luồng 9.976 dòng nguồn → 9.975 dòng phải trả, chống nhập trùng.

### 20.4. Các mẫu/điểm đã khóa thêm

- Bộ `TĐK–NXT`: dùng `_HANDOFF/EXTERNAL_INPUTS/TĐK T8-2026.xlsx thụy.xlsx`, sheet `Ton 7 (2)`, làm golden cho hệ cột/hình thức; từ đó sinh chính thức bốn file TĐK, Nhập, Xuất và NXT. Việc không có sheet mang tên `NXT` trong `Em Thành.xlsx` không phải dữ liệu thiếu.
- Mẫu BK: hệ thống là bên phải cấp file mẫu từ cấu trúc nguồn đã khóa; khách không phải gửi thêm workbook BK.
- Đề nghị thanh toán theo từng nhà thầu: nhận định lịch sử “chưa có” đã được thay thế bởi golden khách gửi ngày 03/09/2026 và implementation tại mục 25.
- “2 phần không cần làm” trong ảnh: không mở lại thành câu hỏi; Xưởng cơm/PO và Chấm công/lương vẫn giữ, còn `Phần làm thêm.docx` để sau theo chỉ đạo trực tiếp.

## 21. Đính chính đã dùng để sửa baseline: `Em Thành.xlsx` là mẫu chuẩn

Ngày 02/09/2026, chủ dự án đính chính rõ cách hiểu cuối cùng:

- **Mọi biểu mẫu và nội dung trong `Em Thành.xlsx` đều là mẫu chuẩn.**
- Sheet `biên nhận` trong ảnh là mẫu chuẩn cần bám theo; không phải bản thân sheet đó sai.
- Biểu mẫu `biên nhận` và các biểu mẫu tương ứng của baseline trước sửa là phần sai; source hiện hành phải và đã được nghiệm thu lại theo golden.
- Không được yêu cầu khách thay đổi mẫu để khớp hệ thống; hệ thống phải được sửa để khớp workbook chuẩn.

Phạm vi dùng `Em Thành.xlsx` làm chuẩn bao gồm:

- Tên và thứ tự cột.
- Cách chia sheet.
- Cách tách/gộp theo nhà thầu, bếp, NCC và người bán.
- Tiêu đề, câu chữ, thông tin pháp nhân và vùng chữ ký.
- Bố cục, định dạng, màu sắc, dòng nhóm và thứ tự dữ liệu.
- Khổ/vùng in và cách trình bày file đầu ra.
- Các mẫu `BÁO GIÁ`, `đặt hàng`, `đơn hàng đi giao`, `bảng kê tổng`, `biên nhận`, `báo cáo tổng hợp` cùng các sheet danh mục liên quan.

Nguyên tắc nghiệm thu biểu mẫu:

1. Lấy đúng sheet tương ứng trong `Em Thành.xlsx` làm golden reference.
2. Đổ dữ liệu hệ thống vào đúng cấu trúc mẫu đó.
3. So sánh trực quan, cấu trúc workbook, vùng in, số sheet, tên sheet, thứ tự cột và tổng số liệu.
4. Bất kỳ khác biệt không được khách yêu cầu đều được coi là lỗi của hệ thống.

Các yêu cầu nghiệp vụ mới như chống trùng, xuất nhiều vòng, trạng thái thanh toán, ghi nhớ mapping hoặc tự cập nhật bếp vẫn phải được triển khai, nhưng đầu ra cuối cùng phải giữ đúng hình thức của `Em Thành.xlsx` trừ khi chủ dự án/khách chốt một thay đổi cụ thể mới hơn.

## 22. Bổ sung hai file khách gửi ngày 02/09/2026

Tin nhắn đi kèm của khách:

- `Đơn hàng 01.09.2026.xlsx`: “đây là đơn hàng mà chị làm để hàng ngày up lên em; những phần cố định thì thôi, còn phần thay đổi thì chị giữ lại”.
- `BÁO GIÁ TOYOTA T09-2026.xlsx`: “mẫu báo giá sau khi đã tách”.
- Khách nhấn mạnh ưu tiên trước mắt: đặt hàng và kiểm soát công nợ đầu ra/đầu vào. Việc khách dùng từ “AI” ở đây được hiểu là mong muốn hệ thống hỗ trợ/tự động hóa các bước này; không tự mở rộng thành tự gửi, tự ký hoặc tự quyết định nghiệp vụ.

### 22.1. File đầu vào hằng ngày `Đơn hàng 01.09.2026.xlsx`

Thông tin nhận diện:

- Dung lượng: 792.695 byte.
- SHA-256: `4C6462CD75178926A9CA3B6406A372CFA0254621FC1DF4A58C64ED5EAC7E44CF`.
- Không có external link.
- Có 8 sheet, đều đang visible:
  - `CCCD`.
  - `T.chiếu`.
  - `danh mục hàng hóa`.
  - `BÁO GIÁ`.
  - `danh mục nhà cc`.
  - `gộp đơn`.
  - `01.09`.
  - `đặt hàng`.

So với `Em Thành.xlsx`:

- Sheet ngày cũ `đơn hàng27.08  ` được thay bằng sheet ngày `01.09`.
- Bốn sheet đầu ra cố định không còn nằm trong file ngày:
  - `đơn hàng đi giao`.
  - `bảng kê tổng`.
  - `biên nhận`.
  - `báo cáo tổng hợp`.

Cách hiểu cần dùng khi triển khai:

- Đây là workbook khách sẽ tải lên hằng ngày.
- Các sheet danh mục/tham chiếu/bảng giá trong workbook hỗ trợ việc tính và kiểm tra dữ liệu, nhưng không được nhập lẫn thành dòng đơn hàng.
- Phần thay đổi chính mỗi ngày là sheet ngày như `01.09` và sheet `đặt hàng` sau khi khách chốt thực tế.
- Bốn sheet đầu ra cố định phải do hệ thống sinh lại theo đúng golden template trong `Em Thành.xlsx`; không yêu cầu khách giữ/copy thủ công chúng trong file ngày.
- Không được chỉ dựa vào vị trí sheet. Phải nhận diện sheet ngày theo cấu trúc/ngày, và nhận diện `đặt hàng` bằng tiêu đề bắt buộc.

### 22.2. Cấu trúc sheet ngày `01.09`

- Có 323 dòng dữ liệu thực tế, từ dòng 3 đến dòng 325.
- Các cột nghiệp vụ gồm:
  - Nhà thầu.
  - Mã tham chiếu.
  - Chọn NCC.
  - NCC.
  - Mã hàng.
  - Mã bếp.
  - Ngày/tháng.
  - Tên hàng.
  - Khối lượng.
  - ĐVT.
  - Giá mua.
  - Giá bán.
  - Tiền hàng chưa VAT.
  - Thuế.
  - Tổng tiền.
  - Lợi nhuận.
  - Kiểm lại.
  - Bảng kê.
  - Nhà cung cấp/người bán.
  - CCCD.
- File có dữ liệu CCCD nên tuyệt đối không log hoặc đưa nội dung cá nhân vào báo cáo kỹ thuật.
- Một số ô công thức `Chọn NCC` và `CCCD` có cached value trống; đây có thể là giá trị trống có chủ đích. Importer phải dựa vào các cột nghiệp vụ bắt buộc, không coi mọi cached blank là workbook hỏng.

### 22.3. Cấu trúc sheet `đặt hàng`

- Có 259 dòng dữ liệu thực tế, từ dòng 3 đến dòng 261.
- Cấu trúc hiện có:
  - Mã hàng.
  - Mã bếp.
  - Ngày.
  - Tên hàng.
  - Số lượng.
  - ĐVT.
  - NCC.
  - Ghi chú.
  - Giá mua.
  - Hỏng.
  - Thêm.
  - Giảm.
  - Thiếu.
  - Số lượng thực tế.
  - Thành tiền.
- Công thức lõi trong workbook thể hiện số lượng thực tế được điều chỉnh từ số lượng gốc theo các cột hỏng/thêm/giảm/thiếu, sau đó thành tiền theo số lượng thực tế × giá mua.
- Đây là hình thức khách dùng làm công nợ phải trả hằng ngày và cộng dồn tháng/năm.
- Cấu trúc này không giống hoàn toàn file round-trip đặt NCC 13 cột hiện tại của hệ thống. Khi triển khai phải thiết kế cầu nối rõ ràng, không được ép khách dùng biểu mẫu hệ thống đang sai và không được để file mua NCC sửa ngược đơn khách/phải thu.

### 22.4. Các sheet cố định trong file ngày

- `CCCD`: danh mục người bán và thông tin định danh; dữ liệu nhạy cảm, chỉ dùng đúng nghiệp vụ bảng kê/biên nhận.
- `T.chiếu`: ánh xạ nhà thầu, mã/tên bếp, địa chỉ giao, chữ cái nhóm và phân loại hàng hóa.
- `danh mục hàng hóa`: mã, nhóm, tên Thành Đạt Phát, tên xuất hóa đơn, ĐVT và thuế.
- `BÁO GIÁ`: ma trận giá mua/NCC/BK/tên bảng kê/ĐVT/thuế và giá theo từng nhà thầu.
- `danh mục nhà cc`: ánh xạ NCC theo mã hàng và bếp/nhà thầu.
- `gộp đơn`: sheet tính/gộp trung gian của workbook khách.

Hệ thống có thể chuẩn hóa những dữ liệu này vào database, nhưng khi nạp file hằng ngày phải chống ghi đè sai danh mục, chống lộ dữ liệu cá nhân và chống tạo trùng.

### 22.5. File mẫu đầu ra `BÁO GIÁ TOYOTA T09-2026.xlsx`

Thông tin nhận diện:

- Dung lượng: 41.030 byte.
- SHA-256: `C3C16615F8DA1AB80843DE3DD611CB8A472B401B8C7B93B177781EDEB203E148`.
- Đây là mẫu báo giá **sau khi đã tách** cho Toyota tháng 09/2026.
- Có một sheet tên `all`.
- Không có công thức và không có external link; đây là file đầu ra độc lập, không phụ thuộc workbook nguồn sau khi xuất.
- Bố cục in ngang, khổ A4; dòng tiêu đề bảng được đặt lặp lại khi sang trang.

Cấu trúc đầu ra:

1. Thông tin Công ty Thành Đạt Phát.
2. Tiêu đề báo giá theo tháng/năm.
3. Dòng kính gửi đúng pháp nhân Toyota.
4. Sáu cột:
   - STT.
   - Mã.
   - Tên Thành Đạt Phát.
   - ĐVT.
   - Giá chưa VAT.
   - Thuế.
5. Dòng nhóm hàng.
6. Danh sách hàng.
7. Ghi chú giá chưa gồm VAT và vùng xác nhận bên bán.

Thống kê mẫu:

- 513 dòng hàng.
- 513 mã duy nhất; không có mã trùng.
- 16 nhóm hàng thực tế:
  - Thịt heo.
  - Gia cầm.
  - Bò, bê, dê.
  - Thủy sản.
  - Hải sản.
  - Giò chả.
  - Bún-bánh.
  - Trứng-đậu.
  - Rau củ.
  - Hoa quả.
  - Đông lạnh.
  - Gạo.
  - Gia vị-đồ khô.
  - Đồ lễ-bánh sữa-nước ngọt.
  - Công cụ dụng cụ.
  - Chất tẩy rửa-giấy các loại.
- Mã được sắp theo nhóm và gần như tăng dần trong từng nhóm. Có một cặp mã trong nhóm Rau củ chưa đúng thứ tự tăng dần; khi sinh file phải ưu tiên yêu cầu bằng văn bản “sắp xếp mã A–Z”.
- Có 5 dòng giá bằng 0. Quy tắc bằng văn bản chỉ nói bỏ `X`/rỗng, chưa nói rõ giá 0; không tự loại giá 0 nếu chưa chốt.

### 22.6. Quan hệ giữa ma trận giá và báo giá Toyota đã tách

- Cột Toyota trong sheet `BÁO GIÁ` của file ngày nằm tại cột `Q`.
- File Toyota đã tách không phải phép sao chép máy móc toàn bộ các dòng đang nhìn thấy ở cột Q: tập mã có chênh lệch, có thể do khách đã chỉnh giá/danh mục hoặc dùng phiên bản nguồn khác trước khi gửi mẫu.
- Vì vậy:
  - Dùng `BÁO GIÁ TOYOTA T09-2026.xlsx` làm golden reference về **hình thức đầu ra**.
  - Dùng file báo giá nguồn đúng kỳ mà khách tải lên làm nguồn **dữ liệu giá**.
  - Không nhập ngược giá từ file đầu ra Toyota vào bảng giá tổng nếu người dùng không xác nhận.
  - Khi xuất phải ghi rõ kỳ, nhà thầu và phiên bản nguồn để truy vết.

### 22.7. Sai lệch baseline đã đưa vào đợt sửa hiện tại

1. Luồng nhập ngày phải nhận đúng workbook khách gửi, không bắt khách đổi sang một biểu mẫu hệ thống khác.
2. Sheet `đặt hàng`/công nợ phải trả phải giữ được hỏng, thêm, giảm, thiếu, số lượng thực tế và thành tiền.
3. Hệ thống phải tự sinh bốn đầu ra cố định bằng mẫu `Em Thành.xlsx`.
4. Báo giá tách theo nhà thầu phải giống mẫu Toyota về tiêu đề, nhóm, cột, định dạng và vùng in.
5. Không trộn file đầu vào hằng ngày, ma trận báo giá nguồn và báo giá đã tách thành một loại import duy nhất.

Các mục trên đã được triển khai trong source và được đưa vào regression/QC; database vận hành thật không bị sửa trực tiếp trong quá trình phát triển. EXE/gói bàn giao phải lấy từ build cuối được định danh ở mục 27 và biên bản nghiệm thu.

## 23. Bản đồ 15 ảnh nhúng trong `Note công việc.docx`

### 23.1. Quy tắc đọc ảnh

Các ảnh trong Word là một phần của đặc tả, không phải ảnh minh họa trang trí. Khi triển khai phải đọc ảnh cùng đoạn chữ đứng ngay trước/sau ảnh.

Có hai loại ảnh:

1. **Golden reference từ Excel**: thể hiện mẫu, cột, bố cục hoặc dữ liệu đầu ra khách đang dùng. Phải bám theo khi sinh file.
2. **Ảnh giao diện hệ thống hiện tại/locator**: khách dùng để chỉ đúng màn hình, vùng hoặc thao tác cần sửa. Không được coi bố cục đang chụp là mẫu đã duyệt.

Các khung đỏ trong ảnh là vùng khách đang nhấn mạnh. Khi ảnh và câu chữ có vẻ mâu thuẫn, ưu tiên lời đính chính mới nhất của chủ dự án và ghi lại điểm chưa rõ; không tự xóa chức năng.

### 23.2. Đối chiếu từng ảnh theo đúng thứ tự trong Word

| Ảnh | Loại | Nội dung nhìn thấy | Ý nghĩa phải dùng khi triển khai |
|---|---|---|---|
| 1 | Giao diện hiện tại/locator | Màn `Báo giá theo nhà thầu`, dropdown đang chọn `BIADAUVOI`, số dòng có giá/chưa xuất, nút `Xuất báo giá BIADAUVOI`, bảng mã–tên–ĐVT–thuế–giá/trạng thái | Đây là màn khách đang nói tới khi yêu cầu thêm nút tải báo giá lên và tách báo giá theo từng nhà thầu. Không coi bảng HTML hiện tại là mẫu báo giá đầu ra; mẫu đầu ra phải theo Excel Toyota/`Em Thành.xlsx`. |
| 2 | Giao diện hiện tại có đánh dấu | Bảng giá HATRAN; khung đỏ quanh cột `Mã hàng` và vùng `Giá / Trạng thái` | Nhấn mạnh việc tách báo giá phải dựa đúng mã hàng và đúng cột giá/trạng thái của nhà thầu. Dòng `X`/rỗng không xuất; mã trùng không được tạo dòng trùng. |
| 3 | Golden reference Excel | Dòng nhóm nền xanh, chữ đậm `GIA CẦM`, nằm giữa hai nhóm hàng | Khi xuất báo giá, hết một nhóm phải chèn dòng tên nhóm màu xanh đúng phong cách workbook. Đây là yêu cầu định dạng thật, không chỉ là nhãn trên giao diện. |
| 4 | Giao diện hiện tại/locator | Menu `Phiếu giao`, thông báo đã tách thành 11 phiếu, các thẻ theo bếp, nút ẩn giá/tải toàn bộ | Chỉ vị trí chức năng phiếu giao trong hệ thống hiện tại. File tải xuống phải đổi sang đúng mẫu sheet `đơn hàng đi giao` trong `Em Thành.xlsx`; số phiếu tách theo bếp/nhà thầu. |
| 5 | Golden reference Excel | `PHIẾU GIAO HÀNG (Kiêm phiếu xuất kho)` ngày 27/08/2026; thông tin bên bán, đơn vị mua, địa chỉ giao, bảng STT–Tên hàng–SL–ĐVT–Đơn giá–Thành tiền–GC, tổng tiền và bốn vùng ký | Đây là mẫu phiếu giao đã được bếp duyệt. Phải giữ bố cục, câu chữ, vùng ký, tổng tiền và định dạng in. Biến thể Nhựa có đơn giá/thành tiền; các bếp không được phép hiện giá phải dùng cùng form nhưng ẩn đúng cột/giá theo quy tắc khách chốt. |
| 6 | Golden reference Excel | Bảng đặt NCC với các cột nhìn thấy: `Mã bếp`, cột ngày, `Tên hàng`, `Số lượng`, `ĐVT`, `NCC`, `ghi chú` | Câu “mẫu đặt hàng gửi Zalo lấy đến cột này” chỉ rõ ảnh gửi NCC kết thúc tại `ghi chú`. Không đưa tồn tủ, giá mua, thành tiền hoặc cột nội bộ ở phía sau vào ảnh gửi Zalo. |
| 7 | Giao diện hiện tại/locator | Màn `Đặt hàng nhà cung cấp`, bước tải file/chọn file đã chỉnh, các thẻ NCC, nút tách theo bếp/sao chép ảnh/tải ảnh | Đây là màn phải bổ sung cơ chế loại trừ/checklist đã đặt–chưa đặt và hoàn tác. Các thẻ hiện tại không đủ bảo đảm chống bỏ sót NCC; không coi trạng thái hiện tại là đã đạt. |
| 8 | Giao diện hiện tại/locator | Toàn màn `Báo cáo và công nợ`, vùng ghi nhận thu/chi, bảng phải thu và phải trả | Chỉ đúng module công nợ cần sửa. Phải thu/phải trả không chỉ là bảng tổng trên màn hình; còn phải có chi tiết và file Excel đúng cấu trúc khách yêu cầu. |
| 9 | Giao diện hiện tại có đánh dấu | Khung đỏ quanh nút `Lưu thanh toán` và tiêu đề `Công nợ phải trả` | Khách muốn dùng thao tác thanh toán để khoản đã trả không còn nằm trong danh sách còn nợ. Phải lưu giao dịch/audit và lịch sử, không xóa dòng công nợ. |
| 10 | Golden reference Excel | Sheet/tab `đặt hàng` trong workbook ngày; các dòng hàng, số lượng, NCC, giá mua, thành tiền và cột trạng thái `ok` | Đây là nguồn công nợ phải trả hằng ngày của khách. Khi nạp/chốt phải cộng dồn theo tháng/năm và giữ khả năng đối chiếu từng dòng. Cấu trúc chi tiết đầy đủ được xác nhận thêm bởi `Đơn hàng 01.09.2026.xlsx`. |
| 11 | Giao diện hiện tại/locator | Màn `Bảng kê, biên nhận và hóa đơn`; các số tổng cần lập, đã nằm trong draft/đã xuất, có thể lập bây giờ, còn chờ hóa đơn đầu vào | Chỉ đúng luồng hóa đơn nhiều vòng. Phải tách theo từng nhà thầu, xuất phần còn tồn, giữ phần thiếu để chạy lại và xuất bảng chưa lập được. Giao diện hiện tại không thay thế mẫu Excel thuế 8/KKKNT/10. |
| 12 | Giao diện hiện tại/locator | Màn `Kho hóa đơn / sổ sách`, nhập tồn đầu kỳ, điều chỉnh kho và bảng chi tiết tồn | Đây là màn khách yêu cầu đổi theo hướng `TĐK–NXT`, bổ sung file nhập, xuất, tồn đầu kỳ và NXT trong kỳ với giá bình quân. Ảnh chỉ vị trí/chức năng cũ; hình thức chính thức lấy từ golden `TĐK T8-2026.xlsx thụy.xlsx` và mở rộng nhất quán thành bộ bốn file. |
| 13 | Giao diện hiện tại có đánh dấu | Màn `Hóa đơn đầu vào mSMI`; danh sách dòng chưa ghép, dropdown tìm mã TĐP được khoanh đỏ | Vùng ghép mã phải tô màu dòng lỗi/chưa mã, dùng được bàn phím và Enter, có filter lỗi/khác ĐVT, ghi nhớ mapping và quy đổi để đồng bộ lại không phải sửa lần nữa. Dropdown hiện tại chỉ là trạng thái cần cải tiến. |
| 14 | Giao diện hiện tại/ảnh đã được đính chính | Cắt phần menu có `Xưởng cơm / PO` và `Chấm công & lương`, đi kèm câu “2 phần này không cần làm nữa” | Không dùng ảnh này để bỏ hai module. Phạm vi hiện hành giữ đầy đủ Xưởng cơm/PO và Chấm công/lương; chỉ `Phần làm thêm.docx` được để sau. |
| 15 | Golden reference Excel | Sheet `báo cáo tổng hợp`; các dòng theo nhà thầu/bếp, dòng tổng nhóm và `TỔNG THÁNG` nền xanh | Đây là bố cục chuẩn cho báo cáo tổng hợp. Báo cáo phải chạy động theo nhà thầu và bếp, tự thêm bếp mới nhưng giữ cách phân nhóm/tổng và hình thức của sheet. Ảnh bị cắt tiêu đề cột nên khi triển khai phải đọc trực tiếp sheet `báo cáo tổng hợp` trong `Em Thành.xlsx`, không đoán ý nghĩa cột chỉ từ ảnh. |

### 23.3. Mức độ chuẩn của từng nguồn hình ảnh

Golden reference bắt buộc đối chiếu trực quan:

- Ảnh 3: dòng nhóm báo giá màu xanh.
- Ảnh 5: phiếu giao đã duyệt.
- Ảnh 6: giới hạn cột của nội dung/ảnh gửi NCC.
- Ảnh 10: nguồn đặt hàng/công nợ phải trả hằng ngày.
- Ảnh 15: báo cáo tổng hợp theo nhà thầu/bếp.

Ảnh chỉ đúng màn/vùng cần sửa, không phải mẫu nghiệm thu giao diện:

- Ảnh 1, 2, 4, 7, 8, 9, 11, 12 và 13.

Ảnh có nội dung mơ hồ đã được chủ dự án đính chính:

- Ảnh 14: không loại Xưởng cơm/PO hoặc Chấm công/lương.

### 23.4. Tiêu chí QC bắt buộc liên quan đến ảnh

Khi bắt đầu triển khai biểu mẫu, mỗi đầu ra phải được kiểm tra theo ba lớp:

1. **Dữ liệu**: đúng nguồn, đúng nhà thầu/bếp/NCC, đúng số lượng, giá, thuế và tổng.
2. **Cấu trúc workbook**: đúng tên/thứ tự sheet, cột, dòng nhóm, vùng ký, vùng in và quy tắc có/không có giá.
3. **Đối chiếu hình ảnh**: render sheet/file đầu ra và so trực quan với ảnh golden reference cùng sheet gốc trong `Em Thành.xlsx`.

Không được tuyên bố biểu mẫu đạt chỉ vì số liệu đúng nếu bố cục khác mẫu; cũng không được coi bố cục giống là đạt nếu nguồn dữ liệu hoặc tổng số sai.

Các ảnh chứa dữ liệu kinh doanh và có thể liên quan thông tin cá nhân; chỉ dùng nội bộ để triển khai/QC, không đưa vào log công khai hoặc gói gửi ngoài phạm vi dự án.

## 24. Bổ sung tin nhắn khách ngày 02/09/2026 lúc 10:56–10:59

Khách nhắn thêm:

- Tạo ngay trên phần mềm phần **tải hóa đơn đầu vào + đầu ra** để khách tự khớp mã và trừ kho.
- Phần này khách muốn **làm trước**, nhằm khớp lại dữ liệu tháng 08/2026.
- Cả hai luồng phải chọn được khoảng **`từ ngày – đến ngày`**; tháng 08/2026 là đợt backfill đầu tiên, không phải kỳ bị hard-code cố định trong phần mềm.

### 24.1. Cách hiểu nghiệp vụ đã đủ căn cứ

- Đây là một khu vực làm việc trên phần mềm cho cả hai chiều hóa đơn, không chỉ là nút đổi nhãn:
  - **Đầu vào**: tải/đồng bộ hóa đơn trong khoảng ngày → ghép mã TĐP → kiểm tra/khớp ĐVT và hệ số quy đổi → người dùng xác nhận → ghi tăng kho hóa đơn.
  - **Đầu ra**: tải/đồng bộ hóa đơn đã phát hành trong khoảng ngày → ghép từng dòng với mã TĐP → người dùng kiểm tra/xác nhận → ghi giảm kho hóa đơn.
- Giao diện cần tách rõ `Đầu vào` và `Đầu ra`, đồng thời có filter/trạng thái tối thiểu: chưa ghép, cần kiểm tra ĐVT, sẵn sàng, đã ghi kho và lỗi/bất thường.
- Đồng bộ lại cùng loại hóa đơn và cùng khoảng ngày phải idempotent: không nhân đôi hóa đơn, dòng hóa đơn hoặc bút toán kho; mapping đã xác nhận phải được ghi nhớ.
- Phải hiển thị nguồn, ngày hóa đơn, ký hiệu/số hóa đơn, đối tác, mã/tên hàng nguồn, mã TĐP đã ghép, ĐVT, số lượng và trạng thái ghi kho để khách tự đối chiếu tháng 08/2026.

### 24.2. Ranh giới an toàn bắt buộc

- Nguồn đã chốt: đầu vào đọc từ mSMI, đầu ra đọc từ M-Invoice. Không tự mở quyền ký, phát hành, sửa hay hủy hóa đơn trên hệ thống bên ngoài; connector trong phạm vi này chỉ được đọc/import.
- Luồng M-Invoice đầu ra đã có adapter chỉ-read và mapping trạng thái được kiểm chứng; trạng thái chưa rõ/nháp/hủy/thay thế/điều chỉnh bị fail-closed, không được suy đoán là đã phát hành.
- Không tự ghép bằng tên gần giống. Dòng chưa có mã hoặc khác ĐVT phải chờ người dùng xử lý; chưa đủ mapping/xác nhận thì không được cộng hoặc trừ kho.
- Hóa đơn đầu ra chỉ được trừ kho khi trạng thái nguồn chứng minh đã phát hành/hợp lệ. Draft, hóa đơn chờ ký, đơn hàng và phiếu giao không được trừ kho.
- Hóa đơn bị hủy, thay thế hoặc điều chỉnh phải tạo luồng đối chiếu/reversal có audit; không xóa bút toán cũ để làm khớp số.
- Không âm kho. Nếu dữ liệu lịch sử tháng 08/2026 làm lộ thiếu tồn hoặc thiếu đầu vào, hệ thống phải báo chênh lệch/chờ xử lý, không tự tạo tồn hoặc bịa hệ số quy đổi.

### 24.3. Thay đổi thứ tự ưu tiên

Tin nhắn này là yêu cầu ưu tiên mới nhất và cụ thể hơn thứ tự ở mục 18/22. Vì vậy, sau khi khóa baseline và bảo vệ dữ liệu, lát dọc phải làm trước trong Goal A là:

1. Màn tải/đồng bộ hóa đơn đầu vào và đầu ra có `từ ngày – đến ngày`.
2. Khớp mã hai chiều và quy đổi ĐVT đầu vào có audit/ghi nhớ.
3. Ghi tăng kho từ đầu vào hợp lệ và ghi giảm kho từ đầu ra đã phát hành hợp lệ.
4. Đối chiếu `Tồn đầu + Nhập − Xuất = Tồn cuối` cho khoảng 01/08/2026–31/08/2026 trên fixture/bản sao an toàn trước khi dùng dữ liệu thật.

Các luồng đơn hàng, NCC và công nợ vẫn còn nguyên phạm vi; chỉ được xếp sau lát ưu tiên hóa đơn–khớp mã–kho này, không bị loại bỏ.

## 25. Bổ sung chốt ngày 03/09/2026 – hóa đơn đầu vào và hồ sơ thanh toán

### 25.1. Hóa đơn đầu vào

- Kết nối hóa đơn hiện có được giữ nguyên; không dựng thêm một API hay bắt người dùng tải file hóa đơn thủ công thay cho luồng đang chạy.
- Sau khi kéo hóa đơn đầu vào theo `từ ngày – đến ngày`, người dùng phải tải được Excel ngay từ chính phiên đồng bộ, trước cả bước ghép mã hoặc tạo phiếu nhập.
- File Excel đầu vào gồm danh sách hóa đơn, chi tiết hàng hóa và thông tin đối chiếu phiên. Thao tác tải file chỉ đọc dữ liệu đã kéo, không tự ghép mã, không tự ghi tăng kho và không đưa raw JSON/mã từ xa/thông tin kết nối vào file.
- Việc ghép mã, quy đổi ĐVT và xác nhận ghi kho vẫn là bước riêng có kiểm soát như các mục trước.

### 25.2. Golden `Đề nghị Thanh toán TĐP (T04.26).xlsx`

- File: `C:\Users\DELL\Downloads\Đề nghị Thanh toán TĐP (T04.26).xlsx`.
- Dung lượng: 189.496 byte.
- SHA-256: `64DC5FD8E062A6B3CFC4056F51BE9FAF11F4927A5378287F39C59CA8925C34A2`.
- Đây là mẫu chính thức khách vừa cung cấp cho hồ sơ đề nghị thanh toán theo nhà thầu. Tên file có chữ `T04.26` nhưng dữ liệu nhìn thấy trong mẫu thuộc kỳ khác; hệ thống phải dùng khoảng ngày người dùng chọn và dữ liệu hóa đơn thật, tuyệt đối không hard-code tháng theo tên file.
- Sheet đề nghị thanh toán dùng bố cục pháp lý, phần căn cứ/nội dung, bảng sáu cột: STT, Ngày hóa đơn, Số hóa đơn, Tổng tiền trước thuế, Tổng tiền thuế, Tổng tiền thanh toán; sau đó là tổng cộng, bằng chữ, thông tin chuyển khoản và vùng ký.
- Sheet BK dùng bố cục `BẢNG TỔNG HỢP GIAO NHẬN` mười cột: STT, Ngày, Tên hàng, ĐVT, Số lượng, Đơn giá, Thành tiền, Thuế suất, Tiền thuế, Thanh toán; kèm thông tin hai bên, kỳ, tổng, bằng chữ và vùng ký.
- Workbook lịch sử có nhiều sheet phụ, công thức/liên kết ngoài VnTools, dòng trống cố định và dữ liệu kỳ cũ. Chỉ dùng hình thức hai mẫu nói trên làm golden; không sao chép công thức, liên kết ngoài, dữ liệu cũ hoặc logic tổng hợp lỗi sang output mới.
- Số liệu chính thức chỉ lấy từ hóa đơn đỏ đầu ra đã phát hành của đúng một nhà thầu. Tổng chi tiết, tổng hóa đơn và tổng chứng từ phải khớp; lệch thì chặn, không tự cân.

### 25.3. Phạm vi hiện tại và phần để sau

- `C:\Users\DELL\Downloads\Phần làm thêm.docx` (SHA-256 `D534201EEB469D5B333EE7BDC8AD743613A98BD47F2198F2CFD7057C821BFA84`) được chủ dự án yêu cầu **tạm bỏ qua hoàn toàn** trong đợt nghiệm thu hợp đồng hiện tại.
- Không dùng bất kỳ nội dung nào trong file “Phần làm thêm” để mở rộng source, giao diện, database, báo giá hoặc thời gian bàn giao hiện tại.
- Xưởng cơm/PO và Chấm công/lương vẫn thuộc hệ thống và vẫn phải hoạt động; chúng không bị loại bởi quyết định tạm bỏ phần nâng cấp thêm.

## 26. Đính chính cuối ngày 03/09/2026 – thay thế các giả định hỏi thừa

Các kết luận dưới đây là cách hiểu hiện hành và có ưu tiên hơn mọi dòng lịch sử nói rằng còn thiếu mẫu BK/NXT:

1. **BK đã đủ căn cứ nghiệp vụ:** cờ `bk` xác định dòng bảng kê; đó là đầu vào của Thành Đạt Phát, giá nhập mặc định bằng 95% giá bán của chính dòng, hệ thống phải cấp mẫu import và chỉ ghi tăng kho sau preview/xác nhận có audit. Không hỏi khách gửi thêm “file BK thực tế”.
2. **NXT đã đủ golden:** dùng file TĐK tháng 8 đã có để tạo bộ bốn file chính thức TĐK–Nhập–Xuất–NXT; tất cả số liệu phải cùng một projection và thỏa `Tồn đầu + Nhập − Xuất = Tồn cuối`. Không hỏi khách gửi thêm mẫu NXT.
3. **Máy in/khay không còn blocker:** chủ dự án xác nhận các khay đã cấu hình xong và yêu cầu không tiếp tục coi phần máy in là việc còn thiếu. Việc ký nhận giấy nếu có là bước vận hành/bàn giao, không phải lỗi kỹ thuật của source.
4. **Hóa đơn đầu ra:** M-Invoice là nguồn đã chốt; adapter chỉ-read, trạng thái, paging/cursor, mapping, ghi kho/reversal và lỗi an toàn đã qua kiểm chứng kỹ thuật. Đây không còn là câu hỏi lựa chọn nguồn cho khách.

## 27. Trạng thái triển khai và phát hành cuối ngày 03/09/2026

### 27.1. Kết luận

**Đã hoàn tất 100% phạm vi hợp đồng hiện tại theo cổng nghiệm thu kỹ thuật đã chốt.** Không còn câu hỏi nghiệp vụ nào về BK, NXT, nguồn hóa đơn, hai module Xưởng cơm/PO – Chấm công/lương hoặc máy in/khay cần bắt khách trả lời trước khi bàn giao. `Phần làm thêm.docx` và hosting/public domain thuộc phạm vi khác, không được tính vào đợt này.

Ranh giới bắt buộc của hóa đơn đầu ra đã được khóa: nút `Ghi nhận hóa đơn đã phát hành` chỉ khóa draft cục bộ và tiếp tục giữ tồn chờ, không ghi TĐK–NXT. Chỉ bản M-Invoice đã đồng bộ ở trạng thái hợp lệ, khớp đúng ký hiệu–số–ngày và toàn bộ mã hàng–ĐVT–số lượng, đã ghép mã/quy đổi và được người dùng bấm `Xác nhận xuất kho hóa đơn` mới ghi giảm kho. Sai bất kỳ dấu vết nào thì fail-closed và giữ tồn chờ.

### 27.2. Bằng chứng bản cuối

- Full regression: `364/364`, không skip, `Ran 364 tests in 169.508s`, kết thúc `OK`.
- `tdp_system/qc_system.py`: exit code 0, `ok=true`, toàn bộ gate nghiệp vụ và golden đạt.
- Browser QC Edge/CDP độc lập: exit code 0; 13 màn hình, 408 dòng đơn, 334 mã tồn đầu, Xưởng cơm/PO, 205 dòng chấm suất, Chấm công/lương, công nợ, hai bộ PDF dry-run và draft đầu ra đều đạt; `browserErrors=0`.
- Source smoke cổng tạm `18770` và EXE smoke cổng tạm `18774`: health/database/schema/integrity đều xanh, chỉ listen loopback; EXE chứng minh lỗi giả của cả mSMI và M-Invoice đều fail-closed `read_only=true` mà không crash.
- Render Excel COM: BK và NXT đều một trang ngang, vùng in trọn, không `####`, công thức, hyperlink hoặc external link; NXT hiển thị riêng Mã TĐP và Mã kho.
- Dry-run migration trên online backup database thật: `migration_passed=true`, 10/10 check đạt, integrity `ok`, khóa ngoại 0 lỗi, mọi bước sẵn sàng idempotent.
- Database vận hành thật giữ nguyên SHA-256 `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF` trước/sau.

### 27.3. Artifact bàn giao hiện hành

| Artifact | Kích thước | SHA-256 |
|---|---:|---|
| `BAN_GIAO_TDP_20260903_100PCT/TDP_Server.exe` | 77.082.006 byte | `76F023D61BC65B8C799A7F713C2C7DD1460665325F21E833939BA5C64F8B9FEB` |
| `BAN_GIAO_TDP_20260903_100PCT/data/tdp.sqlite3` | 60.338.176 byte | `96705D3BCD74FC0C181190315CA9F10DF6BFFF3D3EF63FE1BB327C7CA5769708` |
| `BAN_GIAO_TDP_20260903_100PCT.zip` | 86.481.255 byte | `5EEFB1F1573BEE36D817485391AFAFD1F47D882B8865B2D3BFD96FA9CCD732FD` |

Gói có đúng 8 file allowlist và đúng 8 ZIP entry. Manifest `SHA256SUMS_TDP_20260903_100PCT.txt` đã được kiểm lại với cả file trong thư mục lẫn stream trong ZIP. Gói không chứa `.env`, source, workbook/ảnh khách, log/QC, file xuất cũ, WAL/SHM hoặc EXE lịch sử; chỉ có `.env.example` với tên biến và giá trị trống.

Ngoại lệ dữ liệu được báo minh bạch: file `SUẤT ĂN T3-2026 .xlsx` có ô `E33=125000` mâu thuẫn với `D33=125`; hệ thống chặn đúng và không tự sửa đoán. Người có thẩm quyền cần sửa file nguồn trước nếu muốn nhập lại tháng 03. Đây không phải lỗi release và không chặn dữ liệu tháng 08/phạm vi bàn giao hiện tại.

## 28. Phản hồi báo giá ngày 03/09/2026 – tải riêng, tải tổng và từng lần lưu

- Màn `Báo giá` có ba cách lấy file: tải Excel của nhà thầu đang chọn; tải toàn bộ kỳ dưới dạng ZIP; tải lại đúng từng phiên bản/lần xác nhận trong lịch sử.
- File tải toàn bộ không gộp nhiều nhà thầu vào chung một workbook. ZIP chứa một XLSX riêng cho từng nhà thầu, mỗi file chỉ đọc đúng cột giá của nhà thầu và đúng `version_id` đã chọn; nhà thầu không có dòng xuất hợp lệ được bỏ qua.
- Báo giá theo ngày chỉ được đưa vào ZIP khi đơn hàng được chọn thuộc đúng tháng; sai tháng bị chặn rõ ràng. Dòng trùng xung đột chặn cả lần tải tổng, không tự chọn giá.
- Kiểm thử chức năng đạt `15/15`; full regression đạt `375/375`; QC UTF-8 `ok=true`; browser Edge/CDP trên database tạm đạt tải từng nhà thầu, ZIP toàn bộ và lịch sử phiên bản, không lẫn giá ATV/TOYOTA.
- Đây là thay đổi source sau gói bàn giao ghi ở mục 27. Theo chỉ đạo hiện tại **chưa build lại EXE/ZIP**; `TDP_Server.exe` đang chạy ở cổng 8765 và các hash artifact mục 27 chưa chứa thay đổi này.

## 29. Phản hồi giao diện công nợ ngày 04/09/2026

- Đã tách `Báo cáo` và `Công nợ` thành hai mục riêng trên thanh bên; không còn nhãn/màn gộp `Báo cáo & công nợ`.
- Màn đầu của `Công nợ` chỉ hiện ba lựa chọn: `Công nợ phải thu (bếp)`, `Công nợ phải thu (tổng)` và `Công nợ phải trả`. Dữ liệu chi tiết chỉ được tải và hiển thị sau khi người dùng chọn đúng mục.
- Phải thu theo bếp giữ bộ lọc nhà thầu/bếp/trạng thái, sổ từng dòng, lịch sử và tải Excel/ZIP. Phải thu tổng giữ bảng tổng nhà thầu, ghi nhận đã thu, lịch sử thu và tải tổng. Phải trả giữ lọc NCC/trạng thái, phân bổ từng dòng, thanh toán/hoàn tác, nạp file cũ và tải Excel.
- Số dư đầu kỳ và điều chỉnh được đưa vào vùng mở thêm để màn chính gọn nhưng không mất chức năng. Bộ lọc lưu cũ và các ranh giới nghiệp vụ/audit không thay đổi.
- Kiểm chứng source: `377/377` unit test đạt; `qc_system.py` đạt `ok=true`; Edge/CDP thật đạt cả luồng phải thu và phải trả, đồng thời xác nhận màn tổng quan chỉ có ba lựa chọn và chưa hiện bảng chi tiết. Không build lại EXE/ZIP theo chỉ đạo hiện tại.

## 30. Phản hồi tổng thể trong `em Thành.docx` ngày 04/09/2026

Nguồn chốt của đợt sửa này là toàn bộ chữ và ảnh trong `C:\Users\DELL\Downloads\em Thành.docx`. Ảnh chỉ dùng để xác định màn/vị trí; nội dung chữ của khách quyết định phần giữ lại, phần đưa vào chi tiết và hành vi thao tác.

- `Công việc hằng ngày` thay màn tổng quan cũ và chỉ giữ bốn việc: tạo phiếu đặt hàng, in đơn hàng, bảng kê/biên nhận và duyệt đơn. Có `Từ ngày – Đến ngày`; màn ngoài không còn dàn thẻ thống kê kỹ thuật.
- File đơn hợp lệ tải sau cùng của cùng ngày là bản đang dùng. Khi cả phần bán/giao và mua/phải trả đều hợp lệ, hệ thống tự áp dụng toàn bộ file và tự chốt; nếu có lỗi/xung đột thì vẫn chặn, tô/nêu phần cần sửa và không đoán bỏ qua.
- Tại `Nhập & sửa đơn`, thao tác thêm nhanh một dòng vào đơn có sẵn chỉ yêu cầu `Tên hàng`, `Số lượng`, `Đơn vị tính`; bếp, nhà thầu và ngày được lấy từ đơn đang chọn.
- `Đặt hàng nhà cung cấp` hiển thị một cột dọc, mỗi NCC chỉ có tên, số dòng, tổng lượng/tổng tiền và trạng thái. Chi tiết mặt hàng nằm trong ảnh tạo ra; bấm `Sao chép ảnh` thành công tự ghi nhận `Đã đặt`, còn `Mở lại` dùng khi cần sửa/gửi lại.
- `Phiếu giao` mặc định chỉ hiện tổng số phiếu trong ngày, nút tải toàn bộ và nút mở chi tiết. Màn `In giấy tờ` cho chọn tất cả hoặc từng bếp/từng ngày trong khoảng thời gian rồi tải đúng các file đã chọn.
- `Báo giá` chỉ có hai lựa chọn ngoài: `Báo giá tổng` và `Báo giá chi tiết`; bản mới nhất của tháng là mặc định. Lịch sử và bảng dòng hàng chỉ hiện khi người dùng yêu cầu.
- `Báo cáo tổng hợp` chỉ còn một thẻ theo tháng. `Công nợ` là màn riêng, mở đầu bằng đúng ba lựa chọn phải thu theo bếp, phải thu tổng và phải trả; chi tiết chỉ tải khi bấm vào mục.
- `Báo cáo vật tư hàng hóa` thay tên kho hóa đơn ở giao diện và chỉ giữ ngoài màn khoảng ngày cùng năm nút tải: đủ bốn file ZIP, tồn đầu, nhập, xuất và nhập–xuất–tồn. Phần nhập/chỉnh dữ liệu nằm trong vùng mở chi tiết.
- `Bảng kê & hóa đơn` giữ ngoài màn phần được/chưa được xuất theo nhà thầu, `File tải hóa đơn` và `Bảng kê từ hóa đơn đỏ`; draft, thay thế, thiếu tồn và thao tác kỹ thuật nằm trong `Xử lý chi tiết hóa đơn`.
- `In giấy tờ` thay tên `Duyệt & in`, giải thích rõ loại giấy tờ và cho chọn từng phiếu giao theo bếp. Luồng in trực tiếp Windows vẫn được giữ trong vùng mở thêm, không làm mất chức năng cũ.

Bằng chứng sau sửa: test tập trung `31/31`; full regression `384/384`, không lỗi/không skip; `tdp_system/qc_system.py` trả `ok=true` và gate `customerCompactUiContract` đạt. Chrome/CDP trên database tạm đạt 1440px và 1024px, không tràn ngang/nút bị cắt, không runtime error; kiểm tra thật thao tác `Sao chép ảnh → Đã đặt` và chọn bỏ riêng một phiếu giao theo bếp đều đạt. `/health` của source tạm xanh. Không build lại EXE/ZIP trong đợt này theo đúng chỉ đạo; artifact mục 27 chưa chứa các thay đổi mới.

## 31. EXE một file sau phản hồi khách ngày 04/09/2026

- Artifact gửi khách: `BAN_GIAO_TDP_MOT_FILE_20260904/Thanh_Dat_Phat.exe`.
- Thư mục bàn giao có đúng một file, không cần BAT, Python hay cài dependency. Lần chạy đầu EXE tự tạo thư mục dữ liệu cạnh file và chỉ cài snapshot khởi tạo khi chưa có database; dữ liệu đã tồn tại không bị ghi đè.
- Metadata Windows: `FileVersion` và `ProductVersion` đều là `2026.09.04.1`.
- Dung lượng: `90.744.705` byte.
- SHA-256: `24AF1C0D17193729602FF0C3CF6525DFF0483F7A0671AE96CA0D3EBA0C97A136`.
- Build dùng SQLite online backup có kiểm tra integrity và chỉ lọc đúng tên biến connector cần thiết; giá trị bí mật không được in/log. Archive đã được kiểm tra có giao diện mới, seed database, bốn mẫu thuế, công cụ in và cấu hình connector; không cần `.env` rời khi gửi.
- Smoke chạy trên chính EXE tại cổng tạm `18804`: `/health ok=true`, database/schema ready, integrity `ok`, cache `app.js?v=20260904-22` và `real.css?v=20260904-9` đúng. Chrome/CDP đạt toàn bộ contract giao diện gọn ở 1440×1000 và 1024×900, gồm `Sao chép ảnh → Đã đặt` và chọn riêng phiếu giao theo bếp.
- Sau bổ sung cơ chế QA cô lập, full regression cuối đạt `385/385`, không lỗi/không skip; QC cuối `ok=true`. Chế độ QA chỉ chạy khi có cờ riêng, cổng khác 8765 và toàn bộ đường dẫn nằm dưới Windows Temp; khóa một phiên production không thay đổi.
- EXE smoke và Chrome đã dừng; cổng `18804`/`19342` đóng. EXE cũ người dùng đang mở tại `8765` giữ nguyên PID `9488`, không bị dừng hay ghi dữ liệu qua smoke.

## 32. Tổng lượng/tổng tiền và mẫu công nợ phải trả ngày 04/09/2026

- Mọi vùng giao diện có số lượng hàng đã được bổ sung tổng lượng và tổng tiền phù hợp: đơn hàng, phải thu, phải trả, tồn kho, hóa đơn và lịch sử thay thế; các vùng BK/đặt NCC/kế hoạch bếp vốn đã có tổng được giữ nguyên. Phiếu giao ẩn giá vẫn chỉ hiện tổng lượng và ghi rõ giá đang bị ẩn theo cấu hình bếp.
- Excel công nợ phải trả được thay bằng đúng một sheet `Công nợ phải trả`, chỉ có 14 cột khách chốt: `Tháng`, `Tên bếp`, `Ngày, tháng`, `Tên hàng`, `Số lượng`, `ĐVT`, `NCC`, `Giá mua`, `Hỏng`, `Thêm`, `Giảm`, `Thiếu`, `SL thực tế`, `Thành tiền`.
- Dòng cuối cộng tĩnh `Số lượng`, bốn loại điều chỉnh, `SL thực tế` và `Thành tiền`; không dùng công thức. Dòng nguồn đã hoàn tác bị loại khỏi file gửi khách nhưng vẫn còn đầy đủ trong ledger, payment/allocation và revision nội bộ.
- Giao diện phải trả có thẻ `Tổng số lượng`, `Tổng tiền` và dòng `TỔNG THEO BỘ LỌC`; thao tác chọn dòng, phân bổ, thanh toán và hoàn tác không thay đổi.
- Kiểm chứng cuối: full regression `386/386` đạt; `qc_system.py` trả `ok=true`; Chrome/CDP thật trên bản sao database đạt toàn bộ luồng giao diện gọn ở 1440px và 1024px; source `/health` trả HTTP 200, database/schema/integrity đều `ok`.
- Đây là thay đổi source; theo chỉ đạo hiện tại chưa build lại EXE.

## 33. Căn chỉnh lại Giấy biên nhận ngày 04/09/2026

- Giữ nguyên nội dung pháp lý, màu chữ, năm cột, phép tính, giới hạn 5 triệu/người/ngày và nguồn dữ liệu mua/BK đã chốt của mẫu khách.
- Căn lại khối người mua/người bán thành các trục rõ ràng; toàn bộ giá trị định danh người bán nằm thẳng hàng và không còn phụ thuộc khoảng trắng thủ công.
- Bảng hàng dùng thống nhất Times New Roman 12, tăng chiều cao dòng, căn tên–ĐVT–đơn giá–số lượng–thành tiền đúng loại dữ liệu; dòng tổng rõ và thẳng cột.
- Ngày ký được ghép thành một dòng hoàn chỉnh, căn giữa phía bên bán. Hai vùng `Bên mua hàng` và `Bên bán hàng` chia cân trang; tên người bán nằm chính giữa dưới vùng ký.
- Microsoft Excel thật đã xuất candidate thành PDF A4 một trang và kiểm tra trực quan đạt. Full regression `386/386`; QC UTF-8 `ok=true`. Chưa build lại EXE.

## 34. Căn chỉnh lại Phiếu giao hàng theo PDF khách gửi ngày 04/09/2026

- Đối chiếu trực tiếp `Phiếu mua hàng (1).pdf`: nội dung thực tế là `PHIẾU GIAO HÀNG (Kiêm phiếu xuất kho)`, không phải thiếu chức năng phiếu giao.
- Sửa bản Excel hiện tại từ trạng thái bị dồn trái, thiếu tiêu đề cột khi sang trang, còn màu cảnh báo nội bộ và chia trang lệch thành bản A4 dọc dùng hết chiều ngang, đen trắng, cột/dòng đều và chữ hàng hóa rõ.
- Theo ảnh mẫu mới nhất: ba dòng `PHIẾU GIAO HÀNG` → `(Kiêm phiếu xuất kho)` → ngày được tách riêng và căn giữa; ba dòng thông tin nhà cung cấp in đậm; bổ sung `Hình thức thanh toán: TM/CK`. Đưa Tên hàng–SL–ĐVT gần nhau; tên dài tự tăng chiều cao; bốn vùng ký và bốn chú thích được căn thẳng hàng bằng chữ/ô Excel thật, không chèn ảnh.
- Với phiếu dài, hệ thống tự chia đều số dòng giữa các trang và lặp hàng tiêu đề. Candidate 32 dòng giống tình huống khách gửi được chia `16 + 16`, thay cho `18 + 14` của source trước sửa hoặc `24 + 8` trong PDF khách gửi.
- Microsoft Excel thật đã render candidate 32 dòng thành PDF A4 hai trang; đã kiểm tra trực quan trang đầu, trang tiếp và vùng ký. Chưa build lại EXE.

## 35. Rà soát cuối toàn bộ giấy tờ ngày 04/09/2026

- Đã dựng lại 18 bộ PDF/44 trang từ source hiện tại và rà trực quan toàn bộ; không dùng lại ảnh/PDF cũ để kết luận.
- Đã sửa các lỗi còn sót ở bảng kê đầu ra, dòng tổng bảng lương, vùng tổng công nợ phải thu và cách chọn khổ giấy/căn giữa cho các bảng công nợ ít cột.
- Đã sửa tính không ổn định của SHA-256 hồ sơ suất ăn BOT do thời gian `modified` tự đổi khi lưu Excel.
- Kết quả cuối: kiểm thử trọng điểm `50/50`, full regression `391/391`, QC `ok=true`.
- Mở `KIEM_TRA_CUOI_BIEU_MAU_20260904/KET_QUA_KIEM_TRA.md` để xem danh mục và bằng chứng; chưa build lại EXE.

## 36. Chốt kho tháng và chuyển tồn sang tháng sau ngày 04/09/2026

- Màn `Báo cáo vật tư hàng hóa` có vùng chốt tháng ngay bên ngoài: hiện tháng nguồn, tháng nhận tồn, số mặt hàng, tổng lượng và tổng giá trị tồn cuối.
- Nút chốt dùng đúng projection bình quân di động của sổ TĐK–Nhập–Xuất–NXT để thay toàn bộ snapshot `OPENING` tháng sau; không cộng dồn với tồn đầu đang có và bấm lặp lại không nhân đôi.
- Hệ thống chỉ cho chốt tháng đã kết thúc, chặn mã âm/cần kiểm tra, khóa bằng dấu vết số liệu nguồn và tồn đầu đích để tránh xác nhận trên dữ liệu vừa thay đổi. Nếu tháng sau đã có phát sinh, hệ thống rebuild kiểm tra và hoàn tác toàn giao dịch nếu tạo âm kho.
- Có `Mở lại tháng` để bỏ tạm snapshot tháng sau và cho phép làm lại dữ liệu tháng trước; sau khi sửa phải chốt lại. Không cho mở ngược khi tháng sau đã chốt tiếp.
- Mỗi lần chốt/mở lại có trạng thái, số lần sửa và audit; migration tạo bảng trạng thái riêng, không sửa ledger hóa đơn bất biến.
- Kiểm thử mới phủ tính đúng số lượng/giá trị, idempotency, mở–tính lại–chốt lại, stale guard, tháng chưa kết thúc, downstream guard và API xác nhận. Full regression `399/399`, QC `ok=true`; Chrome thật đạt trạng thái xem trước → đã chốt → có thể mở lại tại 1440px và 1024px, không tràn ngang. Chưa build lại EXE.
