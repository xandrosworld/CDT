# Phân bổ chiết khấu hóa đơn đầu vào — 10/09/2026

Hóa đơn khách gửi: C26TDL / 17690 ngày 08/09/2026, ID 18383.

## Chức năng

- Trong Hóa đơn đầu vào, mở **Phân bổ chiết khấu** tại hóa đơn.
- Chọn dòng hưởng chiết khấu, chia theo tiền hàng hoặc nhập số tiền từng dòng.
- Hàng khuyến mại 0đ mặc định không nhận chiết khấu. Phân bổ phải khớp tổng và không làm âm tiền hàng.
- Lưu phân bổ riêng; giữ nguyên hóa đơn nguồn, tiền thuế, số lượng và quy đổi đã xác nhận.
- Sau khi lưu, dùng nút Nhập kho, chọn đúng hóa đơn trong bảng kiểm tra rồi xác nhận.
- Giá ghi kho, tổng nhập theo mã, giá vốn nhóm hiển thị và đơn giá kho trong Excel dùng giá sau chiết khấu.
- Thay nguồn/mã/quy đổi làm phân bổ cũ mất hiệu lực, phải kiểm tra lại. Không sửa phân bổ khi đã ghi kho.
- Token chống lưu theo dữ liệu cũ; lưu phân bổ và audit cùng giao dịch. Xem trước không ghi kho.

## Kết quả kiểm thử

71 tests PASS: input_discount, invoice_input_integrity, invoice_input_sync, invoice_inventory,
invoice_receipt_summary, invoice_pending_receipts, invoice_valuation, invoice_line_groups,
invoice_input_export. Có kiểm tra tiền âm/không hữu hạn/sai tổng/ID sai, phân bổ lẻ, nguồn đã
trừ CK, ghi trùng, token cũ, tenant khác, rollback khi ghi audit lỗi, Excel giữ tiền hóa đơn
nhưng xuất đơn giá kho sau CK. JavaScript syntax và git diff --check PASS.

Playwright thực hiện qua giao diện trên **bản sao riêng của dữ liệu khách**:

| Nội dung | Kết quả |
|---|---:|
| Tiền hàng trước CK | 5.792.582đ |
| CK bột canh | 113.341đ |
| CK tương ớt | 159.796đ |
| Tổng CK | 273.137đ |
| Giá trị nhập bột canh, 144 gói gồm 12 gói KM | 2.290.357đ |
| Giá trị nhập tương ớt, 312 chai gồm 24 chai KM | 3.229.088đ |
| Tổng giá trị ghi kho và phát sinh nhập trên báo cáo tồn | 5.519.445đ |

Đã kiểm tra 4 bút toán nhập, nguồn hóa đơn giữ nguyên bằng hash trước/sau, không có lỗi
JavaScript. Nhập sai tổng qua giao diện bị chặn, chưa tạo bút toán; sửa đúng mới lưu/ghi kho.

Ảnh bằng chứng và result.json nằm ở `tdp_system/exports/input_discount_test/` (không commit dữ liệu khách).
Ảnh ghi kho có nhãn BẢN SAO. Không dùng kết quả thử để khẳng định đã ghi kho trên dữ liệu thật.
