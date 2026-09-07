# Kiểm tra luồng hóa đơn đầu vào — 07/09/2026

Đã kiểm tra tải nguồn thật, lọc/tìm, sửa mã, quy đổi, gộp/tách, nhập kho và đối chiếu báo cáo trên bản sao Railway mới. Chức năng chạy được trong các tình huống dưới đây. **Chưa thể coi toàn bộ mã khách đã chọn là đúng mặt hàng:** có mapping cần đối chiếu, gồm cả một dòng đã đủ mã/ĐVT về mặt kỹ thuật.

## Hai ảnh khách hỏi vì sao không giống nhau

| Dòng nguồn | Trạng thái đọc từ Railway | Vì sao các ô khác nhau |
|---|---|---|
| Cá ngừ trắng 250g, 5 Hộp, 369.568đ — HĐ 47324 | Chưa có mã | Chọn đúng mã và Ghi nhớ trước; chưa xác định ĐVT kho để hiện hệ số quy đổi. |
| Cá minh thái Alaska 1kg, 1 kg, 57.143đ — HĐ 47324 | Chưa có mã | Cùng bước chọn mã; không phải thiếu nút ngẫu nhiên. |
| Bột tiêu Tây Nguyên gói 500g, 9 Gói — HĐ 5435 | Đã chọn M000048, ĐVT Kg; chưa có hệ số | Hiện ô 1 Gói = … Kg và Lưu quy đổi. Bản sao thử nhập 0,5 hiện 4,5 Kg; không lưu thay khách. |

Ảnh đầu có câu hướng dẫn cũ “Chọn mã trước; khác đơn vị sẽ hiện bước quy đổi ngay sau khi lưu.” Browser đăng nhập Railway đọc JS đang phục vụ đã có hướng dẫn mới và Chọn gộp dòng này, không còn câu đó. Chưa biết thời điểm chụp hoặc trạng thái tab trên máy khách; không kết luận khách cố tình dùng sai hay máy chủ đang phát bản cũ.

Hai dòng chưa có mã sẽ hiện Ghi nhớ. Dòng đã có mã nhưng khác ĐVT hiện Lưu quy đổi. Dòng đủ mã/hệ số có Sửa mã, Sửa quy đổi và ô chọn gộp. Bản mới vẫn hiện ô chọn bị khóa kèm lý do ở dòng chưa đủ dữ liệu.

## Kết quả kiểm tra

| Phép kiểm tra | Kết quả |
|---|---|
| Nguồn mSMI thật, tải lại hai lượt vào DB sao chép | Cả hai đủ 266 HĐ/1.107 dòng/919.234.874đ; cùng tập ID, không nhân đôi, không ghi kho. |
| Toàn bộ trạng thái của snapshot mới | 246 HĐ đủ mã/hệ số; 18 HĐ còn 32 dòng cần xử lý (21 chưa mã, 11 chờ quy đổi); 2 HĐ không nhập tồn; 0 đã nhập kho. |
| Nhập toàn bộ 246 HĐ đang đủ điều kiện kỹ thuật trên bản sao | 1.038 dòng kho; đối chiếu từng dòng nguồn và lượng/giá trị nhập của 113 mã trong báo cáo đạt. Gửi lại toàn bộ không sinh thêm bút toán. |
| Excel theo sáu tổ hợp bộ lọc | Đối chiếu lượng và tiền từng dòng với API, gồm toàn bộ 1.107 dòng, phần chưa ghép, cần quy đổi, đủ mã và đã nhập. |
| Browser bằng sự kiện bàn phím/chuột | Tìm Omachi bằng Ctrl+F; quy đổi 8 thùng thành 240 gói; hủy sửa; lưu 29 rồi sửa lại 30; sửa mã dầu hào/Bỏ sửa; sữa 480+40 gộp/tách/gộp lại. |
| Browser xác nhận cả nhóm sau thao tác thử | 249 HĐ, 1.047 dòng kho; lượng/tiền nhập của 116 mã khớp đối chiếu độc lập. Hủy không nhập; gửi lại không trùng; sửa mã sau nhập bị chặn; mở đúng chi tiết kho. |
| Sữa sau gộp và nhập trên bản sao | Excel chính một dòng 520 Hộp/2.760.000đ, sheet gốc giữ hai dòng. Kho vẫn có dấu vết từng dòng gốc. |
| Hồi quy toàn bộ | 630 bài đạt, không lỗi/thất bại/bỏ qua. |
| Browser Railway | 12 mục/16 ảnh; năm dòng khách đang hỏi khớp trạng thái API, thao tác chọn/xem trước/hủy tại bốn khổ máy tính; không request ghi nghiệp vụ. |

Số 249 chỉ thuộc bản sao sau khi thử quy đổi Omachi và ghép sữa. Không áp dụng các mapping, nhóm gộp hoặc bút toán thử lên production. Số 246 phản ánh đủ dữ liệu theo các khóa hiện có, **không chứng minh mọi mã hàng đã chọn đúng về nghiệp vụ**.

## Những mapping cần kiểm tra trước khi nhập kho

| Nguồn | Mã hiện chọn | Phát hiện / bước cần làm |
|---|---|---|
| Mì Hikari Reito Udon — HĐ 349732 và 313550 | D000015 — Cá rô phi lọc có xương | Khác loại hàng; cần Sửa mã trước. Danh mục có G000072 — Gói mì udon, cần đối chiếu đúng sản phẩm/quy cách. Không nhập hệ số để cho qua mã cá. |
| Mì Kokomi Đại 90 — HĐ 18534 | M000047 — Bột tiêu Tây Nguyên gói 500g | Khác loại hàng; danh mục có G000035 — Mì Kokomi đại 90gr/gói. Cần kiểm tra và chọn lại đúng mã trước khi lưu quy đổi. |
| Khoản tạm ứng dịch vụ — HĐ 5 | A000053 — Xương cổ heo | Không phải hàng thực phẩm để quy đổi sang Kg; cần rà cách phân loại không nhập tồn, không tự sửa số lượng hoặc ghi hàng vào kho. |
| Cá chim phi lê — HĐ 910 | D000015 — Cá rô phi lọc có xương | Cùng Kg nên hệ thống đang coi là đủ mã, nhưng khác loại cá. Cần rà mã trước nhập. Danh mục cá chim hiện có là cá chim sơ chế bỏ đầu, chưa đủ căn cứ tự đổi sang mã đó. |
| Dầu hào MISA và tương ớt MISA — HĐ 1215 | Mã đang chọn trước đây khác nhãn hàng/tên loại | Giữ phần cần đối chiếu đã nêu tại 13.36–13.38; không tự ghép tiếp hàng 0đ theo mã chưa xác nhận. |

Chưa kết luận người nào tạo các mapping này hoặc toàn bộ nguyên nhân thao tác. Lịch sử còn được giữ. Không tự thay lựa chọn nghiệp vụ trong lượt kiểm tra này. Không nên hướng dẫn khách nhập cả nhóm chỉ dựa trên số “đã đủ mã” khi các dòng khác loại hàng trên chưa được rà.

Danh sách 32 dòng có số hóa đơn, tên nguồn, mã/ĐVT đang chọn và lỗi nằm trong `D:/TDP_RAILWAY_PRIVATE/evidence/input-full-copy-01/Dong-con-can-xu-ly.xlsx`; báo cáo dữ liệu thật giữ ngoài Git.

## Bằng chứng và giới hạn

- `input-full-before-01`: snapshot Railway mới, dùng làm nguồn không sửa.
- `input-full-sync-01`: hai lần đọc mSMI thật, chỉ cập nhật DB sao chép.
- `input-full-copy-01`: đối chiếu toàn tháng, sáu file Excel, thử nhập 246 HĐ và đối chiếu kho.
- `input-full-browser-copy-03`: browser đạt 17 mục, Excel/ảnh và đối chiếu độc lập 1.047 dòng. Lượt 01 chọn nhầm G000035 làm Omachi, đã sửa dùng dòng G000031 hiện có; lượt 02 dừng vì công cụ chọn nút tra kho nằm trong phần lịch sử thu gọn, đã chỉ đúng nút ở dòng và chạy lại toàn luồng. Không sửa code sản phẩm để vượt kiểm tra.
- `input-states-hosted-02`: kiểm tra đúng năm dòng và JS trên Railway; lượt 01 cũng đạt trạng thái nhưng ảnh chưa đặt bảng toàn màn hình, lượt 02 bổ sung ảnh rõ các dòng.
- `input-full-regression-01`: bộ hồi quy. Công cụ đối chiếu browser ban đầu truy vấn nhầm tên cột ledger; sửa theo schema thật, kiểm tra lại đạt, không đổi nghiệp vụ.
- Các thư mục trên nằm dưới `D:/TDP_RAILWAY_PRIVATE/evidence`. Không ký/phát hành hóa đơn, đổi mã/quy đổi, gộp thật, nhập kho hoặc ghi nhận tiền trên Railway trong lượt này. Việc chọn đúng mã và xác nhận nghiệp vụ cho các dòng còn mở chưa được thay bằng kết quả test kỹ thuật.
- `input-full-after-02` lấy sau lượt hosted cuối: đối chiếu snapshot đầu lượt, **81/81 bảng giữ nguyên nội dung và schema**, hai DB toàn vẹn ok. Bằng chứng `full-preservation.json`. Đã cập nhật OPEN-MAPPING, ghi chú MAPPING-CORRECT và E11 trên Google Sheet; đọc lại xác nhận bảy ô mục tiêu đúng, giữ định dạng/validation và các ô khách chốt/kiểm tra/ý kiến.
