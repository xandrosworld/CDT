# Làm tròn đơn giá sau khi dồn mã

Nguồn giá là dòng đơn đã duyệt / dự thảo đã phân bổ. Không đối chiếu hay thay giá bằng bảng báo giá riêng. Mã ghi X trong báo giá vẫn xuất được nếu đơn đã duyệt có giá hợp lệ.

Đơn giá bình quân làm tròn đến 1 đồng (ROUND_HALF_UP); thành tiền bằng lượng xuất nhân đơn giá đã làm tròn, làm tròn đến đồng. Áp dụng cho tất cả mã; giữ nguyên quy tắc lượng Kg, phân nhóm nhà thầu/thuế và giữ tồn.

Dự thảo gộp cũ chưa gửi/chưa phát hành được cập nhật giá và tiền ngay khi tải lại. Giữ nguyên mã dự thảo, mã dòng, lượng, phân bổ số lượng về đơn và giao dịch kho; cập nhật tiền phân bổ và tổng tiền/thuế đồng bộ, có nhật ký trước/sau. Tải lại không tiếp tục thay đổi dữ liệu. Không sửa hóa đơn đã phát hành hay đã gửi M-Invoice.

Kiểm thử: 93 bài đạt gồm xuất khoảng ngày, tồn kho, thay mã, kiểm tra chứng từ và file thuế. Bổ sung hồi quy trứng gà 216,9 quả, giá nguồn 2.700/2.800, giá gộp 2.750, tiền 596.475; dự thảo cũ giá 20,5 về 21; không thay đơn/kho và tải lại không thay dữ liệu.
