# Sửa lỗi tải bảng kê ATV ngày 16/10/2026

## Hiện tượng và nguyên nhân

Khách xem trước được lượng xuất theo tồn nhưng tải ZIP bị chặn bởi lỗi
`M000002: có hóa đơn vừa ký chưa đối trừ vào phần giữ chờ`.

Bản nháp gộp còn chứa các dòng đã ký hết. Các dòng đó không còn trong yêu cầu
xuất mới, nên bị đưa vào phần giữ lại ngoài lần xuất. Luồng tạo file cũ dựng lại
và kiểm tra xuất cả phần giữ lại này, rồi hủy toàn bộ giao dịch khi gặp dòng cũ.
Bấm Tính lại không tự xử lý được phần giữ chờ đó.

## Thay đổi

- Đối trừ phần giữ chờ ngoài lần xuất khi có lượng đã ký xác định được và toàn
  bộ giữ chờ của dòng đó thuộc các bản nháp đang thay thế.
- Giữ nguyên phần còn lại khi có cảnh báo đối chiếu hoặc bản nháp khác còn giữ
  dòng đó. Phần này không được đưa vào ZIP.
- Kiểm tra đầy đủ nguồn đơn, lượng đã ký và tồn kho đối với các bản thật sự
  xuất file; không yêu cầu phần giữ lại ngoài lần xuất phải sẵn sàng tải.
- Lưu việc đối trừ cùng giao dịch tạo file. Lỗi tạo Excel hoàn tác cả bản nháp,
  giữ kho và lượng đã đối trừ. Tải lại không đối trừ lần thứ hai.

## Kiểm chứng

227 kiểm thử thành công:

```text
python -m unittest tdp_system.test_outgoing_upload -q
29 tests OK

python -m unittest tdp_system.test_outgoing_readiness tdp_system.test_outgoing_waiting tdp_system.test_outgoing_source_scope tdp_system.test_outgoing_export_lineage tdp_system.test_outgoing_export_receipts -q
198 tests OK
```

Dùng bản sao SQLite lấy chỉ đọc từ production và các mẫu thuế chuẩn trên volume.
Khôi phục trạng thái giữ chờ của bản nháp 932/933 trước sự kiện dọn lúc
18:45:53 ngày 15/10 trên bản sao để tái hiện: mã cũ cho 67 dòng xuất được nhưng
thất bại đúng thông báo M000002; mã mới cho 69 dòng xuất được và tạo ZIP thành công.

Đã thao tác trên Edge: Bảng kê & hóa đơn → Chỉ ATV → Xuất theo tồn · xem trước
→ tích xác nhận → tải file. Giao diện báo tải thành công, không có lỗi JavaScript.
ZIP gồm KKKNT (43 dòng sau gộp) và VAT8 (3 dòng sau gộp), mỗi file đủ 13 cột.

So sánh toàn bộ bản ghi trước/sau trên bản sao: orders, batches, products,
receivable_ledger_lines, payable_ledger_lines, invoice_inventory_ledger,
outgoing_source_invoices và outgoing_source_invoice_items giữ nguyên.

## Hóa đơn 907

Đây là việc đối chiếu riêng: hóa đơn đã ký ngày 12/10/2026, gắn đơn 9–11/10,
47 dòng đã ghép mã, trạng thái kho `ready`, chưa có bút toán xuất kho.
Bản sửa không tự xác nhận ghi kho hoặc xuất lại hóa đơn này. Cảnh báo vẫn giữ
đối với phạm vi liên quan; các dòng đủ điều kiện khác có thể tải tiếp.

Không đưa bản sao dữ liệu thật, file khách, thông tin đăng nhập hoặc ảnh kiểm
thử vào Git.
