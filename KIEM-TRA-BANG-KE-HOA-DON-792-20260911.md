# Bảng kê bị chặn bởi hóa đơn 792

## Nguyên nhân và đối chiếu

- Hóa đơn M-Invoice 1C26TYY/792 ngày 11/09/2026 thuộc Công ty Cổ phần Đóng tàu Sông Cấm, MST 0200168673. Hồ sơ người mua SONGCAM chưa có, nên hệ thống không xác định được đơn liên quan và chặn tải để tránh xuất trùng.
- Đã đối chiếu đủ 11 mã hàng, đơn vị, số lượng và đơn giá: khớp toàn bộ 11 dòng SONGCAM ngày 06/09 đã duyệt. Đã lưu liên kết qua API có nhật ký và bổ sung hồ sơ SONGCAM từ thông tin hóa đơn nguồn. Có bản sao SQLite trước khi cập nhật, tại `/data/manual_backups/invoice792_*.sqlite3`.
- Sau đối chiếu, nguồn đã ghi xuất kho, cảnh báo hóa đơn 792 không còn. Lần tải thật tiếp theo phát hiện lỗi độc lập: BIADAUVOI / I000090 có 40 kg ngày 01/09, 15 gói ngày 06/09 và 40 kg ngày 07/09. Chưa có căn cứ đổi 15 gói sang kg.

## Thay đổi

- Khi tải tất cả nhà thầu, xử lý từng nhà thầu trong savepoint riêng. Nhà thầu gặp lỗi đối chiếu, đơn vị hoặc kiểm tra file giữ nguyên dự thảo và lượng chờ; các nhà thầu hợp lệ vẫn được tải.
- File hướng dẫn trong ZIP ghi số nhà thầu chưa tạo file, tên và lý do. Giao diện thông báo rõ số nhà thầu bị giữ lại, tránh hiểu bộ tải đã gồm tất cả.
- Tải riêng nhà thầu đang lỗi vẫn báo lỗi cụ thể. Hóa đơn chưa biết thuộc nhà thầu nào vẫn cần đối chiếu; không tự coi là đơn ngoài.
- Làm mới lượng chờ theo nhà thầu được chọn, giữ nguyên lượng chờ, dự thảo và số đã đối trừ của các nhà thầu khác.
- Lỗi nhiều đơn vị ghi rõ mã và các đơn vị đang xung đột.

## Kiểm tra

57 bài kiểm thử qua: SourceScopeTests, WaitingTests, OrderInvoiceRangeTests, UnissuedTests. Bao gồm: nhà thầu khác lỗi không chặn tải riêng; ZIP một phần ghi rõ bên bị giữ lại; rollback giữ nguyên dự thảo/tồn đã giữ; tải lặp không đổi số lượng; chưa xác định người mua vẫn chặn; lưu hồ sơ người mua nhận đúng hóa đơn và không trừ hai lần.

Lệnh: `python -m unittest tdp_system.test_outgoing_source_scope.SourceScopeTests tdp_system.test_outgoing_waiting.WaitingTests tdp_system.test_order_invoice_range.OrderInvoiceRangeTests tdp_system.test_outgoing_unissued.UnissuedTests`
