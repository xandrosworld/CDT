# Kiểm tra toàn bộ web — 08/09/2026

**Đang thực hiện. Chưa kết luận hoàn tất toàn bộ luồng.** Đây là nhật ký có phạm vi và bằng chứng; không dùng số bài test hoặc số màn mở được để gọi hệ thống “100% không lỗi”.

## Môi trường và dữ liệu

- Source đầu đợt: `a904f5fa1362c5fa775f2b7abb5c0f617b78d18a`.
- Snapshot Railway mới: `D:/TDP_RAILWAY_PRIVATE/evidence/full-site-20260908-before/snapshot.sqlite3`, SQLite toàn vẹn. Dữ liệu và tài khoản không đưa vào Git.
- Tạo riêng environment/service/volume Railway `audit-20260908` / `tdp-audit-20260908`. Database là bản sao mới, đăng nhập riêng, có nhãn bản thử. Kết nối ngoài máy chủ bị chặn ở socket; cấu hình thật mSMI/M-Invoice không được nạp.
- Lượt ghi thử chỉ được chạy trên bản thử hoặc fixture riêng. Không khôi phục database production để xóa dấu vết thử; không ghi đè công việc khách đang làm. Chưa ký/phát hành hóa đơn hoặc gửi thông báo thật trong đợt này.
- Các lần khởi động harness ban đầu gặp lỗi chặn địa chỉ bind `0.0.0.0` và chèn nhãn vào response trực tiếp; đã sửa harness riêng. Đây không phải lỗi nghiệp vụ sản phẩm.

## Ma trận hiện tại

| Phần | Bằng chứng đã có trong đợt này | Việc còn phải xác minh |
|---|---|---|
| Đăng nhập, 12 mục điều hướng | Railway riêng: 32 màn/trạng thái ở nhiều khổ máy tính; không JavaScript exception, HTTP 5xx hoặc request ghi bị chặn | Kiểm tra production sau khi chốt sửa; mở màn không thay cho từng thao tác |
| Nhập/sửa đơn, NCC, phiếu giao | Browser vòng 2; đối chiếu 320 dòng đơn với API, NCC và file; browser sửa giá/lịch sử đạt | Luồng ghi trên bản Railway dữ liệu thật và đối chiếu sau ghi |
| Danh mục, Excel đầy đủ | Bộ test danh mục/worksheet đạt; bản sửa trước đã kiểm tra 1.255 dòng, sửa/dán/lưu/mất mạng | Rà lại đường sử dụng cùng các sửa đợt này trên Railway |
| Báo giá | Browser báo giá, xung đột và lịch sử đạt; đối chiếu phạm vi được xuất | Các nhà thầu chưa xác nhận giá không được coi là đã nghiệm thu xuất file |
| Báo cáo tháng | Đối chiếu tháng 8 và 9, bảng/API/Excel đạt | Kiểm tra tải từ Railway và từng lựa chọn còn lại |
| Phải thu/phải trả | Browser vòng 3 đạt sau sửa phép đo tương phản; vòng 4 đạt; đối chiếu chi tiết và tổng theo trạng thái đạt | Ghi/hoàn tác và kiểm tra lại trên bản Railway riêng |
| Hóa đơn đầu vào | Browser quy đổi, phân loại chi phí, hóa đơn còn chưa nhập, hộp kiểm tra/gộp/tách đạt; tháng 8 đủ 266 hóa đơn và 1.107 dòng | Đang thử Omachi, dầu hào, sữa và nhập kho trên bản sao Railway |
| Hóa đơn đầu ra | Browser ghi xuất, mất mạng/thử lại, chặn thiếu tồn; browser phân bổ từng phần đạt | Phát hành thật ra ngoài không chạy thử; ghi/hoàn tác trên dữ liệu sao chép cần kiểm tra thêm |
| Nhập–xuất–tồn | Đối chiếu hai kỳ và bốn file xuất đạt; browser bốn workbook, tìm, chuyển sheet, ngày sai/lỗi mạng/phản hồi chậm đạt | Kiểm tra các đường nhập tồn/bảng kê vừa khôi phục |
| Chốt/mở/chốt lại | Browser fixture đạt, bấm lại không cộng tồn; dữ liệu thật có bốn mã âm nên bị chặn | Không sửa số âm nguồn để làm bài thử đạt |
| Giấy tờ/in | Browser vòng 5 đạt; đối chiếu 44 sheet chứng từ đủ điều kiện | Tải/in PDF trên Railway, kiểm tra bố cục/nguồn từng mẫu; máy in vật lý không có trong môi trường QA |
| Sao lưu, lưu tự động | Tải được snapshot nhất quán; kiểm thử backend auth/backup/worksheet đạt | Bảo toàn toàn bộ bảng sau đợt kiểm tra production; xác minh lịch và phục hồi ở bản thử |

## Kết quả và lỗi đã xác định

1. Nút **Đến dòng cần sửa đầu tiên** chọn ô tích gộp thay vì ô mã sau khi thêm cột chọn. Đã sửa ưu tiên ô mã/quy đổi có thể nhập.
2. Đóng toàn màn hình xóa thanh tìm kiếm cùng nút mở lại; bảng đã có dấu đã khởi tạo nên nút không được tạo lại. Đã trả thanh tìm kiếm về bảng trước khi gỡ thanh toàn màn hình. Browser Railway riêng đã thử mở/đóng ba lần và kiểm tra focus đạt.
3. Sau lần thu gọn màn kho trước đợt này, các xử lý nạp tồn đầu/bảng kê mua vào vẫn còn nhưng mất đường mở trên giao diện. Đã thêm mục thu gọn **Nhập tồn đầu, bảng kê mua vào và lịch sử**, giữ phần báo cáo chính gọn. Chưa coi việc khôi phục nút là đã kiểm tra đủ nhập/hoàn tác.
4. Công cụ đối chiếu hóa đơn còn dùng vị trí cột cũ, và cộng cả nguồn đầu ra thử nghiệm vào tập hóa đơn thật. Đã chuyển sang nhận diện theo tiêu đề và lọc nguồn `minvoice`/tenant đang dùng; 459 hóa đơn nguồn thử vẫn được giữ riêng, không xóa hoặc gộp vào kết quả thật.
5. Một số browser cũ dừng vì kỳ vọng ô/nút đã thay đổi hoặc kiểm tra trước khi tải xong. Giữ log chưa đạt; sửa công cụ theo hành vi hiện tại và chạy lại. Không bỏ chặn nghiệp vụ để vượt test.
6. Lưu tồn đầu từng mã không giữ kỳ đã chọn khi tải lại form, khiến thao tác nạp file tiếp theo có thể quay về kỳ mặc định. Đã giữ kỳ theo form; browser `inventory-tools-06` đạt nhập lượng lẻ, chọn file bằng nút thật, xem trước/hủy/xác nhận, nạp lại không cộng trùng và hoàn tác BK.
7. Đóng Excel danh mục sau khi lưu vẫn để nút Sửa của dữ liệu cũ xuất hiện trong lúc tải lại. Bấm nhanh gây báo xung đột dù chỉ một người thao tác. Đã thay bảng cũ bằng trạng thái đang cập nhật ngay khi đóng. `trial-catalog-02` đạt sửa ô cuối trong 1.255 mã trên Railway riêng, đọc lại giá trị đã lưu, sửa trả tên qua form; mọi mã/tên/ĐVT/thuế/tên hóa đơn trở về đúng trước thử.
8. Phản ánh khách trên production lúc khoảng 12:17 ngày 08/09: nhập kho xong bị tự chuyển sang phạm vi mọi kỳ. Đọc trực tiếp API xác nhận tháng 8 có 261 hóa đơn đã nhập, 5 không nhập tồn, không còn dòng cần xử lý. Danh sách 4.776 hóa đơn còn chưa nhập thuộc 01/2022–07/2026, không phải lỗi mới sinh ra từ nhập tháng 8. Đã giữ phạm vi đang xem sau khi nhập/xuất; nút mọi kỳ ghi rõ phạm vi, thêm ngày ngay đầu bảng/toàn màn hình. Không xóa hóa đơn lịch sử hoặc ghi thêm kho để làm mất cảnh báo.

## Số liệu thực tế còn cần xử lý

Tại snapshot đầu đợt, không phải trạng thái tức thời sau khi khách làm tiếp:

- Đơn đang chọn: 320 dòng, **1 dòng lỗi / 20 cảnh báo**, còn nháp.
- Đầu vào tháng 8: **266 hóa đơn**; 253 sẵn sàng, 10 cần ghép/quy đổi, 3 không nhập tồn; chưa ghi kho. Tháng 9: 33 hóa đơn, 25 sẵn sàng, 8 cần ghép/quy đổi.
- Đầu ra tháng 8 từ nguồn thật đang lưu: **89 hóa đơn**; 53 sẵn sàng, 32 cần ghép và 4 lỗi. Có thêm 459 hóa đơn nguồn thử được loại đúng khỏi danh sách thật.
- Bốn mã tồn âm nguồn vẫn còn: `D000056` −1,5; `I000084` −14,1; `I000091` −1,5; `N000009` −3. Chốt tháng bị chặn là đúng với dữ liệu này.
- Kho thực tế có 1.255 mã chưa khai tồn. Một số phạm vi báo giá chưa xác nhận; phạm vi hồ sơ thanh toán VAT đang trả thông báo không có hóa đơn đủ điều kiện.

## Bằng chứng và cách đọc

Gốc riêng: `D:/TDP_RAILWAY_PRIVATE/evidence/full-site-20260908-*`.

- `numeric-03`: **17 nhóm đối chiếu đạt**, DB nguồn không đổi; 44 sheet chứng từ đủ điều kiện được đối chiếu nội dung với Excel tải.
- `regression-02`: 91 module / 690 bài; 689 đạt, 1 kiểm tra cấu trúc giao diện còn yêu cầu xóa form tồn đầu. Sửa kiểm tra để xác nhận form nằm trong mục thu gọn; `export-tests-03`: chạy lại cả nhóm **7/7 đạt**. Không cộng thành 697 bài độc lập.
- `regression-03`: sau các sửa thao tác tồn đầu/danh mục, **91 module / 690 bài đạt**. Sau sửa giữ phạm vi hóa đơn: hai nhóm danh sách/còn chưa nhập **16/16 đạt**; browser `customer-pending-scope-browser-01`, `customer-pending-manual-browser-01`, `customer-output-period-browser-01` đều đạt. Ghi kho theo ngày không tự gọi danh sách mọi kỳ; người dùng chủ động mở mọi kỳ vẫn xem và xử lý tiếp được.
- `rounds-01`: vòng 2/4/5 đạt; vòng 1/3 có điểm dừng được lưu. `rounds-02/round3`: đạt sau sửa phép đo tương phản. Vòng 1 cũ chưa được ghi đạt toàn bộ.
- `modern-01`: quy đổi, phân loại chi phí, danh sách còn chưa nhập, hộp kiểm tra hóa đơn và workspace đạt; hai bài kho dừng ở kỳ vọng công cụ. `modern-02` báo cáo kho đạt; `modern-03` ghi xuất/chốt kỳ/danh mục đạt sau cập nhật chờ tải.
- `extra-01`: báo giá, sửa giá/lịch sử và phân bổ thiếu tồn đều đạt.
- `surface-02`: 32 màn/trạng thái; các điều khiển lặp theo dòng hàng không được tính thành các chức năng độc lập.
- `coverage-01`: 194 tổ hợp route/phương thức, 156 có bằng chứng HTTP trong bộ unit và rà màn đang tổng hợp; 38 chưa có bằng chứng trong **hai nguồn này**. Có route cũ, module đã bỏ và route của harness. Con số này không phải tỷ lệ hoàn tất toàn bộ luồng.
- `trial-business-*`: giữ riêng từng lượt, kể cả các lượt dừng ở công cụ, thời gian tải backup hoặc kết nối. Chỉ ghi đạt trường hợp có kết quả cuối và đối chiếu dữ liệu.
- `trial-business-06`: các phần quy đổi Omachi 8 thùng → 240 gói, gộp dầu hào 24+6 → 30 can và sữa 480+40 → 520 hộp, hủy/gộp/tách giữ tiền nguồn đã đạt. Lượt ghi kho thực sự ghi vào bản thử rồi dừng khi tìm đường mở lại sau tự chuyển mọi kỳ; không chạy lại như thể chưa có ghi. Các lần sau dùng hóa đơn thử khác và lưu log riêng. Đây cũng là lý do phải đối chiếu trạng thái trước mỗi lần chạy lại.

Các phần còn trống phải được cập nhật bằng kết quả thực thi; không tự chuyển thành “đạt” theo suy đoán hoặc theo việc đã có source.

## Sửa khẩn phạm vi hóa đơn đã triển khai

Source `20e7729`, Railway deployment `2f8504ee-d4cc-49a2-9d37-3102f7c22063` **SUCCESS**. Hai lượt browser phạm vi `customer-pending-scope-browser-02` và `customer-pending-manual-browser-02` đạt sau bổ sung chuyển bộ lọc cũ về ngày đã chọn, đổi Đến ngày thoát mọi kỳ và bỏ số đếm chuẩn hóa ngày toàn lịch sử khỏi thông báo kỳ này.

`customer-pending-hosted-01` kiểm tra production chỉ đọc: bộ lọc cũ trở về tháng 8; API và màn hình khớp **266 hóa đơn, 261 đã nhập kho, 5 không nhập tồn, 0 dòng cần xử lý**, tổng **919.234.874đ**. Phạm vi ngày rõ ở toàn màn hình 1440/1024; đóng/mở và tải lại đạt, không tự yêu cầu dữ liệu mọi kỳ, không yêu cầu ghi nghiệp vụ, không JavaScript exception/HTTP 5xx. Đã xem ảnh. Kết quả này xác nhận lỗi phạm vi vừa sửa, không thay thế các phần toàn luồng còn mở ở trên.


## Sửa bảng lớn bị đơ và nhảy vị trí sau lưu

Theo phản ánh khách tiếp theo, đã sửa cơ chế dựng bảng hơn 2.000 dòng theo vùng đang cuộn, giữ toàn bộ dữ liệu/tìm kiếm; cho nhập nhiều dòng nháp, lưu không tự đổi chỗ hay giành con trỏ. Dòng đang gõ được giữ cả khi phản hồi chậm, kiểm tra phiên cũ vẫn chặn ghi đè. Source `3c2c915`, Railway deployment `4f1bc502-3911-4d55-b6ee-906291ab401a` SUCCESS; chi tiết tại README-new-2.md mục 13.44.

`mapping-large-05` đạt fixture 23.901 dòng, gồm thứ tự lưu khác thứ tự nhập, lỗi mạng, xung đột, gộp xem trước/hủy, Ctrl+F ngoài vùng đang dựng và cuộn giữ nháp/tích. `mapping-real-large-01` đạt bản sao payload thật; `mapping-stable-hosted-02` đạt trực tiếp production 4.776 hóa đơn / 23.901 dòng, 1920/1024, không ghi thử. Bốn browser quy đổi/phạm vi/kho cuối đều đạt. Hồi quy 690 bài có một marker observer cũ, đã sửa và chạy lại cả nhóm 14/14 đạt. Đây là bằng chứng cho phần sửa mới; các mục toàn luồng còn mở phía trên vẫn giữ trạng thái riêng.
