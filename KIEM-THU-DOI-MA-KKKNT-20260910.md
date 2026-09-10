# Đổi mã xuất nội bộ và ngoại lệ tồn âm KKKNT

Yêu cầu đã chốt: phần Xuất có Excel đổi mã/tên nội bộ, nhập lại và tính tồn; giữ nguyên nội dung hóa đơn đã phát hành. KKKNT được lập bảng kê khi âm và chuyển nguyên tồn âm sang tháng sau. KCT, 0%, thuế có giá trị và thuế chưa xác định không thuộc ngoại lệ KKKNT.

## Cách thao tác

1. Báo cáo vật tư hàng hóa → chọn trọn tháng → **Xuất · Đổi mã nội bộ qua Excel**. Trong cửa sổ chuyển tồn cũng có nút mở chức năng này.
2. Tải Excel. Sheet `Doi ma xuat kho` chứa các dòng xuất M-Invoice đã ghi kho trong kỳ, mã nội bộ hiện tại và tồn cuối kỳ. Chỉ sửa hai cột vàng `Mã nội bộ mới` và `Tên nội bộ mới`, lấy đúng cặp mã/tên từ sheet danh mục.
3. Tải file lên. Xem số lượng chuyển, tồn mã cũ và mã mới sau khi đổi. Nhập tên người xác nhận và xác nhận.
4. Tồn và báo cáo được tính theo mã nội bộ mới. Mỗi dòng chuyển toàn bộ lượng trừ kho của một dòng hóa đơn; không đổi số lượng, đơn vị, giá bán, tiền hàng, thuế hay tên/mã nguồn trên hóa đơn.
5. Với hàng KKKNT, có thể mở **Bảng kê mua vào bổ sung** từ cửa sổ chuyển tồn; tải mẫu trắng, điền phát sinh mua thực tế và nhập lại. Không phải bù hết âm mới được lập bảng kê hoặc chuyển tháng.

File không có dòng xuất cho mặt hàng chỉ âm từ đầu kỳ. Với KKKNT, số âm được chuyển nguyên; với hàng khác cần đối chiếu nguồn tồn đầu, không tự tạo dòng xuất để đổi mã.

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
