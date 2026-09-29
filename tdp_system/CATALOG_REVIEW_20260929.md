# Sửa danh mục ngay trong bản xem trước — 29/09/2026

Khách xác nhận hàng thực giao của N000006, N000007, N000009, N000057 lần lượt là Cau, trầu; Chè cúng; Hoa cúng; Xôi cúng. File tháng 10 đổi tên xuất của các mã này thành Rau muống. Dữ liệu web đọc trước sửa vẫn giữ đúng bốn tên; không chạy tác vụ thay tên hay đổi ĐVT trên dữ liệu khách.

## Luồng khách sử dụng

1. Danh mục & sao lưu → Nạp từ Excel.
2. Trong bản xem trước, chọn **Giữ tên và ĐVT Thành Đạt Phát; cập nhật tên và ĐVT xuất hóa đơn**, rồi **Kiểm tra lại**. Có thể đổi phạm vi trên cùng file đã nạp.
3. Bấm **Sửa dòng này**. Sửa Tên xuất hóa đơn, ĐVT xuất hóa đơn; nút giữ ĐVT Thành Đạt Phát lấy đúng đơn vị đang lưu. Có nút dùng lại Tên xuất hóa đơn đang lưu. Không tự chọn đơn vị hoặc đổi số lượng.
4. **Kiểm tra lại** chỉ sửa bản xem trước. **Xác nhận cập nhật danh mục** mới ghi dữ liệu, có lịch sử các ô đã sửa. Mất mạng giữ phần nhập; kiểm tra lại cùng yêu cầu trả cùng kết quả. Bản xem trước cũ không được dùng để xác nhận sau khi đã sửa.

ĐVT xuất hóa đơn khác đơn vị nội bộ vẫn phải qua quy đổi/số kg thực tế đã xác nhận ở luồng xuất hiện có. Hoa cúng trên web đang có đơn vị nội bộ Bộ và đơn vị hóa đơn Bó; không tự coi hai đơn vị này bằng nhau.

## Phạm vi bảo vệ danh tính hàng

Quy tắc trong `invoice_identity_policy.py` giới hạn rõ bốn mã đã được xác nhận trên. Cho phép khác dấu/hoa thường/dấu câu của cùng tên; chặn tên khác. Đây không phải bộ suy đoán ngữ nghĩa cho tất cả hàng hóa. Áp dụng ở sửa danh mục, nhập Excel danh mục, nhập riêng tên hóa đơn, nguồn danh mục tham chiếu và các cửa kiểm tra/lập file dự thảo xuất. Kiểm tra cả nhãn cũ còn nằm trong dự thảo, không viết lại hóa đơn đã ký.

Không đổi schema, ngày chứng từ, đơn hàng, số lượng, giá, thuế hay kho khi xem trước/kiểm tra lại. Chế độ giữ nội bộ bảo toàn cả thuế đang dùng. Mã cũ ngoài file không bị xóa.

## Kiểm chứng

- File BÁO GIÁ T10-2026.xlsx có 1.232 mã duy nhất. Trên bản danh mục tách riêng, sửa đúng bốn tên/ĐVT hóa đơn đưa bản kiểm tra về 0 lỗi, giữ 49 mã ngoài file và toàn bộ dữ liệu DB không thay đổi trước xác nhận.
- Kiểm thử API bao gồm bảo toàn dữ liệu, chặn nhãn sai, xác nhận bắt buộc, kiểm tra lại không nạp file, thử lại sau lỗi, bản xem trước cũ, và danh mục bị thay đổi đồng thời.
- Trình duyệt với dữ liệu giả kiểm tra một lần tải file, đổi phạm vi, sửa trực tiếp, mất mạng/thử lại giữ nội dung, xác nhận lưu và xem lại ở 1440/1024px. Kiểm tra production chỉ xem trước/kiểm tra lại, không xác nhận ghi dữ liệu khách.
