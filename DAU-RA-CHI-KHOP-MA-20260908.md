# Đầu ra chỉ khớp mã — yêu cầu khách chốt ngày 08/09/2026, 21:15

Yêu cầu mới thay thế bước quy đổi đầu ra được mô tả trong báo cáo trước: khách chỉ chọn/lưu mã hàng; số lượng, đơn vị, đơn giá và tiền nguồn giữ nguyên. Số lượng ghi xuất dùng trực tiếp số lượng hóa đơn. Đầu vào vẫn quy đổi theo luồng hiện có.

## Thay đổi

- Gỡ ô quy đổi, hệ số ẩn, thông báo đòi quy đổi và bước xác nhận hệ số khỏi màn đầu ra. Mã lưu xong báo “Đã khớp mã”.
- Backend lưu mã đầu ra hoàn tất cả khi ĐVT nguồn và danh mục ghi khác nhau; lượng xuất không nhân hệ số. Không nhận hệ số đầu ra khác 1 từ trình duyệt cũ/API.
- Khi tải lại nguồn, quy tắc cũ được chuyển về lượng nguồn. Kiểm tra trước xuất kho từ chối hệ số cũ khác 1, kể cả khi snapshot cũ khớp hệ số đó.
- Nâng cấp các mã đã chọn ở hóa đơn chưa ghi kho, không chọn mã mới. Có sao lưu trước khởi động, ghi revision/audit, chạy lại không thay đổi dữ liệu lần nữa.
- Giữ nguyên cảnh báo ghép nhầm mặt hàng, tiền nguồn chưa đối chiếu, trạng thái hủy/điều chỉnh, thiếu tồn và khóa hóa đơn đã ghi kho. Không tự ghi xuất trên dữ liệu khách.

## Kết quả kiểm tra trước triển khai

- Bản sao web thật: 16 dòng trước đó chờ quy đổi được hoàn tất mã; không có hệ số cũ khác 1 trong các dòng này. Không thay mã, số lượng, ĐVT, đơn giá, tiền nguồn, danh mục hoặc sổ kho. Chạy nâng cấp lần hai thay đổi 0 dòng.
- Đối chiếu toàn bộ dòng đã ghép tháng 8: 1.913 dòng hợp lệ có lượng xuất bằng lượng nguồn, 9 dòng giữ yêu cầu xác nhận đúng mặt hàng.
- 114 kiểm thử đạt, gồm lưu mã, đồng bộ lại, sửa quy tắc cũ, hệ số cũ 12/0,5, ghi xuất/hoàn tác theo lượng nguồn, idempotency, bảo toàn dữ liệu đã ghi kho, cảnh báo tiền và kiểm tra ghép nhầm mã.
- Hai lượt trình duyệt dữ liệu thử đạt: đầu ra (lưu, tải lại, lọc đỏ, gợi ý mã, báo tiền, xử lý mạng) và đầu vào (mã/quy đổi/gộp/giữ vị trí).
- Bằng chứng riêng: `D:/TDP_RAILWAY_PRIVATE/evidence/output-code-only-*`.
