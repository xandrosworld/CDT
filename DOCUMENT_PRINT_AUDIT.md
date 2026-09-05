# KIỂM TOÁN TOÀN BỘ FILE XUẤT VÀ CHỨNG TỪ IN

Ngày chốt kiểm toán: 03/09/2026
Trạng thái source: **ĐẠT CỔNG NGHIỆM THU BIỂU MẪU**
Trạng thái EXE: **ĐÃ BUILD VÀ SMOKE-TEST ĐẠT** – bản `2026.09.03.0`, one-file.

## 1. Phạm vi và nguyên tắc

- Danh mục được lấy từ toàn bộ route tải file, nút giao diện và hàm sinh workbook/DOCX trong source; không dựa vào trí nhớ.
- `Em Thành.xlsx` là chuẩn cao nhất cho tất cả biểu mẫu có trong file này. Các golden bổ sung của khách được dùng đúng cho báo giá, đề nghị thanh toán, hóa đơn thuế, kho hóa đơn, suất ăn và lương.
- Chứng từ có golden phải giữ artwork, cấu trúc bảng, màu nghiệp vụ, chữ ký, vùng in và nội dung pháp lý của golden. Không vẽ lại bằng mẫu dashboard hoặc ReportLab.
- File không có golden riêng dùng Times New Roman, đen/trắng, đường kẻ mảnh và ngôn từ vận hành tiếng Việt; chỉ giữ màu khi màu đó có trong mẫu khách hoặc mang ý nghĩa nghiệp vụ rõ ràng.
- Tất cả ngày hiển thị cho người dùng là `dd/mm/yyyy` hoặc `dd.mm.yyyy`; kỳ tháng là `mm/yyyy`.
- Cột kỹ thuật phục vụ đối chiếu phải ẩn và nằm ngoài vùng in. Không để lộ mật khẩu, payload thô, hash, mã trạng thái nội bộ hoặc thông tin đăng nhập.
- `Đơn đặt hàng NCC` là file thao tác: tải xuống, chỉnh số liệu, gửi/chụp cho NCC và nhập lại. Đây không phải chứng từ pháp lý để ghép vào PDF `In một nút`.

## 2. Nguồn chuẩn đã đối chiếu

| Nguồn chuẩn | Phạm vi |
|---|---|
| `Em Thành.xlsx` | Đặt hàng NCC, phiếu giao, bảng kê tổng, giấy biên nhận, báo cáo tổng hợp |
| `Đơn hàng 01.09.2026.xlsx` | Cấu trúc file đơn hàng hằng ngày mới nhất |
| `BÁO GIÁ TOYOTA T09-2026.xlsx` | Báo giá nhà thầu |
| `Đề nghị Thanh toán TĐP (T04.26).xlsx` | Đề nghị thanh toán và bảng tổng hợp giao nhận |
| `bosung.30.8.26/thue *.xlsx` | Bốn file tải phần mềm hóa đơn trung gian |
| `_HANDOFF/EXTERNAL_INPUTS/TĐK T8-2026.xlsx thụy.xlsx` | Tồn đầu kỳ và hình thức dẫn xuất Nhập/Xuất/NXT |
| `bosung.30.8.26/Công nợ phải trả Thành Đạt Phát.xlsx` | Công nợ phải trả lịch sử |
| Bộ file suất ăn, xưởng cơm và chấm công khách đã giao | PO xưởng cơm, hồ sơ suất ăn, bảng lương |

## 3. Kết quả từng đầu ra

| # | Đầu ra | Vai trò | Kết quả |
|---:|---|---|---|
| 1 | Đơn đặt hàng nhà cung cấp | File thao tác/tái nhập | **ĐẠT** – đúng sheet `đặt hàng`; không đưa vào PDF chứng từ |
| 2 | Phiếu giao theo bếp | Chứng từ in, golden | **ĐẠT** – giữ mẫu; chân trang bốn vùng ký là chữ/ô Excel thật, không dùng ảnh chụp |
| 3 | Bảng kê tổng hàng mua | Chứng từ in, golden | **ĐẠT** – đúng mẫu, tổng số lượng/tiền và chữ bằng tiền |
| 4 | Giấy biên nhận theo người bán/ngày | Chứng từ in, golden | **ĐẠT** – đúng mẫu pháp lý; vùng in C:H giữ trọn chức vụ/địa chỉ; A4 và A5 đều đạt |
| 5 | Báo cáo tổng hợp tháng | Chứng từ in, golden | **ĐẠT** – đúng nhóm, bếp, tổng và màu nghiệp vụ của mẫu |
| 6 | Báo giá nhà thầu | Chứng từ gửi khách, golden | **ĐẠT** – đúng Toyota golden; không còn hash/phiên bản hiện trên giấy; dấu vết nguồn nằm trong thuộc tính workbook |
| 7 | Bảng kê hàng hóa đầu ra | File kiểm tra | **ĐẠT** – 3 sheet/trang, ngày Việt Nam, đen/trắng |
| 8 | File thuế KKKNT | File tải phần mềm trung gian | **ĐẠT** – giữ đúng template khách |
| 9 | File thuế VAT 8% | File tải phần mềm trung gian | **ĐẠT** – giữ đúng template khách |
| 10 | File thuế VAT 10% | File tải phần mềm trung gian | **ĐẠT** – giữ đúng template khách |
| 11 | File VAT 10% có khuyến mại | File tải phần mềm trung gian | **ĐẠT** – giữ đúng dòng khuyến mại và ô trống bắt buộc |
| 12 | Danh sách còn thiếu hóa đơn đầu vào | File kiểm tra | **ĐẠT** – 2 sheet/trang, kỳ `dd/mm/yyyy`, ngôn từ rõ |
| 13 | Excel hóa đơn đầu vào đã kéo từ mSMI | File kiểm tra | **ĐẠT** – 3 sheet/trang; trạng thái và tính chất đã đổi sang tiếng Việt; không tác động kho |
| 14 | Đề nghị thanh toán theo nhà thầu | Chứng từ in, golden | **ĐẠT** – 1 trang A4, đúng 6 cột, số tiền bằng chữ, tài khoản và vùng ký |
| 15 | Bảng tổng hợp giao nhận theo hóa đơn | Chứng từ in, golden | **ĐẠT** – 1 trang A4; dữ liệu người mua/bán đầy đủ; tổng khớp hóa đơn |
| 16 | Tồn đầu kỳ | File kho, golden | **ĐẠT** – đúng TĐK khách và mã kho |
| 17 | Nhập trong kỳ | File kho dẫn xuất | **ĐẠT** – đúng contract kho và dấu vết nguồn |
| 18 | Xuất trong kỳ | File kho dẫn xuất | **ĐẠT** – đúng contract kho và dấu vết nguồn |
| 19 | Nhập – Xuất – Tồn | File kho dẫn xuất | **ĐẠT** – tổng nhập/xuất/tồn đối chiếu được |
| 20 | Mẫu nhập BK hàng mua không hóa đơn | File nhập liệu | **ĐẠT** – ngày Việt Nam, nguồn cố định, không công thức/người bán mẫu |
| 21 | Công nợ tổng – Phải thu | File đối soát | **ĐẠT** – đen/trắng, số liệu và kỳ đúng |
| 22 | Công nợ tổng – Phải trả | File đối soát | **ĐẠT** – đen/trắng, số liệu và kỳ đúng |
| 23 | Công nợ tổng – Thu chi | File đối soát | **ĐẠT** – ngày tạo đã đổi sang ngày Việt Nam |
| 24 | Công nợ tổng – Điều chỉnh | File đối soát | **ĐẠT** – ngày tạo đã đổi sang ngày Việt Nam |
| 25 | Công nợ tổng – Chi tiết phải trả cũ | File đối soát | **ĐẠT** – giữ số tiền khách chốt và hiện chênh lệch |
| 26 | Công nợ phải trả theo NCC | File đối soát | **ĐẠT** – 5 sheet/trang đại diện; lịch sử, thanh toán, phân bổ và hoàn tác khớp; chỉ dùng đỏ nhạt cho dòng đã đảo |
| 27 | Công nợ phải thu theo nhà thầu/bếp | File đối soát | **ĐẠT** – 3 sheet/trang đại diện; cột kỹ thuật ngoài vùng in; `Revision` đã đổi thành `Lần cập nhật` |
| 28 | PO xưởng cơm | File vận hành/in | **ĐẠT** – ngày và kỳ nguồn giá Việt Nam; cost, suất, lợi nhuận khớp |
| 29 | Đề nghị thanh toán suất ăn bản Word | Chứng từ in, golden | **ĐẠT** – 1 trang, giữ form khách, tổng tiền/tài khoản/vùng ký đầy đủ |
| 30 | Hồ sơ BOT – `BBĐC` | Chứng từ in, golden | **ĐẠT** – giữ nguyên artwork và công thức mẫu |
| 31 | Hồ sơ BOT – `ĐNTT` | Chứng từ in, golden | **ĐẠT** – giữ nguyên artwork và công thức mẫu |
| 32 | Hồ sơ BOT – `suất ăn` | Chứng từ in, golden | **ĐẠT** – giữ nguyên artwork và công thức mẫu |
| 33 | Bảng lương `LƯƠNG XƯỞNG` | Chứng từ in, golden | **ĐẠT** – đúng 16 cột khách; tạm ứng không còn `#####`; tổng lương khớp |
| 34 | Chi phí lao động theo bếp | File đối soát | **ĐẠT** – kỳ `mm/yyyy`, đen/trắng, tổng theo bếp |
| 35 | In một nút – Phiếu giao | PDF in hàng loạt | **ĐẠT** – Excel Office render trực tiếp mẫu và khối chữ ký dạng text, 2 trang A4 |
| 36 | In một nút – Chứng từ khác | PDF in hàng loạt | **ĐẠT** – bảng kê + biên nhận + báo cáo, 3 trang ở cả A4 và A5; không kèm file đặt NCC |

Không tính backup SQLite là giấy tờ để in. Ảnh/Zalo gửi NCC là bước giao tiếp sử dụng file đặt hàng, không thay thế phiếu giao, bảng kê, biên nhận hoặc báo cáo.

## 4. Bằng chứng render và kiểm tra máy

- 25 workbook đại diện và 1 DOCX được sinh từ source với dữ liệu có số lượng, thuế, công nợ, hoàn tác, lương và suất ăn.
- Microsoft Excel/Word thật đã render **48 trang** thuộc các nhóm chứng từ/file vận hành.
- Quét tự động toàn bộ vùng in: không còn ngày ISO, mã trạng thái kỹ thuật, `raw_json`, `Revision` hoặc `#####`. Chuỗi kỹ thuật phục vụ đối chiếu hóa đơn chỉ nằm ở cột ẩn ngoài vùng in.
- Manifest nhóm biểu mẫu cốt lõi: `tmp/document_print_audit_20260903/core_render_manifest.json`.
- Manifest nhóm biểu mẫu mở rộng: `tmp/document_print_audit_20260903/secondary/secondary_render_manifest.json`.
- Ảnh từng trang: `tmp/document_print_audit_20260903/pages/` và `tmp/document_print_audit_20260903/secondary/pages/`.

## 5. Cổng chất lượng cuối

| Cổng | Kết quả |
|---|---|
| Unit test toàn hệ thống | **372/372 OK** |
| `tdp_system/qc_system.py` | **OK – `"ok": true`** |
| Source `/health` trên database tạm, cổng 8877 | **HTTP 200; `ok`, `database_ready`, `schema_ready` đều true** |
| Dữ liệu thật đang dùng | Không bị dùng cho health smoke test |
| EXE one-file | **ĐẠT** – chạy trên thư mục dữ liệu sạch; `/health` HTTP 200; database `quick_check = ok`; trang chính, JavaScript và CSS đều HTTP 200 |
| Tính toàn vẹn bản phát hành | Thư mục giao chỉ có `Thanh_Dat_Phat.exe`; SHA-256 `94365A4F14BEB8029BEC67BFB9461EB144169DD8C38249126DACC4FC31EE80F1` |
| ZIP | Chưa tạo theo yêu cầu; chỉ phát hành một file EXE |

## 6. Kết luận

Toàn bộ biểu mẫu và file xuất trong phạm vi hợp đồng hiện tại đã qua đối chiếu nguồn, render Office, kiểm tra vùng in, kiểm tra ngôn từ/ngày tháng, unit test và QC. Source đạt cổng nghiệm thu biểu mẫu; EXE one-file đã được build từ source này và chạy smoke-test độc lập thành công. Bản EXE cũ được lưu trong thư mục archive để có thể phục hồi, không bị ghi đè mất.
