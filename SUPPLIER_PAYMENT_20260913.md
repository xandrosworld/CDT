# Ghi nhận trả tiền theo NCC

Khách không có ô nhập một khoản trả cho NCC: giao diện cũ yêu cầu chọn và nhập phân bổ từng dòng; phần dưới chỉ cộng tổng. Bản sửa đặt form **Ghi nhận trả tiền NCC** ngay dưới bộ lọc.

Chọn khoảng ngày và NCC → xem **Còn phải trả trong kỳ** → nhập **Số tiền trả lần này** → kiểm tra **Sau lần trả này còn** → bấm **Ghi nhận thanh toán NCC** rồi xác nhận. Nút **Trả hết số còn nợ** điền số tiền còn nợ trong phạm vi đó. Có thể mở **Thanh toán theo từng dòng (tùy chọn)** khi cần chọn riêng chứng từ.

Khoản trả trừ vào các dòng còn nợ của đúng NCC trong kỳ, theo ngày cũ đến mới, rồi mã dòng. Màn hình xác nhận ghi rõ số tiền trước/sau và số dòng được trả. Số dư đầu kỳ ngoài phạm vi đã chọn vẫn nằm ở bảng tổng NCC; trả hết dòng trong kỳ không xóa khoản nợ kỳ trước. Ngày thanh toán ngoài kỳ có hướng dẫn xem bảng tổng tại kỳ chứa ngày thanh toán đó.

API xem trước chỉ đọc. Lệnh ghi nhận dùng cơ chế giao dịch, phân bổ, lịch sử, hoàn tác và chống trùng hiện có. Snapshot và revision chặn dữ liệu đã thay đổi hoặc hai người cùng trả một khoản. Trình duyệt giữ nguyên yêu cầu khi mất kết nối, kể cả sau tải lại trang, để gửi lại cùng mã thay vì lập giao dịch khác. Giao dịch theo NCC hỗ trợ đến 20.000 dòng, không bị giới hạn bởi trang HTML hoặc 500 dòng của chế độ nhập tay.

Đã sửa việc so tên NCC khác chữ hoa/thường giữa dòng hàng, thanh toán, Excel và bảng tổng (ví dụ sim / Sim). Dấu tiếng Việt vẫn được giữ để phân biệt NCC khác nhau; không đổi mã trong dữ liệu nguồn.

## Kiểm tra

- 39 kiểm tra Python: thanh toán, sổ phải trả, Excel, giao diện và chứng từ. Bao gồm trả một phần/toàn phần, hoàn tác, ghi đồng thời, trùng yêu cầu, sửa kế hoạch, stale snapshot, sai số tiền, sai kỳ và 805 dòng trong một giao dịch.
- `tdp_system/qa_supplier_payment.cjs`: thao tác trình duyệt trên bản sao dữ liệu khách và Railway. Bản sao thử ghi trả 500.000đ, mất phản hồi, tải lại và gửi lại đúng yêu cầu; trả hết phần còn lại; đối chiếu cả số dòng lẫn bảng tổng rồi hoàn tác các giao dịch thử.
- Railway: chọn NCC thật, xem số còn nợ, nhập tiền, mở màn hình xác nhận, quay lại và thử nút trả hết. Không xác nhận ghi khoản thanh toán thử lên sổ thật. Ảnh này chứng minh giao diện và kế hoạch trừ nợ trên Railway; ảnh đã ghi thanh toán nằm riêng trong thư mục bản sao.

Minh chứng: `tdp_system/exports/supplier_payment_railway_20260913` và `tdp_system/exports/supplier_payment_local_20260913`.
