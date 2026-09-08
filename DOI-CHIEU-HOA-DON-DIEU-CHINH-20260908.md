# Đối chiếu hóa đơn điều chỉnh đầu ra 695–696

Phần mềm trước đây gộp hóa đơn điều chỉnh mới và hóa đơn gốc bị điều chỉnh vào trạng thái chặn chung. Vì vậy hai hóa đơn 695–696 không có thao tác xử lý, mặc dù khách cần đối chiếu chúng. Đây không phải kết luận rằng mọi hóa đơn điều chỉnh hoặc thay thế đều không được ghi kho.

## Dữ liệu đã kiểm tra

Đã đọc lại chi tiết nguồn M-Invoice của cả 695, 696 và hai hóa đơn được dẫn chiếu 685, 686. Hai hóa đơn điều chỉnh dẫn chiếu **hai hóa đơn gốc khác nhau**.

| Hóa đơn | Hóa đơn được điều chỉnh | Mặt hàng | Số lượng | Tiền trước thuế | Thuế |
|---|---|---|---:|---:|---:|
| 695 | 685 | Đá viên | −887 túi | −8.870.000 đ | 0 đ |
| 696 | 686 | Đá viên | +887 túi | +8.870.000 đ | +709.600 đ |
| Cộng | | | 0 | 0 đ | +709.600 đ |

Tên và đơn vị trùng duy nhất mã **K000035 · Đá viên · Túi**. Hóa đơn 695 ghi lý do xuất sai thuế suất. Các con số cân bằng không tự chứng minh rằng thực tế không giao/nhận thêm hàng; khách phải xác nhận điều đó.

## Thao tác mới

Ở một trong hai dòng, bấm **Đối chiếu điều chỉnh**. Bảng hiển thị cả hai hóa đơn, hóa đơn gốc được dẫn chiếu, mã hàng, lượng, tiền và thuế.

Nếu đúng chỉ sửa thuế, khách đánh dấu **Tôi xác nhận cặp này chỉ sửa thuế, không giao thêm hoặc nhận trả hàng**, rồi bấm **Xác nhận đã đối chiếu**. Cả hai dòng chuyển sang đen, hiển thị mã Đá viên và trạng thái đã đối chiếu, không thay đổi kho. Đóng bảng hoặc Esc không lưu gì.

Xác nhận chỉ thêm nhật ký đối chiếu, không sửa dữ liệu hóa đơn, ghép mã nguồn, danh mục, quy tắc hoặc sổ kho. Kết quả tồn tại sau tải lại và đồng bộ lại cùng dữ liệu. Nếu nguồn, quan hệ hóa đơn hoặc danh mục đổi, xác nhận cũ không còn được áp dụng. API từ chối xác nhận thiếu lựa chọn rõ ràng hoặc dùng nội dung đối chiếu đã cũ.

Chỉ đề xuất cặp có dữ liệu nguồn hợp lệ, cùng bên mua, ngày, mặt hàng, đơn vị, đơn giá, lượng và tiền trước thuế đối ứng chính xác. Cặp có nhiều khả năng ghép, khác lượng, nguồn hủy/thay thế, hóa đơn gốc bị điều chỉnh, dữ liệu thiếu hoặc đã có bút toán kho đều không được áp dụng bước này.

## Phạm vi và kiểm tra

- Bản sửa xử lý bước đối chiếu cặp điều chỉnh thuế, không mở ghi kho chung cho mọi hóa đơn điều chỉnh/thay thế. Trường hợp thực sự thay đổi hàng giao cần xử lý riêng theo hóa đơn gốc và lịch sử ghi kho.
- 76 kiểm tra phía máy chủ đạt: đối chiếu điều chỉnh, phân loại nguồn, đồng bộ đầu ra, danh sách, ghi kho hàng loạt, sổ kho và đầu ra chỉ khớp mã.
- Trình duyệt thử hủy, xác nhận cả cặp, chuyển đen, giữ nguyên lượng/tiền, tải lại và không xuất hiện quy đổi.
- Trên bản sao dữ liệu thật: 89 hóa đơn, 1.953 dòng. Thử xác nhận làm số dòng cần xử lý giảm 2 xuống 0; hai cảnh báo tiền của 716–717 vẫn giữ nguyên. So sánh 84 bảng nghiệp vụ: chỉ `audit_log` thay đổi. Sổ kho giữ 1.099 dòng, không thêm bút toán.
- Không thực hiện xác nhận thay khách trên dữ liệu thật khi chưa có xác nhận về việc giao/nhận hàng.

Bằng chứng riêng tư nằm trong `D:/TDP_RAILWAY_PRIVATE/evidence/output-adjustment-*`.
