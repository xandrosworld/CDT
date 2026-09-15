# Thêm mặt hàng mới từ file đầy đủ

Khách xác nhận Vỏ đậu hũ là mặt hàng mới. Trong file nhận, sheet BÁO GIÁ dòng 673 dùng M000358 cho Vỏ đậu hũ nhưng sheet danh mục hh dòng 1254 và danh mục trên web dùng M000358 cho Hạt nêm KNORR 5KG. M000359 được kiểm tra chưa sử dụng trên web và trong toàn bộ file; bản sửa dùng mã này cho Vỏ đậu hũ, ĐVT Gói, thuế 8%, thêm vào danh mục và đồng bộ mã tham chiếu báo giá. Không sửa tên hay mã của Hạt nêm.

Nạp toàn bộ danh mục trước đây còn chặn bởi H000002 (Cái/Kg), M000318 (Hộp/Chai), N000009 (Bộ/Bó) đã có dữ liệu sử dụng. Bước nạp danh mục nay mặc định chọn chức năng new_only đã có ở backend: chỉ thêm mã chưa có, giữ nguyên mọi trường của mã cũ. Hai phạm vi cập nhật cũ vẫn có thể chọn riêng. Nạp lại không có mã mới sẽ hiển thị lý do và không cho bấm xác nhận rỗng.

41 kiểm tra qua: catalog_invoice_labels 13, daily_catalog_capture 12, catalog_product_create 10, invoice_unit_catalog 6. Trường hợp mới kiểm tra nạp file có dòng cũ khác đơn vị, bảo toàn mã cũ và giao dịch, nạp lại không trùng, mã mới trùng xung đột vẫn bị chặn. Trình duyệt trên bản sao nạp đúng file đã sửa: 1 mã mới, 0 lỗi, 0 cập nhật mã cũ; đọc lại đủ 1.267 mã và giữ nguyên 1.266 mã trước đó.

Bản Excel sửa bằng thay đúng 10 ô trong hai sheet; các thành phần khác trong file ZIP/XLSX được đối chiếu giống nguyên bản từng byte. File gốc được giữ nguyên. Bản báo giá đã xác nhận trên web vẫn giữ phiên bản và giá cũ; thao tác này chỉ thêm danh mục.
