# Công nợ phải trả theo đầy đủ sheet Đặt hàng

Khách xác nhận ngày 15/09/2026: tập hợp tất cả các dòng trên sheet Đặt hàng, gồm cả NCC `kho`. Quy tắc này áp dụng cho sổ phải trả chi tiết, tổng công nợ và file Excel.

- Bỏ loại trừ tài khoản `kho` khỏi nguồn phải trả. Các dòng đã bị loại được kích hoạt lại với cùng mã dòng và lịch sử sửa đổi; đồng bộ lặp không cộng trùng.
- Giữ điều kiện ngày đã duyệt, nguồn đã xác nhận và mốc công nợ lịch sử. Việc tính phải trả không ghi thêm chứng từ kho hoặc sửa đơn bán.
- Khi mở lại màn hình công nợ hoặc chuyển tab phải thu/phải trả, tải lại số tổng và sổ chi tiết để không giữ thông báo từ lần xem cũ.

Đối chiếu trên bản sao dữ liệu hiện hành: 02/09 có 63 dòng, tổng 8.156.750đ; 08/09 có 219 dòng, tổng 54.246.470đ. Khoảng 01–04/09 có 618 dòng, tổng 121.963.665đ và không có cảnh báo thiếu nguồn. Đã so sánh từng dòng nguồn của 11 ngày đã chốt; 327 dòng kho được kích hoạt lại, chỉ hai bảng sổ phải trả và lịch sử của sổ thay đổi.

Kiểm tra: `test_payable_ledger`, `test_payable_purchase_sheet`, `test_purchase_returns`, `test_payable_export`, `test_payable_settlement`, `test_payable_ui`, `test_daily_payable_recovery` (68 lượt kiểm tra). Trình duyệt xác minh tổng, xuất Excel, mở sổ chi tiết và tình huống quay lại một màn hình đang giữ thông báo thiếu sheet cũ.
