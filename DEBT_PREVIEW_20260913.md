# Xem sổ công nợ trực tiếp trên web

Khách mở nút toàn màn hình ở bảng tổng TOYOTA nhưng chỉ thấy nhà thầu và dòng TỔNG. Nút cũ chụp lại đúng bảng HTML đang chọn, không mở sổ từng mặt hàng hay toàn bộ file Excel.

## Cách dùng sau sửa

Vào **Công nợ → Công nợ phải thu / Công nợ phải trả**, chọn khoảng ngày và đối tượng, bấm **Xem sổ chi tiết trên web** ngay cạnh bộ lọc.

- Phải thu: toàn bộ dòng theo ngày, nhà thầu, bếp và trạng thái đang chọn. Có số đặt, thực giao, khách trả, giao ròng, đơn giá, thuế, thành tiền và tổng cuối sổ.
- Phải trả: đúng mẫu Excel NCC, có số lượng, giá mua, hỏng/thêm/giảm/thiếu, thực tế và thành tiền. Khi chọn tất cả NCC, có thêm sheet tổng và từng NCC.
- Mở bảng không tải file. Nút **Tải Excel sổ đang xem** trong bảng sử dụng đúng bộ lọc khi mở.
- Hai nút ở bảng tổng được ghi rõ **Phóng to bảng tổng** và **Phóng to tổng theo bếp**. Nút ở bảng chi tiết cũng mở toàn bộ sổ, không bị giới hạn bởi trang HTML hiện tại.

Hai API preview dùng chung hàm tạo workbook với API xuất Excel, chỉ đọc dữ liệu. Không thay đổi công thức công nợ, số tiền đã thanh toán, doanh thu, tồn kho hoặc chứng từ.

Khi đổi bộ lọc trong lúc chờ, phản hồi cũ không mở đè lên lựa chọn mới. Ngày nhập trên form được dùng cả khi chưa bấm Xem công nợ. Nếu dữ liệu quá lớn để xem một lần, hệ thống báo thu hẹp khoảng ngày; không trả bảng bị cắt thiếu dòng. Excel vẫn có thể tải qua nút hiện có.

## Kiểm tra

42 bài kiểm tra Python thuộc 8 nhóm: phải thu, phải trả, xuất Excel, thanh toán, giao diện và chứng từ. Kiểm tra từng ô preview với Excel, tất cả/riêng đối tượng, ngày không có dữ liệu, trạng thái, trả tiền, khoảng ngày sai, lỗi tạo bảng và không ghi dữ liệu khi xem.

`tdp_system/qa_debt_preview.cjs` chạy trình duyệt trên bản sao dữ liệu khách hoặc `https://tdp.up.railway.app`; dùng GET để xem công nợ và tải file, không tạo thanh toán thử. Các lỗi kết nối/phản hồi chậm chỉ được mô phỏng trên bản sao.

Đối chiếu dữ liệu khách ngày 01–04/09/2026:

| Bộ lọc | Số dòng | Thành tiền |
|---|---:|---:|
| Phải thu TOYOTA / TOYOTA | 48 | 9.329.320đ |
| Phải thu NHUAHAIPHONG / NHUAHP | 28 | 6.915.520đ |
| Phải thu ATV / LSVINA | 101 | 29.398.589đ |
| Phải trả NCC sim | 82 | 1.541.280đ |

Ảnh, workbook tải từ nút trong bản xem và kết quả QA được lưu riêng trong `tdp_system/exports/debt_preview_local_20260913` và `tdp_system/exports/debt_preview_railway_20260913`. Chỉ thư mục Railway là minh chứng web thật.
