# Duyệt đơn kèm bảng kê — 09/09/2026

Trước đây duyệt đơn không ghi phần bảng kê mua vào, nên đơn đã duyệt vẫn thiếu tồn cho hàng kê khai. Bản sửa nối bảng kê với cùng lần duyệt đơn; không yêu cầu xuất rồi nhập lại Excel.

- Trước khi duyệt, hiển thị số dòng, tiền bảng kê và tỷ lệ giá đang cấu hình.
- Lượng theo thực nhận sau hỏng/trả; nếu có phần mua đã chốt thì lấy phần mua đó. Giá bảng kê theo tỷ lệ giá bán đã cấu hình, mặc định 95%.
- Thiếu giá, hồ sơ người bán, sai mã/tên/đơn vị hoặc phần mua chưa chốt: báo dòng cụ thể, không duyệt một phần.
- Dòng lấy từ KHO hoặc không đánh dấu BK không tạo phiếu mua mới. Giữ quy tắc loại trừ người bán hiện hữu.
- Cùng mã đã nhập từ hóa đơn cùng ngày: cần xác nhận đây là phần mua riêng; không tự coi cùng mã là cùng lần mua.
- Duyệt, ghi bảng kê, sổ kho và cập nhật công nợ trong cùng giao dịch. Lỗi giữa chừng hoàn tác toàn bộ.
- Duyệt lại, kể cả hai yêu cầu đồng thời, không cộng kho lần nữa.
- Chứng từ bảng kê lấy lượng/giá đã ghi; tải lại mẫu BK giữ dấu nguồn để không nhập lặp.
- Đơn có bảng kê đã ghi kho được bảo vệ khi sửa hoặc thay file mua. Hoàn tác bảng kê bằng luồng lịch sử hiện có sẽ mở lại đơn để sửa và duyệt lại.

## Kiểm chứng

- Kiểm thử mới: duyệt/duyệt lại, đọc trước không ghi, hủy xác nhận, thay nguồn sau preview, thiếu giá/hồ sơ, sai tên/ĐVT, hỏng/trả, lỗi dòng thứ hai, lượng thực mua từ nguồn chuẩn, hoàn tác/sửa/duyệt lại, tải lại mẫu, thay file mua sau ghi kho, trùng mã với hóa đơn và duyệt đồng thời.
- Kiểm thử liên quan: BK import, purchase summary export, purchase sales boundary, order import idempotence, purchase order roundtrip.
- Trình duyệt Chrome: xem lỗi, nút Sửa dòng, hủy duyệt không ghi, duyệt thành công, duyệt lại không cộng kho; không lỗi JavaScript.
- Bằng chứng riêng: `D:/TDP_RAILWAY_PRIVATE/evidence/batch-bk-*20260909*`.

## Dữ liệu khách

Đã kiểm tra bản sao dữ liệu, không tự duyệt hoặc ghi hàng vào kho thật để thử.

- Phiên 29/08: còn 19 dòng thiếu giá bán để tính bảng kê và 1 dòng thiếu hồ sơ người bán.
- Phiên 04/09: kiểm tra riêng phần bảng kê có 159 dòng hợp lệ. Các kiểm tra chung của đơn vẫn áp dụng khi duyệt.
- Bản sửa luồng duyệt không đồng nghĩa các trang ngày lịch sử chưa nạp đã được nhập lên web; không tự backfill các ngày đó hoặc lấy tồn tháng 9 bù tháng 8.
