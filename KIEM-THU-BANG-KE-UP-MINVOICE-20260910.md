# Bảng kê từ đơn đã duyệt để nhập M-Invoice

Khách cần lấy file trước khi phát hành hóa đơn đỏ. Thêm form đầu trang Bảng kê & hóa đơn: chọn nhà thầu (hoặc tất cả), khoảng ngày, **Tải bảng kê để up M-Invoice**. Phần bảng kê từ hóa đơn đã phát hành được thu gọn và ghi rõ thời điểm sử dụng.

API POST `/api/export/order-invoices` chạy trong BEGIN IMMEDIATE: kiểm tra toàn bộ phạm vi đã duyệt, chỉ lập dự thảo cho nhà thầu đã chọn chưa có dự thảo có thể tải, giữ nguyên các dự thảo hiện có, kiểm tra tồn lại khi xuất file. Lượng chỉ lấy từ các dòng dự thảo đã giữ tồn; phần chưa phân bổ ghi trong hướng dẫn ZIP và đếm trên giao diện. KKKNT giữ ngoại lệ đã được khách xác nhận. Các file Excel giữ mẫu 13 cột hiện hành, tách ngày/nhà thầu/nhóm thuế. Không gọi API M-Invoice, không ký hay đánh dấu đã phát hành.

Lỗi tạo file hoặc không có lượng xuất làm rollback toàn bộ dự thảo mới. Tải lặp không thay dự thảo đã có hoặc tăng lượng giữ kho. Dự thảo đã lưu M-Invoice/đã phát hành được loại khỏi file mới. Kho toàn cục vẫn trừ lượng đã giữ cho nhà thầu/ngày khác.

Kiểm thử: 51 kiểm thử hồi quy tồn/phân bổ/an toàn PASS; nhóm phạm vi có 8 kiểm thử mới PASS (runner cũng chạy lại 33 kiểm thử fixture). Có kiểm tra hai ngày cùng dùng 7 đơn vị tồn, đơn cần 10 chỉ xuất 7 và để lại 3; chỉ chọn một nhà thầu không thay nhà thầu khác; chưa duyệt chặn toàn bộ; lỗi file rollback; tồn giảm chặn tải lại; KKKNT được âm; hàng có thuế tồn 0 không ra file rỗng. Kiểm thử giao diện bản sao khách: ATV 01–03/09 tạo/tải 5 Excel, 14 dòng chưa phân bổ, không lỗi JavaScript.

Bằng chứng tại `tdp_system/exports/order_range_test`. Chỉ ảnh/file có tiền tố `HE_THONG_THAT` là lấy từ hệ thống thật. File thử không được nhập M-Invoice.
