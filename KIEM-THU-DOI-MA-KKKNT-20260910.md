# Đổi mã xuất nội bộ và ngoại lệ tồn âm KKKNT

Yêu cầu đã chốt: phần Xuất có Excel đổi mã/tên nội bộ, nhập lại và tính tồn; giữ nguyên nội dung hóa đơn đã phát hành. KKKNT được lập bảng kê khi âm và chuyển nguyên tồn âm sang tháng sau. KCT, 0%, thuế có giá trị và thuế chưa xác định không thuộc ngoại lệ KKKNT.

## Cách thao tác

1. Báo cáo vật tư hàng hóa → chọn trọn tháng → **Xuất · Đổi mã nội bộ qua Excel**. Trong cửa sổ chuyển tồn cũng có nút mở chức năng này.
2. Tải Excel. Sheet `Doi ma xuat kho` có hướng dẫn ở đầu bảng. Chỉ sửa hai cột vàng **A–B: Mã hàng muốn chuyển sang / Tên hàng muốn chuyển sang**, lấy đúng cặp mã/tên từ sheet danh mục. Cột C–G là mã/tên đang trừ kho, lượng chuyển, đơn vị và tồn cuối kỳ để đối chiếu. Cột H–Q là hóa đơn gốc; mã nguồn ở J có thể trống, không có nghĩa là thiếu mã nội bộ. ID dòng kho ở R được ẩn để tránh nhầm với mã hàng.
3. Tải file lên. Xem diễn giải **Từ mã/tên hàng cũ → Sang mã/tên hàng nhận**, lượng chuyển và tồn hai hàng sau khi đổi. Nhập tên người xác nhận và xác nhận. Mẫu cũ đã tải trước lần đổi bố cục này vẫn được nhận với hai cột vàng Q–R; vẫn kiểm tra thời hạn và dữ liệu có thay đổi như trước.
4. Tồn và báo cáo được tính theo mã nội bộ mới. Mỗi dòng chuyển toàn bộ lượng trừ kho của một dòng hóa đơn; không đổi số lượng, đơn vị, giá bán, tiền hàng, thuế hay tên/mã nguồn trên hóa đơn.
5. Với hàng KKKNT, có thể mở **Bảng kê mua vào bổ sung** từ cửa sổ chuyển tồn; tải mẫu trắng, điền phát sinh mua thực tế và nhập lại. Không phải bù hết âm mới được lập bảng kê hoặc chuyển tháng.

File không có dòng xuất cho mặt hàng chỉ âm từ đầu kỳ. Với KKKNT, số âm được chuyển nguyên; với hàng khác cần đối chiếu nguồn tồn đầu, không tự tạo dòng xuất để đổi mã.

Kiểm thử đổi bố cục: 17 ca remap/KKKNT qua, gồm 15 ca chạy với bố cục cũ để giữ tương thích và 2 ca mới kiểm tra vị trí cột, mã hóa đơn nguồn trống, nhập/xác nhận đúng dòng, chặn sửa 16 cột gốc/công thức/xóa dòng. Trình duyệt tải mẫu mới, sửa A–B, nhập lại, xác nhận và chuyển tháng thành công.

## Kiểm soát dữ liệu

- Mã/tên mới phải khớp danh mục; đơn vị mã nhận phải khớp đơn vị kho của dòng cũ. File không được sửa cột nguồn, xóa/lặp dòng, thêm ID hoặc dùng công thức.
- Kiểm tra tồn mã nhận, cả phần dự thảo đang giữ; mã nhận không thuộc KKKNT không được âm sau khi chuyển.
- File hết hạn sau 7 ngày; xem trước có hiệu lực 15 phút. Dữ liệu nguồn/danh mục/kỳ chốt/tồn/dự thảo thay đổi thì yêu cầu đối chiếu lại. Kỳ đã chốt hoặc có tồn đầu kỳ sau phải mở lại trước khi sửa.
- Ghi nhận thay đổi nguyên tử, có lịch sử người xác nhận và từng mã cũ/mới. Gửi lại cùng lượt xác nhận không áp dụng hai lần.
- Giữ nguyên ledger gốc; lớp mã nội bộ có hiệu lực được dùng cho tính tồn, báo cáo, giữ tồn và hoàn tác. Nội dung hóa đơn và quy tắc ghép mã dùng chung không bị sửa. Hoàn tác hóa đơn về sau trả về mã nội bộ đã đổi, giữ snapshot giá trị của mã nhận.
- Dòng lập hóa đơn phải có thuế KKKNT và mã danh mục thuộc KKKNT mới được miễn chặn tồn; mã dùng lẫn thuế không được mở ngoại lệ cho các dòng có thuế.

## Kết quả kiểm thử

- Bộ hồi quy 144 ca qua: readiness, chốt tháng, ledger, thuế xuất, bảng kê mua vào/duyệt đơn, báo cáo thuế/NXT/tồn, tách giá mua–bán, thay thế hàng trước phát hành.
- Bộ 10 ca chuyên biệt qua: Excel đi/về; bất biến nguồn và ledger; sai mã/tên/đơn vị/công thức/cột gốc/thiếu dòng; stale file/preview; âm mã nhận; rollback khi ghi lỗi; không giữ tồn hai lần cho hóa đơn đã đồng bộ; KKKNT âm vẫn tạo/tải/xác nhận và tính lại; KCT/0%/thuế lỗi không được miễn; bảng kê mua bổ sung khi vẫn âm; chuyển tháng và hoàn tác hóa đơn ở tháng sau về đúng mã/giá trị kho.
- Trình duyệt trên SQLite tạm: KKKNT âm vẫn tạo và tải ZIP; tải Excel đổi mã, sửa hai cột, nhập lại, xem trước và xác nhận; hết âm hàng có thuế; chốt tháng khi KKKNT còn âm. Không có lỗi JavaScript.
- Bản sao dữ liệu Railway lấy bằng SQLite backup chỉ đọc rồi thử trong RAM: 34 mã âm gồm 20 mã KKKNT và 14 mã còn chặn. Đơn 04/09 còn 3 mã âm chặn, 4 mã KKKNT cảnh báo và 1 dòng thuế chưa hợp lệ. Excel có 1.951 dòng xuất đã ghi kho. Giả lập đổi một dòng thành công; hash toàn bộ dữ liệu hóa đơn gốc và ledger gốc không đổi.

Minh chứng: `tdp_system/exports/output_stock_remap_test/` gồm ảnh thao tác, Excel/ZIP thử nghiệm, `result.json` và `real_snapshot_result.json`. Các phép đổi mã, lập bảng kê và chuyển tồn trong kiểm thử chạy trên dữ liệu tạm/bản sao RAM, không sửa tồn hoặc phát hành hóa đơn của khách.

## Rà soát bổ sung sau triển khai

Phát hiện và sửa thêm ba trường hợp bằng kiểm thử tái hiện:

- Excel lưu số với 15 chữ số có nghĩa: file chỉ sửa hai cột vàng có thể bị báo nhầm sửa cột gốc khi nguồn có số dài hơn. Xuất/đối chiếu theo biểu diễn số của Excel; giá trị nguồn trong cơ sở dữ liệu vẫn giữ nguyên. Sửa thực sự lượng, giá, tiền hoặc các cột gốc vẫn bị từ chối.
- Mã nhận còn tồn cuối tháng 8 và cuối tháng 9 nhưng thiếu tại một thời điểm đầu tháng 9: khoản nhập về sau không còn che mất thiếu hụt này. Xem trước và xác nhận đều kiểm tra tồn thấp nhất từ cuối kỳ trở đi, trừ cả dự thảo đang giữ. Chỉ kiểm tra một lần cho mỗi mã nhận.
- Biến thể API M-Invoice dùng `inv_vatAmount`: lấy đúng tiền thuế dòng nguồn, gồm số thập phân/0/số âm của dòng điều chỉnh, thay vì rơi vào phép tính lại và làm tròn thuế suất. Không cập nhật hóa đơn nguồn.

Bổ sung kiểm thử: lưu lại file theo độ chính xác Excel; thiếu tồn giữa các giao dịch tháng sau; giao dịch tháng sau thay đổi sau xem trước; xác nhận đồng thời chỉ ghi một lần; preview khác đã cũ bị từ chối; đổi mã lần hai không trừ hai lần; hai dòng cùng mã chỉ đổi dòng được chọn; đồng bộ lại nguồn giữ nguyên mã nội bộ đã đổi; Excel Xuất giữ nguyên tên, lượng, giá, tiền và thuế của dòng nguồn.

Bộ hồi quy sau sửa: **160/160 ca qua** (145 ca các luồng liên quan và 15 ca đổi mã/KKKNT). Kiểm tra diff không có lỗi khoảng trắng. Chạy đúng một lượt đầy đủ sau thay đổi cuối, không tính các lượt lặp vào số ca.

Trên bản sao dữ liệu thật trong RAM: giả lập 18 dòng đổi mã xử lý được 13/14 mã đang chặn. Mã `N000040` còn thiếu 6,4 lít, phép tìm mã nhận cùng đơn vị và đủ tồn không tìm được ứng viên; chốt tháng tiếp tục bị chặn đúng. Sau khi thêm **một giao dịch nhập giả lập chỉ trong RAM** cho thiếu hụt này, chốt tháng thành công; toàn bộ số lượng và giá trị tồn đầu tháng 9 khớp tồn cuối tháng 8. Hash hóa đơn nguồn và ledger gốc trước/sau đổi mã không đổi. Đây là kiểm thử kỹ thuật, không phải phương án ghép hàng hay chứng từ mua hàng đề xuất cho khách.

Trình duyệt dữ liệu tạm đã kiểm tra cả luồng đổi mã → chốt tháng với KKKNT âm và luồng sửa 7 lỗi tồn → duyệt đơn → lập dự thảo → tải ZIP → tính lại → hủy/tạo lại. Không có lỗi JavaScript. Kết quả chi tiết: `full_recovery_audit.json`, `result.json` trong thư mục minh chứng; kiểm thử tab Bảng kê ở `tdp_system/exports/documents_resolution_test/`.
