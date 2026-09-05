# BIÊN BẢN TRẠNG THÁI BÀN GIAO KỸ THUẬT TĐP

Ngày chốt: 03/09/2026
Phạm vi: hợp đồng hiện tại và các đính chính đã ghi trong `README-new.md`; không gồm nội dung của `C:\Users\DELL\Downloads\Phần làm thêm.docx`.

## 1. Kết luận

Đợt nghiệm thu hiện tại đã được đính chính sau khi đọc lại đầy đủ nguồn khách: **BK và bộ bốn file TĐK–Nhập–Xuất–NXT không còn thiếu dữ liệu/mẫu và không được coi là câu hỏi phải gửi khách**. Source cuối, luồng M-Invoice đầu ra, kiểm thử, QC, browser, build, smoke EXE và database portable đều đã đạt cổng kỹ thuật của phạm vi hợp đồng hiện tại.

Gói dưới đây là baseline đã tạo **trước đính chính**, chỉ giữ làm lịch sử và không còn là gói bàn giao cuối:

`BAN_GIAO_TDP_20260903_FINAL`

File nén lịch sử: `BAN_GIAO_TDP_20260903_FINAL.zip`, kích thước `83,917,950` byte, SHA-256 `229B2E93C38FD732FADDA201EF8B9E0CA589C062A2BE7991FD3052093928D5AC`.

Không chuyển gói lịch sử này cho khách như bản 100%. Gói bàn giao hiện hành là `BAN_GIAO_TDP_20260903_100PCT`; checksum của từng file nằm trong `SHA256SUMS_TDP_20260903_100PCT.txt`, còn checksum ZIP được ghi tại mục 27 của `README-new.md` và log phát hành cuối của `BIG_PLAN_TDP.md` để tránh vòng lặp checksum tự tham chiếu trong chính gói.

Không dùng thư mục `_STAGING_KHONG_BAN_GIAO_TDP_20260903` vì đó là thư mục staging trung gian.

Chủ dự án đã xác nhận các khay in được cấu hình đầy đủ và yêu cầu không tiếp tục coi phần máy in là việc còn thiếu. Vì vậy máy in/khay không còn là blocker kỹ thuật; ký nhận giấy nếu có là bước vận hành/bàn giao riêng.

### 1.1. Bằng chứng bản cuối

- Full regression: `364/364` test đạt, không skip; `Ran 364 tests in 169.508s`, kết thúc `OK`.
- QC hệ thống: exit code 0, `ok=true`; toàn bộ gate nghiệp vụ, mẫu golden, BK, bộ bốn file TĐK–Nhập–Xuất–NXT, mSMI đầu vào, M-Invoice đầu ra, công nợ, xưởng cơm và chấm công/lương đều đạt.
- Browser QC độc lập trên Edge/CDP và database tạm: exit code 0, 13 màn hình, 408 dòng workbook, 334 mã tồn đầu, 205 dòng chấm suất, 6.020 suất, luồng in dry-run và draft đầu ra đều đạt; `browserErrors=0`. Xác nhận phát hành cục bộ đã được chứng minh chỉ khóa draft/giữ hold và không đổi tồn canonical.
- Source smoke cổng tạm `18770`: `/health` xanh, chỉ listen `127.0.0.1`, nguồn đầu vào `msmi`, đầu ra `minvoice`, xuất được BK, NXT và đúng bốn file kho.
- EXE smoke cổng tạm `18774`: `/health` xanh, integrity `ok`, chỉ listen `127.0.0.1`; cả hai lỗi connector giả được trả fail-closed `HTTP 502`, `ok=false`, `read_only=true` mà tiến trình không crash.
- Render Excel COM: BK và NXT đều một trang ngang, `fitToWidth=1`, không `####`, không công thức, hyperlink hoặc external link; NXT hiển thị tách biệt Mã TĐP và Mã kho.
- Dry-run migration trên online backup của database thật: `migration_passed=true`, 10/10 check đạt, integrity `ok`, khóa ngoại 0 lỗi, mọi bước sẵn sàng đều idempotent và database nguồn giữ nguyên hash.
- EXE hiện hành: `TDP_Server.exe`, kích thước `77.082.006` byte, SHA-256 `76F023D61BC65B8C799A7F713C2C7DD1460665325F21E833939BA5C64F8B9FEB`.
- Database portable đã migration: kích thước và checksum được khóa trong manifest; SHA-256 `96705D3BCD74FC0C181190315CA9F10DF6BFFF3D3EF63FE1BB327C7CA5769708`, integrity `ok`, khóa ngoại 0 lỗi; 334 mã tồn đầu có Mã kho, gồm 113 mã kho khác Mã TĐP và 43 mã có nhiều mã kho.
- Database vận hành thật không bị ghi trong toàn bộ đợt chốt: SHA-256 trước/sau `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF`.

Ngoại lệ dữ liệu nguồn được giữ fail-closed: `SUẤT ĂN T3-2026 .xlsx`, ô `E33` có giá trị `125000` mâu thuẫn với số suất `125` tại `D33`. File tháng 03 phải được người có thẩm quyền sửa đúng nguồn trước khi nhập; hệ thống không tự đoán hoặc tự sửa. Điểm này không chặn dữ liệu tháng 08 và bản phát hành hợp đồng hiện tại.

## 2. Phạm vi đã chốt trong bản này

- Giữ đầy đủ luồng đơn hàng, nhà cung cấp, mua/giao, kho, báo giá, công nợ phải thu/phải trả và biểu mẫu.
- Giữ Xưởng cơm/PO và Chấm công/lương.
- mSMI là nguồn kéo hóa đơn đầu vào; M-Invoice là nguồn/luồng hóa đơn đầu ra theo cấu hình hiện có.
- Sau khi kéo hóa đơn đầu vào có thể xuất ngay file Excel ba sheet mà không tác động kho.
- Dòng có cờ `bk` là đầu vào TĐP theo bảng kê mua vào không có hóa đơn. Hệ thống cấp file mẫu; giá nhập mặc định bằng 95% giá bán của chính dòng và chỉ ghi tăng kho sau preview/xác nhận có audit, chống trùng.
- Xuất chính thức bốn file TĐK, Nhập, Xuất và NXT từ golden `_HANDOFF/EXTERNAL_INPUTS/TĐK T8-2026.xlsx thụy.xlsx`; bốn file dùng cùng kỳ/cùng projection và phải thỏa `Tồn đầu + Nhập − Xuất = Tồn cuối`.
- Đề nghị thanh toán và Bảng tổng hợp giao nhận được xuất bằng hai file XLSX chính thức theo workbook khách cung cấp; dữ liệu chỉ lấy từ hóa đơn đỏ đã phát hành đúng nhà thầu/kỳ.
- Không triển khai nội dung của `Phần làm thêm.docx`.

## 3. Bằng chứng baseline trước đính chính

- Full regression: `327/327` test đạt, `Ran 327 tests in 158.001s`, kết thúc `OK`.
- QC: exit code 0, `ok=true`; gồm hai gate `inputInvoiceImmediateExcelExport` và `invoicePaymentOfficialDocuments`.
- Kiểm tra tĩnh: JavaScript syntax, Python compile và `git diff --check` đạt; chỉ có cảnh báo line ending LF/CRLF đã biết.
- Source đang chạy tại `127.0.0.1:8765`: `/health ok=true`, database/schema ready, integrity `ok`, không có cảnh báo trùng hóa đơn/phải trả.
- Database trong gói: `PRAGMA integrity_check = ok`, `foreign_key_check = 0` lỗi.
- Smoke đúng EXE trong gói trên database tạm, cổng `18767`: health xanh; chỉ listen `127.0.0.1`; UI có route xuất Excel đầu vào và tải Đề nghị thanh toán + BK; API trả đúng mã lỗi an toàn cho phạm vi giả. Tiến trình smoke đã dừng sau kiểm tra.
- Microsoft Excel COM đã render Đề nghị thanh toán ở quy mô 1 và 29 hóa đơn; Bảng tổng hợp giao nhận ở quy mô 2 và 100 dòng. Header lặp, tổng tiền, ngày, vùng ký, khổ A4 và footer nhiều trang đạt kiểm tra hình ảnh.

Các số trên chứng minh baseline cũ, không thay thế bằng chứng bắt buộc cho source sau đính chính. Biên bản cuối phải ghi lại số test mới, kết quả QC mới, render BK/NXT, `/health`, smoke EXE và hash artifact mới; không được tái sử dụng số `327/327` để tuyên bố bản mới đã đạt.

## 4. Định danh artifact lịch sử – không dùng làm bản cuối

| File | Kích thước | SHA-256 |
|---|---:|---|
| `TDP_Server.exe` | 76,987,185 byte | `FB550D6FA2FB5B995DF1BC9F41202FB9D0E84C6138E3D249CD419DCC24994ADA` |
| `data/tdp.sqlite3` | 50,409,472 byte | `3E94FBE254098E354A3D75F6E2AD0BEBDF8D36FC8E1EE34B5089D619D19B592F` |
| `HUONG_DAN_SU_DUNG.txt` | 34,626 byte | `521B0E63D5780FC89BA6E11CD5A8C959EE633A4D7F55B2266D3ED81C74855639` |
| `MO_HE_THONG_TDP.bat` | 213 byte | `53841D0AA8B566CC82AEEADDADD59FB8EB25E60F6455FC6BA47E1826192E2534` |

Database trong gói được tạo bằng SQLite online backup từ database source; không chép nóng file đang mở.

## 5. Cấu hình và an toàn bí mật

- Gói sạch không chứa `.env`; chỉ chứa `.env.example`.
- `.env` đang vận hành trong source và `BAN_PC_TDP` được giữ nguyên, không bị sửa/xóa và không có giá trị nào được in/log trong quá trình nghiệm thu.
- Khi cài tại máy khách, người có quyền phải tự đặt `.env` thật cạnh EXE hoặc sao chép cấu hình hiện có bằng kênh nội bộ an toàn. Không gửi `.env` qua chat/email công khai.
- Gói không chứa thư mục/file `exports`; không kèm file xuất cũ, ảnh QC, workbook khách hay EXE cũ.

## 6. Kiểm tra vận hành trên máy bàn giao

1. Đặt `.env` thật cạnh `TDP_Server.exe` bằng kênh bảo mật.
2. Chạy `MO_HE_THONG_TDP.bat`, mở `http://127.0.0.1:8765` và kiểm tra `/health` xanh.
3. Kéo thử hóa đơn đầu vào mSMI read-only, tải Excel ngay sau khi kéo; không post kho trong bước nghiệm thu kết nối.
4. Kéo thử hóa đơn đầu ra M-Invoice read-only, kiểm tra mapping trạng thái phát hành/hủy/thay thế; trạng thái không rõ không được trừ kho.
5. Tải mẫu BK, preview và xác nhận trên dữ liệu nghiệm thu; kiểm tra giá mặc định 95%, ghi tăng kho đúng một lần và reversal có audit.
6. Tải đủ TĐK, Nhập, Xuất và NXT của cùng một kỳ; đối chiếu từng mã và tổng kỳ theo `Tồn đầu + Nhập − Xuất = Tồn cuối`.
7. Chọn một nhà thầu/kỳ có hóa đơn đỏ đã phát hành, tải Đề nghị thanh toán + Bảng tổng hợp giao nhận và đối chiếu tổng.
8. Cấu hình Canon/khay đã được chủ dự án xác nhận xong; không lặp lại phần này như một blocker kỹ thuật.

## 7. Trạng thái các điểm từng bị coi là còn mở

- **BK – đã khóa, không hỏi khách:** cờ `bk` là đầu vào TĐP; hệ thống cấp mẫu; giá mặc định 95% giá bán và confirm mới ghi tăng canonical ledger. Kết luận cũ rằng chỉ được preview là giả định quá thận trọng, nay đã bị thu hồi.
- **NXT – đã khóa, không hỏi khách:** golden TĐK tháng 08/2026 đủ căn cứ để sinh chính thức bộ bốn file. Việc `Em Thành.xlsx` không có sheet tên NXT không tạo ra blocker.
- **Máy in/khay – đã đóng:** chủ dự án xác nhận đã cấu hình; không phải blocker kỹ thuật.
- **M-Invoice đầu ra – đã hoàn tất kiểm chứng kỹ thuật:** connector chỉ-read, paging/cursor, ánh xạ trạng thái, fail-closed, mapping, ghi kho và reversal đã đạt unit/integration test cùng live probe chỉ-read. Đây không còn là câu hỏi bắt khách chọn lại nguồn.
