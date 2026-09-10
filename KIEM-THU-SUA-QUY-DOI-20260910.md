# Sửa quy đổi hóa đơn đã nhập kho — 10/09/2026

Khách xác nhận hóa đơn C26MHP / 541588 ngày 06/09: BO HAM VISSAN 150G*4,
mã M000004, 9 lốc; 1 lốc = 4 hộp. Dữ liệu cũ dùng 12, đã ghi 108 hộp.

## Kết quả và thao tác

Thêm **Sửa quy đổi đã nhập kho** tại thao tác hóa đơn và trong bảng Kiểm tra.
Chọn dòng, nhập hệ số, bấm Kiểm tra thay đổi, đối chiếu lượng/giá/tồn/giá vốn,
nhập người xác nhận và lý do rồi xác nhận. Không phải nhập kho lại.

- Dòng bò hầm: 108 → 36 hộp; 9.953,666667 → 29.861đ/hộp.
- Tiền nhập giữ nguyên 1.074.996đ. Giữ nguyên nguồn, thuế, lượng hóa đơn 9 lốc.
- Bản sao dữ liệu thực: tồn cuối tháng 9 M000004 là 180 → 108 hộp; giảm đúng 72.
- Bút toán nhập chính và bảng tương thích cùng cập nhật, lưu toàn bộ trước/sau và audit
  trong một giao dịch. Token chống dữ liệu cũ; cùng yêu cầu gửi lại không sửa lặp.
- Nếu có chiết khấu đã phân bổ, giữ nguyên tiền phân bổ, chỉ đổi lượng và đơn giá kho.
- Báo cáo bình quân tháng tự tính lại tồn và giá vốn xuất từ lượng nhập đã sửa.
- Chặn khi nguồn không an toàn, bút toán không khớp, tháng/kỳ sau đã chốt hoặc có tồn
  đầu kỳ sau. Không tự sửa số đã chuyển tháng. Hệ số phải dương/hữu hạn.
- Có lịch sử người sửa/lý do/lượng trước-sau. Có lựa chọn nhớ hệ số cho dòng mới cùng
  tên, mã nguồn, đơn vị, nhà cung cấp và mã kho; chỉ áp dụng từ ngày hóa đơn đã sửa,
  không tự viết lại các dòng cũ hoặc dòng đã có ghép mã.

## Kiểm chứng

79 tests PASS: ConversionRepairTests, invoice_mapping, invoice_line_groups,
DiscountTests, invoice_inventory, invoice_valuation, invoice_receipt_summary,
inventory_period_close. Bao gồm rollback nếu audit lỗi, stale token, khác tenant,
khóa kỳ, sai mapping revision, giữ chiết khấu, ghi lại idempotent, nhớ quy đổi cho
dòng mới, giá vốn xuất/bảo toàn tổng giá trị và nguồn hóa đơn đầu ra giữ nguyên.

Playwright trên bản sao hóa đơn thật: sửa qua giao diện, xác nhận, mở lại và đối chiếu
tổng nhập 36 hộp. Không có lỗi JavaScript. Ảnh tại exports/beef_conversion_test.
Kiểm tra JavaScript syntax và git diff --check đạt.

Rà soát mở rộng phát hiện test cũ
`InvoiceRepairTests.test_revaluation_cannot_move_consumed_stock_and_create_negative_balance`
không đạt ở hàm sửa MÃ hàng cũ (`invoice_repairs.py`, không thay đổi trong bản này).
Luồng mới sửa hệ số cùng mã, có kiểm thử riêng trường hợp giá vốn xuất phía sau.

Phát hiện các hóa đơn bò hầm tháng trước cũng có hệ số 12. Tháng 8 đã chốt;
không tự sửa các hóa đơn đó trong lần sửa hóa đơn 541588.
