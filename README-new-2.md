# TỔNG HỢP ĐẦU VIỆC SAU CUỘC GỌI KHÁCH HÀNG 04/09/2026

> **Quyết định mới của chủ dự án:** lưu mốc source lên `xandrosworld/CDT`, sau đó
> chuyển sang web Railway cho khách, không tiếp tục bàn giao EXE như trước.
> Mốc Git này chưa phải bản đã triển khai/nghiệm thu Railway. Xem **13.12**.

> **Lỗi 1 (BUG-0509-04): đã sửa và kiểm chứng bằng EXE ứng viên `2026.09.05.2`.**
> Chạy chính EXE trên bản sao DB cũ đạt **257 → 266**, mở lại lần hai vẫn đúng;
> danh sách/API và Excel khớp tập hóa đơn, tổng tiền **919.234.874 đồng**.
> DB nhúng trong EXE mới cũng đủ 266. Chưa thay bản khách đang dùng, chưa tạo ZIP
> bàn giao chung; các lỗi khác vẫn mở. Bằng chứng và giới hạn tại **13.11**.
>
> **P0 — đã giải thích được 266 → 257 trên DB local:** ngày hóa đơn cũ lưu theo
> ngày UTC, lệch sớm một ngày. Đọc lại timestamp nguồn theo giờ Việt Nam cho
> **266 hóa đơn đầu vào tháng 8**, trong khi lọc ngày đã lưu chỉ có **257**;
> **9 hóa đơn ngày 01/08 bị lưu thành 31/07**. DB vận hành gốc chưa bị sửa. File khách gửi
> tiếp là bảng kê phiếu nhập, có **261 phiếu**, cần đối chiếu riêng. Xem mục 13.9.
> **Đã kiểm tra trực tiếp EXE bàn giao trên D:** hàm sửa múi giờ có trong bản
> `2026.09.05.1`, nhưng DB khởi tạo bên trong EXE vẫn sai ngày và DB của lần
> smoke chạy EXE hai lần vẫn chỉ có 257. Thiếu xử lý dữ liệu lịch sử và kiểm tra
> số liệu sau nâng cấp, không phải quên đóng gói hàm sửa ngày. Xem mục 13.10.
>
> **Cập nhật rà soát phản ánh khách chiều 05/09/2026:** đã xác nhận lỗi đọc NCC,
> thiếu tương thích sheet đặt hàng của file 03/09 và thiếu luồng lập đề nghị thanh
> toán trực tiếp từ hóa đơn VAT đã đồng bộ. Xem **mục 13** để phân biệt lỗi đã
> chứng minh, yêu cầu giao diện bổ sung và phần còn cần dữ liệu khách.
> **Ngoài lỗi 1, các phát hiện mới chưa được sửa.** Các mục kiểm tra trước 13.11
> lưu lịch sử tại thời điểm kiểm tra; không dùng trạng thái build cũ để kết luận hết lỗi.

> Trạng thái mới nhất 05/09/2026: **ĐÃ BUILD EXE 2026.09.05.1 VÀ KIỂM TRA BẢN ĐÓNG GÓI**.
> File bàn giao: `D:\TDP_BAN_GIAO_20260905\Thanh_Dat_Phat.exe` (90.870.375 byte).
> SHA-256: `8FE9904BFC4CCFB8712FE246C0B7E1F43F3CEB18A32A92BA392BAAB5D37BDE4E`.
> Các ghi chú “chưa build” ở kết quả từng lượt là lịch sử trước bản này; không phải trạng thái bàn giao hiện tại.
>
> File này được lập sau khi đọc toàn bộ cuộc gọi dài 61 phút 12 giây trong
> `transcript_cuoc_goi_20260904.txt` và các quyết định bổ sung của chủ dự án.
> Khi có mâu thuẫn với ghi chú cũ, quyết định mới trong file này được ưu tiên cho
> đợt sửa tiếp theo. Không tự mở rộng sang phần AI/giai đoạn 2.

## 1. Mục tiêu cần đạt

Hệ thống phải giúp khách làm được một chu trình thực tế, liền mạch và dễ hiểu:

1. Nạp đơn hàng hằng ngày.
2. Sửa hết lỗi bắt buộc rồi duyệt đơn.
3. Tạo đơn đặt nhà cung cấp và phiếu giao.
4. Tải hóa đơn đầu vào, ghép mã và ghi nhập kho.
5. Xác định rõ phần được xuất và chưa được xuất hóa đơn đầu ra.
6. Chỉ xuất trong phạm vi tồn kho hóa đơn, tuyệt đối không làm âm kho.
7. Tải file đúng chuẩn để đưa lên M-Invoice.
8. Theo dõi phải thu, phải trả và các khoản đã thanh toán.
9. Đối chiếu nhập–xuất–tồn cuối tháng.
10. Chuyển tồn cuối tháng trước thành tồn đầu tháng sau.

Khách không muốn phải tải Excel chỉ để xem thông tin. Dữ liệu phải xem trực tiếp
trên phần mềm; chỉ kết xuất khi cần gửi, in hoặc lưu hồ sơ.

## 2. Quyết định thay đổi phạm vi đã chốt

### 2.1. Bỏ hai module không còn phù hợp

Bỏ khỏi giao diện và quy trình sử dụng hằng ngày:

- `Suất ăn & đặt hàng bếp/PO`.
- `Chấm công & lương` cùng phần chấm suất liên quan.

Nguyên nhân:

- Định mức suất ăn thay đổi theo từng ngày, không có một công thức cố định đủ giá trị.
- Khách đã có file Excel riêng để tính và in.
- Việc nạp lại các file này không giúp giảm đủ công việc thực tế.

Nguyên tắc khi bỏ:

- Ẩn menu, nút và hướng dẫn liên quan khỏi giao diện chính.
- Không xóa dữ liệu lịch sử hoặc bảng dữ liệu đang có.
- Không để hai module tiếp tục tham gia vào báo cáo, điều hướng hoặc quy trình nghiệm thu.
- Giữ khả năng khôi phục về sau nếu có yêu cầu mới bằng văn bản.

Bổ sung khách nhắn ngày 05/09/2026, đã được chủ dự án hỏi và xác nhận lại: **giữ chức năng kho hàng thực tế gắn với đặt hàng, đặt hàng là trừ tồn ngay dù chưa giao**, để khách xem hàng còn/hết và lên kế hoạch nhập. Không được bỏ chức năng kho này cùng module suất ăn/PO.

- Khi sửa số lượng của đơn đã đặt, chỉ cập nhật phần chênh lệch; hủy đơn thì hoàn lại lượng đã trừ.
- Giao hàng sau đó không trừ lần hai; bấm lại hoặc nạp lại cùng đơn không được trừ trùng.
- Đây là quy tắc kho thực tế, không thay đổi quy tắc kho hóa đơn và không dùng tồn thực tế để mở khóa xuất hóa đơn.
- **Đã triển khai source lượt 2 ngày 05/09/2026, chưa build EXE.** Đơn khách đã lưu là nguồn trừ kho; đặt mua thêm NCC không phải xuất kho. Nguồn và bằng chứng kiểm thử ghi tại mục 10.2 bên dưới.

### 2.2. Phần thay thế ngang phạm vi

Thay hai module trên bằng chức năng **xem trực tiếp chứng từ dạng bảng Excel trên web**.

- Áp dụng cho toàn bộ chứng từ/báo cáo còn nằm trong phạm vi hệ thống.
- Mở mục nào phải xem được dữ liệu của mục đó ngay trên màn hình.
- Không tự tải file khi người dùng chỉ muốn xem.
- Vẫn giữ nút tải Excel/PDF/ZIP khi cần gửi khách, in hoặc lưu hồ sơ.
- Đây là thay đổi ngang phạm vi, **không tính thêm tiền** trong đợt hiện tại.

### 2.3. Giai đoạn 2

Các chức năng AI vẫn là giai đoạn 2 và phải có báo giá/hợp đồng riêng:

- AI hỗ trợ đọc và nhập đơn.
- AI hỗ trợ đặt hàng.
- AI hỗ trợ lập/xuất hóa đơn.
- Các tự động hóa mới chưa được mô tả và nghiệm thu trong giai đoạn hiện tại.

Không dùng các con số ước lượng miệng trong cuộc gọi làm báo giá chính thức.

## 3. Đầu việc ưu tiên P0 – bắt buộc đúng trước khi bàn giao lại

### 3.1. Không được âm tồn kho hóa đơn

Đây là yêu cầu khách nhấn mạnh nhất.

- Tồn được phép xuất phải lấy từ sổ kho hóa đơn chuẩn.
- Không dùng tồn điều chỉnh tay hoặc nguồn không đủ điều kiện để mở khóa xuất hóa đơn.
- Với mỗi mã hàng, số lượng xuất không được vượt số lượng tồn khả dụng tại thời điểm xuất.
- Nếu khách cần 10 nhưng chỉ còn tồn 7, hệ thống chỉ cho xuất 7.
- Ba đơn vị còn thiếu phải được giữ lại cho lần xử lý tiếp theo.
- Không được làm mất dòng thiếu, không xuất trùng và không giữ tồn trùng qua nhiều vòng.
- Nếu bất kỳ thao tác xác nhận/phát hành nào làm âm một mã hàng, hệ thống phải chặn toàn bộ giao dịch và chỉ rõ mã, lượng cần, lượng có và lượng thiếu.
- Hoàn tác hóa đơn phải hoàn trả đúng lượng đã trừ và không làm sai thứ tự lịch sử.

Màn tổng quan phải luôn hiện rõ:

- Tổng số lượng khách cần.
- Số lượng đã tạo dự thảo.
- Số lượng đã phát hành.
- Số lượng hiện có thể xuất.
- Số lượng còn thiếu.
- Giá trị tương ứng của phần được xuất và phần còn thiếu.

### 3.2. Tách rõ “được xuất” và “chưa được xuất”

Tại `Bảng kê & hóa đơn`:

- Hiện bảng tổng theo từng nhà thầu ngay ngoài màn hình.
- Có thể mở chi tiết từng mã hàng/bếp.
- Phần đủ điều kiện phải có nút tạo/tải file rõ ràng.
- Phần chưa đủ tồn phải có lý do cụ thể, không chỉ hiện trạng thái chung.
- Phần thiếu được giữ lại và tự tính tiếp khi có thêm hóa đơn đầu vào hợp lệ.
- Dòng đã phát hành không được đưa trở lại đợt sau.
- Dòng đang được dự thảo giữ tồn không được dùng cho dự thảo khác.
- File tải lên M-Invoice phải tách đúng nhà thầu, nhóm thuế và vòng xuất.

Quy trình phải được viết ngay trên màn hình bằng ngôn ngữ người dùng:

`Duyệt đơn → Ghi đủ đầu vào → Xem phần được xuất → Tạo file hóa đơn → Phát hành → Phần thiếu tiếp tục chờ`.

Kết quả rà và sửa riêng 3.1–3.2 ngày 05/09/2026 (source, chưa build EXE):

- Luồng phân bổ một phần, giữ thiếu và tạo nhiều vòng đã có trước đợt rà này; đã kiểm tra lại, không ghi thành chức năng mới làm.
- Sửa phép kiểm tra tồn tại ngày hóa đơn: phải xét cả ngày không có bút toán. Không cho lấy đầu vào ngày hôm sau để bù âm cho ngày phát hành trước đó.
- Đơn hàng cũ vẫn được lập tiếp phần thiếu khi có thêm đầu vào. Ngày đơn hàng không mặc nhiên là ngày phát hành; kiểm tra chặn âm khi xác nhận dùng ngày hóa đơn thực tế. File tải trung gian không có cột ngày phát hành, nên kiểm tra lượng đang giữ/tồn hiện có khi tải và kiểm tra ngày thực tế khi xác nhận.
- Kiểm tra lại tồn khi xác nhận đã phát hành; báo mã hàng, lượng cần/có/thiếu và giữ nguyên dự thảo khi bị chặn. Nếu hóa đơn M-Invoice tương ứng đã được ghi kho, không trừ hai lần khi ghi nhận lại dự thảo cục bộ.
- Trước khi tải file hoặc gửi dự thảo lên M-Invoice, kiểm tra phần giữ tồn còn khớp số lượng và còn đủ tồn. Gửi trực tiếp M-Invoice kiểm tra thêm theo ngày hóa đơn trong dự thảo; không tự đổi ngày để vượt chốt.
- Lỗi giữa lúc tạo dự thảo cho nhiều nhà thầu phải hoàn tác cả giao dịch, không để lại một phần đã giữ tồn.
- Màn được/chưa được xuất đã bổ sung giá trị tiền tương ứng và lý do thiếu; dòng đã phát hành không còn bị ghi nhầm là đang dự thảo.
- Kiểm tra: **116 test đạt** về phân bổ, xuất nhiều vòng, kho hóa đơn, hoàn tác, xuất file thuế, đồng bộ, định giá và chốt tháng. Có test hai yêu cầu đồng thời không giữ vượt tồn, lỗi giữa chừng không lưu dở, tồn thay đổi thì chặn tải/gửi/xác nhận.
- Browser smoke trên Edge headless đạt: cần 10 → lập được 7/thiếu 3 → giữ 7 trong dự thảo → bổ sung đầu vào 3 thì còn lập được 3. Kiểm tra cả tiền và lý do thiếu. Ảnh kiểm tra: `D:\TDP_TEMP_OUTGOING\readiness-browser.png`.
- Chỉ dùng database cô lập và dữ liệu giả, không gọi ghi dữ liệu lên M-Invoice thật, không sửa database khách. Chưa build EXE; kết quả này không đồng nghĩa toàn bộ checklist đã hoàn thành.

### 3.3. Hóa đơn đầu vào và ghi kho

- Bộ lọc ngày phải dùng ngày Việt Nam, không cắt trực tiếp ngày UTC.
- Khoảng 01/08/2026–31/08/2026 phải nhận đúng 266 hóa đơn nguồn mSMI.
- Hóa đơn ngoài khoảng ngày không được gắn nhầm vào đợt tải.
- Tải lại cùng phạm vi không nhân đôi dữ liệu.
- Dòng chưa ghép mã, thiếu đơn vị hoặc có lỗi phải tự đưa lên đầu.
- Có bộ lọc `Chưa ghép mã`, `Cần kiểm tra`, `Sẵn sàng`, `Đã ghi kho`.
- Tiêu đề bảng phải cố định khi cuộn.
- Mã gợi ý chỉ được lưu sau khi người dùng xác nhận; không tự đoán trường hợp không chắc chắn.
- Sau khi ghép mã phải có bước xác nhận ghi nhập kho rõ ràng.
- Ghi kho xong phải có đường dẫn/nút mở thẳng sang chi tiết nhập trong `Báo cáo vật tư hàng hóa`.
- Trạng thái phải phân biệt rõ: đã tải, chưa ghép, sẵn sàng, đã ghi kho và lỗi.

### 3.4. Hóa đơn đầu ra M-Invoice

- Bộ lọc khoảng ngày phải dùng cùng quy tắc ngày Việt Nam như đầu vào.
- Không lấy nhầm hóa đơn đầu hoặc cuối kỳ do timestamp UTC.
- Phân biệt rõ dự thảo cục bộ, đã phát hành, đã hủy và thất bại.
- Chỉ hóa đơn đã phát hành hợp lệ mới được ghi xuất kho hóa đơn.
- Lỗi kết nối hoặc trạng thái không rõ phải dừng an toàn, không tự coi là đã phát hành.
- Tải lại cùng khoảng không nhân đôi hóa đơn hoặc bút toán kho.
- Màn hình phải nói rõ file nào dùng để tải lên M-Invoice và file nào chỉ dùng đối chiếu.

### 3.5. Chốt tháng và chuyển tồn

- Chọn đúng tháng cần chốt.
- Hiện tổng số mã, tổng lượng và tổng giá trị tồn cuối trước khi xác nhận.
- Chặn chốt nếu còn mã âm hoặc mã cần kiểm tra.
- Tồn cuối tháng 8 trở thành đúng tồn đầu tháng 9.
- Không cộng chồng với tồn đầu tháng 9 đã có.
- Bấm lại không nhân đôi.
- Có chức năng mở lại tháng 8 khi cần sửa, nhưng phải kiểm tra các kỳ phía sau.
- Sau khi sửa tháng 8 phải chốt lại **tháng 8** để cập nhật tồn đầu tháng 9. Nếu các tháng sau đã chốt, phải mở lại theo thứ tự từ tháng sau về trước; không tự chốt tháng 9 khi tháng đó chưa kết thúc.
- Mọi lần chốt/mở phải có lịch sử và người thao tác.

### Kết quả lượt 1 ngày 05/09/2026 — đã sửa source, chưa build EXE

- **Danh sách hóa đơn:** sửa lỗi chỉ xem lần tải mới nhất. Lấy đầy đủ hóa đơn trong ngày đang lọc, kể cả khi trước đó tải cả tháng, tải nhiều lần chồng nhau hoặc nhập từ luồng cũ; không đếm trùng. Đầu vào và đầu ra dùng chung cách lọc theo ngày hóa đơn đã chuẩn hóa.
- **Bảng làm việc trực tiếp:** gom dòng thiếu mã/lỗi lên trên toàn bảng; lọc trạng thái từng hóa đơn và từng dòng; nhảy đến dòng cần sửa; giữ tiêu đề và cột nhận diện khi cuộn. Lịch sử tải được thu gọn, không lấy số lần tải làm số hóa đơn.
- **Tổng và Excel:** nút `Excel đúng bộ lọc` dùng chung nguồn và bộ lọc với bảng. Tổng lượng tách theo ĐVT; tiền dòng chưa thuế tách rõ với tổng thanh toán hóa đơn (mỗi hóa đơn tính một lần). Giữ số lượng đến 6 chữ số lẻ; tiền hiển thị nguyên đồng, không sửa giá trị nghiệp vụ gốc. Chuỗi nguồn không được biến thành công thức Excel.
- **Ghi kho và tra cứu:** giữ bước xác nhận; hủy xác nhận không ghi dữ liệu, bấm lại không ghi trùng. Có nút mở đúng các dòng hàng của hóa đơn vừa ghi trong `Báo cáo vật tư hàng hóa`, chọn sẵn tháng tương ứng, giữ ĐVT tại lần ghép đã ghi sổ. Nút này vẫn có sau khi bộ lọc sẵn sàng không còn chứa hóa đơn vừa nhập.
- **Kho tháng:** đã rà lại chốt, mở lại, chốt lại, chặn âm và thay tồn đầu tháng sau không cộng chồng. Bảng nhập–xuất–tồn mở trực tiếp. Bổ sung cảnh báo hóa đơn đã tải nhưng chưa ghi kho trước khi chốt. Thêm tên người xác nhận và lịch sử chốt/mở ngay tại màn kho; tên do người dùng nhập, không phải tài khoản đã xác thực. Không gán tên cho lịch sử cũ.
- **Kiểm thử:** 191 test đạt trên 20 nhóm liên quan (hóa đơn đầu vào/đầu ra, ghép mã/quy đổi, sổ kho, định giá, chuyển kỳ, xuất Excel, chống âm/phân bổ và bảo vệ dữ liệu). Có test phản hồi tải chậm không ghi đè bộ lọc mới, lỗi tải không để lại danh sách cũ, tổng theo bộ lọc khớp Excel, số lượng `0,855` không bị hiển thị thành `0,86`.
- **Trình duyệt thật:** Edge headless đạt luồng lọc → mã sai bị chặn → Enter ghép mã → quy đổi → hủy/xác nhận nhập → mở đúng chi tiết → xác nhận xuất → chốt/mở/chốt lại → đối chiếu lượng và giá trị đầu tháng sau. Kiểm tra quy mô **266 hóa đơn giả lập / 285 dòng**, tiêu đề, thanh cuộn, tên người xác nhận trong lịch sử; không tràn trang tại 1440px và 1024px. Script tái chạy: `tdp_system/browser_smoke_invoice_round1.js`; fixture riêng: `tdp_system/browser_fixture_invoice_round1_server.py`.
- Ảnh bằng chứng: `D:\TDP_ROUND1\invoice-table-browser.png`, `D:\TDP_ROUND1\stock-trace-browser.png`. Số 266 trong kiểm thử lần này là **dữ liệu giả lập**, không phải một lần đối soát mới với tài khoản thật của khách.
- **Giới hạn:** không sửa database khách, không ký/phát hành/sửa hóa đơn lên nguồn thật, không đổi quy tắc kho thực tế của lượt 2. Chỉ bổ sung phụ thuộc vào script đóng gói cho lần build sau; **không chạy build EXE**. Không dùng kết quả lượt này để đánh dấu xong các lượt 2–5 hoặc thay cho nghiệm thu dữ liệu thật trên máy khách.

## 4. Đầu việc ưu tiên P1 – giao diện phải dùng được ngay

### 4.1. Nhập và sửa đơn

- Có nút đưa thẳng tới dòng lỗi đầu tiên.
- Có bộ lọc chỉ hiện dòng đỏ/lỗi bắt buộc.
- Có bộ lọc cảnh báo riêng, không trộn với lỗi chặn duyệt.
- Tiêu đề cột cố định khi cuộn dọc.
- Cột quan trọng không bị cách nhau quá xa.
- Hiện tổng số dòng, tổng lượng và tổng tiền theo bộ lọc.
- File hợp lệ tải sau cùng của cùng ngày là bản đang sử dụng.
- Khi nạp lại phải nói rõ dữ liệu nào được thay, dữ liệu nào được giữ.

### 4.2. Đặt hàng nhà cung cấp

- Màn ngoài chỉ giữ tên NCC, số dòng, tổng lượng, tổng tiền và trạng thái.
- Chi tiết mặt hàng mở bên trong hoặc trong ảnh gửi NCC.
- Sao chép thành công tự chuyển trạng thái `Đã đặt`.
- NCC đã đặt được đẩy xuống dưới; NCC chưa đặt nằm trên.
- Có nút mở lại khi phải sửa hoặc gửi lại.

### 4.3. Điều hướng gọn

- Bỏ mục `Phiếu giao` riêng nếu chức năng đã có đầy đủ trong `Công việc hằng ngày`.
- Bỏ hai mục `Suất ăn & đặt hàng bếp/PO` và `Chấm công & lương` theo quyết định tại mục 2.
- Không để một nghiệp vụ xuất hiện ở nhiều menu khiến khách không biết phải vào đâu.
- Mỗi màn phải có một câu mô tả ngắn: dùng để làm gì và bước tiếp theo là gì.

### 4.4. Báo cáo tổng hợp

- Danh sách dòng phải lấy từ danh mục bếp và nhà thầu hiện tại.
- Bếp mới được khai báo phải tự xuất hiện trong báo cáo.
- Không giới hạn dữ liệu theo những dòng có sẵn trong file mẫu.
- File mẫu chỉ quyết định bố cục, tiêu đề, định dạng và thứ tự nhóm.
- Dữ liệu thực tế quyết định số dòng được tạo.
- Có tổng tháng và tổng theo nhóm/nhà thầu.

### 4.5. Công nợ phải trả

- Chọn được từ ngày, đến ngày, tất cả NCC hoặc một NCC.
- Màn hình hiện trực tiếp bảng công nợ, tổng lượng và tổng tiền.
- File Excel giữ đúng mẫu 14 cột khách đã chốt.
- Khi chọn tất cả phải có phần tổng và dữ liệu theo từng NCC.
- Khi khách trả tiền, dùng thao tác `Ghi nhận đã trả`.
- Mặc định danh sách công nợ chỉ hiện khoản còn phải trả.
- Khoản đã trả được ẩn khỏi danh sách còn nợ nhưng vẫn tra cứu được trong lịch sử.
- Tuyệt đối không xóa chứng từ, khoản nợ hoặc lịch sử thanh toán thật.
- Có thể hoàn tác thanh toán sai với lý do và dấu vết người thao tác.

### 4.6. Công nợ phải thu

- Giữ ba lựa chọn ngoài màn: phải thu theo bếp, phải thu tổng và phải trả.
- Phải thu theo bếp có chi tiết từng mặt hàng.
- Phải thu tổng cộng đúng toàn bộ bếp của nhà thầu.
- Khoản khách đã trả phải được ghi nhận, không xóa lịch sử.
- Excel/ZIP chỉ tải khi người dùng yêu cầu.

### 4.7. Tự động lưu và sao lưu

- Mọi thao tác xác nhận phải lưu ngay vào database.
- Không bắt người dùng nhớ bấm sao lưu cuối ngày.
- Hệ thống tự tạo bản sao lưu theo lịch và giữ số bản hợp lý.
- Màn hình chỉ cần hiện lần sao lưu gần nhất và trạng thái thành công/thất bại.
- Sao lưu lỗi không được làm mất dữ liệu đang vận hành.

## 5. Xem chứng từ trực tiếp dạng Excel trên web

### 5.1. Phạm vi

Áp dụng cho các chứng từ/báo cáo còn sử dụng sau khi bỏ hai module:

- Đơn hàng và bảng sửa đơn.
- Đơn đặt nhà cung cấp.
- Phiếu giao hàng.
- Báo giá tổng và báo giá theo nhà thầu.
- Báo cáo tổng hợp.
- Công nợ phải thu theo bếp.
- Công nợ phải thu tổng.
- Công nợ phải trả.
- Hóa đơn đầu vào và danh sách ghép mã.
- Phần được/chưa được xuất hóa đơn đầu ra.
- File tải hóa đơn M-Invoice.
- Bảng kê giao nhận và đề nghị thanh toán.
- Tồn đầu, nhập, xuất và nhập–xuất–tồn.
- Giấy biên nhận và các giấy tờ in còn lại.

### 5.2. Hành vi bắt buộc

- Khi mở mục, dữ liệu hiển thị ngay trên web; không tự tải file.
- Bảng có thanh cuộn ngang và dọc khi nhiều cột/dòng.
- Hàng tiêu đề cố định.
- Cột số lượng, đơn giá và thành tiền căn phải và có tổng.
- Có chế độ thu gọn/tổng quan và nút mở chi tiết.
- Có thể phóng to/thu nhỏ để người lớn tuổi dễ đọc.
- Bảng hiển thị và file tải phải dùng cùng một nguồn dữ liệu, không được lệch số.
- File tải vẫn giữ đúng mẫu khách, khổ giấy và quy tắc in.
- Không hiển thị các cột kỹ thuật, ID nội bộ hoặc trạng thái khó hiểu ở màn tổng quan.
- Thông báo lỗi phải chỉ rõ dòng/cột và cho phép đi thẳng tới vị trí cần sửa.

## 6. Giấy tờ và dữ liệu người bán

### 6.1. Giấy biên nhận

- Không dùng một địa chỉ/nơi cấp mặc định cho tất cả người bán.
- Số CCCD, ngày cấp, nơi cấp và địa chỉ phải lấy cùng một hồ sơ người bán.
- Trường hợp người bán ở Thái Bình không được tự hiện Hải Phòng.
- Có nguồn/danh mục CCCD riêng để quản lý và đối chiếu.
- Thiếu dữ liệu phải cảnh báo và chặn in chính thức; không tự điền đoán.
- Ngày ký, hai bên ký và tên người bán phải căn đúng mẫu khách.

Nguồn dữ liệu khách gửi bổ sung ngày 04/09/2026:

- File `THÀNH ĐẠT PHÁT- BCTC 2025 bản in (Hà 080626) - in.xls`.
- Dùng sheet `CCCD` làm nguồn tham chiếu thông tin người bán.
- Khóa đối chiếu là **Tên người bán** ở cột B.
- Địa chỉ lấy từ cột C; số CCCD lấy từ cột D; ngày cấp lấy từ cột E; nơi cấp lấy từ cột F.
- Sheet có 52 người bán không trùng tên và đủ các trường trên: 29 địa chỉ Hải Phòng, 23 địa chỉ Thái Bình.
- Khi tạo giấy biên nhận phải dò đúng người bán rồi lấy đồng bộ các cột C–F của chính người đó.
- Nếu không tìm thấy tên hoặc dữ liệu không khớp thì phải báo thiếu để người dùng xử lý; tuyệt đối không tự gán địa chỉ Hải Phòng.

Kết quả triển khai riêng mục CCCD/địa chỉ ngày 05/09/2026 (source, chưa build EXE):

- Đã trích riêng dữ liệu sheet `CCCD` vào `tdp_system/templates/seller_identities_20260904.xlsx`; không chép các sheet BCTC hay macro. Đối chiếu 318 ô gồm tiêu đề và 52 hồ sơ, khớp file XLS gốc mở chỉ đọc.
- Khi khởi động, cập nhật đủ địa chỉ/số giấy tờ/ngày cấp/nơi cấp kể cả máy đã nạp danh mục cũ. Không sửa đơn hàng lịch sử; không nạp đè lại hồ sơ ở lần khởi động sau khi nguồn không đổi. Nạp lại `Em Thành.xlsx` không ghi ngược thông tin người bán về bản cũ.
- Biên nhận lấy cùng một hồ sơ người bán; thiếu địa chỉ, không tìm thấy tên, sai số giấy tờ hoặc số giấy tờ dùng cho nhiều người thì chặn xuất và báo lỗi.
- **Quyết định thay thế ngày 05/09/2026:** Đoàn Văn Giang (dòng 15) và Nguyễn Văn Toại (dòng 23) bị loại khỏi lựa chọn và bảng kê/biên nhận mới; không chờ khách sửa CCCD nữa. Giữ nguyên nguồn, đơn hàng, kho, công nợ và lịch sử; không đoán số giấy tờ. Bộ có cả người hợp lệ và bị loại chỉ lập phần hợp lệ, thông báo rõ phần bị loại; bộ toàn người bị loại phải báo không có chứng từ hợp lệ.
- Kiểm tra: 44 bài test đạt, gồm cập nhật danh mục, xuất bảng kê/biên nhận, xuất/in chứng từ và chốt số liệu. Trong test dùng 52 hồ sơ nguồn: 50 hồ sơ xuất đúng các ô D9–D12; 2 hồ sơ trùng số bị chặn đúng. Chỉ dùng database kiểm thử, chưa cập nhật database đang làm việc của khách.

### 6.2. Phiếu giao và các mẫu khác

- Giữ bố cục đen trắng, cân khổ giấy và không dùng ảnh chèn thay vùng chữ ký.
- Tên hàng dài phải tự tăng chiều cao dòng, không đè đường viền.
- Ngày, tiêu đề và phần ký phải đúng vị trí mẫu khách.
- Mọi biểu mẫu có số lượng phải có tổng lượng; có tiền phải có tổng tiền.
- Bản xem trên web và bản tải/in phải khớp dữ liệu tuyệt đối.

## 7. Các quy tắc không được hiểu sai

- Duyệt đơn hàng không đồng nghĩa tự động phát hành hóa đơn đỏ.
- Duyệt đơn không tự động ghi mọi hóa đơn đầu vào vào kho.
- Hóa đơn đầu vào chỉ tăng kho sau khi ghép mã, kiểm tra và xác nhận ghi kho.
- Hóa đơn đầu ra chỉ giảm kho sau khi phát hành hợp lệ.
- Riêng kho thực tế: đơn đã đặt trừ tồn ngay dù chưa giao; sửa/hủy điều chỉnh lại, giao không trừ lần hai. Không áp dụng quy tắc này sang kho hóa đơn.
- Công nợ vận hành và công nợ theo hóa đơn đỏ là hai nguồn khác nhau.
- `Đã trả` không có nghĩa xóa lịch sử công nợ.
- `Chưa được xuất` không có nghĩa bỏ dòng; dòng phải được giữ cho lần sau.
- Timestamp UTC phải được đổi sang ngày Việt Nam trước khi lọc kỳ.
- File mẫu quyết định hình thức, không được khóa cứng danh sách dữ liệu.
- Không dùng từ `100%`, `hoàn tất` hoặc `đã nghiệm thu` nếu chưa chạy được quy trình thật trên dữ liệu khách.

## 8. Hướng dẫn sử dụng và bàn giao

- Khi có bản chốt, tạo lối mở thuận tiện để khách không phải tìm EXE mỗi lần.
- Làm lại hướng dẫn Word theo đúng giao diện cuối.
- Làm clip thao tác bằng dữ liệu mẫu gần dữ liệu thật.
- Hướng dẫn phải đi theo quy trình công việc, không đi lần lượt theo menu kỹ thuật.
- Mỗi bước phải nói rõ: vào đâu, bấm gì, kết quả đúng trông như thế nào.
- Có riêng một đoạn hướng dẫn xử lý các lỗi thường gặp:
  - Dòng đỏ chưa sửa.
  - Chưa ghép mã.
  - Chưa ghi kho.
  - Không đủ tồn để xuất.
  - Sai khoảng ngày.
  - Chưa có bảng giá tháng.
  - Không chốt được tháng vì còn tồn âm.

## 9. Tiêu chí nghiệm thu bắt buộc

Chỉ bàn giao bản mới khi chứng minh được đầy đủ các tình huống sau trên bản sao dữ liệu an toàn:

1. Tải hóa đơn đầu vào tháng 8 đúng 266 hóa đơn.
2. Tải lại không nhân đôi.
3. Dòng chưa ghép mã tự nổi lên đầu và có thể lọc riêng.
4. Ghép mã, xác nhận và ghi kho xong xem được ngay trong báo cáo vật tư.
5. Đơn cần 10 nhưng tồn 7 chỉ được xuất 7; còn thiếu 3 được giữ lại.
6. Có thêm đầu vào thì ba đơn vị còn thiếu được xử lý tiếp, không xuất trùng.
7. Không thao tác nào tạo tồn âm **trong kho hóa đơn**. Kho thực tế theo đơn đặt trước phải hiện rõ phần thiếu nếu lượng đặt lớn hơn hàng có; không dùng phần thiếu này để cho phép xuất hóa đơn.
8. File M-Invoice chỉ chứa phần đủ điều kiện.
9. Bếp mới trong danh mục tự xuất hiện trong báo cáo tổng hợp.
10. Khoản công nợ đã trả biến khỏi danh sách còn nợ nhưng vẫn có trong lịch sử.
11. Tồn cuối tháng 8 chuyển đúng thành tồn đầu tháng 9 và bấm lại không cộng trùng.
12. Giấy biên nhận dò đúng tên trong sheet `CCCD`, lấy đồng bộ địa chỉ/số CCCD/ngày cấp/nơi cấp và không tự gán Hải Phòng.
13. Tất cả chứng từ trong phạm vi xem được trực tiếp trên web.
14. Bảng xem trên web khớp tổng lượng/tổng tiền với file Excel/PDF tải xuống.
15. Hai module đã bỏ không còn xuất hiện trên menu hoặc hướng dẫn chính.
16. Dữ liệu cũ vẫn còn nguyên sau nâng cấp.
17. Tự động lưu và sao lưu hoạt động mà người dùng không phải bấm cuối ngày.
18. EXE cuối khởi động được trên máy khách và dùng lại database hiện tại.
19. Kho thực tế: tồn 10, đặt 4 chưa giao còn 6; sửa thành 5 còn 5; hủy đơn trở lại 10. Giao hoặc gửi/nạp lại cùng đơn không trừ thêm lần nữa. Các thao tác này không làm thay đổi sổ kho hóa đơn.

## 10. Kế hoạch gom việc ngày 05/09/2026

### 10.1. Phần đã kiểm tra và phần đang chờ

- Kho hóa đơn, được/chưa được xuất: đã rà/sửa và có kết quả test tại 3.1–3.2. Giữ các test hồi quy, không làm lại từ đầu.
- Lượt 1 hóa đơn/tra cứu kho: đã sửa và kiểm tra source, xem bằng chứng ngay sau mục 3.5; chưa đưa vào EXE mới.
- CCCD/địa chỉ: đã sửa theo 6.1. Quyết định mới là loại hai hồ sơ trùng khỏi chứng từ mới, không còn chờ khách trả lời.
- Kho thực tế trừ ngay khi đặt hàng: khách đã chốt tại 2.1; đưa vào lượt 2, không còn ghi là chờ xác nhận thời điểm trừ.
- Các lượt dưới đây là **cách gom phạm vi để triển khai**, không phải kết luận rằng mọi chức năng trong đó chưa có. Rà cái đang có rồi chỉ sửa phần thiếu/sai.

### 10.2. Bốn lượt sửa và một lượt bàn giao

| Lượt | Gom làm cùng nhau | Đối chiếu mục gốc |
|---|---|---|
| 1. Hóa đơn và tra cứu kho | Rà lọc ngày đầu vào/đầu ra, chống tải/ghi trùng; đưa dòng chưa ghép/lỗi lên đầu, lọc trạng thái, giữ tiêu đề; ghi kho xong mở đúng chi tiết nhập; rà chốt tháng/chuyển tồn trên sổ kho hóa đơn hiện có. Hoàn thiện bảng xem trực tiếp của các màn này cùng lượt. | 3.3–3.5; phần hóa đơn/kho tại 5; 12.2 |
| 2. Đơn hàng, NCC và kho thực tế | Nạp/sửa/nạp lại đơn, lọc lỗi và nhảy đến dòng lỗi; màn NCC gọn, trạng thái đã đặt/mở lại; giữ chức năng trừ tồn ngay khi đặt, sửa/hủy cập nhật chênh lệch và chống trừ hai lần. Làm luôn bảng xem đơn/NCC và kiểm tra liên kết đến phiếu giao. | 2.1; 4.1–4.2; phần đơn/NCC tại 5; tiêu chí 9.19 |
| 3. Báo cáo và công nợ | Bếp/nhà thầu động, tổng nhóm/tổng tháng; phải thu theo bếp/tổng, phải trả đúng 14 cột; lọc còn nợ/đã trả, ghi nhận/hoàn tác và giữ lịch sử. Làm bảng xem trực tiếp, bộ lọc, tổng lượng/tiền và đối chiếu Excel cùng lượt. | 4.4–4.6; phần báo cáo/công nợ tại 5 |
| 4. Chứng từ, xem trước và in | Hoàn thiện xem trực tiếp các chứng từ còn lại, gồm báo giá, phiếu giao, bảng kê/đề nghị thanh toán và biên nhận; chọn một/nhiều/tất cả phiếu để in ngay tại danh sách; căn cột/dòng, chữ ký, tên hàng dài và bản in nền trắng. Kiểm tra định dạng số giữa màn hình/Excel/PDF. Không làm lại phần CCCD đã qua test. | Phần còn lại của 5; 6; 12.1, 12.3–12.5 |
| 5. Gọn menu, bảo toàn dữ liệu và bàn giao | Sau khi kho thực tế đã có đường sử dụng riêng, ẩn hai module/menu trùng mà không mất nghiệp vụ; kiểm tra tự lưu, sao lưu theo lịch và nâng cấp giữ dữ liệu; nghiệm thu xuyên suốt, rồi cập nhật Word/clip theo giao diện cuối. Chỉ build khi chủ dự án yêu cầu lại. | 2.1; 4.3, 4.7; 8–9; 11 |

**Lượt 1–4 và phần sửa source của lượt 5 (mục 3, 6, 14 trên checklist) đã triển khai, đã đóng gói EXE 2026.09.05.1 theo yêu cầu mới.** Kết quả và giới hạn kiểm thử ghi riêng bên dưới. Phần tạo lại Word/clip chưa thực hiện trong lượt build. Không dùng kết quả này thay cho đối soát dữ liệu thật trên máy khách.

### Kết quả lượt 2 ngày 05/09/2026

- **Đơn hàng:** thêm lọc lỗi chặn duyệt, cảnh báo không chặn và dòng đủ dữ liệu; lỗi lên đầu và có nút nhảy tới lỗi đầu tiên. Tiêu đề cố định khi cuộn. Tìm/lọc cập nhật số dòng, tổng lượng theo từng ĐVT và tổng tiền ngay, không mất giá đang gõ nhưng chưa lưu. Số lượng giữ tới 6 chữ số lẻ, ô sửa nhận `0,855` và lượng nhỏ; tiền hiển thị nguyên đồng. Có lối mở kho thực tế và phiếu giao từ bảng đơn.
- **Nạp lại:** file giống hệt không sinh thêm đơn. File hợp lệ khác cùng ngày và cùng phạm vi sheet thay bản trước, lưu lịch sử; ngày/sheet độc lập và danh mục không bị thay. File cũ đã bị thay thế không được âm thầm khôi phục. File mới lỗi hoặc bản cũ đã liên kết chứng từ thì chặn và giữ dữ liệu cũ để đối chiếu. Phạm vi thay/giữ được nói rõ trước và sau khi nạp. Luồng workbook chuẩn vẫn giữ các phạm vi bán/giao và mua/phải trả riêng.
- **NCC:** tái dùng trạng thái đã có; mỗi NCC một thẻ, có tổng lượng theo ĐVT và tổng tiền, mở bảng chi tiết bên trong. Ảnh sao chép bao gồm tất cả nhóm bếp của NCC đó, vẫn giữ quy tắc gộp từng NCC. Chỉ sao chép thành công mới tự ghi `Đã đặt`; lỗi clipboard/tải ảnh thay thế không ghi nhầm trạng thái. Đã đặt xuống dưới, có mở lại; sửa nội dung đơn/kế hoạch mua tự chuyển `Cần đặt lại`. Nội dung thay đổi trong lúc tạo ảnh bị phát hiện trước khi ghi trạng thái.
- **Nguồn kho thực tế:** module riêng `tdp_system/physical_inventory.py`, menu `Kho thực tế`. Không lấy tồn từ hóa đơn hoặc bảng kho cũ đang trộn nhiều nguồn. Người dùng khai số kiểm đếm **đầu ngày bắt đầu, trước các đơn của ngày đó**; nhập/điều chỉnh hàng thực về được lưu riêng, có người thực hiện và lý do. Chưa khai tồn đầu hoặc sai mã/ĐVT/lượng thì báo chưa đủ dữ liệu, không khẳng định hàng còn/hết. Khi triển khai cho khách phải khai/đối chiếu tồn đầu thực tế, không tự bịa hoặc sao chép tồn hóa đơn sang.
- **Quy tắc trừ:** đọc trực tiếp đơn khách hiện hành nên lưu đơn là trừ theo số đặt, kể cả giao ngày sau. Sửa lượng đổi phần trừ; xóa đơn hợp lệ hoàn lại lượng đang trừ. Nút `Chốt lượng đã giao` chuyển từ lượng đặt sang thực giao trừ khách trả, không phát sinh lần xuất thứ hai; có mở lại. Chốt lại phạm vi bán/giao trong workbook chuẩn cũng chuyển sang lượng thực giao. Việc sửa đơn đang liên kết hóa đơn/chứng từ vẫn chịu các khóa an toàn sẵn có.
- **Chống trùng và lịch sử:** nhập thực tế dùng mã lần lưu để bấm lại không cộng trùng; sửa tồn đầu và chốt lượng giao kiểm tra phiên dữ liệu đang xem. Có dấu vết thay đổi đơn, lịch sử tồn đầu và nhập/điều chỉnh; khởi tạo/nâng cấp schema lại không làm tăng/giảm tồn thêm lần nữa. Tổng tiền kho thực tế được ghi rõ là **ước tính theo giá nhập gần nhất**, không phải giá trị sổ kho hóa đơn.
- **Kiểm thử cuối lượt:** **265 test đạt, 0 lỗi**, gồm 14 test riêng kho thực tế và các nhóm đơn/nạp lại/NCC/giá/phiếu giao, cùng toàn bộ 191 test hồi quy hóa đơn/kho của lượt 1. Bao gồm đặt → sửa → giao → khách trả → xóa, lượng lẻ, đơn giao tương lai, file lặp/file thay thế/file lỗi, hai người lưu đồng thời, rollback khi lỗi và tách nguồn kho hóa đơn.
- **Trình duyệt:** `tdp_system/browser_smoke_round2.js` chạy đạt trên fixture độc lập `browser_fixture_round2_server.py`: 65 dòng giả lập; lọc và tổng, giữ giá chưa lưu, tiêu đề/cuộn ngang, ô lượng lẻ, ảnh NCC đủ bếp, clipboard lỗi/thành công, mở lại NCC, khai tồn/nhập thực tế, mở đúng đơn nguồn, chốt giao/mở lại và liên kết phiếu giao. Không tràn trang tại 1440px/1024px. Ảnh: `D:\TDP_ROUND2\orders-browser.png`, `suppliers-browser.png`, `physical-stock-browser.png`.
- **Giới hạn bàn giao:** chỉ sửa source và danh sách phụ thuộc cho lần đóng gói sau; **không build EXE, không sửa DB khách, không gọi ghi dữ liệu lên nguồn hóa đơn thật**. Chưa làm lượt 3–5; chưa cập nhật Google Sheet hay tài liệu Word trong lượt này.

### Kết quả lượt 3 ngày 05/09/2026

- **Giữ phần đã có:** sổ phải thu từ thực giao đã duyệt, sổ phải trả, phân bổ tiền trả NCC, số dư đầu kỳ/điều chỉnh, lịch sử và mẫu Excel phải trả 14 cột. Không coi các chức năng này là làm mới toàn bộ.
- **Báo cáo tổng hợp:** thêm bảng xem ngay theo tháng, dùng chung workbook với nút tải Excel. Tự lấy danh mục bếp hiện tại, hiện cả bếp chưa phát sinh, có tên dòng tổng nhóm và tổng tháng. Màn tháng chỉ cộng đơn đã duyệt; báo số phiên chưa duyệt, không tự cộng bản nháp đang mở ở màn khác. Đường xuất theo phiên cũ vẫn giữ quy tắc xem trước riêng của nó.
- **Tổng lượng và tiền:** phải thu/phải trả hiển thị tổng đúng bộ lọc, lượng tách theo ĐVT, giữ lượng lẻ đến 6 chữ số; không cộng kg với cái. Tách rõ tiền dòng và số dư tài khoản (đầu kỳ + phát sinh + điều chỉnh − đã thu/trả). Dòng đã đảo chỉ để tra cứu, không tự cộng lại vào số dư.
- **Phải trả:** Excel bám bộ lọc trạng thái/ngày/NCC; chọn tất cả có bảng chung 14 cột, sheet `Tổng NCC` và sheet 14 cột từng NCC. Mặc định màn hình là còn phải trả; trả hết thì dòng ra khỏi bộ lọc này, vẫn còn lịch sử. Ghi nhận tiền giữ mã chống trùng khi gửi lại; hoàn tác bắt buộc lý do và tên người thực hiện.
- **Phải thu:** giữ 3 lựa chọn ngoài màn, chi tiết theo bếp và tổng toàn bộ bếp của nhà thầu. Thêm `Excel theo bộ lọc`; `Excel toàn bộ bếp`/ZIP nhà thầu vẫn là số liệu toàn tài khoản, được ghi rõ trên nút. Không tự tải file khi mở màn. Bảng tổng có dòng tổng cộng và lịch sử thu đúng khoảng ngày, đọc trong cùng snapshot với số dư.
- **Bảo toàn khoản thu:** thay xóa bằng hoàn tác, chặn API xóa giao dịch; giữ số tiền gốc, lý do, người ghi nhận/người hoàn tác và audit. Gửi lặp/đồng thời cùng mã không tạo thêm khoản thu; audit lỗi thì rollback toàn giao dịch. Bản cũ chưa ghi tên người thao tác được để trống/ghi rõ là bản cũ, không suy đoán tên.
- **Giao diện:** tiêu đề cố định, cuộn ngang trong bảng, phân trang chi tiết và lịch sử trả NCC; tổng tính toàn bộ bộ lọc, không chỉ trang hiện tại. Thu gọn khối tổng và sửa thanh lọc tràn ở 1024px. Đổi nhà thầu chỉ cập nhật danh sách bếp, áp dụng khi bấm lọc để không bị phản hồi nền xóa lựa chọn mới. Đổi tháng nhanh hoặc tải lỗi không được hiện số tiền của kỳ cũ như kỳ mới.
- **Kiểm thử:** lượt hồi quy rộng chạy **309 test, 0 lỗi/0 thất bại**; sau sửa cuối ở bộ lọc giao diện, chạy lại **17 test hợp đồng giao diện**. Có 9 test mới trong `test_round3_documents.py`: đối chiếu API/Excel, bếp mới/tháng trống, lượng khác ĐVT, lọc đã trả/còn nợ, hoàn tác, gửi trùng/đồng thời, rollback khi audit lỗi, bảo toàn khoản thu cũ khi nâng schema, chuỗi tên hàng giống công thức vẫn là text. Giữ kiểm tra các mảng đơn hàng, kho thực tế, chốt tháng và kho/hóa đơn từ lượt trước.
- **Trình duyệt:** dữ liệu giả 70 dòng, kiểm tra báo cáo/bộ lọc, phân trang, tổng ĐVT, ghi nhận/hoàn tác thu và trả, phản hồi tháng cũ đến muộn, tải lỗi, không tự xuất Excel, tiêu đề/cuộn ngang và khổ 1440px/1024px. Script `browser_smoke_round3.js`; ảnh ở `D:\TDP_ROUND3\report-browser.png`, `receivable-browser.png`, `payable-browser.png`.
- **Giới hạn:** chỉ sửa source và thêm phụ thuộc đóng gói; **không build EXE, không sửa DB thật, không gọi ghi lên nguồn hóa đơn thật**. Chưa làm lượt 4–5, chưa cập nhật Google Sheet/Word. Hai CCCD trùng vẫn chờ khách. Người thao tác hiện là tên nhập khi lưu/hoàn tác, không phải xác thực tài khoản cá nhân mới.

### Kết quả lượt 4 ngày 05/09/2026

- **Xem chứng từ:** phiếu giao hiện ngay tại màn; báo giá giữ bảng trực tiếp và thêm bản gửi khách của từng nhà thầu/tổng. Bảng kê mua hàng, biên nhận, bảng kê giao nhận và đề nghị thanh toán có nút mở bản xem ngay trong màn đang dùng. Không tự tải Excel khi mở mục. Tái dùng các hàm xuất hiện có, không xây lại nguồn số liệu hay bỏ khóa CCCD/hóa đơn.
- **Chọn và in:** tại `In giấy tờ`, lọc từ ngày/đến ngày; phiếu giao lọc thêm khách hàng/bếp. Có chọn một/nhiều/tất cả, xem từng dòng và in phần đã chọn ngay trong màn danh sách. Bảng kê/biên nhận chọn tiếp từng phiếu trong bản xem. Hiện số đang lọc/đã chọn; lấy toàn bộ ngày trong khoảng lọc, không chỉ 100 phiên gần nhất. Mỗi lần tạo bản xem tối đa 100 phiên đơn và 300 phiếu; vượt giới hạn báo thu hẹp lựa chọn, không âm thầm bỏ phần còn lại.
- **Bảng xem:** nền trắng, chữ đen, giữ ô gộp/đường kẻ; tiêu đề cố định, cuộn ngang/dọc trong bảng, phóng to 80–150%. Không đưa cột kỹ thuật hoặc sheet ẩn lên màn/in. Excel vẫn giữ các sheet đối chiếu ẩn cần thiết. PDF được tạo bằng bộ dựng Excel gốc, không dùng ảnh chụp bảng web làm bản in.
- **Khớp bản xem và file:** giữ bản chụp số liệu lúc mở trong 24 giờ. Xem/Excel/PDF cùng đọc bản đó; muốn lấy đơn vừa sửa phải bấm `Đọc lại dữ liệu mới`. Kiểm tra mã băm để chặn file tạm bị thay đổi. Khóa lựa chọn trong lúc tạo file; nếu mở phiếu khác giữa chừng thì bỏ phản hồi cũ, không mở nhầm PDF. API đọc chứng từ dùng giao dịch chỉ đọc, không ghi kho/công nợ/lịch sử phát hành.
- **Căn mẫu và số:** giữ tiêu đề, ngày riêng dòng và chữ ký; tên hàng dài được tăng chiều cao. Phiếu giao ẩn giá vẫn có tổng lượng, không lộ giá. Bảng kê/biên nhận/giao nhận và đơn NCC giữ lượng lẻ tới 6 chữ số, tổng tách theo ĐVT. Tiền/đơn giá hiển thị nguyên đồng, dấu phẩy hàng nghìn, làm tròn nửa lên theo 13 ví dụ khách; sửa cả trường hợp số âm và dấu chấm thừa sau lượng nguyên. Phiếu giao cộng các thành tiền đã làm tròn từng dòng, khớp cách tính tiền đơn. Không sửa giá gốc trong database.
- **Kiểm thử:** nhóm chứng từ/giao diện chạy 116 test đạt; bổ sung kiểm tra API bảng kê/biên nhận lấy đúng địa chỉ hiện hành, chặn thiếu địa chỉ, báo cáo và bảng kê đầu ra chỉ đọc — nhóm `test_round4_documents.py` chạy 22 test đạt. Hồi quy rộng chạy 399 test: 398 đạt, 1 bài còn kỳ vọng dấu chấm hàng nghìn cũ (`26.466`) ở màn kho. Đã đổi kỳ vọng sang dấu phẩy đúng mẫu khách (`26,466`), không đổi lại phần mềm theo mẫu cũ; chạy lại cả nhóm hóa đơn/tra cứu kho, hợp đồng giao diện và chứng từ: **48/48 test đạt**, gồm bài vừa nêu. Không cộng các lượt chạy trùng thành số test mới. Kiểm tra cú pháp JavaScript, hai script đóng gói và `git diff --check` đều qua; không chạy script build.
- **Trình duyệt và PDF:** `browser_smoke_round4.js` đạt trên dữ liệu giả, gồm chọn phiếu/lọc bếp, tổng ĐVT, tiêu đề trắng cố định, phóng to, không tự tải file, yêu cầu in trong cùng màn, khóa lựa chọn khi đang tạo file và bỏ phản hồi PDF cũ. Không tràn trang ở 1440px/1024px. Excel trên máy đã xuất được bộ mẫu 7 trang; đã xem lại các trang phiếu giao có/ẩn giá, bảng kê, biên nhận, báo giá, đề nghị thanh toán và bảng kê giao nhận. File: `D:\TDP_ROUND4\artifacts\Chung_tu_kiem_tra.pdf`; ảnh trình duyệt ở `D:\TDP_ROUND4\delivery-browser.png`, `printing-browser.png`. Đây là dữ liệu kiểm thử, không phải giấy tờ để gửi khách thanh toán.
- **Giới hạn:** chưa thử máy in vật lý của khách. Tạo PDF đúng mẫu cần Microsoft Excel trên máy chạy phần mềm; lỗi tạo PDF được báo tại chỗ và vẫn cho xem/tải Excel. Không build EXE, không sửa DB khách, không gọi ghi lên nguồn hóa đơn thật; chưa làm lượt 5, chưa cập nhật Google Sheet/Word. Hai hồ sơ CCCD trùng vẫn chờ khách xác nhận.

### Hoàn thiện mục 3, 6, 14 ngày 05/09/2026 — phần source của lượt 5

- **Mục 3:** bỏ menu Phiếu giao trùng và ẩn Suất ăn/PO, Chấm công/lương khỏi luồng hằng ngày. Phiếu giao vẫn mở từ Công việc hằng ngày hoặc In giấy tờ; Kho thực tế và Đặt hàng nhà cung cấp vẫn hoạt động. API của màn hằng ngày không tính/nạp dữ liệu hai module đã ẩn; API lịch sử và bảng dữ liệu cũ được giữ nguyên.
- **Mục 6:** theo quyết định mới của chủ dự án, loại Đoàn Văn Giang và Nguyễn Văn Toại khỏi danh sách gợi ý và bảng kê/biên nhận mới, không chờ khách sửa CCCD nữa. Không xóa người bán hay đơn, kho, công nợ lịch sử. Bộ lẫn người hợp lệ vẫn xuất phần hợp lệ, báo số dòng bị loại ngay trên bản xem và ghi chú ô đầu Excel. Nếu toàn bộ bị loại, báo không có chứng từ hợp lệ; không âm thầm trả bộ rỗng. Bộ dựng chứng từ trực tiếp cũng chặn hai tên này, kể cả đổi số giấy tờ.
- **Mục 14:** dữ liệu vẫn được ghi sau khi Lưu/Xác nhận thành công; không tuyên bố ô đang gõ đã được lưu. Sao lưu tự động chạy khi mở phần mềm và mỗi 30 phút trong lúc đang mở, giữ bản mới nhất của 14 ngày có sao lưu. Dùng bản chụp SQLite nhất quán, kiểm tra toàn vẹn rồi mới thay thế bản cũ; lỗi không xóa bản an toàn trước đó. Danh mục & sao lưu hiện giờ thành công gần nhất và cảnh báo, cập nhật mỗi phút khi đang xem.
- **Nâng cấp:** tạo bản sao riêng trước thay đổi dữ liệu, giữ 5 bản; không sao được thì dừng nâng cấp. Dữ liệu kèm theo chỉ được cài khi chưa có DB, kể cả tình huống DB khách xuất hiện đúng lúc đang kiểm tra bản kèm theo. Giữ nguyên dữ liệu cũ qua nhiều lần khởi động/nâng cấp. Chỉ dọn file sao lưu đúng tên do hệ thống tạo, không đụng file khách tự đặt tên.
- **Kiểm thử:** 269 bài hồi quy của 26 nhóm đều đạt, gồm chứng từ, 50 hồ sơ người bán hợp lệ, kho thực tế, chốt tháng, phải thu/phải trả, hóa đơn đầu vào/đầu ra, chống âm kho và an toàn in. Sau đó bổ sung bài kiểm tra giữ file khách tự đặt tên khi dọn bản sao trước nâng cấp và chạy lại nhóm hoàn thiện: **29/29 đạt**. Không cộng hai lượt chạy thành số bài độc lập.
- **Tình huống sao lưu đã thử:** dữ liệu đã ghi nhưng còn ở WAL, dữ liệu chưa xác nhận, thiếu/hỏng nguồn, lỗi ổ đĩa/quyền ghi, thay bản sao thất bại, lưu cùng ngày, sang ngày mới khi không khởi động lại, giữ 14 ngày, nhiều yêu cầu đồng thời, phục hồi bản sao, chạy/dừng lịch theo vòng đời ứng dụng, nâng cấp lặp và tranh chấp cài DB ban đầu.
- **Trình duyệt:** đã qua `browser_smoke_round5.js` ở 1440 và 1024: menu gọn, còn đường mở phiếu giao, xem sao lưu thành công/lỗi, bộ biên nhận hợp lệ có cảnh báo phần loại, không tự tải Excel/PDF chỉ vì mở màn. Ảnh kiểm tra: `D:\TDP_ROUND5\settings-browser.png`. Không có lỗi JavaScript; kiểm tra cú pháp hai script giao diện đạt.
- **Google Sheet:** đã đổi đúng E7, E10, E18 trong tab `Khách hàng kiểm tra` sang `Đã sửa sau cuộc gọi`, kèm ghi chú bằng chứng/giới hạn. Đọc lại xác nhận giá trị, định dạng và dropdown không đổi ngoài ba ô; giữ nguyên các cột khách chốt/khách kiểm tra/ý kiến khách. Các nhận xét cũ ở cột Ý kiến khách không bị ghi đè. Link: https://docs.google.com/spreadsheets/d/1c1C4Imexri4VRolrNSSmWmSnpmM0hgj0TCCbm9if3D8/edit
- **Giới hạn bàn giao:** chỉ sửa source, hướng dẫn TXT và khai báo module khi đóng gói; chưa build EXE, chưa tạo lại Word/clip, chưa thử máy in khách và chưa đối soát tài khoản hóa đơn thật. Kiểm thử dùng DB/thư mục riêng trên D:, không sửa DB khách. Bản sao trên cùng ổ không phòng được hỏng/mất ổ; cần thêm bản sang ổ khác khi chuyển máy. Ghi nhận “chờ hai CCCD” ở báo cáo lượt 3–4 phía trên là lịch sử, đã được quyết định mới này thay thế.

### 10.3. Cách giảm việc lặp và tránh sửa chồng

**Bổ sung kiểm tra bản đóng gói 2026.09.05.1:** build thành công trên D:, không ghi đè bản EXE cũ. Chạy chính EXE hai lần trên DB/thư mục/cổng riêng: khởi động, schema/toàn vẹn, menu gọn, loại hai người bán, sao lưu tự động và bản sao trước nâng cấp đều đạt; bản mở lại giữ đúng dữ liệu đánh dấu sau lần đầu. Đã mở phiếu giao và tải Excel từ chính EXE. Bốn bài kiểm thử cấu hình đóng gói đạt. Kết quả lưu tại `D:\TDP_BUILD_20260905\temp\tdp-release-20260905-r4kpaylw\result.json`. Không gọi nguồn hóa đơn thật, không sửa DB khách, chưa thử máy in khách. Khi nâng cấp máy khách phải đóng bản cũ, thay đúng EXE trong thư mục đang dùng và giữ nguyên thư mục `data`.

- Từ lượt 1 thống nhất cách làm bảng: cuộn ngang/dọc, tiêu đề cố định, lọc lỗi, tổng theo bộ lọc. Tái dùng phần phù hợp ở lượt 2–4, không xây lại một kiểu bảng cho từng màn.
- Quy tắc hiển thị tiền/đơn giá tại 12.3 được rà ở chỗ dùng chung và áp dụng theo từng lượt; không đợi làm xong mọi màn mới quay lại sửa. Không làm tròn số lượng như tiền và không tự đổi công thức nghiệp vụ chưa chốt.
- Mỗi bảng xem và file tải lấy cùng nguồn dữ liệu nghiệp vụ. Hoàn thiện phần xem trực tiếp ngay khi xử lý màn tương ứng, không để thành một đợt lớn riêng rồi phải sửa lại tất cả.
- Rà dữ liệu và đường cập nhật trước, hoàn thiện giao diện sau, test cả luồng trong từng lượt. Không thay đổi đồng thời hai nghiệp vụ khác nhau chỉ vì cùng nằm trong một file code.
- Bảo đảm database/thư mục thử nghiệm cô lập và bản sao an toàn ngay trước mọi thao tác thử nâng cấp; việc này không được đợi đến lượt bàn giao. Lượt 5 là kiểm tra đầy đủ tính năng tự sao lưu và nâng cấp.
- Kết thúc mỗi lượt ghi rõ cái đã có, cái vừa sửa, test nào đã chạy và phần còn chờ. Không lấy bản EXE cũ hoặc tổng số test của lượt khác để đánh dấu nghiệm thu cả lượt mới.
- Gom việc không bỏ yêu cầu và không tự cho phép sửa code/build: cập nhật kế hoạch lần này chỉ sửa README; triển khai lượt tiếp theo khi chủ dự án yêu cầu.

## 11. Ranh giới hiện tại

- Tiến độ từng mục phải theo bằng chứng kiểm tra riêng; đã sửa source mục CCCD/địa chỉ tại 6.1 và rà/sửa kho hóa đơn tại 3.1–3.2, không có nghĩa các mục còn lại đã hoàn thành.
- EXE `2026.09.04.1` đã gửi trước khi file này được lập nên chưa chứa toàn bộ thay đổi mới nêu trên.
- Không build lại EXE cho tới khi các đầu việc được triển khai và nghiệm thu.
- Không xóa dữ liệu thật của khách trong bất kỳ bước sửa hoặc kiểm thử nào.
- Mọi kiểm thử có ghi dữ liệu phải dùng database và thư mục tạm độc lập.

## 12. Phản hồi bổ sung trong `New-F3.docx` ngày 04/09/2026

Nguồn bổ sung: `C:\Users\DELL\Downloads\New-F3.docx`, gồm nội dung chat và bốn
ảnh minh họa của khách. Các yêu cầu dưới đây bổ sung và làm rõ cho các mục phía
trên; hình ảnh cột trái/cột phải là chuẩn quyết định cách định dạng số.

### 12.1. In đơn và in bảng kê ngay tại màn danh sách

- Tại mục in đơn/in bảng kê, hiển thị danh sách phiếu theo kiểu phần mềm cũ.
- Có bộ lọc khách hàng, từ ngày và đến ngày.
- Cho phép chọn tất cả phiếu đang lọc hoặc chọn tùy ý một/nhiều phiếu.
- Bấm một lần để in toàn bộ phần đã chọn.
- Không bắt người dùng chuyển sang một giao diện khác chỉ để chọn và in.
- Mỗi dòng có thao tác xem trước khi cần kiểm tra riêng một phiếu.
- Tổng số phiếu đang lọc và tổng số phiếu đã chọn phải hiện rõ trước khi in.

### 12.2. Hình thức bảng trên màn hình

- Trình bày đơn thuần như một bảng Excel quen thuộc, không trang trí màu mè.
- Nền trắng, đường kẻ rõ, màu nhấn chỉ dùng cho lỗi hoặc trạng thái cần chú ý.
- Không dùng mảng nền đậm gây tốn mực khi in.
- Các cột phải đều, vừa nội dung và thuận mắt; dữ liệu dài được xuống dòng hợp lý.
- Tiêu đề cột cố định khi cuộn; bảng nhiều cột có thanh kéo ngang.
- File nhập/hóa đơn đầu vào phải đưa toàn bộ dòng chưa khớp mã lên trên cùng.

### 12.3. Quy tắc biến đổi và hiển thị số theo ảnh khách chốt

Đối với cột số tiền/đơn giá mà khách minh họa, giá trị gốc ở **cột trái** phải
được làm tròn và hiển thị đúng như **cột phải**:

- Làm tròn số học đến số nguyên gần nhất.
- Phần lẻ từ `0.5` trở lên làm tròn lên; nhỏ hơn `0.5` làm tròn xuống.
- Bỏ toàn bộ chữ số thập phân sau khi làm tròn.
- Bỏ dấu chấm thừa ở cuối các số nguyên từ nguồn.
- Giữ dấu phẩy phân cách hàng nghìn.
- Định dạng hiển thị/Excel bắt buộc: `#,##0`.
- Giá trị dùng để tính và giá trị hiển thị/xuất phải áp dụng thống nhất tại điểm
  nghiệp vụ đã chốt, không để màn hình và file kết xuất lệch nhau.

Ví dụ chuẩn từ ảnh khách:

| Cột trái – giá trị nguồn | Cột phải – kết quả bắt buộc |
|---:|---:|
| `42,500.` | `42,500` |
| `42,000.` | `42,000` |
| `152,000.994706` | `152,001` |
| `5,208.` | `5,208` |
| `29,629.665` | `29,630` |
| `9,196.25149` | `9,196` |
| `29,629.633328` | `29,630` |
| `26,465.5` | `26,466` |
| `44,500.` | `44,500` |
| `30,962.967143` | `30,963` |
| `167,832.` | `167,832` |
| `741.` | `741` |
| `440,000.` | `440,000` |

Quy tắc này mô tả chính xác phép biến đổi cột trái → cột phải trong ảnh. Không
được hiểu thành giữ lại một chữ số thập phân như `29,629.7`.

### 12.4. Hình thức bản in

- Đơn hàng và bảng kê in ra phải gần cách trình bày của phần mềm cũ khách đang dùng.
- Giữ bố cục cân đối nhưng không tô nền đậm hoặc đổ nhiều mực.
- Dùng nền trắng, chữ đen, đường bảng thông thường và chỉ nhấn phần thật cần thiết.
- Cho phép in tất cả hoặc in các phiếu được chọn ngay từ danh sách hiện tại.
- Không dùng việc “giống mẫu” để giữ lại mảng màu/tô nền mà khách đã yêu cầu bỏ.

### 12.5. Điều kiện kiểm tra bổ sung

1. Lọc một ngày có nhiều đơn, chọn tất cả và in bằng một thao tác.
2. Chọn rời rạc một số đơn và chỉ in đúng các đơn đó.
3. Thao tác in không điều hướng sang màn hình khác.
4. Dòng chưa khớp mã luôn nằm trên các dòng đã hoàn tất.
5. Toàn bộ 13 ví dụ số trong bảng trên cho kết quả đúng tuyệt đối.
6. Bản xem trên web và file tải xuống dùng cùng kết quả làm tròn.
7. Bản in nền trắng, không có mảng tô đậm không cần thiết và không tốn nhiều mực.

## 13. Rà soát phản ánh khách chiều 05/09/2026 — chưa triển khai sửa

### 13.1. Nguồn và giới hạn kiểm tra

- Khách phản ánh: “cái này chưa có đề nghị thanh toán lấy số liệu trên bảng kê hóa đơn VAT”.
- Chat 16:22:03: “c đang rất cần khớp đầu vào đầu ra mà em chưa làm đc phần đó à”; 16:26:57 khách thúc xử lý vì lo bị phạt thuế. Đây là mức độ khẩn cấp khách nêu, không phải kết luận hệ thống đã gây phạt hoặc sai thuế.
- Chủ dự án cập nhật tiếp trong cùng cuộc trao đổi: khách complain **không xuất được hóa đơn đầu ra để khớp với đầu vào**, đang rất bực. Ghi nhận đây là công việc xuất hóa đơn đang bị chặn theo phản ánh khách; chưa có thông báo lỗi hoặc bước thao tác cụ thể để xác định nguyên nhân kỹ thuật.
- **Làm rõ sau đó, ưu tiên hơn cách diễn giải trên:** chủ dự án cho biết khách chỉ nói chung chung, “ko khớp so với phần mềm cũ là 266 thôi, chỉ xuất đc ra 257”. Ghi nhận chênh lệch số đếm **266 − 257 = 9**; chưa có tên màn hình, đơn vị đếm, kỳ lọc hay thông báo lỗi. Từ “xuất” có thể là xuất danh sách/file, chưa đủ căn cứ đồng nhất với ký/phát hành hóa đơn đầu ra.
- **Bằng chứng bổ sung tiếp theo:** `C:\Users\DELL\Downloads\nhập T8.2026 (1).xlsm`, sheet `weekend`, tiêu đề `Bảng kê phiếu nhập`, kỳ 01–31/08/2026. Đã đọc chỉ đọc, không chạy macro hoặc lưu lại workbook; kết quả đối chiếu với `raw_json` hóa đơn local tại mục 13.9 thay cho các nghi vấn nguyên nhân trước đó ở phạm vi đã chứng minh.
- Ảnh đơn NCC **ÁNH — 03/09/2026**, khoanh lượng **0,54 kg Gạo nếp**, dòng bếp đối chiếu được là **LSVINA**.
- Ảnh/chat giao diện lúc 16:11: khách muốn menu lên ngang màn hình máy tính, mở chức năng có vùng nội dung rộng để dễ nhìn.
- File khách gửi sau khi được hỏi lúc 16:38: `C:\Users\DELL\Downloads\Đơn hàng  03.09.2026.xlsx`. Giữ nguyên file; đã đọc cả giá trị lưu, công thức và định dạng ô.
- Đã đọc source hiện tại, chạy riêng hàm nhận diện trên file thật, kiểm tra catalog/database local bằng kết nối SQLite chỉ đọc. Tình huống thiếu hồ sơ thanh toán được tái hiện bằng dữ liệu giả trong SQLite bộ nhớ, không gọi API hóa đơn thật.
- Các DB đã kiểm tra gồm `tdp_system/data/tdp.sqlite3` và bản kèm các gói bàn giao 03/09, 04/09: chỉ có phiên đơn **29/08/2026, 233 dòng**. Những DB có bảng nguồn đầu ra/sổ kho hóa đơn đều chưa có bản ghi ở các bảng này. Chưa có DB đang vận hành trên máy khách để xác định toàn bộ ảnh hưởng.
- Đã xác nhận file EXE trên D: và báo cáo smoke tại mục 10.3 tồn tại; chưa xác nhận khách đang chạy đúng EXE đó. Không dùng kết quả rà source để khẳng định đã tái hiện trên EXE/DB khách.
- Lượt này chỉ cập nhật tài liệu: không sửa code nghiệp vụ, không nhập đơn, không sửa DB/Excel, không cập nhật Google Sheet, không build hoặc gửi tin cho khách.

### 13.2. Tổng hợp đúng các phản ánh của khách

| Phản ánh | Kết luận hiện tại | Trách nhiệm / việc còn thiếu |
|---|---|---|
| Chưa lập được đề nghị thanh toán lấy số liệu bảng kê hóa đơn VAT | Có mẫu và nút xuất, nhưng thiếu đường lấy trực tiếp hóa đơn M-Invoice đã đồng bộ; còn phụ thuộc kỳ của đơn đang chọn | Thiếu sót phía phần mềm đã xác nhận ở mức source và tình huống giả lập; chưa xác định đúng tập hóa đơn khách đang chọn |
| Số liệu không khớp phần mềm cũ: cũ 266, bên mình chỉ xuất được 257; khách rất bức xúc | P0: đã chứng minh DB local lọc tháng 8 thiếu 9 hóa đơn ngày 01/08 do lưu lệch ngày UTC; chuẩn hóa nguồn chỉ trong bộ nhớ cho đúng 266 | Lỗi dữ liệu ngày phía hệ thống có thật; cần kiểm tra cùng tình huống trên DB khách. File phiếu nhập vừa gửi có 261 phiếu, không đồng nhất với 266 hóa đơn; xem 13.9 |
| Khoanh số 0,54 trên ảnh đơn NCC Ánh | Lượng gốc đúng là 0,54; Excel có cách hiển thị/làm tròn thành 0,5. Đồng thời phát hiện lỗi NCC: file chọn kho nhưng code có thể chuyển sang ánh | Lỗi đọc NCC đã xác nhận; chưa xác nhận khách muốn lượng gửi NCC là 0,5 hay đang phản ánh vấn đề khác ở ô khoanh |
| Menu lên ngang, mở chức năng rộng màn hình máy tính | Giao diện vẫn là sidebar dọc, chưa đáp ứng bố cục khách vừa yêu cầu | Yêu cầu bổ sung về cách sử dụng màn hình, chưa triển khai; không đồng nhất với việc ẩn menu trùng đã làm ở lượt 5 |

**Không quy toàn bộ phản ánh cho khách dùng sai.** Có lỗi/thiếu sót phía phần mềm thật, nhưng chưa có căn cứ nói phần mềm tính sai số 0,54 hoặc làm lệch toàn bộ sổ thuế.

### 13.3. BUG-0509-01 — đọc cột cảnh báo thành NCC, bỏ NCC khách đã chọn

**Trạng thái: đã xác nhận trên file thật và code hiện tại; chưa sửa. Ưu tiên P0 vì có thể đặt sai NCC.** Liên quan mục 4.1–4.2 và lượt 2.

Bằng chứng tại sheet `03.09`, dòng 342:

| Ô | Ý nghĩa | Giá trị |
|---|---|---|
| C2 / C342 | Tiêu đề / cảnh báo chọn NCC | `Chọn NCC` / `Chọn NCC` |
| D2 / D342 | Tiêu đề / NCC được chọn | `NCC` / `kho` |
| E342 | Mã hàng | `L000004` |
| F342 | Bếp | `LSVINA` |
| H342 | Tên hàng | `Gạo nếp` |
| I342 | Khối lượng | `0.54` kg |

Nguyên nhân đã lần theo:

1. `tdp_system/server.py`, `HEADER_ALIASES` coi cả `Chọn NCC` và `NCC` là trường `supplier`.
2. `detect_header()` giữ cột khớp đầu tiên. Chạy chính hàm trích từ source trên file khách trả về `supplier: 3` (cột C), thay vì cột D.
3. `resolve_order()` coi giá trị `Chọn NCC` là rỗng rồi lấy `product["supplier"]` từ danh mục.
4. Catalog local của `L000004` ghi NCC `ánh`. Chuỗi đọc này cho kết quả **kho → ánh**, phù hợp với ảnh khách gửi. Chưa kiểm tra catalog hoặc lịch sử sửa tay trên máy khách.

Đây là lỗi nhận diện dữ liệu của phần mềm; không phải bằng chứng khách chọn sai NCC. Có thể ảnh hưởng các dòng khác có cùng cấu trúc; chưa thống kê số dòng/đơn đã lưu sai trên máy khách.

Điều kiện đóng lỗi sau này: nhận đúng cột NCC nghiệp vụ, bỏ cột cảnh báo; giữ `kho` của dòng 342 qua xem trước → lưu → bảng NCC/ảnh. Kiểm tra cả mặt hàng có nhiều NCC và trường hợp thiếu NCC. Dữ liệu cũ nghi bị ảnh hưởng phải được đối chiếu trước khi sửa, không tự cập nhật hàng loạt.

### 13.4. BUG-0509-02 — không nhận diện sheet đặt hàng của file thật

**Trạng thái: đã tái hiện bằng bộ nhận diện hiện tại; chưa sửa. Ưu tiên P1, làm cùng lỗi nhập đơn/NCC.** Liên quan lượt 2 và yêu cầu dùng workbook của khách.

- `analyze_daily_workbook()` nhận sheet `03.09` có **352 dòng nghiệp vụ**, ngày `2026-09-03`.
- Kết quả `purchaseSheets` rỗng; sheet `đặt hàng` bị xếp `unrecognized_reference`, dù chứa dữ liệu đặt hàng thực tế.
- Header thực tế: `J2 = Đơn giá`, `O2 = SL \nthực té`, `P2` là công thức `SUBTOTAL(...)` với giá trị số, không có chữ `Thành tiền`.
- Trong `tdp_system/daily_workbook_import.py`, bộ nhận diện yêu cầu đủ `buy_price`, `actual_qty`, `amount`; `Đơn giá` đang được nhận là `sell_price` và tiêu đề số không khớp `amount`. Chạy riêng `_header_map()` xác nhận thiếu đúng **`buy_price` và `amount`**. Cột `SL thực té` vẫn nhận đúng `actual_qty` sau chuẩn hóa dấu/khoảng trắng; không coi cách viết này là nguyên nhân lỗi như nghi vấn ban đầu.
- `tdp_system/contract_modules.py`, `parse_canonical_purchase_workbook()` cũng yêu cầu các trường giá mua/lượng thực tế/thành tiền; cần rà cả bước đọc và xác nhận, không chỉ sửa nhãn ở màn xem trước.

Hệ quả đã xác nhận: luồng nhận diện workbook không đưa sheet này vào phạm vi đặt hàng có thể xử lý. Chưa thực hiện nhập/xác nhận trên DB khách nên chưa khẳng định đã mất điều chỉnh hỏng/thêm/giảm/thiếu trong dữ liệu vận hành.

Điều kiện đóng lỗi sau này: nhận đúng sheet và ý nghĩa cột bằng cấu trúc mẫu có kiểm chứng; đối chiếu các điều chỉnh, lượng thực tế, tiền và tổng giữa Excel/xem trước/kết quả lưu. Không yêu cầu khách sửa mẫu chỉ để né lỗi nhận diện, không đoán cột tiền từ một ô số bất kỳ.

### 13.5. BUG-0509-03 — hồ sơ thanh toán VAT phụ thuộc hóa đơn cục bộ

**Trạng thái: xác nhận thiếu luồng trong source và tái hiện có kiểm soát; chưa sửa. Ưu tiên P0 theo nhu cầu khách.** Liên quan mục 5, 7, lượt 4 và quy tắc nguồn hóa đơn tại README-new.md mục 25.2.

- Đã có mẫu `invoice_payment_documents.py` và nút `Tải Đề nghị thanh toán + bảng kê`; không ghi thành “chưa làm mẫu đề nghị thanh toán”.
- `issued_invoice_payment_scope()` trong `invoice_payment_scope.py` chọn các dòng `outgoing_invoice_drafts` có `status='issued'` làm đầu vào bắt buộc.
- Hóa đơn tải từ M-Invoice được lưu vào `outgoing_source_invoices`. Luồng thanh toán chỉ tìm nguồn đồng bộ để kiểm tra hóa đơn cục bộ tương ứng, chưa lấy trực tiếp tập hóa đơn đồng bộ để lập hồ sơ.
- Tái hiện chỉ trong SQLite bộ nhớ: có hóa đơn nguồn M-Invoice trạng thái đã phát hành/đã đồng bộ, không có draft cục bộ → hàm trả lỗi **404 `issued_invoice_scope_empty`**. Không chạy đồng bộ, ký/phát hành hoặc ghi sổ thật.
- Vì vậy khách đã tải hóa đơn VAT vẫn có thể không lập được đề nghị thanh toán bằng luồng hiện tại. Đây là thiếu sót phía phần mềm; cần kiểm tra tập hóa đơn thật để xác nhận tình huống cụ thể khách gặp.

**Hạn chế đi kèm về chọn kỳ:** `renderDocuments()` và xử lý `paymentRequestForm` trong `static/app.js` lấy kỳ từ đầu tháng đến `batch.work_date`, không có bộ lọc ngày thanh toán độc lập. Ví dụ đang chọn đơn 03/09 thì luồng này lấy 01–03/09, không phải tháng 8. API danh sách dùng cho chọn nhà thầu còn giới hạn 200 draft gần nhất (`contract_modules.py`, `api_outgoing_invoices()`); có nguy cơ không hiện nhà thầu của kỳ cũ, chưa chứng minh xảy ra trên DB khách.

Điều kiện đóng lỗi sau này: lập hồ sơ theo nhà thầu/kỳ được chọn từ đúng hóa đơn VAT đầu ra hợp lệ đã đồng bộ, kể cả hóa đơn không tạo qua draft cục bộ; đối chiếu tiền trước thuế/thuế/tổng, không lấy công nợ vận hành thay thế. Giữ kiểm tra trạng thái hủy/thay thế/điều chỉnh và nguồn chứng từ; thiếu liên kết bếp/chi tiết thì báo rõ, không tự dựng lịch sử giao hàng.

### 13.6. Số 0,54 và khớp đầu vào–đầu ra: phần chưa được kết luận là lỗi tính toán

**Lượng gạo nếp:**

- `03.09!I342`: số nhập trực tiếp **0.54**, không phải công thức bị đọc/làm tròn sai.
- `đặt hàng!F103` và `O103`: giá trị **0.54**, định dạng hiển thị một chữ số lẻ nên thấy **0,5**. `O103 = F103+L103-K103-N103-M103`.
- `gộp đơn!F338`: **0.54**; `K338 = ROUND(F338,1)` cho **0.5**.
- `đặt hàng!P103` lưu kết quả **14.040 đồng = 0,54 × 26.000**, vẫn tính theo lượng gốc.
- Ảnh NCC hiện tại dùng `stockQty()` tối đa sáu chữ số lẻ. Giá trị `0,54` trong ảnh khớp lượng gốc, nhưng khác cách Excel hiển thị/làm tròn ở các ô trên.
- Chưa có xác nhận rằng lượng nghiệp vụ phải đổi thành `0,5`. Quy tắc làm tròn tiền ở mục 12.3 không tự động áp dụng cho số lượng. Không sửa lượng hoặc tiền gốc để làm ảnh trông giống Excel trước khi chốt đúng quy tắc này.

**P0 — chênh số lượng so với phần mềm cũ: 266 so với 257:**

**Cập nhật:** phần dưới lưu lại hướng điều tra trước khi nhận file nhập tháng 8. Đã tìm được bằng chứng cụ thể về ngày lưu lệch trên DB local tại **13.9**; không tiếp tục ghi nguyên nhân 266/257 trên DB local là chưa rõ. Phần vận hành trên máy khách và đối soát toàn bộ lượng/tiền vẫn chưa hoàn tất.

- Yêu cầu này đã nằm trong phạm vi P0 tại mục 3, không phải yêu cầu mới ngoài phạm vi.
- Dữ kiện mới nhất là **266 ở phần mềm cũ, 257 ở kết quả xuất bên mình, chênh 9**. Thay cách hiểu trước đó là đã xác nhận không phát hành được hóa đơn đầu ra. Khách chưa nêu lỗi cụ thể; chưa khẳng định 257 là số hóa đơn, số dòng hàng, số đã tải, số đã ghi kho hay số được xuất.
- Mốc **266 hóa đơn đầu vào tháng 8** đã có trong mục 3.3 nên cần ưu tiên kiểm tra nhánh danh sách/xuất Excel đầu vào. Đây là hướng điều tra có căn cứ từ yêu cầu cũ, chưa phải xác nhận khách đang nói chính tập dữ liệu đó.
- Việc này khác BUG-0509-03: sửa hồ sơ đề nghị thanh toán không tự giải quyết chênh lệch 266/257.
- Cần đối chiếu danh sách nguồn 266 với danh sách xuất 257 trên cùng kỳ, loại hóa đơn, đơn vị đếm và bộ lọc. Nếu là hóa đơn, ghép theo định danh nguồn hoặc MST bên bán + ký hiệu + số + ngày; liệt kê cả phần chỉ có bên cũ, chỉ có bên mới và bản trùng. Chênh số đếm 9 không chứng minh có đúng 9 hóa đơn bị bỏ sót nếu hai tập còn khác nhau hoặc trùng lặp.
- Các điểm cần kiểm tra, **chưa phải nguyên nhân đã xác nhận**: lọc ngày Việt Nam/rìa kỳ, tải đủ trang và các lượt tải chồng nhau, loại/trạng thái hóa đơn, lọc dòng đã ghép/chưa ghép/đã ghi kho và cách đếm dòng so với hóa đơn. `invoice_workbench_listing.py` có cả tổng hóa đơn trước lọc và số hóa đơn còn dòng sau lọc; cần biết khách đang so con số nào.
- Chỉ chuyển sang điều tra giữ tồn/tạo file/phát hành M-Invoice nếu bằng chứng cho thấy khách đang nói bước đó. Kiểm tra phiên bản đang chạy và dữ liệu vận hành; chưa có căn cứ thì không quy cho khách thao tác sai hoặc bỏ chặn để ép đủ số lượng.
- Code có tải hóa đơn, ghép mã/quy đổi, xác nhận ghi kho, chống âm và NXT. Tải thành công chưa đồng nghĩa đã ghép mã và ghi kho thành công.
- Hiện chưa có DB khách đang dùng, tập hóa đơn tháng 8 cùng trạng thái ghép/ghi kho và mã đang lệch để kết luận nguyên nhân cụ thể. File đơn 03/09 không thay thế các dữ liệu này.
- Kiểm thử 266 hóa đơn giả tại lượt 1 không chứng minh đã đối soát lại đủ 266 hóa đơn thật. Không suy ra khách làm sai bước, phần mềm đã tính đúng hoặc có lỗi sổ kho chỉ từ số lượng test đã đạt.
- Cần tiếp tục đối chiếu trên bản sao DB vận hành: đúng kỳ và nguồn hóa đơn → trạng thái hợp lệ → mã/ĐVT/quy đổi → xác nhận nhập/xuất → tồn đầu, nhập, xuất, tồn cuối theo mã; nêu rõ dòng thiếu/lệch và lý do. **Ưu tiên P0, đang chờ dữ liệu vận hành để xác định nguyên nhân.**
- Điều kiện đóng việc: xác định được từng mục tạo ra chênh lệch 266/257 và lý do, xử lý lỗi nếu có, đối chiếu lại số đếm/tổng tiền giữa nguồn–màn hình–file cùng bộ lọc. Nếu tập nguồn thực sự có 266 hóa đơn thuộc phạm vi hợp lệ thì phải hiển thị/xuất đủ tập đó, hoặc giải thích cụ thể mục không thuộc phạm vi; không ép số đếm bằng cách thêm bản trùng. Nếu phát sinh vấn đề xuất kho/phát hành, tiếp tục giữ yêu cầu không âm và không xuất trùng. Chưa tự ký/phát hành hóa đơn thật trong lượt rà soát này.

### 13.7. UI-0509-01 — menu ngang và vùng nội dung rộng

**Trạng thái: yêu cầu bổ sung của khách ngày 05/09, chưa triển khai. Ưu tiên P1 sau các phần số liệu khẩn cấp.**

- Mong muốn khách: đưa menu lên ngang màn hình máy tính; khi chọn chức năng thì vùng nội dung đủ rộng, dễ nhìn.
- `tdp_system/static/index.html` vẫn dùng `aside.sidebar`; `demo_tdp/styles.css` dùng lưới `270px minmax(0, 1fr)`, nội dung có `max-width: 1500px`.
- Đợt gọn menu trước chỉ ẩn/tránh menu trùng; kiểm tra không tràn ở 1440/1024px không chứng minh đã có menu ngang hoặc dùng hết vùng nội dung.
- Không tự hiểu “full máy tính” thành yêu cầu bắt trình duyệt bật chế độ F11. Ghi nhận theo bố cục và diện tích hiển thị; kiểm tra khả năng đọc bảng và truy cập đủ chức năng khi triển khai.

### 13.8. Trạng thái checklist và thứ tự xử lý đề xuất

- Khi đọc Google Sheet trong lượt kiểm tra chiều 05/09, tab `Khách hàng kiểm tra`, cả 14 mục đều ghi **Đã sửa sau cuộc gọi** ở cột E, **Chưa chốt** ở D và **Chưa kiểm tra** ở F. Nhiều nhận xét cột G còn mô tả tình trạng cũ; đây là cột ý kiến khách, không tự ghi đè. Chưa cập nhật Sheet trong đợt rà này.
- Không dùng cột E, bản build hoặc kết quả fixture để kết luận khách đã nghiệm thu. Giữ kết quả các lượt trước làm lịch sử bằng chứng, đồng thời mở lại những phần có lỗi mới ở mục 13.
- Thứ tự đề xuất theo phản ánh mới nhất: **đầu tiên P0 đối chiếu và xử lý chênh lệch 266/257; tiếp theo P0 hồ sơ thanh toán VAT và P0 lỗi NCC (làm cùng P1 đọc sheet đặt hàng); sau đó P1 menu ngang.** Vấn đề hiển thị lượng chỉ xử lý sau khi tách rõ hiển thị và giá trị nghiệp vụ.
- Đây là danh sách để chủ dự án xem và tiếp tục công việc. **Chưa sửa các bug, chưa chạy lại regression sau sửa, chưa build bản thay thế.**

### 13.9. BUG-0509-04 — dữ liệu ngày hóa đơn cũ lệch UTC, giải thích đúng 266/257

**Trạng thái: đã chứng minh trên DB local bằng timestamp nguồn và file khách, chưa sửa DB/code. P0 xử lý đầu tiên.** Liên quan mục 3.3, 3.5 và kết quả lượt 1. Chưa xác nhận bản DB khách đang chạy có cùng trạng thái.

**Bằng chứng số đếm:**

- DB kiểm tra: `tdp_system/data/tdp.sqlite3`, kết nối `mode=ro`, `PRAGMA query_only=ON`.
- Lọc `msmi_invoices.invoice_type = INPUT_ELECTRONIC_INVOICE`, `invoice_date` đã lưu trong 01–31/08/2026: **257 hóa đơn**, đều `synced`, `pending_mapping` trong DB này.
- Đọc timestamp ngày lập từ `raw_json` của toàn bộ hóa đơn đầu vào, chuyển múi giờ sang UTC+7 và lọc tháng 8 **chỉ trong bộ nhớ**: **266 hóa đơn**. Không có timestamp không đọc được trong tập đã kiểm tra.
- So sánh bằng ID bản ghi: tập sau chuẩn hóa thêm đúng **9**, không loại hóa đơn nào của tập 257. Cả 9 có nguồn `tdlap = 2026-07-31T17:00:00Z`, tương ứng **00:00 ngày 01/08/2026 tại Việt Nam**, nhưng cột ngày đã lưu là **2026-07-31**.
- Do đó **257 + 9 = 266**; không phải bằng chứng mất dữ liệu nguồn hoặc thiếu 9 hóa đơn ngày 31/08. Dữ liệu cuối tháng nhìn thành 30/08 cũng do lệch ngày: ví dụ hóa đơn nguồn `2026-08-30T17:00:00Z` là ngày 31/08 tại Việt Nam.

Chín hóa đơn bị lọc ra ngoài tháng 8 trong DB local:

| ID local | MST bên bán | Ký hiệu | Số hóa đơn | Ngày đúng VN / ngày lưu sai |
|---:|---|---|---|---|
| 457 | 0202299079 | C26MTT | 1610 | 01/08 / 31/07 |
| 458 | 0202325120 | C26TAA | 279 | 01/08 / 31/07 |
| 459 | 1001318936 | C26THD | 1407 | 01/08 / 31/07 |
| 460 | 0201925686 | C26THP | 5392 | 01/08 / 31/07 |
| 461 | 0202310290 | C26TYY | 717 | 01/08 / 31/07 |
| 462 | 0202291055 | C26TYY | 3318 | 01/08 / 31/07 |
| 463 | 0100109106 | K26DAB | 27155463 | 01/08 / 31/07 |
| 464 | 0100109106-043 | K26TVA | 894696 | 01/08 / 31/07 |
| 465 | 030083006876 | C26MYY | 1722 | 01/08 / 31/07 |

**Phân biệt source mới và dữ liệu cũ:** `contract_modules.py::as_date()` hiện đã chuyển timestamp chuỗi có múi giờ sang giờ Việt Nam. Tuy nhiên cột ngày trong DB local vẫn giữ giá trị sai đã lưu trước đó, còn `invoice_workbench_listing.py::invoice_range_payload()` lọc trực tiếp theo cột này. Vì vậy sửa hàm đọc ngày hoặc thay EXE chưa chứng minh dữ liệu lịch sử đã được sửa. Đây là vấn đề phải kiểm tra khi nâng cấp/tái đồng bộ; không kết luận mọi bản EXE hiện tại đều còn lỗi chuyển ngày.

**Đối chiếu file `nhập T8.2026 (1).xlsm`:**

- Sheet `weekend`, hàng tiêu đề 8, tổng cộng hàng 1351. Có **261 số chứng từ PN khác nhau**, khớp 261 dòng đầu phiếu có TT dương; **1.341 dòng có ngày chứng từ bao gồm cả dòng đầu phiếu và chi tiết**, không phải 1.341 hóa đơn.
- Có **260 cặp MST bên bán + số hóa đơn** đầy đủ từ cột Y/AB với ngày hóa đơn ở AA. File không có ký hiệu hóa đơn, nên phép ghép này là đối chiếu trong phạm vi kỳ và tập local, không thay thế khóa định danh đầy đủ cho hệ thống.
- Cả 260 cặp đều tìm thấy duy nhất trong dữ liệu local quanh kỳ. **260/260 ngày hóa đơn trong file muộn hơn ngày lưu DB đúng một ngày**, nhất quán với lỗi UTC; không có cặp nào thiếu khỏi dữ liệu nguồn local trong phép ghép này.
- Riêng phiếu **00132**, hàng **757–758**, ngày chứng từ **18/08**, giá trị **1.200.000 đồng**, hàng diễn giải ghi `Hóa đơn số: 5785`, nhưng cột ngày/số hóa đơn ở chi tiết trống. Không tự suy ra đây là hóa đơn độc lập. Bản nguồn cùng MST `0201925686`, số `5785` có ngày Việt Nam **16/08** và tổng **5.282.800 đồng**, nên cần đối chiếu chi tiết trước khi gộp/cân tiền.
- Sáu hóa đơn trong tập nguồn tháng 8 chuẩn hóa chưa có cặp đối chiếu đầy đủ trong file: `0202360816 / 9`, `0202338578 / 855`, `030083006876 / 2087`, `030083006876 / 2088`, `0100109106 / 27155463`, `0100109106-043 / 894696`. Chưa kết luận sáu hóa đơn này buộc phải tạo phiếu nhập kho; cần xét nội dung và phạm vi báo cáo.
- Vì thế phải tách **266 hóa đơn nguồn**, **257 hóa đơn lọc theo ngày sai**, **261 phiếu nhập trong file khách** và **260 cặp hóa đơn đủ trường để ghép**. Không đổi số liệu để ép bốn con số bằng nhau.

**Trách nhiệm và bước đóng lỗi:** dữ liệu hóa đơn local đang sai ngày là lỗi phía hệ thống đã xác nhận, không quy cho khách lọc sai. Cần kiểm tra DB vận hành, sao lưu và lập phương án xử lý ngày lịch sử/ảnh hưởng sổ kho theo timestamp nguồn trước khi ghi sửa; không cộng một ngày hàng loạt theo phỏng đoán. Nghiệm thu bằng ID/tập hóa đơn đúng kỳ và tổng tiền, kiểm tra cả rìa tháng, không ghi trùng hoặc thay đổi kỳ kho đã chốt âm thầm. Việc khớp toàn bộ phiếu nhập và đầu ra vẫn cần đối soát tiếp; chưa dùng kết quả số đếm này để tuyên bố đã hoàn tất luồng thuế.

### 13.10. Vì sao đã sửa ngày nhưng EXE bàn giao 05/09 vẫn còn 257?

**Kết luận: bản sửa hàm ngày đã được đóng gói đúng, nhưng chưa xử lý dữ liệu lịch sử và còn đóng gói DB khởi tạo sai ngày. Đây là thiếu sót của đợt sửa/nâng cấp và kiểm thử bàn giao phía hệ thống. Chưa sửa trong lượt kiểm tra này.**

**Đúng artifact chủ dự án xác nhận đã bàn giao:**

- `D:\TDP_BAN_GIAO_20260905\Thanh_Dat_Phat.exe`, 90.870.375 byte, thời gian sửa file 05/09/2026 15:35:51.
- SHA-256 đọc trực tiếp: `8FE9904BFC4CCFB8712FE246C0B7E1F43F3CEB18A32A92BA392BAAB5D37BDE4E`, khớp bản ghi ở đầu README.
- Dùng bộ đọc archive PyInstaller đọc module và DB nhúng trong EXE; không khởi chạy lại ứng dụng, không giải nén cấu hình bí mật hoặc ghi ra DB vận hành. DB nhúng được đọc trong SQLite bộ nhớ; chỉ bản sao header trong bộ nhớ được đổi chế độ journal để đọc độc lập, không thay byte nào của EXE/DB trên đĩa.

**Bằng chứng trực tiếp trong EXE:**

1. Hàm `contract_modules.as_date` đã có chuyển UTC+7. Gọi riêng code của hàm trích từ EXE: `2026-07-31T17:00:00Z → 2026-08-01`, `2026-08-30T17:00:00Z → 2026-08-31`.
2. Đối chiếu bytecode, tên và hằng số của các hàm trong EXE với source hiện tại: `as_date`, `init_contract_schema`, `upsert_msmi_invoice`, `invoice_range_payload` đều khớp. Không có bằng chứng build quên hàm sửa ngày.
3. EXE nhúng `seed\tdp_seed.sqlite3`, **60.350.464 byte**. Lọc ngày đã lưu của DB này cho **257** hóa đơn đầu vào tháng 8; dùng chính hàm `as_date` từ EXE đọc lại timestamp nguồn trong bộ nhớ cho **266**, thêm đúng ID **457–465**.
4. `BUILD_SINGLE_EXE.ps1` lấy snapshot từ `tdp_system/data/tdp.sqlite3`; `build_release_inputs.py::snapshot_database()` sao chép nhất quán và kiểm tra toàn vẹn SQLite, không chuẩn hóa lại ngày hóa đơn trong snapshot. DB không hỏng cấu trúc vẫn có thể sai ngày nghiệp vụ.
5. `install_seed_database_if_missing()` giữ nguyên DB đã có; chỉ cài snapshot khi chưa có DB. Vì vậy thay EXE không tự sửa các ngày đã lưu trong DB khách. Cài vào thư mục mới cũng nhận snapshot cũ đang sai ngày.

**Bằng chứng sau khởi động và lỗ hổng kiểm thử:**

- Đọc chỉ đọc DB của lần smoke EXE đã có tại `D:\TDP_BUILD_20260905\temp\tdp-release-20260905-r4kpaylw\data\tdp.sqlite3`: sau hai lần khởi động vẫn có **257** hóa đơn tháng 8; ID 457–465 vẫn ngày **31/07**. Như vậy khởi động/nâng cấp bản này chưa tự sửa trường hợp dữ liệu lịch sử đã chứng minh.
- `result.json` của chính lượt smoke ghi `ok=true`, nhưng các kiểm tra là khởi động hai lần, schema, integrity, menu, người bán, sao lưu, tải mẫu và giữ dữ liệu cũ. **Không có kiểm tra đối soát 266 hóa đơn thật sau nâng cấp.**
- Các test ngày đúng và fixture 266 đã chứng minh được logic mới ở phạm vi đã thử, nhưng bỏ sót tình huống nâng cấp từ DB có ngày UTC sai đã lưu sẵn. Vì vậy không được dùng kết quả đó để khẳng định bản bàn giao đã khắc phục dữ liệu thật.

**Giới hạn của cách tải lại:** `upsert_msmi_invoice()` cập nhật ngày nguồn với hóa đơn chưa ghi kho khi hóa đơn đó thực sự được đồng bộ lại. Với hóa đơn đã `posted`, khác biệt ngày nằm trong kiểm tra thay đổi nghiệp vụ; hàm có thể giữ ngày/kho cũ và báo `review_required`. Không hứa rằng chỉ tải lại hoặc thay EXE sẽ sửa toàn bộ, không bỏ bảo vệ chứng từ đã ghi kho để ép ngày mới.

**Điều kiện đóng BUG-0509-04 bổ sung:** kiểm tra an toàn cả DB cũ đã ghi/chưa ghi kho và DB khởi tạo của bản build; xử lý ngày từ timestamp nguồn có đối chiếu, giữ liên kết và lịch sử; chạy chính EXE trên bản sao dữ liệu lịch sử để chứng minh tập hóa đơn tháng 8, số đếm và tổng tiền đúng sau nâng cấp và sau mở lại. Chưa được ghi hoàn thành trước khi có bằng chứng này. Việc máy khách có cùng tình trạng cần đọc đúng DB đang dùng, nhưng lỗi trong artifact bàn giao đã được xác nhận độc lập.

### 13.11. Sửa riêng lỗi 1 / BUG-0509-04 — nhật ký triển khai và kiểm chứng

**Chỉ đạo mới:** chủ dự án yêu cầu kiểm tra kỹ và sửa lỗi 1 trước; cập nhật README để lưu bằng chứng. Lượt này chưa xử lý lỗi NCC, nhận diện sheet đặt hàng, thanh toán VAT hoặc menu ngang; chưa tạo ZIP bàn giao chung.

- Thêm `tdp_system/invoice_date_migration.py`: đối chiếu timestamp nguồn có múi giờ với ngày đã lưu; chỉ tự sửa trường hợp chứng minh được ngày UTC bị cắt và hóa đơn chưa ghi kho. Không cộng một ngày đại trà, không nạp lại chi tiết, không thay lượng/tiền/mã ghép. Lịch sử trước/sau lưu tại `invoice_date_repairs`.
- `server.init_database()` gọi bước sửa sau sao lưu trước nâng cấp và khởi tạo schema. Mỗi lượt sửa có savepoint; lỗi giữa chừng hoàn tác cả lượt, mở lại không sửa trùng.
- Hóa đơn đã ghi kho/có dấu vết bút toán hoặc ngày lệch không đúng mẫu UTC: giữ ngày và sổ kho, đưa trạng thái cần kiểm tra với lý do; hiện danh sách ngày đang lưu/ngày nguồn VN trên màn đầu vào và sheet Excel đối chiếu. Danh sách cảnh báo xét cả ngày cũ và mới để không giấu các hóa đơn nằm phía bên kia rìa tháng. Chưa tự điều chỉnh bút toán đã ghi hoặc kỳ đã chốt.
- `build_release_inputs.snapshot_database()` sửa **bản snapshot dành cho build**, không sửa DB nguồn. Còn trường hợp ngày cần đối chiếu thì dừng tạo seed, giữ artifact cũ. Hai script build khai báo module mới; bản ứng viên kiểm thử mang phiên bản `2026.09.05.2`, chưa thay EXE `2026.09.05.1` đã giao.
- Kiểm thử đợt đầu: **58 test đạt** về sửa ngày lịch sử, mSMI/sync đầu vào, bảng/Excel, nhập kho và chốt tháng; kiểm tra cú pháp JS đạt. Test mới có 257→266 bằng tập ID, rìa tháng 9, chống trùng, rollback, dữ liệu ngày không đủ căn cứ, chặn sửa hóa đơn đã ghi kho, giữ DB nguồn và chặn seed còn lỗi.
- `verify_invoice_date_upgrade.py` chạy trên bản sao `tdp_system/data/tdp.sqlite3`: **đạt 257→266** sau nâng cấp và khởi động lại; API danh sách và Excel khớp tập ID/tổng tiền; giữ payload nguồn, tiền, các cột đơn cũ, chi tiết hóa đơn, mapping và các bảng sổ kho. Có bản sao trước sửa, seed tạo riêng đúng ngày, DB nguồn không đổi.
- Bằng chứng source: `D:\TDP_BUG1_QA\source-upgrade-02\result.json`, `listing_summary.json`, `input_august.xlsx`, `verified_seed.sqlite3`. Lượt `source-upgrade-01` dừng ở phép so fingerprint vì migration kho thực tế đã có từ trước bổ sung cột `orders.physical_stage`; kiểm tra từng cột cũ không đổi. Đã sửa bộ kiểm chứng để so đúng mọi cột tồn tại trước nâng cấp, giữ kiểm tra đầy đủ dữ liệu cũ; không sửa nghiệp vụ kho thực tế để né phép kiểm tra.
- Hồi quy mở rộng: **71 test đạt** về đóng gói desktop, các phần hoàn thiện trước, sổ kho hóa đơn, đồng bộ đầu ra, mapping và xuất đầu vào. Đây là nhóm chạy riêng ngoài nhóm 58 test ở trên; không coi số lần chạy test là bằng chứng đã nghiệm thu toàn hệ thống.
- **Đã chạy chính EXE ứng viên trên bản sao DB cũ, đạt:** từ **257 lên 266**, thêm đúng ID 457–465 theo timestamp nguồn. Tổng tiền tập 266 hóa đơn là **919.234.874 đồng**, khớp API và tổng cuối Excel. Khởi động hai lần cho cùng tập ID, số tiền, lịch sử sửa và dữ liệu được bảo vệ; có backup giữ trạng thái trước sửa. Không gọi connector thật.
- Bước nâng cấp trên bản sao ghi **5.240 bản sửa ngày lịch sử** từ timestamp nguồn của toàn bộ hóa đơn đầu vào; **9** là số hóa đơn chuyển vào phạm vi tháng 8, không phải tổng số ngày cần sửa. Payload nguồn, tiền, chi tiết, mapping, các cột đơn đã tồn tại và các bảng sổ kho được đối chiếu không đổi. DB vận hành nguồn vẫn giữ nguyên.
- Bằng chứng EXE: `D:\TDP_BUG1_QA\temp\exe-upgrade-01\result.json`, `listing_summary.json`, `input_august.xlsx`; có bản sao DB đã nâng cấp và `data\migration_backups` trong cùng thư mục. Script tái kiểm chứng: `tdp_system/verify_invoice_date_upgrade.py` (đầu ra phải là thư mục mới; khi dùng `--exe`, thư mục phải nằm trong TEMP).
- Artifact kiểm thử: `D:\TDP_BUG1_QA\candidate\Thanh_Dat_Phat.exe`, phiên bản **2026.09.05.2**, SHA-256 **`C71453AC35718EFE3441F8332AF52862AAAFE877A58B87BCA7B147F821CF6AE3`**. Đọc trực tiếp archive xác nhận có module migration mới và **DB seed nhúng đủ 266 hóa đơn đầu vào tháng 8**.
- Kiểm tra lại EXE đã giao `D:\TDP_BAN_GIAO_20260905\Thanh_Dat_Phat.exe`: SHA-256 vẫn **`8FE9904BFC4CCFB8712FE246C0B7E1F43F3CEB18A32A92BA392BAAB5D37BDE4E`**, không bị thay thế.
- **Kết luận phạm vi lỗi 1:** đã sửa source và kiểm chứng artifact ứng viên với dữ liệu lịch sử local thật bằng bản sao. Chưa xác nhận DB đang chạy trên máy khách; nếu chứng từ khách đã ghi kho, hệ thống giữ sổ và báo cần đối chiếu, không tự đổi ngày bút toán. Chưa kết luận đã khớp toàn bộ đầu vào/đầu ra hoặc xử lý hết phản ánh khách. Chưa sửa các lỗi còn lại hay tạo ZIP bàn giao chung.

### 13.12. Mốc Git trước khi chuyển sang Railway — 05/09/2026

- Chủ dự án yêu cầu commit/push bản source hiện tại làm mốc khôi phục trước khi sửa tiếp và chuyển hướng sang web Railway. Đã xác nhận repo đích **`xandrosworld/CDT`**, nhánh `main`; remote `tdp` (`xandrosworld/T-P`) không thuộc lần push này.
- Tag dự kiến cho mốc source: **`checkpoint-2026-09-05-before-railway`**. Đây là mốc hiện trạng có bằng chứng kiểm thử, không phải cam kết tất cả chức năng đã đúng hoặc đã được khách nghiệm thu. Trạng thái push sẽ được xác minh bằng commit trên remote.
- Lưu source, kiểm thử, script build/kiểm chứng, tài liệu và bốn mẫu trình bày đã loại dữ liệu giao dịch. Không đưa `.env`, DB, danh mục CCCD, file khách, EXE/ZIP, log hay thư mục bàn giao lặp vào Git. DB vận hành và cấu hình thật cần sao lưu/chuyển riêng khi triển khai; checkout Git không tự phục hồi các dữ liệu này.
- Đọc thêm bản sao DB tại `D:\TDP_BUG1_QA\temp\exe-upgrade-01\data\tdp.sqlite3`: tháng 8 có **266 đầu vào**, gồm **264 `pending_mapping` và 2 `not_inventory`**; bảng `invoice_line_mappings`, `invoice_inventory_ledger` và `outgoing_invoice_drafts` đều **0 bản ghi**. Đây là dữ liệu local đã có, chưa phải xác nhận DB trên máy khách. Đủ 266 hóa đơn tải về chưa chứng minh đã ghép mã, nhập kho và khớp đầu ra. Khách/chủ dự án đã tạm dừng bước kiểm thử/chụp màn hình tiếp theo để bàn hướng hosting; chưa có ảnh bằng chứng bổ sung cho toàn luồng.
- Các việc còn mở: đối soát vận hành đầu vào–đầu ra; thanh toán từ VAT đồng bộ; lỗi đọc NCC và sheet đặt hàng 03/09; yêu cầu menu ngang. Không đổi các mục này thành hoàn thành khi push.
- Lần này lưu mốc source; chưa triển khai Railway. Bước chuyển web cần kiểm tra đường dẫn DB/lưu trữ bền vững, sao lưu/khôi phục và nâng cấp dữ liệu, cấu hình môi trường, đăng nhập/phân quyền trước khi mở Internet, cùng các phụ thuộc Windows/in Excel/PDF. `requirements.txt` hiện còn `pywin32` và công cụ đóng gói desktop; không coi source desktop hiện tại là cấu hình Linux đã kiểm chứng.
- Kiểm tra trước commit: chạy **69 module / 520 test trong 417,141 giây**, **519 đạt, 1 thất bại** do test `test_payroll_ui` cũ vẫn yêu cầu hiện hai menu đã được chủ dự án quyết định ẩn ở mục 2.1 và khóa cứng phiên bản JS cũ. Đã cập nhật test theo quyết định này: hai menu không hiện, kho thực tế vẫn hiện, phần triển khai/API cũ vẫn còn. Chạy riêng test vừa sửa **đạt 1/1**; không thay code sản phẩm để vượt test, không chạy lại toàn bộ 520 sau thay đổi chỉ ở test.
- Log bộ tổng lưu local: `D:\TDP_BUG1_QA\temp\tdp-git-checkpoint-mc7o2k6a\tests.log`. Bộ test dùng DB/exports cô lập và cấu hình connector offline. Kiểm tra cú pháp các file Python trong commit và **24 file JS/MJS** đạt; `git diff --cached --check` đạt sau chuẩn hóa khoảng trắng tài liệu. Kiểm tra các giá trị bí mật thực trong `.env` không xuất hiện ở file staged; các vị trí regex báo nghi vấn đều là placeholder kiểm thử. Danh mục CCCD, DB và `.env` vẫn bị Git bỏ qua.
