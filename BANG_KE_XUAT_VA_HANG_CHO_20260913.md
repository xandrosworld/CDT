# Một nút xuất hóa đơn và danh sách phần còn chờ

Hai nút “Tải bảng kê để up M-Invoice” và “Tải file xuất bù đủ điều kiện” đều dùng luồng cộng dồn đơn đã duyệt, gây nhầm rằng có thể đưa cả hai bộ lên M-Invoice. Danh sách chưa xuất còn trộn phần đủ điều kiện với phần chưa đủ điều kiện.

- Giữ một nút “Tải bảng kê để up M-Invoice” ở đầu trang cho cả đơn mới và xuất bù. Dùng nguyên luồng kiểm tra tồn, ngoại lệ BK, đối chiếu hóa đơn đã ký và phân bổ hiện có.
- Dùng chung nhà thầu và mốc ngày ở đầu trang. Vào trang hoặc đổi bộ lọc sẽ nạp danh sách còn chờ; phản hồi cũ không được ghi đè bộ lọc mới.
- Tách bảng “Hàng còn chờ” chỉ gồm lượng `waiting_qty > 0`, kèm ngày đơn và lý do: tồn khả dụng, phần lẻ, đơn vị, dữ liệu dòng, hóa đơn cần đối chiếu hoặc chờ cập nhật phân bổ. Không kết luận thiếu đầu vào chỉ vì chưa có dự thảo giữ lượng.
- Tải riêng lượng còn chờ theo mẫu 13 cột, kèm workbook lý do. Bản đối chiếu toàn bộ chưa ký hóa đơn giữ trong phần mở rộng, gồm cả lượng đủ điều kiện đang giữ.
- GET và tải bản đối chiếu chỉ đọc. Không xóa đơn, không tự ghi phát hành, không thay cách trừ kho/doanh thu/công nợ.

Kiểm tra: 7 trường hợp mới cho tách lượng, file tải, bổ sung tồn, phần lẻ cộng dồn, đơn vị/BK/KKKNT, hóa đơn chưa đối chiếu và phạm vi nhà thầu/ngày; cùng các bộ catch-up, unissued, waiting, order range và readiness hiện có. Kiểm thử trình duyệt `tdp_system/qa_invoice_pending.cjs` dùng bản sao dữ liệu khách và web Railway; file tải được đối chiếu theo mã, đơn vị, giá và số lượng. Trên Railway chỉ xem và tải bảng đối chiếu; không ghi phát hành hóa đơn thử.

Yêu cầu khách bổ sung lúc 18:45 về “bảng thay thế” là luồng khác. Cần biết bảng mới thay đổi mã hàng, số lượng, đơn vị hay giá để xác định liên kết với đơn gốc và cách đối trừ. Chưa triển khai việc thay thế/xóa phần chờ khi chưa rõ các thay đổi này.
