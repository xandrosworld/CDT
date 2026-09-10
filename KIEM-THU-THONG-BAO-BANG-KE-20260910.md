# Thông báo bảng kê từ hóa đơn đỏ

Tái hiện trên hệ thống thật: Bảng kê & hóa đơn → ATV → 01–03/09/2026 → Xem và tải bảng kê. API trả 404 với mã `issued_invoice_scope_empty` và giải thích chưa tìm thấy hóa đơn VAT đã phát hành, nhưng hàm hiển thị lỗi ghi đè mọi 404 thành “Không tìm thấy chức năng này”.

Sửa giữ nguyên thông báo cụ thể từ API cho cả xem và tải file. Chỉ dùng thông báo thiếu chức năng khi 404 không có giải thích hoặc máy chủ báo đường dẫn không tồn tại. Không sửa điều kiện hóa đơn phát hành, không phát hành hóa đơn hoặc ghi dữ liệu kinh doanh khi kiểm tra.

Kiểm thử: 6 kiểm tra JavaScript PASS (API, tải file, lỗi nghiệp vụ 404, đường dẫn HTML 404 và thiếu tồn). 32/34 kiểm thử Python PASS trong các nhóm invoice_payment_scope, invoice_payment_documents, invoice_delivery_statement, ui_language_contract. Hai kiểm thử giao diện đã thất bại trên HEAD chưa sửa: `test_large_modules_are_summary_first` còn đòi chữ “Tải đủ 4 file ZIP”; `test_last_daily_workbook_becomes_standard_without_a_second_approval_click` còn đòi lời gọi tự duyệt cũ. Không thay quy trình duyệt chỉ để đáp ứng các kiểm thử này.

Playwright dùng giao diện sửa với API thật đã xác nhận giữ đúng mã lỗi `issued_invoice_scope_empty`; không còn báo thiếu chức năng. Ảnh `BAN_THU_GIAO_DIEN.png` chỉ là bản thử giao diện. Ảnh `02_SAU_SUA.png` được chụp lại sau khi triển khai. Bằng chứng tại `tdp_system/exports/payment_scope_test`.
