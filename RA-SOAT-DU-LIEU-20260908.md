# Rà soát dữ liệu hóa đơn và kho — 08/09/2026

Đã kiểm tra dữ liệu thật, triển khai sửa lỗi và kiểm tra lại trên Railway. Không kết luận toàn bộ nghiệp vụ đã đúng 100%: chiết khấu chưa phân bổ, một số lựa chọn mã đầu ra và số tồn đầu âm còn cần đối chiếu.

## Kết quả đã xác minh

| Phạm vi | Kết quả |
|---|---|
| Danh mục | 1.258 mã; không trùng mã sau chuẩn hóa, không thiếu tên/đơn vị |
| Hóa đơn đầu vào | 5.273 hóa đơn, 25.319 dòng; trường nguồn được kiểm tra với raw nguồn lưu tại thời điểm tải |
| Hóa đơn đầu ra đang sử dụng | 89 hóa đơn M-Invoice, 1.953 dòng; dữ liệu nguồn không bị đổi bởi sửa mã |
| Đã nhập kho | 261 hóa đơn, 1.099 bút toán; mã, lượng, giá, ngày, lần xác nhận và phiên bản quy đổi khớp giữa dòng hóa đơn và hai sổ liên quan |
| Đã xuất kho theo hóa đơn | 0 bút toán tại thời điểm kiểm tra |
| Gộp dòng | 4 nhóm hợp lệ; tổng lượng và tiền khớp các dòng gốc |
| Tồn đầu | 334 dòng, không trùng mã trong kỳ; cộng độc lập tồn đầu và phát sinh khớp báo cáo tồn |
| Tính toàn vẹn SQLite | `integrity_check = ok`; không có lỗi khóa ngoại |

Không phát hiện bút toán nhập trùng, nhập thiếu dấu vết nguồn, mã không tồn tại trong danh mục, hoặc dòng đầu vào lấy trùng mã nguồn nhưng tên khác tên/biệt danh của mã đó. Đây là kiểm tra tính nhất quán dữ liệu; không thay thế việc xác nhận hai tên hàng khác nhau có thực sự là cùng một mặt hàng.

## Lỗi mới tìm được và đã sửa

Nguồn có lượng và tiền nhưng gửi đơn giá bằng 0. Bộ đọc cũ đánh dấu nhầm 4 dòng hàng là không nhập kho. Cả 4 chưa có bút toán kho. Bản sửa khôi phục chúng về cần ghép mã, giữ nguyên đơn giá nguồn bằng 0; giá nhập được tính từ thành tiền / lượng sau quy đổi khi đủ điều kiện.

| Hóa đơn | Ngày | Dòng hàng | Lượng nguồn | Thành tiền nguồn |
|---|---|---|---:|---:|
| C26THS / 14418 | 18/06/2026 | STTT ít đường VNM 1L | 144 | 5.090.400 đ |
| C26TAA / 1611 | 15/05/2026 | Đùi gà góc tư đông lạnh | 20 | 1.140.000 đ |
| C26TAA / 1541 | 09/05/2026 | Sườn heo đông lạnh | 10 | 790.000 đ |
| C26TAA / 1258 | 15/04/2026 | Cá bống mối đông lạnh | 40 | 1.620.000 đ |

Đã kiểm tra thêm và bổ sung:

- Danh mục đổi đơn vị sau khi ghép: chặn dùng lại quy đổi cũ khi nhập/xuất kho hoặc lưu hệ số. Phải lưu lại mã và xác nhận quy đổi theo đơn vị hiện tại. Dữ liệu thật hiện chưa có trường hợp này.
- Chiết khấu/điều chỉnh chưa khớp với giá trị dòng hàng: hiện “Cần kiểm tra”, chặn cả nhập một hóa đơn và nhập hàng loạt. Không tự đặt cách phân bổ hoặc sửa thành tiền nguồn.
- Phân loại chi phí rồi chuyển lại hàng kho vẫn nhận đúng dòng có lượng/tiền nhưng thiếu đơn giá.
- Sửa dữ liệu cũ không đụng dòng đã nhập kho, dòng đã có dấu vết kho hoặc lựa chọn chi phí đã được người dùng xác nhận; chạy lại không sửa lần hai.

## Những khoản vẫn cần đối chiếu

1. **316 hóa đơn có chiết khấu/điều chỉnh chưa khớp giá nhập** trong toàn bộ lịch sử 2022–2026. Có 315 hóa đơn đến hết tháng 8 và 1 hóa đơn tháng 9; không có trường hợp thuộc tháng 8/2026. Chúng chưa nhập kho. Chưa thực hiện phân bổ chiết khấu cho các hóa đơn này; hiện hệ thống chặn ghi kho để tránh dùng giá vốn chưa đối chiếu.
2. **12 dòng đầu ra cần xác nhận tên/mã**, trên 9 hóa đơn. Không mặc định cả 12 là sai hàng. Một số tên có thể là cùng hàng nhưng khác cách ghi. Cả 9 hóa đơn đều bị loại khỏi danh sách có thể ghi xuất kho. Dòng bánh đa đỏ ướt đã sửa trước đó vẫn là **G000007**, không quay lại HT00233.
3. **4 mã có tồn đầu âm** ở kỳ 08/2026: D000056 (-1,5), I000084 (-14,1), I000091 (-1,5), N000009 (-3). Dấu âm nằm ở bút toán OPENING đã có; bản sửa này không sinh ra và không tự điều chỉnh chúng. Báo cáo định giá vẫn đánh dấu cần kiểm tra tồn đầu.
4. **16 hóa đơn đầu vào có số âm cần đối chiếu nguồn** vẫn được cách ly. Hóa đơn đầu ra 716/717 có tổng đầu hóa đơn khác tổng chi tiết; 695/696 thuộc trạng thái điều chỉnh. Chúng không được tự sửa số hoặc ghi kho để ép khớp.

Khi kiểm tra tổng tiền, phải phân biệt tổng nguồn bỏ trống và dòng chiết khấu ghi số dương với khoản tiền bị mất. Ví dụ 33 hóa đơn đã nhập có subtotal/tax nguồn bỏ trống: tổng chi tiết của cả 33 vẫn khớp tổng thanh toán nguồn. Không lấy trường subtotal được lưu là 0 để kết luận mất toàn bộ tiền hóa đơn.

## Kiểm thử và kiểm tra sau triển khai

- **139 kiểm thử / 13 bộ kiểm thử đều đạt**: đọc nguồn, ánh xạ, quy đổi, phục hồi dòng, phân loại chi phí, nhập lẻ/hàng loạt, gộp/tách, sổ kho, định giá, xuất Excel và ghép mã đầu ra.
- Luồng trình duyệt “Kiểm tra lượng & tiền” đạt trên dữ liệu thử cô lập, gồm sửa/quy đổi/gộp và kiểm tra lượng/giá sau gộp.
- Trình duyệt trên web thật kiểm tra lại 4 dòng đã khôi phục, cảnh báo chiết khấu, mã G000007 và 12 cảnh báo danh tính hàng. Không có lỗi JavaScript/HTTP 5xx; không gửi yêu cầu ghi dữ liệu nghiệp vụ trong lần kiểm tra này.
- Kiểm tra xuất kho hàng loạt chỉ dùng GET chạy thử trên bản sao trong bộ nhớ; không tạo bút toán thật.
- So sánh **85 bảng trước–sau triển khai: 81 bảng giữ nguyên hoàn toàn**. Bốn bảng thay đổi là trạng thái của đúng 4 hóa đơn, cờ phân loại của đúng 4 dòng, 4 bản ghi audit và bộ đếm audit. **Tất cả số lượng, đơn giá, thành tiền, raw nguồn, mã đã lưu, bảng quy đổi và sổ kho giữ nguyên.**

Mã triển khai: `360e39a9849dfb29f74e83e3757eead806d106c2`.
Railway deployment: `aed4b2c9-5217-4dd4-a7c0-82ccdfdde683`, SUCCESS.

Chứng cứ riêng tư lưu tại `D:/TDP_RAILWAY_PRIVATE/evidence/`: `data-integrity-deep-before`, `deep-predeploy`, `deep-postdeploy`, `deep-live`, `deep-browser-review`, `deep-regression-*`. Không đưa bản sao dữ liệu hoặc thông tin đăng nhập vào Git.
