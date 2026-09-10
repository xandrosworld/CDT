# Tải bảng kê đầu vào theo các ngày đã duyệt

Thêm nút **Tải bảng kê đầu vào** trong In giấy tờ → Bảng kê và biên nhận. Các phiên đơn được chọn xuất chung một file Excel, theo thứ tự ngày; chỉ lấy lượng, đơn giá và thành tiền từ bảng kê đã ghi kho. Tải file không ghi thêm tồn kho.

API `/api/bk-import/export-approved` đọc trong một giao dịch nhất quán, loại ID trùng, kiểm tra ngày đã duyệt, nguồn đơn và dấu vết kho. Chặn phiên chưa duyệt, bảng kê chưa ghi kho hoặc dấu vết không khớp; không trả file một phần khi lựa chọn có lỗi. Các phiên không phát sinh bảng kê được bỏ qua; nếu toàn bộ không có bảng kê thì báo rõ.

Giữ nguyên chính sách khách xác nhận: KKKNT vẫn được xuất khi thiếu tồn; hàng không thuộc ngoại lệ tiếp tục kiểm tra tồn và lượng đang giữ cho các bảng xuất khác.

Kiểm thử: 118 tests PASS từ `test_batch_bk_approval`, `test_bk_import`, `test_selected_document_export`, `test_outgoing_readiness`, `test_outgoing_substitution`, `test_final_safety_regressions`. Bao gồm gộp nhiều ngày, giữ giá đã ghi dù tỷ lệ cấu hình thay đổi, tải lặp không ghi dữ liệu, chặn chưa duyệt/chưa ghi kho, kiểm tra lựa chọn; hồi quy tồn và KKKNT.

Playwright trên bản sao dữ liệu khách: bấm nút thật, tải Excel thành công, không có lỗi JavaScript. Ngày 01/09/2026, phiên 3: 10 dòng, 997.595đ, khớp bảng kê đã ghi kho. Ảnh bản sao và kết quả nằm tại `tdp_system/exports/bk_selected_test`; chỉ ảnh có tiền tố `HE_THONG_THAT` là bằng chứng chạy trên hệ thống thật.
