# TỔNG HỢP ĐẦU VIỆC SAU CUỘC GỌI KHÁCH HÀNG 04/09/2026

> **Sửa lỗi tab hóa đơn của đơn 04/09 — 06/09/2026:** đã bổ sung đúng hai mã
> `M000357`, `O000139` từ file khách và khôi phục ĐVT bị bỏ sót khi nhập.
> Railway đã hiển thị lại bảng khả năng xuất; 320 dòng đơn giữ nguyên lượng,
> giá và tiền, vẫn là nháp. Nguyên nhân và bằng chứng tại **13.26**.

> **Hồ sơ người bán — 06/09/2026:** khách xác nhận **Đoàn Văn Giang** là
> hồ sơ đúng trong hai người bị loại trước đây. **Đã mở lại Giang trên Railway**;
> **Nguyễn Văn Toại vẫn bị loại** khỏi bảng kê/biên nhận mới. Kết quả kiểm tra
> và trạng thái triển khai tại **13.25**; thay quyết định loại cả hai ở 6.1/10.2.

> **Xử lý phần Phong — 06/09/2026:** hai khoản mua hộ do hàng hỏng ngày 03/09
> được trừ **207.000 đồng vào công nợ Phong**, giữ doanh thu và lượng bán.
> Đã deploy Railway và kiểm tra lại; kết quả và phạm vi tại **13.24**.
> Bốn mã tồn đầu âm vẫn chờ khách chốt, không tự đổi số.

> **Tự động xử lý phần đủ căn cứ — 06/09/2026:** chủ dự án yêu cầu tự ghép
> mã chắc chắn, bỏ bước bắt khách xem rồi xác nhận lại. Dòng còn cần xử lý hoặc
> xác nhận nằm trước, phần đã xử lý xong nằm dưới; chỉ lỗi mới tô đỏ. Đã áp dụng
> **941 dòng trên Railway**, còn **163 dòng** thiếu căn cứ. Xem **13.23**.

> **Quyết định mới 06/09/2026:** chỉ dòng có **lỗi** mới tô đỏ cả dòng, áp dụng
> chung mọi file; cảnh báo hiển thị riêng. Hai dòng âm đặt hàng 03/09 được giải thích
> là hàng hỏng, chị đi mua cho khách; quyết định công nợ mới tại **13.24** thay phần chờ ở **13.22**.

> **Đối chiếu số liệu và màu cảnh báo 06/09/2026:** bảng Excel tô đỏ cả dòng
> lỗi/cảnh báo và hết đỏ sau khi sửa hợp lệ. Đã đối chiếu nguồn–API–Excel trên
> bản sao Railway, sửa tổng lượng nhiều ĐVT và trạng thái tổng file kho.
> Còn dữ liệu chưa đủ điều kiện chốt; xem **13.21** và báo cáo đối chiếu riêng.

> **Rà soát máy tính 06/09/2026:** phát hiện và sửa lỗi nhập lượng `0,855` trong
> bảng Excel bị hiểu thành `855`, cùng hướng dẫn in/sao lưu chưa đúng bản web.
> Phạm vi từng màn và kết quả tại **13.20**; không kết luận “100% không lỗi”.

> **Nhập đơn nhiều lần trong ngày và bảng Excel trên web — 06/09/2026:**
> đã triển khai và kiểm tra trên Railway. File đầu được lưu nháp
> dù còn thiếu; file mới hợp lệ cùng ngày/phạm vi cập nhật bản đang dùng, có lịch sử.
> Bảng đơn sửa ô/dán nhiều ô và tự lưu. Phạm vi và bằng chứng tại **13.19**.

> **Đổi domain 06/09/2026:** địa chỉ hiện tại là https://tdp.up.railway.app/login.
> Đã xử lý lỗi tên máy không nằm trong danh sách tin cậy và kiểm tra đăng nhập,
> mở màn hình, tải phiếu giao trên domain mới. Xem **13.18**; đây chưa phải nghiệm thu toàn bộ quy trình.

> **Quyết định mới của chủ dự án:** lưu mốc source lên `xandrosworld/CDT`, sau đó
> chuyển sang web Railway cho khách, không tiếp tục bàn giao EXE như trước.
> Mốc Git này chưa phải bản đã triển khai/nghiệm thu Railway. Xem **13.12**.

> **Đợt sửa để nghiệm thu Railway đang thực hiện:** xem **13.15**. Các mục bên dưới có mốc ngày là lịch sử kiểm tra, không thay thế kết quả mới nhất.

> **Mốc xem trước ngày 06/09/2026, trước quyết định tự động tại 13.23:** đã triển khai trên Railway hai luồng xem trước
> để giảm khối lượng ghép mã hóa đơn đầu vào, gồm ghép chính xác theo danh mục và
> đối chiếu bảng kê nhập của phần mềm cũ. Tại mốc này production chỉ chạy xem trước, chưa
> xác nhận ghi mapping hoặc ghi kho. Kết quả và giới hạn tại **13.17**.

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
- Theo quyết định mới tại 13.23, tự lưu mã khớp duy nhất theo danh mục/ĐVT hoặc bảng kê cũ đủ điều kiện. Chỉ trường hợp chưa đủ căn cứ mới cần người dùng chọn mã/quy đổi; giữ lựa chọn đã có.
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
- Có thể nạp bản thiếu từ tối hôm trước/đầu ngày, rồi nạp nhiều bản hoàn thiện trong ngày. Ngày nghiệp vụ lấy từ file/phạm vi đã xác định, không lấy ngày upload thay thế. Bản sau hợp lệ ưu tiên dữ liệu của file, kể cả ô từng sửa trên web; giữ lịch sử bản trước. Nạp file không tự duyệt đơn hoặc chốt giao hàng. Xem 13.19.

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

**Cập nhật 06/09/2026:** khách đã xác nhận hồ sơ Đoàn Văn Giang; chỉ giữ loại Nguyễn Văn Toại. Quyết định và kết quả mới tại **13.25** thay quy tắc loại cả hai ngày 05/09 bên dưới.

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
- CCCD/địa chỉ: đã sửa theo 6.1. Quyết định ngày 06/09 tại 13.25 mở lại Đoàn Văn Giang theo xác nhận khách; Nguyễn Văn Toại vẫn bị loại khỏi chứng từ mới.
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

### 13.13. Triển khai Railway qua GitHub — đang thực hiện

- Chủ dự án đã cho phép deploy, cấu hình biến, chuyển DB/tài nguyên lên Railway rồi kiểm thử như người dùng thật. Chỉ đạo bổ sung: **deploy từ `xandrosworld/CDT`, nhánh `main`**, để push sau tự cập nhật. Không dùng upload source local làm nguồn triển khai.
- Railway đã đăng nhập; project `thanh-dat-phat` (`6a082880-d1c8-4151-aa58-a6e5c15097b1`), environment `production` (`a13cdd3b-9265-43aa-b435-2fdddf5882bf`), service `tdp-web` (`352a9558-f37a-4777-a14f-facc9e894323`), volume `tdp-web-volume` (`d14068eb-edb4-48aa-bc32-2fb2aa7a804b`) gắn `/data`.
- Docker Linux riêng dùng Python/Waitress, đọc `PORT`, một instance; SQLite `/data/tdp.sqlite3`, file xuất `/data/exports`, mẫu/dữ liệu tham chiếu `/data/assets`. Không đóng DB/bí mật vào image hoặc Git. Source có cổng đăng nhập bằng mật khẩu băm, cookie HttpOnly/Secure, chặn ghi khác nguồn và hạn chế thử mật khẩu; cấu hình thiếu thì dừng.
- Bản chuyển DB lấy từ dữ liệu local đã có, tạo snapshot và sửa ngày có bằng chứng; không được diễn đạt là DB mới nhất trên máy khách. Chuẩn bị 75 tài nguyên Office cần dùng/đối chiếu, tổng DB+tài nguyên khoảng 81 MB; chưa phải toàn bộ file tải về/media/build desktop.
- Railway cần container chạy để upload volume. Bước bootstrap chỉ trả trạng thái chuẩn bị, không mở API nghiệp vụ và không tạo DB trống. Chỉ khởi động ứng dụng thật sau khi upload xong DB/tài nguyên và marker; DB thiếu ở chế độ vận hành thì dừng, không âm thầm tạo lại.
- Thêm chuyển Excel→PDF bằng LibreOffice cho Linux; giữ workbook/mẫu và render từng sheet hiển thị. Cần kiểm tra bố cục PDF thực tế trên Railway; không coi tương đương Microsoft Excel 100% khi chưa có ảnh đối chiếu.
- Kiểm tra ban đầu: **7 test đạt** về đăng nhập, CSRF, chống thử mật khẩu và bộ render PDF hiện có. Đang kiểm tra deploy, chuyển dữ liệu, khởi động lại, xuất file và trình duyệt; chưa ghi thành công trước kết quả.
- Đã đọc lại Google Sheet `1c1C4Imexri4VRolrNSSmWmSnpmM0hgj0TCCbm9if3D8`, tab `Khách hàng kiểm tra`, A1:I22: 14 mục vẫn `Chưa chốt` / `Đã sửa sau cuộc gọi` / `Chưa kiểm tra`. Không sửa cột nghiệm thu của khách; dùng cùng README để đối chiếu sau deploy.

### 13.14. Kiểm tra trực tiếp Railway — tối 05/09/2026

**Kết luận: đã deploy và đăng nhập được; chưa đạt kiểm thử sử dụng đầy đủ. Hai lỗi cloud dưới đây còn mở, chưa sửa trong lượt kiểm tra này.**

- Railway CLI xác nhận service `tdp-web`, environment `production`, deployment `683aad5d-c71d-435f-80f6-7636ab8e943f` có trạng thái `SUCCESS`, instance `RUNNING`. Nguồn `xandrosworld/CDT`, nhánh `main`, commit `c79774d8c748031c26827846300564d345fb8c1b`, khớp HEAD local lúc kiểm tra.
- Truy cập HTTPS `/login` đạt 200; `/health` đạt 200, `database_ready=true`, `schema_ready=true`, `integrity=ok`. Chưa đăng nhập gọi `/api/bootstrap` bị chặn 401. Đăng nhập bằng Chrome thật thành công; mở được 11 màn hình chính, chụp 12 ảnh gồm trang đăng nhập, không ghi nhận JavaScript exception trong lượt chạy.
- Danh sách đầu vào tháng 8 trên API và màn hình đủ **266 hóa đơn**, **1.107 dòng**, tổng thanh toán **919.234.874 đồng**. Trạng thái: **264 cần ghép mã, 2 không nhập kho, 0 đã ghi kho**; có 1.104 dòng cần xử lý. Đầu ra tháng 8 trong DB hiện tại là 0. Đây là dữ liệu đã chuyển từ local, không phải xác nhận dữ liệu mới nhất trên máy khách hoặc kết quả đồng bộ mới từ nhà cung cấp.
- Volume gắn `/data`; DB `/data/tdp.sqlite3`, exports `/data/exports`, `TDP_BOOTSTRAP=0`. Kiểm tra container thấy 75 file tài nguyên và marker bootstrap. API backup báo thành công gần nhất `2026-09-05T21:43:42`, chu kỳ 30 phút, giữ 14 ngày. Lượt này không restart/redeploy hoặc kiểm thử khôi phục backup.
- **Lỗi kết nối hóa đơn:** `/api/msmi/status` và `/api/minvoice/status` đều trả **502**, thông báo thiếu cấu hình `.env`. Các biến Railway cần thiết đã có nhưng `MsmiConfig.from_env_files()` và `MinvoiceConfig.from_env_files()` chỉ đọc file, không đọc `os.environ`. Vì thế chưa kiểm chứng được kết nối nguồn thật; cần sửa cách nạp cấu hình cloud rồi kiểm tra lại, không kết luận sai mật khẩu hay nhà cung cấp bị sập.
- **Lỗi phiếu giao:** gọi `/api/documents/preview` với phiếu đang có trả **500**, báo `Không thể dùng mẫu phiếu giao đã khóa: Không tìm thấy workbook golden`. `cloud_server.py` gán `server.MASTER_SOURCE` thành `/data/.no_automatic_master_import.xlsx` để ngăn nhập lại danh mục, nhưng các hàm xuất chứng từ trong `server.py` cũng dùng chính biến này làm `template_path`. Container thực tế có `/app/Em Thành.xlsx`; cần tách điều kiện tự nhập danh mục khỏi đường dẫn mẫu. Luồng phiếu giao bị chặn trước bước tải Excel/PDF, chưa thể ghi hai định dạng này đạt.
- Bằng chứng riêng ngoài Git: `D:\TDP_RAILWAY_PRIVATE\evidence\recheck-20260905\browser-result.json` và 12 ảnh; lượt chẩn đoán tiếp `D:\TDP_RAILWAY_PRIVATE\evidence\diagnostic-20260905\browser-result.json`. Script chuẩn `tdp_system/qc_cloud_browser.mjs` dừng thất bại ở mSMI; bản chẩn đoán riêng tiếp tục qua hai lỗi connector để phát hiện lỗi phiếu giao. Không thay tiêu chí đạt của script chuẩn.
- Phạm vi lượt này: kiểm tra cấu hình, log, dữ liệu hiển thị, đăng nhập và xem chứng từ; không sửa source sản phẩm, biến Railway, dữ liệu nghiệp vụ hoặc phát hành hóa đơn thật. Các lỗi nghiệp vụ còn mở ở mục 13 vẫn cần xử lý riêng.

### 13.15. Sửa theo 14 mục checklist và phản ánh bổ sung — 05/09/2026

- Chủ dự án yêu cầu sửa triệt để để khách kiểm tra các chức năng trên Railway. Đã đọc lại Google Sheet `Khách hàng kiểm tra`, A1:I22: 14 mục vẫn `Chưa chốt` / `Đã sửa sau cuộc gọi` / `Chưa kiểm tra`. Sheet là nguồn yêu cầu; không thay phần khách xác nhận bằng kết quả test kỹ thuật.
- Đã sửa cấu hình mSMI/M-Invoice: biến môi trường được ưu tiên hơn file `.env`, kể cả giá trị trống để không dùng lại bí mật cũ. Đã tách tùy chọn nhập lại danh mục khỏi đường dẫn mẫu in, giữ `Em Thành.xlsx` cho các hàm xuất.
- Đã sửa ưu tiên cột NCC nghiệp vụ so với cột cảnh báo `Chọn NCC`. Bổ sung nhận diện cấu trúc B:P của sheet đặt hàng 03/09, gồm `Đơn giá`, tiêu đề tiền là tổng SUBTOTAL và thứ tự trừ các cột điều chỉnh tương đương. Không suy ra cột tiền chỉ từ một ô số bất kỳ.
- Kiểm tra trên bản sao DB local và đúng file khách `Đơn hàng  03.09.2026.xlsx`: đọc 352 dòng đơn, không có lỗi chặn ở các dòng đơn; dòng 342 giữ `kho`, mã `L000004`, lượng `0,54` qua đọc → lưu bản sao → kế hoạch đặt hàng. Nhận 273 dòng đặt hàng, dòng 103 giữ `kho`, `0,54`, **14.040 đồng**. DB nguồn không thay đổi.
- Hai dòng nguồn vẫn cần khách xác nhận: dòng 157 `quả dưa hấu` và 158 `quả nhãn` có lượng **−1**; dòng 158 thiếu mã hàng. Giữ chặn để không ghi âm/sai công nợ. Đã hỏi chủ dự án đó là hàng trả hay nhập nhầm; không tự sửa Excel hoặc diễn giải thành nghiệp vụ trả hàng.
- Hồ sơ VAT: bổ sung lấy trực tiếp hóa đơn đầu ra đã đồng bộ theo MST hồ sơ nhà thầu, không cần draft cục bộ; ghép với nguồn cục bộ không đếm trùng, kiểm tra trạng thái, danh tính người mua và ba tổng. Hóa đơn chưa liên kết bếp/ngày giao xuất **bảng kê hóa đơn VAT** kèm cảnh báo, không bịa lịch sử giao nhận. Thông tin nhận tiền được khóa trong phạm vi xem trước theo cấu hình lúc lập đề nghị. Luồng cục bộ giữ kiểm tra snapshot lịch sử. Bộ lọc nhà thầu/kỳ độc lập với đơn đang mở và giới hạn 200 draft.
- Menu máy tính đã chuyển ngang; nội dung dùng toàn bộ chiều rộng. Giữ đường vào các chức năng còn dùng và điều hướng thu gọn trên điện thoại; nút đăng xuất hiển thị đủ chữ.
- Hồi quy: **73 module / 539 test đều đạt, không bỏ qua bài nào**, dùng DB/thư mục riêng và connector offline. Log `D:\TDP_RAILWAY_PRIVATE\evidence\acceptance-regression-01\summary.json`; tái chạy bằng `python -m tdp_system.qa_railway_acceptance --output THU_MUC_RIENG`.
- Trình duyệt: cả 5 lượt hóa đơn/kho, đơn/NCC/kho thực tế, báo cáo/công nợ, chọn/xem/in chứng từ và menu/sao lưu đều đạt trên fixture riêng. Có thao tác ghi/hoàn tác, giữ phần thiếu, chốt/mở/chốt lại, kiểm tra 1440/1024px. Lượt 4 được chạy lại sau sửa đường dẫn trong công cụ chạy test; không thay tiêu chí đạt của sản phẩm. Bằng chứng ở `browser-acceptance-01` và `browser-acceptance-02` dưới thư mục evidence; tái chạy bằng `python -m tdp_system.qa_browser_rounds --output THU_MUC_RIENG`.
- Bản sửa `74e270e` đã chạy trên Railway, deployment `154e7af3-892c-420e-9646-8d1527bc9518` thành công. Trình duyệt hosted kiểm tra 15 ảnh / 19 mục đạt; hai connector trả 200, phiếu giao tải được Excel và PDF A4. Backup trước/sau đều toàn vẹn; so sánh nội dung 10 bảng nghiệp vụ không đổi (`data-preservation.json`).
- Bổ sung hồ sơ người mua độc lập với dự thảo; API danh sách trả toàn bộ hồ sơ; form giữ dữ liệu đang nhập khi tải nền. Đã lưu/đọc lại qua API và trình duyệt trên DB thử (`browser-profile-02`). Nhận đúng trường `inv_buyerAddressLine` của nguồn thật. Dự thảo nguồn không cộng tiền và có thông báo số lượng bị loại; hóa đơn hủy/thay thế/điều chỉnh hoặc bất nhất vẫn chặn đối chiếu.
- Tìm thêm lỗi PDF Linux: Calc in cả sheet ẩn còn vùng in, làm 7 sheet mẫu thành 12 trang và lộ sheet đối chiếu nội bộ. Đã xóa vùng in của sheet không chọn trong bản sao render, giữ sheet để công thức còn tham chiếu; ép tắt xuất toàn sheet. Bộ mẫu chạy bằng renderer sửa trên Railway ra đúng **7 sheet / 7 trang A4**, không lặp (`linux-print-03`). Đổi khóa cache PDF để không dùng lại bản in cũ. Mẫu Excel gốc không bị sửa.
- Hồi quy bổ sung: **73 module / 541 test đạt** (`acceptance-regression-02`); sau đó chạy lại riêng 14 test hồ sơ VAT, 4 test renderer và các test chứng từ chịu ảnh hưởng. Các kiểm thử này dùng DB/thư mục riêng. Đọc nguồn mSMI thật tháng 8 hai lượt trên DB sao chép đều đủ 266, không tạo trùng; đồng bộ đầu ra thật được thử trên bản sao, không ghi kho hoặc ký hóa đơn.
- Hướng dẫn đối chiếu đủ 14 mục và dữ liệu còn cần xác nhận: [NGHIEM-THU-RAILWAY.md](NGHIEM-THU-RAILWAY.md). Không tự đánh dấu khách đã nghiệm thu trong Google Sheet.
- **Cấu hình đầu ra chưa thể nghiệm thu nghiệp vụ:** kiểm tra hostname sau khi đọc nguồn cho thấy `MINVOICE_API_BASE_URL` đang là `0106026495-999.minvoice.site`, máy chủ kiểm thử M-Invoice. Dữ liệu thử chỉ vào DB sao chép riêng (đã dừng lượt quét); không chuyển vào production. Vì vậy thông báo kết nối 200 ở trên chỉ xác nhận đăng nhập được, không xác nhận tài khoản hóa đơn của Thành Đạt Phát. Đã thêm cảnh báo trạng thái, chặn tải vào DB nghiệp vụ và chặn gửi nháp nghiệp vụ tới máy chủ này. Cần URL/tài khoản chính thức của khách; đã hỏi chủ dự án cung cấp qua cấu hình Railway hoặc file riêng. Các test chặn môi trường thử và trạng thái UI/API đều đạt (`environment-guard-01`).

### 13.16. Giữ tài khoản hiện tại theo quyết định của chủ dự án — 06/09/2026

- Chủ dự án xác nhận **chỉ dùng tài khoản hiện tại**. Quyết định này thay yêu cầu đổi tài khoản ở mục 13.15: giữ URL và thông tin đăng nhập, thêm `MINVOICE_ALLOW_TEST_ENVIRONMENT=true` để cho phép đồng bộ và lưu nháp bằng tài khoản đã chọn. Không còn chặn chỉ vì hostname khi đã bật lựa chọn này; vẫn hiển thị đúng môi trường nhà cung cấp. Các kiểm tra trạng thái hóa đơn, ghép mã, kho, chống trùng và xác nhận lưu nháp được giữ nguyên.
- Đã kiểm tra 38 test cấu hình, M-Invoice và đồng bộ đầu ra (`selected-account-01`), gồm cả mặc định chặn, cho phép theo lựa chọn chủ dự án, đồng bộ không tự ghi kho và lưu nháp không tự ký/phát hành.
- Làm rõ bộ đếm: **266 hóa đơn = 264 chờ ghép mã + 2 không nhập tồn**; **1.107 dòng hàng, 1.104 dòng cần xử lý**. Không thiếu hai hóa đơn.
- Đã mở lại file `Đơn hàng  03.09.2026.xlsx`, sheet `đặt hàng`: dòng 157, `J000017`, `quả dưa hấu`, F157/O157 = −1, P157 = −117.000; dòng 158, `quả nhãn`, B158 trống, F158/O158 = −1, P158 = −90.000. Đây là dữ liệu đặt hàng Excel, không phải lỗi thiếu hóa đơn. Chưa tự diễn giải thành hàng trả hoặc sửa số lượng.

### 13.17. Đối chiếu mã hóa đơn đầu vào có bước xem trước — 06/09/2026

- Mục tiêu của lượt này là giảm **1.104 dòng hóa đơn đầu vào tháng 8 cần xử lý** mà không tự đoán mã, không bỏ bước xác nhận của người dùng và không ghi kho khi chỉ đang đối chiếu. Đã bổ sung hai luồng ngay tại màn `Hóa đơn đầu vào`: ghép theo tên hàng trùng chính xác với danh mục và đối chiếu mã từ bảng kê nhập của phần mềm cũ.
- Luồng ghép theo danh mục chỉ nhận tên hàng duy nhất và ĐVT trùng chính xác. Bản xem trước trên production tìm được **650 dòng tháng 8 / 86 quy tắc**, dự kiến làm **65 hóa đơn** sẵn sàng; cùng các quy tắc này có thể ảnh hưởng **7.054 dòng chưa ghi kho ở mọi kỳ**. Có 5 dòng trùng tên nhưng cần rà ĐVT và 449 dòng chưa có tên duy nhất. Chưa bấm xác nhận trên production.
- Luồng bảng kê cũ đọc file Excel mà không chạy macro. Một dòng chỉ được nhận khi đồng thời khớp MST bên bán, số hóa đơn, tên hàng chuẩn hóa, số lượng, thành tiền, mã hàng tồn tại và ĐVT của nguồn/file/danh mục trùng nhau. Trường hợp thiếu mã, không tìm thấy hóa đơn, không duy nhất hoặc lệch ĐVT được tách riêng để người dùng rà; không tự chọn mã gần giống.
- Chạy **xem trước** trên Railway bằng đúng file `nhập T8.2026 (1).xlsm` tìm được **876 dòng khớp trực tiếp / 99 quy tắc**. Các quy tắc này dự kiến ghép **892 dòng tháng 8**, làm **157 hóa đơn** sẵn sàng và ảnh hưởng **7.896 dòng chưa ghi kho ở mọi kỳ**. Phần bỏ qua gồm 20 dòng không tìm thấy hóa đơn, 158 dòng không xác định duy nhất, 47 dòng thiếu mã sản phẩm và 3 dòng cần rà ĐVT. Trước và sau lượt xem trước, production vẫn giữ **0 dòng đã ghép / 1.104 dòng cần xử lý**.
- Đã thử thao tác xác nhận trên **bản sao DB production**, không phải DB Railway đang vận hành. Xác nhận bảng kê cũ rồi ghép chính xác theo danh mục cho kết quả **941/1.104 dòng đã ghép**, **171/264 hóa đơn sẵn sàng**; còn **163 dòng thuộc 93 hóa đơn** cần xử lý thủ công. Sổ kho hóa đơn vẫn 0 vì chưa gọi ghi kho. Thử tiếp 65 hóa đơn sẵn sàng trên một bản sao riêng ghi đúng 201 bút toán; bấm lại không sinh bút toán trùng và kiểm tra toàn vẹn SQLite đạt.
- API xác nhận dùng mã snapshot của bản xem trước, mở lại file và tính lại dưới giao dịch khóa ghi trước khi lưu. Nếu dữ liệu nguồn thay đổi thì dừng. Mapping chỉ lan sang cùng NCC, tên nguồn và ĐVT trên hóa đơn chưa ghi kho. Backend đã chặn ghép mã cho nguồn không còn trạng thái `synced`; với đầu ra còn bắt buộc nguồn là hóa đơn đã phát hành hợp lệ.
- Đã tạo bảng chuẩn bị rà riêng cho 163 dòng còn lại tại `D:\TDP_RAILWAY_PRIVATE\evidence\mapping-review-remaining-01\Dong_con_lai_can_ghep_ma_T8_2026.xlsx`: 93 hóa đơn được gom thành 82 nhóm NCC + tên nguồn + ĐVT. Phân loại gồm 150 dòng chưa có tên trùng duy nhất trong danh mục, 8 dòng trùng nhiều mã và 5 dòng cần xác nhận quy đổi ĐVT. File có cột để người rà ghi mã/hệ số/ghi chú; đây là báo cáo từ DB sao chép, không phải lệnh nhập mapping vào production.
- Kiểm thử mục tiêu và các nhóm chịu ảnh hưởng đạt **87/87**. Lượt hồi quy rộng trước đó chạy 552 test, có 547 đạt và 5 lỗi chỉ do test giao diện khóa phiên bản cache JS cũ; đã cập nhật đúng kỳ vọng và chạy lại toàn bộ nhóm chịu ảnh hưởng đạt. Browser fixture của lượt hóa đơn đạt; kiểm tra cú pháp Python/JavaScript và `git diff --check` đều đạt.
- Source đã đẩy lên `xandrosworld/CDT`, nhánh `main`, commit `48a974a51b2aaf3d10f073ba7f92560605e35842`. Railway deployment `dc63c861-37a9-45e5-b66a-e2be2931e379` trạng thái `SUCCESS`; `/health` báo database/schema sẵn sàng và `integrity=ok`. Bằng chứng xem trước hosted: `D:\TDP_RAILWAY_PRIVATE\evidence\mapping-hosted-01\summary.json`; bằng chứng bản sao: `legacy-route-realdata-01`, `safe-mapping-realdata-02` trong cùng thư mục evidence.
- Hướng dẫn thao tác và cách đọc phần bỏ qua đã cập nhật tại [NGHIEM-THU-RAILWAY.md](NGHIEM-THU-RAILWAY.md). Bước vận hành tiếp theo là người dùng xem bảng kết quả và chủ động xác nhận hai lượt ghép mã; sau đó xử lý 163 dòng còn lại trước khi ghi kho. Lượt này không ký/phát hành hóa đơn, không ghi nhận thanh toán và không thay đổi dữ liệu nghiệp vụ production.

### 13.18. Khôi phục truy cập sau đổi domain Railway — 06/09/2026

- Chủ dự án đổi Public Networking sang `tdp.up.railway.app`; `/login` trả 403 với thông báo tên máy không nằm trong danh sách tin cậy. Biến `TDP_TRUSTED_HOSTS` vẫn chứa domain cũ. Đã cập nhật đúng hostname mới và triển khai lại, giữ cơ chế kiểm tra host và nguồn yêu cầu.
- Deployment cấu hình `6623feca-a03a-404a-abe2-82069db0017c` đạt `SUCCESS`, source vẫn `a5744caecfb0163cc21554a2a243fce733f61d86`. `/login` trả 200, `/health` xác nhận DB/schema sẵn sàng và `integrity=ok`.
- Chrome đăng nhập thành công ở domain mới, mở 12 màn, đăng xuất rồi kiểm tra API lại bị chặn đúng. Bộ kiểm tra hosted đạt 20 mục, 15 ảnh, không có JavaScript exception; phiếu giao xem trước và tải Excel/PDF đều trả 200, bố cục 1024/390px đạt. Hai API trạng thái mSMI/M-Invoice đều trả 200 trong lượt này; lỗi kết nối mSMI 502 ở lượt kiểm tra trước không tái hiện, chưa đủ căn cứ quy nguyên nhân lỗi đó cho việc đổi domain.
- Đầu vào tháng 8 vẫn 266 hóa đơn, tổng 919.234.874 đồng, 1.104 dòng cần xử lý và 0 đã ghi kho. Đầu ra hiện có 251 hóa đơn nguồn, gồm 232 cần kiểm tra, 18 cần ghép mã và 1 không nhập tồn; không dùng đăng nhập thành công để kết luận đã khớp kho hoặc nghiệm thu toàn bộ nghiệp vụ.
- Bằng chứng: `D:\TDP_RAILWAY_PRIVATE\evidence\domain-change-20260906\browser-result.json` cùng ảnh và phiếu giao tải về. Đã cập nhật link trong hướng dẫn nghiệm thu. Lượt sửa domain không nhập đơn, ghi mapping, ghi kho, thu/trả tiền hoặc ký/phát hành hóa đơn; đợt thử quy trình bằng ba file khách mới vẫn đang thực hiện trên DB sao chép.

### 13.19. Nhập đơn liên tục và bảng Excel toàn màn hình — 06/09/2026

- Chủ dự án chốt: file gửi sau là bản hoàn thiện hơn của cùng ngày/phạm vi. Bản đầu còn thiếu được nhận thành nháp và hiện lỗi; bản sau hợp lệ tự cập nhật, không tạo thêm đơn hoặc tự duyệt/chốt giao. File sai hoặc vướng liên kết chứng từ vẫn bị chặn, giữ bản đang dùng. Ngày/sheet khác không bị thay; file giống hệt không tạo giao dịch lặp.
- Workbook khách có chế độ nhập liên tục, không khóa ngày ngay sau lần nạp thứ hai. Đã thử bản đầu thiếu rồi ba lần sửa: cùng phiên đơn, lượng 4 → 7 → 9, trạng thái nháp; NCC và ghi chú sửa trên web được thay theo file mới. Lưu đầy đủ dòng trước khi thay, tên file và trạng thái mua trước đó để đối chiếu. Giữ phạm vi mua riêng của sheet đặt hàng và các khóa chứng từ.
- Nhúng Univer 0.25.1 trong ứng dụng. Nút Sửa nhanh cả bảng/Mở bảng Excel mở hết vùng trình duyệt, có X quay lại. Cho chọn ô, Enter/Tab, dán nhiều ô, kéo cột, tìm, nhảy đến lỗi; cố định tiêu đề và hai cột nhận diện. Ô tính tiền/lỗi chỉ xem. Sửa giá bán vẫn cần người sửa/lý do và lịch sử giá.
- Tự lưu theo lần sửa, nhiều ô lưu nguyên tử; kiểm tra phiên từng dòng và mã chống gửi lặp. Mất mạng giữ phần đang nhập. Sửa tiếp trong lúc phản hồi chậm được giữ lại. Đọc thay đổi của người khác mỗi 5 giây khi bảng rảnh; xung đột cùng dòng thì dừng lưu. Nút Đọc lại/đối chiếu cho tải phần chưa lưu trước khi chủ động bỏ bản đang sửa. X không âm thầm làm mất phần chưa lưu.
- Bảng nhập–xuất–tồn dùng đầy đủ danh sách API định giá với ô số/tiền. Các bảng HTML khác có bản chỉ xem toàn màn hình của **phần đang hiển thị**, gồm giới hạn phân trang đang chọn. Đây chưa phải trình sửa mọi loại chứng từ; ghép mã, ghi kho, thanh toán, duyệt/chốt vẫn dùng thao tác chuyên biệt. Bản xem này không thay mẫu in/Excel/PDF.
- Hồi quy rộng: 76 module, 573 lượt test, 568 đạt và 5 thất bại chỉ vì khóa phiên bản cache JS cũ. Đổi đúng kỳ vọng và chạy lại 5 nhóm: 34/34 đạt. Sau hoàn thiện ưu tiên dữ liệu file/trạng thái giá, chạy lại 14 test nhập workbook đạt. Nhóm cuối về sửa bảng/kho thực tế/giá đạt 39 lượt test. Không cộng lượt chạy lặp thành số bài độc lập.
- Browser trên DB riêng 65 dòng: sửa ô, dán hai dòng, phản hồi chậm, mất mạng/X/thử lại, người khác sửa và đồng bộ, xung đột giữ dữ liệu server, đọc lại để đối chiếu, khổ 1440/1024/390 đều đạt, không có JavaScript exception. Bằng chứng `D:\TDP_RAILWAY_PRIVATE\evidence\worksheet-11\result.json` và ảnh; tái chạy bằng `qa_worksheet.py`. Lượt 04–08 phát hiện hộp thoại bảo vệ ô khi cập nhật ô tính toán; đã sửa phản hồi server và chạy lại đạt, giữ bảo vệ ô người dùng.
- Bản sao trước triển khai: `D:\TDP_RAILWAY_PRIVATE\evidence\worksheet-before-deploy\snapshot.sqlite3`, toàn vẹn đạt. Các thao tác chủ động sửa/nạp đơn kiểm thử dùng DB riêng. Lượt xem hosted phát sinh lỗi lưu ngoài ý định nêu bên dưới; không ghi mapping/kho/thanh toán hoặc phát hành hóa đơn trên production.
- Bản chức năng `094eaaf` đã chạy tại deployment `d66b1e7b-09ff-4d1e-9107-f2e511845b1a`, trạng thái SUCCESS. Browser hosted đạt 22 mục/17 ảnh về mở màn/tải phiếu. Bản sao `worksheet-after-deploy` được tải khi browser còn chạy nên kết quả 8 bảng không đổi lúc đó **chưa chứng minh bảo toàn dữ liệu sau toàn lượt**; kết luận này đã được thay bằng kiểm tra và khắc phục phía dưới.
- Hoàn thiện tiếp cảnh báo giá: kiểm tra theo giá thực lưu để dòng còn giá bán 0 không bị mất lỗi chỉ vì bảng giá tham chiếu đã có giá. Nhóm sửa bảng/giá 20 lượt test đạt; browser `worksheet-12` đạt cả các tình huống cũ, thêm số dòng lỗi/cảnh báo ngay trên thanh bảng. Đây là kiểm tra kỹ thuật, chưa thay xác nhận nghiệm thu của khách.
- Kiểm tra file thật 01/09 trên bản sao production tìm thêm trường hợp chỉ ghi chú khác thì phép so sánh cũ bỏ qua. Đã bổ sung so toàn bộ giá trị nhập trong chế độ liên tục; 15 test workbook đạt. Chạy lại `worksheet-real-copy-02`: nạp 30 dòng, sửa ghi chú qua API bảng rồi nạp bản sao file có metadata mới nhưng giữ nguyên ô nghiệp vụ; ghi chú trở lại đúng file, cùng phiên đơn, có lịch sử. 233 dòng đơn cũ nguyên vẹn, sổ kho hóa đơn vẫn 0, toàn vẹn DB đạt. File khách gốc không bị sửa; đây là mô phỏng hai lần nạp bằng một file nguồn, không phải hai bản sáng/tối thực tế khách đã gửi.
- **Lỗi phát hiện khi đối chiếu hosted:** `getValues()` của SDK trả số đã định dạng (`130,000`), bị so nhầm với giá trị gốc (`130000`). Đóng bảng dù không sửa đã gửi hai lượt lưu, mỗi lượt 224 dòng. Tác động: cập nhật giờ/lỗi/cảnh báo của các dòng, thay giá mua của một dòng và tạo một phiên sổ phải trả; lượng, số tiền phải trả, khoản thanh toán, hóa đơn và kho không thay. Đây là lỗi phía phần mềm và kiểm tra, không phải thao tác nhập sai của khách.
- Đã đổi sang `getRawValues()`, thêm chặn backend nếu giá trị gửi không thay đổi. Browser riêng `worksheet-13` kiểm tra mở/đóng không có yêu cầu lưu và dữ liệu giữ nguyên, rồi chạy lại các tình huống sửa/dán/mất mạng/xung đột đạt. Nhóm backend 21 lượt test đạt. Bộ hosted bổ sung chặn mọi PUT/PATCH/DELETE ngoài ý định trước khi gửi và khẳng định không phát sinh yêu cầu sửa.
- **Khắc phục dữ liệu:** sau khi bản sửa `bea78ae` chạy SUCCESS tại deployment `db95897a-d8a2-4bba-869a-a842cd4f4739`, đã sao lưu riêng và kiểm tra từng phiên dòng cùng hai mã lần lưu trước khi phục hồi 224 dòng về đúng bản trước QA. Phục hồi giá trị sổ phải trả dòng 64 bằng phiên lịch sử thứ ba; giữ phiên sai thứ hai và thêm audit `qa.worksheet.restore`, không xóa dấu vết. Không thay thế toàn bộ DB hoặc ghi đè thay đổi ngoài phạm vi đã đối chiếu. Script/bằng chứng riêng: `worksheet-restore-script.py`, `worksheet-restore-result.log` dưới evidence.
- **Kết quả sau khắc phục:** `worksheet-hosted-04` đạt 23 mục/17 ảnh, gồm mở/đóng không gửi yêu cầu sửa, không có JavaScript exception, phiếu giao Excel/PDF, đăng xuất và bố cục 1024/390. Snapshot `worksheet-restored` toàn vẹn; 233 dòng đơn khớp đầy đủ bản trước, tám bảng kiểm tra khớp, giá trị nghiệp vụ sổ phải trả khớp; chỉ giữ thêm lịch sử QA/khắc phục. Đối chiếu mở rộng tại `worksheet-restored/full-preservation.json`. Không dùng kết quả này thay nghiệm thu toàn bộ nghiệp vụ thuế.

### 13.20. Rà từng màn và chức năng trên máy tính — 06/09/2026

- Theo ảnh chủ dự án gửi, sửa dòng tổng NXT cố định bị quá cao: giữ footer một hàng, tiền không xuống dòng, lượng nhiều ĐVT hiện nút mở bảng tổng riêng theo ĐVT. Đặt nút `Xem bằng Excel · toàn màn hình` ngay cạnh tiêu đề chi tiết NXT, dùng cùng dữ liệu báo cáo trong phạm vi ngày. Kiểm tra browser riêng với 240 mã/24 ĐVT/tổng tiền 2,4 tỷ tại 1680/1366/1024px: cuộn giữa/cuối và ngang, footer 52px, đối chiếu tổng từng ĐVT và mở Excel đều đạt (`inventory-footer-browser-02`). Nhóm kho/xuất file và hợp đồng UI chịu ảnh hưởng **45/45 đạt** (`inventory-footer-tests-01`). Lượt browser trước dừng ở selector của công cụ kiểm tra Excel, đã sửa đúng selector và chạy lại cả lượt đạt.
- Chủ dự án yêu cầu kiểm tra kỹ toàn bộ màn/chức năng; chỉ tập trung máy tính. Phạm vi, ma trận từng màn và giới hạn: [KIEM-TRA-MAY-TINH-20260906.md](KIEM-TRA-MAY-TINH-20260906.md).
- Phát hiện bằng browser trên DB thử: nhập `0,855` ở ô số lượng của bảng Excel bị thư viện đọc thành `855`. Đã giữ nguyên chuỗi nhập trước bước đọc thập phân; tiền vẫn giữ định dạng đã chốt. Browser sau sửa kiểm chứng gõ dấu phẩy/dấu chấm và dán nhiều dòng lượng lẻ, cùng mất mạng/thử lại/xung đột hai người/mở đóng không tự ghi; không sửa số lượng production theo phỏng đoán.
- Sửa bản hosted để không hiện các nút gửi máy in Windows trên máy chủ. Người dùng in từ PDF và hộp thoại trình duyệt của máy tính; lịch sử in vẫn tra cứu được. Hướng dẫn sao lưu nêu đúng dữ liệu trực tuyến và lịch vẫn chạy khi đóng trình duyệt.
- Bộ hồi quy trước các sửa mới đạt **576/576**. Sau sửa, **135/135** bài nhóm chịu ảnh hưởng đạt; không cộng thành số bài độc lập. Năm lượt browser nghiệp vụ đạt sau cập nhật bài lượt 2 theo bảng Excel mới. Browser báo giá, sửa giá/lịch sử và phân bổ thiếu hàng cũng đạt; các lần dừng do kỳ vọng giao diện cũ được giữ trong báo cáo.
- Source sản phẩm cuối `7afd5b9efd9cef69fa769d5f9452a63896d370c1` đã deploy **SUCCESS**, deployment `12a4a94e-9efa-4333-be61-0621907c9b83`. Browser Railway cuối `inventory-footer-hosted-02` đạt **30 mục/48 ảnh**, gồm 12 màn máy tính, tổng NXT cố định, bảng tổng 21 ĐVT, Excel NXT toàn màn hình và phiếu giao Excel/PDF. Không có JavaScript exception, HTTP 5xx hoặc request ghi ngoài phạm vi. Đã sửa thêm độ tương phản tiêu đề bảng ĐVT sau khi xem ảnh hosted; browser riêng `inventory-footer-browser-03` và hosted cuối đều qua kiểm tra mới này.
- Bằng chứng dưới `D:\TDP_RAILWAY_PRIVATE\evidence\full-audit-*` và `inventory-footer-*`. Kiểm tra ghi nghiệp vụ dùng DB riêng; trên Railway chặn request ghi ngoài phạm vi xem trước ngay tại giao thức trình duyệt. Snapshot `full-audit-hosted-after` được lấy **sau khi browser cuối kết thúc**; đối chiếu với `full-audit-hosted-before` cho **80/80 bảng nguyên nội dung và schema**, hai DB toàn vẹn `ok` (`full-preservation.json`). Lượt này không làm thay đổi dữ liệu nghiệp vụ production; không dùng kết quả kiểm tra giao diện để tuyên bố khớp toàn bộ kho/thuế hoặc mọi tình huống tương lai đều không lỗi.

### 13.21. Đối chiếu số liệu và tô đỏ toàn dòng trong Excel — 06/09/2026

- Theo yêu cầu chủ dự án: kiểm tra số liệu mọi màn và file, chỉ tập trung máy tính; không kết luận đúng toàn bộ chỉ từ thao tác mở màn. Ma trận nguồn, phép đối chiếu và phần bị chặn: [DOI-CHIEU-SO-LIEU-20260906.md](DOI-CHIEU-SO-LIEU-20260906.md).
- Bảng Excel đơn tô đỏ toàn dòng có lỗi **hoặc cảnh báo**, cả cột chỉ xem. Phản hồi lưu/đồng bộ xác nhận đã hết vấn đề mới bỏ đỏ. Thử bằng browser màu pixel của cả dòng lỗi và dòng chỉ cảnh báo; sửa lượng hợp lệ hết đỏ, mở/đóng không tự ghi và các tình huống mạng/xung đột đều đạt (`numeric-red-worksheet-03`). NXT và viewer HTML giữ dấu hiệu cảnh báo khi mở Excel.
- Thẻ tổng lượng NXT thu gọn thành nút xem theo ĐVT. Giữ footer cố định gọn. Phát hiện bốn file kho còn tổng cộng lẫn ĐVT và NXT luôn ghi `KHỚP`; đã tách sheet `Tổng ĐVT`, giữ trạng thái `CẦN KIỂM TRA` khi có mã lỗi. Tiền/đơn giá định dạng nguyên đồng, giữ lượng lẻ và tiền nghiệp vụ gốc.
- Bộ đối chiếu trên snapshot production riêng `numeric-real-copy-06` đạt **17 nhóm**, nguồn snapshot không đổi. Đối chiếu 233 dòng đơn/NCC/phiếu giao; 266 đầu vào/1.107 dòng và 251 đầu ra/1.163 dòng tháng 8; 334 mã NXT ở hai kỳ cùng bốn file kho; báo cáo tháng, phải thu/phải trả chi tiết và công nợ tổng; báo giá và các sheet chứng từ đủ điều kiện. Không tự ghi mapping, kho, thu/trả hoặc phát hành hóa đơn trên production.
- Tổng đầu vào tháng 8 **919.234.874 đồng**; tập đầu ra đang lưu **174.950.392 đồng**. NXT giá trị gốc **2.419.360.717,75 đồng**, hiển thị nguyên đồng **2.419.360.718 đồng**. Tổng lịch sử phải trả đầu kỳ **2.327.247.387 đồng** vẫn tồn tại; bộ lọc phát sinh kỳ này 0 dòng không có nghĩa đã hết nợ cũ.
- Dữ liệu còn mở: **45 dòng đơn lỗi/15 cảnh báo; 1.104 dòng đầu vào cần xử lý; 232 hóa đơn đầu ra cần kiểm tra/18 cần ghép; 4 mã tồn đầu âm; 1.253 mã kho thực tế chưa khai tồn**. Bảy báo giá tháng chưa có phiên bản xác nhận; bảng kê mua thiếu giá/hồ sơ người bán; hồ sơ VAT chưa có phạm vi hóa đơn hợp lệ. Không tự bổ sung số liệu để vượt chặn và không ghi nghiệm thu các phần này.
- Hồi quy `numeric-regression-01`: **576/576 đạt** trước sửa mới file kho. Sau sửa file kho: xuất kho **6/6**, định giá **6/6**, chốt kỳ **8/8**, chứng từ **22/22** đạt; browser nghiệp vụ hóa đơn/kho `numeric-inventory-browser-01` đạt. Các lần thử bộ đối chiếu trước lượt 06 lưu riêng chẩn đoán/kỳ vọng của công cụ; không xóa kết quả chưa đạt.
- Source sản phẩm `7603431f9122073d3f12f1db238a54af02f23a36` đã chạy trên Railway tại deployment `f654a792-05ee-44aa-8339-11641c2f11e3`, **SUCCESS**. `numeric-hosted-01` đạt **31 mục/48 ảnh**, gồm 12 màn máy tính, màu đỏ cả dòng Excel trên dữ liệu thật, thẻ lượng NXT gọn, footer cố định và phiếu giao Excel/PDF; không lỗi JavaScript, HTTP 5xx hay yêu cầu ghi ngoài phạm vi.
- Bản xem và Excel tải theo lựa chọn trên DB sao chép khớp nội dung/ô gộp của **22 sheet chứng từ**. Tải bốn file kho trực tiếp từ Railway, so **11.070 ô trên 8 sheet hiển thị** với bản sao đã đối chiếu: giá trị và định dạng số khớp (`numeric-hosted-exports-01`). Phiếu giao PDF hosted một trang A4 có **3 dòng lượng khớp Excel** và tổng tách theo ĐVT; đã xem ảnh. Phiếu này ẩn giá, không dùng nó để kết luận mọi số tiền PDF đã kiểm tra (`numeric-hosted-01/pdf-quantity-reconciliation.json`).
- Snapshot `numeric-audit-after` lấy sau khi kết thúc browser và tải file: so `numeric-audit-before`, **80/80 bảng giữ nguyên nội dung và schema**, hai DB toàn vẹn `ok`; bằng chứng `numeric-audit-after/full-preservation.json`. Giữ nguyên dữ liệu và các chặn nghiệp vụ còn mở. Bổ sung hướng dẫn dòng đỏ/ĐVT và sửa ghi chú sao lưu trên thanh menu thành `Sao lưu tự động theo lịch`, tránh hiểu phải giữ trình duyệt mở.
- Rà cuối bộ xuất: sheet `Tổng ĐVT` dùng chung cách ghi text an toàn của file kho; tên đơn vị không trở thành công thức Excel. Nhóm xuất kho chạy lại **7/7 đạt** (`numeric-inventory-export-03`), thêm tình huống chuỗi bắt đầu bằng `=`. Không thay lượng/tiền; các báo cáo hosted phía trên giữ nguyên phạm vi tại commit đã ghi.

### 13.22. Hàng hỏng ngày 03/09 và quy tắc chỉ tô đỏ lỗi — 06/09/2026

- Chủ dự án giải thích hai dòng đặt hàng 157–158 là **hàng bị hỏng, chị đi mua cho khách**. Không còn ghi lý do là chưa biết hàng trả hay nhập nhầm. Chưa đủ thông tin để xác định khoản âm trừ tiền NCC Phong hay theo dõi tiền mua bù riêng; đã hỏi rõ ảnh hưởng công nợ. Dòng 158 vẫn thiếu mã hàng. Chưa đổi dấu, bỏ kiểm tra số âm/mã thiếu hoặc nhập hai dòng vào dữ liệu vận hành.
- Quyết định màu mới thay quy tắc ở 13.21: **chỉ dòng có lỗi mới đỏ cả dòng**, áp dụng chung mọi file. Dòng chỉ có cảnh báo giữ nội dung cảnh báo riêng; hết lỗi sau lưu/đồng bộ thì hết đỏ. Nút `Tới dòng lỗi` chỉ đến dòng lỗi.
- Đã sửa bảng Excel và đường mở các bảng HTML sang Excel: lấy dấu hiệu lỗi kiểm tra dữ liệu, không suy lỗi từ màu nhãn trạng thái. Các bản xem trước ghép mã, danh mục, tồn đầu, bảng kê và công nợ được đánh dấu lỗi/cảnh báo riêng; bảng đơn/đặt hàng giữ cách phân loại này. Cảnh báo đối chiếu NXT vẫn hiện chữ `Cần kiểm tra`, không tự coi là đã khớp.
- Kiểm thử nhóm chịu ảnh hưởng: **69/69 lượt test đạt** (`error-only-tests-01`). Các bằng chứng mới nằm dưới `D:\TDP_RAILWAY_PRIVATE\evidence\error-only-*`; trạng thái browser và triển khai được ghi sau khi có kết quả.
- Browser DB riêng `error-only-worksheet-03` đạt: đo màu dòng lỗi/cảnh báo khi mở và sau lưu; viewer chung phân biệt lỗi với nhãn trạng thái đã hoàn tác; nhập/dán lượng lẻ, lưu chậm, mất mạng/thử lại, đồng bộ/xung đột, mở/đóng không tự ghi. Không có JavaScript exception. Hai lượt trước dừng ở công cụ kiểm tra (bảng QA bị lần tải nền thay thế; vùng đo pixel lấn sang dòng bên cạnh), đã sửa và chạy lại toàn bộ. Snapshot production trước triển khai `error-only-before` toàn vẹn `ok`.
- Source `2ba0df8e5d1d7ecd6df0dfe425e89a8776a41bb2` đã chạy Railway **SUCCESS**, deployment `30582043-04b1-4cb0-bace-9a426ec37e2d`. Browser hosted `error-only-hosted-01` đạt **31 mục/48 ảnh**, có mở bảng đơn và tải phiếu giao Excel/PDF; không JavaScript exception, HTTP 5xx hoặc yêu cầu ghi ngoài phạm vi. Snapshot `error-only-after` lấy sau khi browser kết thúc: **80/80 bảng giữ nguyên nội dung/schema**, hai DB toàn vẹn `ok` (`full-preservation.json`). Phần hàng hỏng vẫn chờ chốt ảnh hưởng công nợ, chưa được tự chuyển thành nghiệp vụ ghi giảm hay khoản mua bù.

### 13.23. Tự ghép phần chắc chắn, đưa phần cần thao tác lên đầu — 06/09/2026

- Chỉ đạo mới của chủ dự án thay yêu cầu xác nhận mọi mã ở 3.3/13.17: phần có đủ căn cứ được tự xử lý; chỉ phần thật sự cần chọn mã, quy đổi hoặc xác nhận nghiệp vụ mới ưu tiên trên đầu bảng. Giữ quy tắc chỉ lỗi mới đỏ; thứ tự ưu tiên không phải dấu hiệu lỗi.
- Hóa đơn đầu vào tự ghép tên duy nhất và cùng ĐVT sau khi tải. Bảng kê cũ có một thao tác **Tự ghép từ file cũ**: đối chiếu file rồi xử lý tiếp theo danh mục trong cùng giao dịch, bỏ bước xem trước → xác nhận lần nữa. GET/mở màn/đổi bộ lọc vẫn chỉ đọc; không phát sinh ghi ngoài ý định khi chỉ xem.
- Tự động giữ nguyên mã và quy đổi đã chọn, kể cả quy tắc có kỳ hiệu lực hoặc dòng lịch sử không còn quy tắc đi kèm. Không chọn tên gần giống, không đoán hệ số, không sửa nguồn lỗi/đã ghi kho. Khóa giao dịch trước khi tính và ghi; lỗi audit hoàn tác cả lượt, chạy lại không thêm lịch sử nếu không có gì mới.
- Bảng hóa đơn và Excel cùng thứ tự: dòng có lỗi/thiếu mã/cần quy đổi → hóa đơn đủ mã chờ xác nhận ghi kho → dòng đã xử lý xong/không nhập tồn. Phần ghép xong cập nhật bộ đếm và chuyển xuống sau khi lưu. Đủ mã không tự coi là đã nhập kho; phát hành hóa đơn, thu/trả tiền và sửa tồn đầu vẫn cần dữ liệu nghiệp vụ tương ứng.
- Bản sao production mới `auto-mapping-copy-02`: tự ghép **941/1.104 dòng tháng 8**, **171 hóa đơn sẵn sàng**, còn **163 dòng/93 hóa đơn**; 111 quy tắc gồm 99 từ bảng kê cũ và 12 từ danh mục, áp dụng **9.193 dòng** cùng nguồn ở mọi kỳ chưa ghi kho. Chạy lại cùng file không ghi thêm; lượng/tiền nguồn và dữ liệu được bảo vệ của 76 bảng giữ nguyên, DB nguồn không đổi, SQLite toàn vẹn. Lượt copy-01 dừng do công cụ hash sắp theo địa chỉ đối tượng SQLite Row; sửa công cụ so tuple dữ liệu rồi chạy lại, không sửa sản phẩm để vượt kiểm tra.
- Kiểm thử mục tiêu/hồi quy chịu ảnh hưởng **104/104 đạt**, gồm 6 bài mới tự ghép không cần xác nhận, tải đầu vào tự ghép, giữ lựa chọn cũ, rollback khi audit lỗi, gửi lại không thay dữ liệu và thứ tự API/Excel. Lượt đầu bài tải dùng ngày giả 44/08 bị chặn đúng; sửa fixture ngày hợp lệ và chạy lại. Browser `auto-mapping-browser-01` đạt toàn luồng hóa đơn/kho cũ, thêm bấm tự ghép không mở confirm, ghép xong chuyển nhóm, chạy lại và đối chiếu thứ tự DOM/API; không JavaScript exception.
- Source **`d3d511fa04efec7f36f7b9a3bd1472e4675e7f2f`** đã deploy Railway **SUCCESS**, deployment **`daf9db5f-aa49-4a40-8f7d-7c16f0bd77ee`**. Sau sao lưu riêng ngay trước thao tác, **đã áp dụng 941 dòng trên production**, không chờ khách bấm xác nhận lại. Từng mapping khớp bản sao đã kiểm chứng; dữ liệu được bảo vệ của 76 bảng không đổi, tổng vẫn **266 hóa đơn / 919.234.874 đồng**. Sổ kho hóa đơn vẫn 0; chưa ký/phát hành hoặc ghi nhận thanh toán. Bằng chứng `auto-mapping-production-01/summary.json`, `before.sqlite3`, `after.sqlite3` dưới `D:\TDP_RAILWAY_PRIVATE\evidence`.
- Đã tự dò bốn mã tồn âm về file **`TĐK T8-2026.xlsx thụy.xlsx`**, sheet **`Ton 7 (2)`**: dòng 58 `D000056` lượng −1,5; dòng 166 `I000084` lượng −14,1; dòng 168 `I000091` lượng −1,5; dòng 321 `N000009` lượng −3. Giá trị âm có ngay trong nguồn, khớp bút toán tồn đầu đã lưu; không có căn cứ để đổi dấu/đưa về 0. Phần hàng hỏng 03/09 vẫn thiếu căn cứ xác định khoản trừ NCC hay mua bù; không tự chuyển thành nghiệp vụ tiền.
- Kiểm tra hosted cuối `auto-mapping-hosted-02` đạt **32 mục/49 ảnh**, gồm đối chiếu thứ tự từng dòng màn hình với API sau tự ghép, không còn nút xác nhận mã gợi ý, mở bảng đơn không tự ghi, phiếu giao Excel/PDF và đăng xuất; không JavaScript exception, HTTP 5xx hoặc request ghi ngoài phạm vi. Lượt hosted-01 dừng do công cụ đổi nhiều bộ lọc trong lúc DOM tải lại; sửa công cụ dùng bộ lọc đã đặt sẵn và chạy lại. Snapshot `auto-mapping-final` lấy sau khi kết thúc browser: so với snapshot ngay sau tự ghép, **80/80 bảng nguyên nội dung/schema**, SQLite toàn vẹn. Đây là kiểm tra bảo toàn sau tự ghép, không tuyên bố 80 bảng không đổi so với trước khi áp dụng mapping.

### 13.24. Trừ tiền mua hộ vào công nợ Phong — 06/09/2026

- Chủ dự án yêu cầu xử lý phần Phong, deploy rồi kiểm tra lại trong lúc chờ khách chốt bốn mã tồn đầu âm. Cách tính đã chốt: hai khoản mua hộ do hàng hỏng ngày 03/09 **117.000 + 90.000 = 207.000 đồng trừ phải trả Phong**, giữ doanh thu, lượng và giá bán. Quyết định này thay phần chờ xác định công nợ ở 13.22–13.23.
- Bổ sung loại dòng **Trừ tiền mua hộ do hàng hỏng** vào sheet đặt hàng và lịch sử. Hai dòng nguồn 157–158 được nhận theo đúng ngày, Phong, bếp, tên, mã/ĐVT và số tiền đã đối chiếu; không dùng riêng số dòng Excel để suy nghiệp vụ. Sau nhập, khoản tiền có lượng/giá mua/điều chỉnh lượng bằng 0, không liên kết dòng xuất hàng. Dòng nhãn thiếu mã không tự sinh mã tồn. Dòng âm khác hoặc khác căn cứ vẫn bị chặn.
- Sổ phải trả giữ khoản trừ riêng, chỉ có hiệu lực khi đơn được duyệt; hiển thị cùng lý do ở màn NCC, công nợ và Excel phải trả 14 cột. Không tạo khoản thanh toán. File NCC tải ra giữ thành tiền trực tiếp và cột Loại dòng để nạp lại; khoản tiền không bị tính lại thành lượng × giá bằng 0. Sửa có phiên lịch sử, gửi lại không thêm khoản trừ; lỗi audit hoàn tác cả lượt.
- Kiểm chứng đúng file khách trên snapshot Railway riêng `phong-real-copy-02`: **352 dòng bán / 273 dòng mua**, hai khoản trừ tổng **207.000đ**. Phong có tiền hàng **997.040đ**, còn phải trả **790.040đ**; sổ và Excel 14 cột khớp. Dòng gạo nếp 103 vẫn là kho, 0,54 kg, 14.040đ. Nạp lại không thêm phiên phải trả. Giữ nguyên 233 dòng đơn cũ; phần mua không đổi đơn bán, sổ phải thu, sổ kho hóa đơn, tồn đầu và nhập/điều chỉnh kho thực tế. DB nguồn và file khách gốc không đổi, SQLite toàn vẹn.
- Browser trên chính bản sao đó đạt: hai khoản trừ, tổng, số tiền công nợ, chặn chọn khoản trừ làm dòng trả tiền, màn máy tính 1440/1024px; không JavaScript exception hoặc request ghi khi chỉ xem. Ảnh `phong-purchases.png`, `phong-payable.png` và `browser-result.json` trong cùng thư mục. Tái chạy bằng `qa_phong_copy.py` rồi `qa_phong_browser.py`, luôn chỉ định snapshot/thư mục thử riêng.
- Kiểm thử mới gồm xử lý đúng căn cứ, số âm khác vẫn chặn, khoản tiền rõ loại phải có lượng 0/tiền âm, nạp lại, xuất/nạp lại, tổng Excel phải trả, trạng thái nháp và rollback. Lượt công cụ ban đầu gọi nhầm cột `supplier` thay vì `supplier_code`, rồi tham chiếu helper sai module; đã sửa công cụ. Lượt copy-01 chọn sheet mua qua chế độ nhập liên tục chỉ dành cho bán nên bị chặn đúng; copy-02 dùng luồng nhập NCC riêng, không bỏ chặn của sản phẩm.
- Source **`6443acc82a2b3bef7935244f4ae7ea9338f38d9e`** đã deploy từ `xandrosworld/CDT/main` thành công, deployment **`2dc8ff20-c375-421e-ab41-9b1d19e126c4`**. `/health` xác nhận database/schema sẵn sàng, toàn vẹn `ok`, không cảnh báo nguồn công nợ trùng. Browser `phong-hosted-01` đạt **32 mục/49 ảnh**, gồm các màn máy tính, đầu vào sau tự ghép, Excel toàn màn hình, phiếu giao Excel/PDF và đăng xuất; không JavaScript exception, HTTP 5xx hoặc request ghi ngoài ý định.
- Snapshot `phong-after` lấy sau khi browser kết thúc: so với `phong-before`, **80/80 bảng giữ nguyên mọi cột và giá trị đã có**; hai bảng dòng mua/lịch sử chỉ thêm `line_kind` mặc định hàng hóa. Hai DB toàn vẹn `ok`; bằng chứng `phong-after/full-preservation.json`. Không diễn đạt schema giữ nguyên vì đã thêm hai cột có chủ đích.
- Chưa tự nạp hoặc duyệt đơn 03/09 trên production; số 790.040đ ở trên là kết quả trên bản sao. Bốn mã tồn đầu âm và các dòng hóa đơn chưa đủ căn cứ giữ nguyên. Hướng dẫn thao tác đã cập nhật tại NGHIEM-THU-RAILWAY.md.
- Hồi quy trước triển khai `phong-regression-01`: **78 module / 589 test đạt, 0 lỗi/0 thất bại/không bỏ qua bài nào**. Browser bản sao kiểm tra thêm tổng phát sinh tài khoản Phong ở `/api/debts` khớp 790.040đ; kiểm tra cú pháp JS và `git diff --check` đạt.

### 13.25. Mở lại Đoàn Văn Giang theo hồ sơ khách xác nhận — 06/09/2026

- Khách xác nhận ảnh hồ sơ **Đoàn Văn Giang** là đúng trong hai người từng bị loại; chủ dự án yêu cầu xử lý. Quyết định này thay việc loại cả Giang và Toại ở 6.1/10.2. **Nguyễn Văn Toại vẫn bị loại** khỏi lựa chọn và bảng kê/biên nhận mới.
- Đối chiếu ảnh với danh mục nguồn và snapshot Railway mới `giang-before`: số giấy tờ 9 chữ số có số 0 đầu, ngày cấp 28/05/2018 và nơi cấp Cục cảnh sát khớp. Địa chỉ đã có trong đúng hồ sơ Giang là **Xã Khởi Nghĩa - Huyện Tiên Lãng - Hải Phòng**; ảnh không cung cấp địa chỉ mới. Không thêm số để biến thành CCCD 12 chữ số. Số giấy tờ đầy đủ và chứng từ thử được giữ ngoài Git.
- Bỏ Giang khỏi danh sách loại theo tên. Khi kiểm tra trùng số giấy tờ để lập biên nhận mới, chỉ xét người bán được phép sử dụng; hồ sơ Toại vẫn được giữ để tra cứu, không làm chặn Giang đã được khách xác nhận. Hai người được phép sử dụng mà trùng số vẫn bị chặn; Toại không thể vượt chặn bằng cách đổi số giấy tờ.
- Không cần sửa hồ sơ hoặc dữ liệu nghiệp vụ Railway vì hồ sơ Giang hiện tại đã khớp. Không đổi danh mục nguồn, đơn hàng, kho, công nợ hoặc lịch sử. Màn chọn người bán nêu rõ Giang được mở lại, Toại còn bị loại; nạp lại danh mục không đưa Toại trở lại lựa chọn.
- **105 lượt test đạt** trong 10 nhóm chịu ảnh hưởng (`giang-tests-01`, `giang-tests-02`): gồm 9 bài danh mục/định danh, 29 bài hoàn thiện và 67 bài chứng từ/giao diện liên quan. Bộ 52 hồ sơ nguồn xuất đúng 51 người, chặn Toại; kiểm tra các ô D9–D12 của từng biên nhận, giữ hồ sơ/đơn lịch sử và chặn trùng giữa người bán còn được phép sử dụng.
- `giang-real-copy-01` dùng kết nối chỉ đọc tới snapshot Railway mới, hồ sơ thật và dòng hàng kiểm thử trong bộ nhớ: xuất riêng Giang, bộ có Giang–Toại chỉ xuất Giang, bộ chỉ Toại bị chặn. Excel giữ số giấy tờ dạng text có số 0 đầu và bốn ô hồ sơ khớp nguồn; snapshot không đổi. Các chứng từ này là mẫu kiểm thử, không dùng thanh toán.
- Browser `giang-browser-03` đạt luồng chọn/xem bảng kê, mở đúng biên nhận Giang và cảnh báo loại Toại, menu/sao lưu và khổ 1440/1024px; không JavaScript exception. Đã xem ảnh `round5/giang-receipts-browser.png`: tên, địa chỉ, số giấy tờ, ngày/nơi cấp đúng hồ sơ. Lượt 01–02 cũng đạt phạm vi trước khi bổ sung ảnh biên nhận riêng. Bằng chứng nằm dưới `D:\TDP_RAILWAY_PRIVATE\evidence\giang-*`.
- Source **`868e2c1b12c44d07230ba9e2ed29754b2f47ac97`** đã deploy từ `xandrosworld/CDT/main` tại deployment **`4f4c5ad0-52ba-4c24-b550-570619700c32`**, trạng thái **SUCCESS**. `/health` báo DB/schema sẵn sàng, toàn vẹn `ok`. Browser `giang-hosted-01` đạt **33 mục/49 ảnh**, xác nhận Giang có trong lựa chọn và chỉ Toại bị loại; các màn máy tính, bảng Excel, phiếu giao Excel/PDF và đăng xuất đạt. Không JavaScript exception, HTTP 5xx hoặc yêu cầu ghi ngoài ý định.
- Snapshot `giang-after` lấy sau khi browser kết thúc, so với `giang-predeploy`: **80/80 bảng giữ nguyên nội dung và schema**, hai DB toàn vẹn `ok` (`giang-after/full-preservation.json`). Dữ liệu đơn khách nhập thêm trước đợt triển khai được giữ nguyên; không thay DB bằng snapshot cũ. **Giang đã được mở lại trên web**, không cần nhập lại hồ sơ. Kiểm tra xuất biên nhận Giang dùng dòng hàng thử và hồ sơ thật trên snapshot; không tạo đơn, công nợ hoặc chứng từ thanh toán thật trên production trong lượt này.

### 13.26. Sửa lỗi thiếu mã tại Bảng kê & hóa đơn của đơn 04/09 — 06/09/2026

- Khách đã nhập file `Đơn hàng  04.09.2026.xlsx`: phiên ngày 04/09 có **320 dòng**, trạng thái **nháp**. Tab Bảng kê & hóa đơn dừng vì hai mã chưa có trong danh mục Railway: `M000357` — Mắm nam ngư siêu tiết kiệm can 5 lít, ĐVT **Can**; `O000139` — Xô nhựa, ĐVT **Cái**. Đây là hai mã mới có trong file khách, không phải bằng chứng khách xóa danh mục.
- Đối chiếu đúng file tại `C:/Users/DELL/Downloads/121233/Đơn hàng  04.09.2026.xlsx`: sheet `04.09` dòng 32/79 khớp mã, tên và ĐVT với sheet `danh mục ncc` dòng 1037/1038. Lượng/giá mua/giá bán lần lượt **2 / 70.500 / 80.000** và **1 / 40.000 / 50.000**. Không dùng giá 0 ở sheet đặt hàng để thay giá của dòng bán. File khách gốc được giữ nguyên.
- Phát hiện lỗi nhận diện tiêu đề: hàm chuẩn hóa bỏ chữ `Đ`, khiến `ĐVT` không khớp alias `dvt`; các mã cũ lấy ĐVT từ danh mục nên che mất lỗi. Hai mã mới bị lưu trống ĐVT và không có lỗi dòng. Đã sửa riêng chuẩn hóa tiêu đề, bổ sung lỗi mã chưa có trong danh mục và thiếu đơn vị tính ngay khi đọc/sửa đơn. Không đổi hàm khóa tên dùng chung hoặc bỏ kiểm tra danh mục/tồn của hóa đơn.
- **71 bài đạt** thuộc 5 nhóm nhập workbook, nạp lại, sửa bảng Excel, sửa giá và khả năng xuất (`sep04-tests-02`). Bài mới kiểm tra giữ ĐVT tiếng Việt của mã mới và báo thiếu danh mục/ĐVT. Lượt đầu bài mới đọc nhầm tuple trả về của parser thành danh sách dòng; đã sửa công cụ và chạy lại toàn bộ nhóm đạt.
- Bản sao `sep04-copy-01` tái hiện đúng lỗi 409 trước sửa dữ liệu, sau đó thêm đúng hai sản phẩm qua API danh mục và sửa ĐVT qua API bảng có kiểm tra phiên dòng. Gửi lại cùng mã thao tác không ghi thêm; API khả năng xuất trả **200 / 320 dòng**. Browser riêng kiểm tra bảng hiện bình thường tại 1440/1024px, hai mã mới vẫn thiếu tồn và không được tự mở khóa xuất. Không JavaScript exception hoặc yêu cầu ghi khi chỉ xem.
- Source **`f10da7878c0cdcd8b4b8f1816a6db7dc335a2b59`** deploy từ `xandrosworld/CDT/main`, deployment **`e6db19ee-91e7-4063-820a-1360838ff270`**, trạng thái **SUCCESS**. Sau sao lưu và đối chiếu phiên dữ liệu, đã áp dụng đúng hai sản phẩm mới và ĐVT của hai dòng trên production (`sep04-production-01`). Giữ nguyên 1.253 sản phẩm cũ; không nạp lại toàn bộ file hoặc ghi đè đơn khách đang thử.
- Browser Railway `sep04-hosted-01` đạt **34 mục / 49 ảnh**, có kiểm tra bổ sung bắt buộc bảng khả năng xuất của chính phiên 04/09 hiển thị, API trả 200 và đủ 320 dòng. Đã xem ảnh `09-documents.png`; không còn thông báo thiếu hai mã. Không JavaScript exception, HTTP 5xx hoặc request ghi ngoài phạm vi xem trước.
- Snapshot `sep04-after` lấy sau browser, đối chiếu `sep04-before-repair`: schema của **80 bảng giữ nguyên**, **70 bảng nguyên nội dung**. Chỉ thêm hai sản phẩm; hai dòng đơn và hai dòng tương ứng trong mỗi sổ phải thu/phải trả đổi ĐVT cùng phiên/giờ cập nhật, giữ toàn bộ lượng, giá, tiền và trạng thái. Các bảng lịch sử/audit thêm dấu vết, không sửa lịch sử cũ; SQLite toàn vẹn `ok`. Bằng chứng `sep04-after/preservation.json`, các script và dữ liệu riêng dưới `D:/TDP_RAILWAY_PRIVATE/evidence/sep04-*`.
- Đơn 04/09 vẫn là nháp; không tự duyệt, ghi kho, thu/trả tiền hoặc phát hành hóa đơn. Khách chỉ cần tải lại trang để xem kết quả, không cần nhập lại file. Bốn mã tồn đầu âm và các dòng hóa đơn còn thiếu căn cứ không thuộc lần sửa này.
