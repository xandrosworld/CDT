# BIG PLAN – ĐẠI CẬP NHẬT HỆ THỐNG THÀNH ĐẠT PHÁT

> Ngày lập: 02/09/2026
>
> Trạng thái: **ĐÃ HOÀN TẤT SOURCE ĐÍNH CHÍNH BK–NXT–M-INVOICE VÀ CỔNG PHÁT HÀNH EXE/GÓI BÀN GIAO CUỐI; MÁY IN/KHAY ĐÃ ĐƯỢC CHỦ DỰ ÁN XÁC NHẬN ĐÓNG**
>
> Nguồn yêu cầu chính: `README-new.md`
>
> Golden reference biểu mẫu: `Em Thành.xlsx`

## 1. Mục đích của Big Plan

Big Plan này là bộ điều khiển cho **Goal A – hoàn thiện source đã kiểm chứng**. Sau khi chủ dự án duyệt và bật Goal, Goal phải tự chạy lần lượt từng task trong cùng một chat/workspace: chọn task đủ điều kiện, triển khai, kiểm thử, tự review, cập nhật bằng chứng vào file này rồi tự chuyển sang task tiếp theo. Người dùng không phải gõ `tiếp` sau mỗi task.

Big Plan không phải lệnh cho phép Goal tự suy đoán nghiệp vụ. Điểm nào chưa đủ căn cứ phải được ghi vào mục **Quyết định còn mở**. Goal được phép tiếp tục các task độc lập khác; chỉ dừng xin quyết định khi điểm mở chặn mọi đường an toàn còn lại hoặc có nguy cơ làm sai dữ liệu/tài chính/pháp lý.

Goal A kết thúc ở source candidate đã qua TDP-113. `TDP-100` (hosting) vẫn là phạm vi riêng. `TDP-114` đã đóng bằng full regression/QC/browser/source smoke, build, EXE smoke và gói portable cuối. `TDP-115` không còn là blocker: chủ dự án đã xác nhận khay in được cấu hình đầy đủ và yêu cầu đóng phần kiểm tra máy in trong nghiệm thu kỹ thuật hiện tại.

## 2. Thứ tự ưu tiên nguồn khi có mâu thuẫn

Không dùng quy tắc mơ hồ “file mới hơn luôn thắng”. Mỗi nguồn chỉ có thẩm quyền trong đúng vai trò của nó:

1. **Phạm vi và cách hiểu cuối:** đính chính trực tiếp mới nhất của chủ dự án được ghi trong `README-new.md`.
2. **Hình thức biểu mẫu chung:** `Em Thành.xlsx` là golden reference bắt buộc cho tên/thứ tự cột, sheet, tách/gộp, tiêu đề, câu chữ, style, vùng ký và vùng in.
3. **Contract đầu vào hằng ngày:** `C:\Users\DELL\Downloads\Đơn hàng 01.09.2026.xlsx` chỉ có quyền xác định workbook khách sẽ nạp và các phần thay đổi hằng ngày; nó không được dùng để thay mẫu của bốn sheet output cố định.
4. **Báo giá đã tách:** `C:\Users\DELL\Downloads\BÁO GIÁ TOYOTA T09-2026.xlsx` là golden cụ thể hơn cho output báo giá Toyota. Dữ liệu giá vẫn phải lấy từ nguồn báo giá đúng kỳ.
5. **Hồ sơ thanh toán:** `C:\Users\DELL\Downloads\Đề nghị Thanh toán TĐP (T04.26).xlsx` là golden chính thức cho Đề nghị thanh toán sáu cột và Bảng tổng hợp giao nhận mười cột; dữ liệu kỳ cũ/công thức ngoài không phải nguồn số liệu.
6. **Yêu cầu chữ và ảnh:** `C:\Users\DELL\Downloads\Note công việc.docx`; phần chữ chốt hành vi, ảnh golden chốt hình thức, ảnh locator chỉ chỉ vùng cần sửa.
7. **Nền kỹ thuật/lịch sử:** `MASTER_PROMPT_CHUYEN_MAY_2026-09-01.md`, tài liệu `_HANDOFF`, `BIEN_BAN_CHOT_YEU_CAU_DEMO_2026-08-28.md`, `tdp_system/HUONG_DAN_SU_DUNG.txt`.
8. Source hiện tại và EXE cũ chỉ là hiện trạng kỹ thuật; không được dùng để phủ nhận mẫu khách đã chốt.

Quy tắc ưu tiên đặc biệt:

- Nếu đầu ra hệ thống khác `Em Thành.xlsx` mà không có yêu cầu mới hơn cho phép khác, **hệ thống là phần sai**.
- Xưởng cơm/PO và Chấm công/lương **vẫn bắt buộc giữ**; không dùng ảnh 14 trong Word để xóa/ẩn hai module.
- File báo giá Toyota là chuẩn hình thức báo giá đã tách; dữ liệu giá phải lấy từ nguồn báo giá đúng kỳ, không nhập ngược từ file output.
- Ảnh trong Word là một phần đặc tả. Ảnh golden dùng để nghiệm thu; ảnh locator chỉ chỉ ra màn/vùng cần sửa.
- Khi hai nguồn có vai trò khác nhau, phải kết hợp chúng thay vì chọn một và bỏ một. Ví dụ: file ngày quyết định dữ liệu input, còn `Em Thành.xlsx` quyết định hình thức output.
- Tin nhắn khách ngày 02/09/2026 lúc 10:56–10:59 đổi **thứ tự thi hành**, không đổi ranh giới nguồn: sau baseline phải làm trước màn tải hóa đơn đầu vào + đầu ra theo `từ ngày–đến ngày`, khớp mã và đối chiếu trừ kho cho tháng 08/2026. Các luồng đơn hàng/NCC/công nợ vẫn giữ nguyên phạm vi và thực hiện sau lát ưu tiên này.
- Đính chính cuối ngày 03/09/2026: cờ `bk` là đầu vào TĐP; hệ thống cấp mẫu import và dùng giá nhập mặc định bằng 95% giá bán của chính dòng. Golden TĐK đã đủ để sinh chính thức bốn file TĐK–Nhập–Xuất–NXT. Không được mở lại hai nội dung này thành câu hỏi cho khách.
- Nguồn hóa đơn đã chốt là mSMI đầu vào và M-Invoice đầu ra. Connector M-Invoice chỉ-read, schema, paging/cursor và mapping trạng thái đã được kiểm chứng kỹ thuật; Q-011 đã đóng, trạng thái không rõ vẫn fail-closed.

## 3. Ranh giới an toàn không được phá

1. Không `reset`, `checkout`, xóa, ghi đè hoặc làm mất thay đổi local đang có.
2. Source trong snapshot mới hơn EXE. Không sửa trực tiếp `BAN_PC_TDP/TDP_Server.exe` hoặc `dist/`.
3. Không build/copy EXE cho đến task phát hành cuối và có chỉ đạo rõ của chủ dự án.
4. Không in/log/đưa vào báo cáo giá trị `.env`, token, tài khoản, mật khẩu hoặc CCCD.
5. Không sửa workbook/Word/PDF gốc của khách. Mọi phân tích và fixture phải dùng bản sao hoặc đọc chỉ-read-only.
6. Không sửa database thật nếu chưa tạo backup bằng SQLite backup API hoặc dừng server và sao lưu đúng file đích.
7. Migration phải thử trước trên database tạm/bản sao, có `PRAGMA integrity_check = ok` và có đường nâng cấp idempotent.
8. Không dùng file đặt NCC để sửa đơn khách, lượng giao, doanh thu hoặc công nợ phải thu.
9. Không trộn công nợ vận hành với chứng từ chính thức theo hóa đơn đỏ.
10. Kho hóa đơn/sổ sách chỉ giảm khi hóa đơn đỏ đầu ra đã phát hành/được đối chiếu hợp lệ; draft, đơn giao và đơn đặt không được tự giảm kho này.
11. Không âm kho hóa đơn; cho phép xuất từng phần và giữ phần thiếu cho vòng sau.
12. Không tự đoán mã hàng, hệ số quy đổi, CCCD, nhà cung cấp, mặt hàng thay thế, giá ngày hoặc giá theo nhà thầu.
13. Không tự gửi Zalo, tự in, tự ký hoặc tự phát hành hóa đơn.
14. GIANHAPTAY và YLKHAN dùng giá đúng ngày; không kế thừa giá nhà thầu/ngày khác.
15. Các cảnh báo dữ liệu có chủ đích không được “sửa” bằng cách bịa giá hoặc tự điền thông tin.
16. Không commit, tag, push, tạo PR, upload, deploy hoặc thay đổi hệ thống bên ngoài nếu chủ dự án chưa yêu cầu rõ.
17. Goal A không gọi API production chứa dữ liệu hóa đơn thật trong test tự động. mSMI/M-Invoice dùng mock/fixture hoặc database tạm; kiểm tra live read-only chỉ thực hiện khi có chỉ đạo riêng và không log payload nhạy cảm.
18. Không tiếp tục làm phình `tdp_system/contract_modules.py` bằng các khối nghiệp vụ lớn. Chức năng mới ưu tiên module chuyên trách nhỏ, có contract/test riêng; không refactor toàn bộ monolith nếu task không cần.
19. `C:\Users\DELL\Downloads\Phần làm thêm.docx` nằm ngoài đợt nghiệm thu hợp đồng hiện tại theo chỉ đạo ngày 03/09/2026; không tự triển khai bất kỳ nội dung nào từ file này.

## 4. Baseline đã xác nhận trước khi lập kế hoạch

Ngày 02/09/2026:

- Worktree có nhiều thay đổi local cần bảo toàn.
- `.env` tồn tại; đã kiểm tra đúng 19 tên biến, không đọc/hiển thị giá trị.
- `python -m unittest discover -s tdp_system -p "test_*.py"`: **97/97 đạt**.
- `python -m tdp_system.qc_system`: **QC `ok=true`**.
- Source local `/health`: `ok=true`, `database_ready=true`, `schema_ready=true`, `integrity=ok`.
- Database nguồn chuẩn: `tdp_system/data/tdp.sqlite3`.
- Source chính: `tdp_system/server.py`, `tdp_system/contract_modules.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/static/real.css`.
- Các module in/PDF/API đang có regression test; không được phá để làm nhanh biểu mẫu mới.

## 5. Quy ước trạng thái task

- `[ ]` Chưa bắt đầu.
- `[~]` Đang thực hiện; chỉ một task được ở trạng thái này.
- `[x]` Hoàn thành và có bằng chứng kiểm thử.
- `[!]` Bị chặn bởi một quyết định/đầu vào cụ thể; ghi ID quyết định và tiếp tục task độc lập khác nếu an toàn.
- `[-]` Chủ dự án quyết định loại khỏi phạm vi; phải ghi ngày và lý do, không tự gán.

Ngoại lệ trạng thái hiện hành: phiên sửa triệt để ngày 03/09/2026 được điều phối song song cho TDP-082 và TDP-083, nên hai task có thể cùng mang `[~]`. Quy tắc một task `[~]` vẫn áp dụng cho các lượt Goal tuần tự thông thường.

Mỗi task chỉ được đánh dấu `[x]` khi đủ cả bốn điều kiện:

1. Code/schema/UI theo đúng phạm vi task.
2. Test mới cho yêu cầu và test hồi quy liên quan đều đạt.
3. Goal tự review diff, kiểm tra không làm lộ bí mật/PII và không làm thay đổi dữ liệu ngoài ý muốn.
4. Ghi bằng chứng ngắn vào **Nhật ký hoàn thành** ở cuối file này.

## 6. Vòng lặp tự động bắt buộc của Goal

Với mỗi task, Goal phải tự thực hiện chu trình sau mà không chờ người dùng bấm Enter:

1. Đọc lại task, dependency, quyết định còn mở và phần liên quan trong `README-new.md`.
2. Kiểm tra `git status --short`; bảo toàn mọi thay đổi ngoài task.
3. Chuyển task từ `[ ]` sang `[~]` trong file này.
4. Viết hoặc cập nhật test trước/đồng thời với implementation.
5. Triển khai lát dọc nhỏ nhất đủ dùng: schema/domain → API → UI/output → test.
6. Chạy test mục tiêu; nếu fail thì tự phân tích, sửa và chạy lại.
7. Chạy tập regression gần nhất với module bị sửa.
8. Tự review diff theo tiêu chí dữ liệu, tài chính, idempotency, bảo mật và tương thích ngược.
9. Với output Excel/PDF: kiểm tra ba lớp dữ liệu, cấu trúc workbook và render trực quan so với golden.
10. Ghi bằng chứng; đánh dấu `[x]` nếu đạt hoặc `[!]` nếu thật sự thiếu quyết định.
11. Tự chọn task `[ ]` tiếp theo có dependency đã đạt và tiếp tục bằng một lượt/message mới trong cùng Goal.

Nếu một task quá lớn cho một lượt an toàn, Goal giữ task ở `[~]`, ghi checkpoint và tự tiếp tục chính task đó ở lượt kế tiếp. Không gom thêm task khác vào cùng lượt và không đánh `[x]` chỉ vì đã xong một phần.

Goal chỉ dừng khi:

- Tất cả task trong phạm vi của Goal đang chạy đã `[x]`, `[!]` hoặc `[-]` và điều kiện kết thúc của Goal đó đã đạt.
- Một quyết định bên ngoài chặn toàn bộ task còn lại.
- Cần quyền mới hoặc hành động phá hủy/ghi dữ liệu thật/build/phát hành chưa được cho phép.
- Chủ dự án pause hoặc thay đổi Goal.

## 7. Kiến trúc nguồn dữ liệu phải giữ xuyên suốt

| Sổ/đầu ra | Nguồn đúng | Tuyệt đối không lấy từ |
|---|---|---|
| Đơn khách, phiếu giao | Sheet ngày + lượng thực giao | File đặt NCC |
| Doanh thu, phải thu vận hành | Lượng thực giao × giá bán giao dịch đúng kỳ/nhà thầu | Giá mua, kho hóa đơn |
| Đặt NCC | Nhu cầu mua sau người dùng kiểm tra tồn tủ và chốt điều chỉnh | Toàn bộ lượng khách đặt một cách máy móc |
| Giá vốn, phải trả NCC | Số lượng mua/thực nhận hợp lệ × giá mua chốt | Giá bán, công nợ phải thu |
| Bảng kê thu mua/biên nhận người bán | Dòng mua/BK đã chốt + người bán/CCCD + số lượng thực nhận/giá mua | Phải thu vận hành, hóa đơn bán ra |
| Nhập kho hóa đơn | Hóa đơn đầu vào đã ghép mã và quy đổi ĐVT | Đơn đặt NCC chưa có chứng từ |
| Xuất kho hóa đơn | Hóa đơn đỏ đầu ra đã phát hành/đối chiếu | Draft, phiếu giao, đơn khách |
| Bảng kê giao hàng/đề nghị thanh toán chính thức | Hóa đơn đỏ đầu ra đã phát hành của đúng nhà thầu | Phải thu vận hành chưa xuất hóa đơn, bảng kê thu mua |
| Giá bán hàng thay thế | Báo giá đúng kỳ/nhà thầu hoặc override được duyệt | Giá vốn bình quân/giá nhập kho |

## 8. Danh sách task theo thứ tự thực hiện

### Làn ưu tiên khẩn theo tin nhắn 02/09/2026

Các giai đoạn bên dưới vẫn nhóm task theo miền nghiệp vụ, nhưng thứ tự chạy Goal A phải tuân theo ngoại lệ mới nhất sau:

1. Hoàn thành TDP-000, TDP-001 và TDP-002.
2. Chạy lát dọc hóa đơn–khớp mã–kho: `TDP-069 → TDP-070 → TDP-074 → TDP-071 → TDP-072 → TDP-073 → TDP-080 → TDP-081`.
3. Chứng minh trên fixture/bản sao rằng khoảng `2026-08-01`–`2026-08-31` thỏa `Tồn đầu + Nhập − Xuất = Tồn cuối`, đồng bộ lại không nhân đôi và không âm kho.
4. Sau đó quay lại TDP-010 và tiếp tục các task còn lại theo dependency.

Không dùng ưu tiên này để gọi API production, ghi database thật hoặc bỏ qua bước người dùng xác nhận mapping/post kho trong Goal A.

### Giai đoạn 0 – Khóa đặc tả và bộ QC golden

#### [x] TDP-000 – Khóa baseline và bộ bảo vệ dữ liệu

- Phụ thuộc: không.
- Mục tiêu: biến baseline ở mục 4 thành kiểm tra lặp lại được trước/sau mỗi milestone.
- Thực hiện:
  - Ghi nhận danh sách file local đã thay đổi nhưng không đưa nội dung nhạy cảm vào log.
  - Xác định rõ mọi test/QC đang dùng database tạm hay database nguồn.
  - Tạo helper/fixture chỉ khi cần để đảm bảo test mới không ghi database thật.
  - Ghi lệnh baseline chuẩn cho Windows UTF-8.
- Kiểm thử: 97 test, QC và `/health` vẫn xanh; hash database nguồn không đổi sau test không có chủ đích migration.
- Hoàn thành khi: có bằng chứng baseline tái lập và không có file khách/database thật bị sửa.

#### [x] TDP-001 – Lập manifest golden reference có hash và vai trò rõ ràng

- Phụ thuộc: TDP-000.
- Nguồn tối thiểu:
  - `Em Thành.xlsx`.
  - `Đơn hàng 01.09.2026.xlsx`.
  - `BÁO GIÁ TOYOTA T09-2026.xlsx`.
  - `Note công việc.docx` và 15 ảnh.
  - Bộ `bosung.30.8.26/thue *.xlsx`.
  - `bosung.30.8.26/Công nợ phải trả Thành Đạt Phát.xlsx`.
- Thực hiện:
  - Lưu manifest nội bộ: đường dẫn, SHA-256, sheet, used range, merged cells, print area, orientation, paper size, repeat rows/columns, hidden state, công thức/external links.
  - Phân loại từng file là input, output golden, reference-only hay dữ liệu lịch sử.
  - Không chép CCCD hoặc dữ liệu dòng hàng vào manifest công khai.
- Kiểm thử: chạy lại manifest cho cùng file cho kết quả ổn định; hash nguồn không đổi.
- Hoàn thành khi: mọi task biểu mẫu phía sau có thể chỉ tới một golden cụ thể, không nói chung chung “giống Excel”.

#### [x] TDP-002 – Tạo harness so sánh workbook ba lớp

- Phụ thuộc: TDP-001.
- Mục tiêu: tự động kiểm tra output bằng dữ liệu + topology workbook + hình ảnh render.
- Thực hiện:
  - So sánh tên/thứ tự sheet, cột, merged cells, style trọng yếu, vùng in, khổ giấy, hướng giấy và dòng lặp.
  - So sánh số liệu/tổng bằng giá trị chuẩn hóa, không phụ thuộc công thức Excel external link.
  - Render sheet golden và output thành ảnh/PDF nội bộ để review trực quan.
  - Phát hiện renderer khả dụng trên máy (Excel/LibreOffice hoặc đường render đã kiểm chứng). Nếu không có renderer đáng tin cậy, đánh dấu lớp visual là chưa nghiệm thu; không lấy kiểm tra openpyxl thuần làm bằng chứng “nhìn giống”.
  - Mask hoặc không lưu vùng CCCD trong artifact QC.
- Kiểm thử: harness phải bắt được ít nhất một sai cột, một sai vùng in và một sai tổng trong fixture cố ý lỗi.
- Hoàn thành khi: các task báo giá/phiếu giao/bảng kê/biên nhận/báo cáo có thể dùng chung harness.

### Giai đoạn 1 – Nhập workbook hằng ngày và vòng đời dữ liệu ngày

#### [x] TDP-010 – Thiết kế contract và migration cho import ngày hai giai đoạn

- Phụ thuộc: TDP-000, TDP-001.
- Mục tiêu: phân biệt rõ lần nạp tối hôm trước và lần chốt ngày hôm sau, không nhân đôi batch.
- Thực hiện:
  - Audit schema hiện tại trước khi thêm bảng/cột; migration chỉ thêm tối thiểu và idempotent.
  - Định nghĩa identity ổn định theo workbook hash, sheet ngày, work date và khóa dòng nghiệp vụ.
  - Tách trạng thái `nháp/soạn hàng` khỏi `đã chốt dữ liệu ngày`.
  - Tách quyền cập nhật đơn khách với quyền cập nhật sheet `đặt hàng`.
  - Ghi audit nguồn, phiên bản và thời điểm confirm; không lưu PII trong audit metadata.
- Kiểm thử: migration mới/cũ/chạy lặp, rollback khi lỗi, integrity check, import trùng không tạo batch mới.
- Hoàn thành khi: có contract dữ liệu rõ, chưa cần UI hoàn chỉnh.

#### [x] TDP-011 – Preview/confirm đúng `Đơn hàng 01.09.2026.xlsx`

- Phụ thuộc: TDP-010.
- Mục tiêu: nhận trực tiếp workbook khách gửi hằng ngày, không bắt khách đổi biểu mẫu.
- Thực hiện:
  - Nhận diện sheet ngày bằng cấu trúc + ngày, không dựa vào vị trí sheet.
  - Nhận diện sheet `đặt hàng` bằng header bắt buộc.
  - Không nhập nhầm `CCCD`, `T.chiếu`, danh mục, `BÁO GIÁ`, `danh mục nhà cc`, `gộp đơn` thành order.
  - Cho xem trước số dòng, lỗi, cảnh báo và phạm vi dữ liệu sẽ ghi.
  - Cached blank ở `Chọn NCC`/`CCCD` không tự biến thành lỗi workbook.
  - Confirm token dùng một lần, có state hash và transaction toàn phần.
- Kiểm thử golden: sheet ngày `01.09` nhận đúng 323 dòng; không log CCCD; đổi tên file không nhân đôi nếu nội dung/phạm vi giống nhau.
- Hoàn thành khi: preview/confirm an toàn trên DB tạm và giữ nguyên file nguồn.

#### [x] TDP-014 – Xử lý an toàn các sheet tham chiếu nằm trong workbook ngày

- Phụ thuộc: TDP-001, TDP-011.
- Mục tiêu: dùng đúng vai trò của `CCCD`, `T.chiếu`, `danh mục hàng hóa`, `BÁO GIÁ`, `danh mục nhà cc` và `gộp đơn` mà không nhập chúng thành order hoặc âm thầm ghi đè database.
- Thực hiện:
  - `CCCD`: chỉ dùng cho nghiệp vụ bảng kê/biên nhận; dữ liệu nhạy cảm không vào log/audit metadata.
  - `T.chiếu`: dùng xác minh nhà thầu, bếp, địa chỉ và nhóm; thay đổi durable phải qua preview/confirm riêng.
  - `danh mục hàng hóa`: đối chiếu mã/tên/ĐVT/thuế; không ghi đè catalog đã chốt nếu chưa có confirm riêng.
  - `BÁO GIÁ`: không tự nhập vào price book trong luồng đơn ngày; muốn lưu giá phải đi qua TDP-050 với kỳ/phiên bản rõ.
  - `danh mục nhà cc`: dùng kiểm tra mapping; thay đổi durable phải có diff và confirm.
  - `gộp đơn`: chỉ là sheet trung gian/reference, không phải source ledger.
- Kiểm thử: workbook ngày không làm thay đổi catalog/price/NCC/CCCD khi chỉ confirm order; từng import tham chiếu riêng có stale-state lock, transaction và replay-safe.

#### [x] TDP-013 – Chỉnh nhanh giá bán trên lưới với audit

- Phụ thuộc: TDP-010.
- Mục tiêu: sửa một vài giá bán thực tế mà không nạp lại cả báo giá.
- Thực hiện: inline edit/bulk keyboard flow, lý do thay đổi, người/thời điểm, optimistic locking và không sửa giá kỳ chuẩn.
- Kiểm thử: chỉnh một dòng, rollback lỗi, concurrent stale update, giá không hữu hạn/âm bị chặn theo rule hiện hành.
- Hoàn thành khi: doanh thu/phải thu dùng giá override đúng dòng và audit tra cứu được.

### Giai đoạn 2 – Đặt NCC ưu tiên cao và chống bỏ sót

#### [x] TDP-020 – Cầu nối giữa sheet `đặt hàng` chuẩn và round-trip nội bộ

- Phụ thuộc: TDP-010, TDP-002.
- Mục tiêu: output/import của người dùng bám sheet `đặt hàng` trong `Em Thành.xlsx` và file 01.09, nhưng vẫn giữ ranh giới an toàn hiện có.
- Cột nghiệp vụ chuẩn phải giữ: mã hàng, mã bếp, ngày, tên hàng, số lượng, ĐVT, NCC, ghi chú, giá mua, hỏng, thêm, giảm, thiếu, số lượng thực tế, thành tiền.
- Thực hiện:
  - Thiết kế identity dòng trong database mà không làm hỏng bố cục visible của golden.
  - Map file round-trip 13 cột hiện có sang contract mới hoặc thay bằng export canonical có migration tương thích.
  - Người dùng vẫn tự kiểm tra tồn tủ và sửa lượng thực mua.
  - Preview/confirm không bao giờ sửa dữ liệu bán.
- Kiểm thử: file golden 259 dòng được nhận đúng; round-trip không đổi tổng khi chưa chỉnh; sửa phần mua chỉ đổi payable/purchase.
- Hoàn thành khi: khách có thể tiếp tục dùng mẫu của họ thay vì biểu mẫu hệ thống cũ.

#### [x] TDP-021 – Hỏng/thêm/giảm/thiếu và số lượng thực tế

- Phụ thuộc: TDP-020.
- Mục tiêu: giữ nguyên các điều chỉnh mua thực tế và công thức công nợ phải trả.
- Thực hiện:
  - Xác lập công thức theo cached/formula và đối chiếu file khách; không đoán dấu nếu mẫu mâu thuẫn.
  - Thành tiền = số lượng thực tế × giá mua chốt, VND rounding thống nhất.
  - Chặn mua ngoài có số lượng dương nhưng giá mua không hợp lệ; `Kho` vẫn được phép giá 0.
  - Lưu từng thành phần điều chỉnh và audit, không chỉ lưu kết quả net.
- Kiểm thử: từng nhánh hỏng/thêm/giảm/thiếu, tổ hợp, số âm/NaN, replay và stale preview.

#### [x] TDP-022 – Quy tắc dồn NCC chính xác

- Phụ thuộc: TDP-020.
- Mục tiêu: giữ đúng rule đã chốt, không mở rộng bằng suy đoán.
- Rule:
  - Hoài: chỉ dồn `Cà rốt`.
  - Thu, Kỳ, Tân, Phượng, Dung và Kho: dồn dòng có tên hàng giống nhau.
  - NCC khác: không tự dồn.
- Thực hiện: giữ dòng gốc để truy vết; dồn chỉ là presentation/gửi NCC.
- Kiểm thử: tên giống/khác, khác bếp, Hoài ngoài Cà rốt, NCC ngoài whitelist và Unicode/hoa-thường theo rule hiện hữu.

#### [x] TDP-023 – Checklist NCC đã đặt/chưa đặt và hoàn tác

- Phụ thuộc: TDP-020.
- Mục tiêu: người dùng luôn nhìn thấy NCC chưa xử lý; đánh dấu nhầm có thể hoàn tác.
- Thực hiện:
  - Trạng thái theo batch + NCC, có `pending/ordered/reopened` và audit.
  - Mặc định ưu tiên/đưa NCC chưa đặt lên trước.
  - Không xóa hoặc ẩn vĩnh viễn dòng khi đánh dấu đặt.
  - Không tự đánh dấu chỉ vì đã tải/sao chép ảnh; cần thao tác chủ đích hoặc rule được chốt.
- Kiểm thử: ordered → undo → ordered; reload/browser refresh; hai thao tác đồng thời; batch khác không bị ảnh hưởng.

#### [x] TDP-024 – Ảnh/nội dung gửi NCC đúng giới hạn đến `Ghi chú`

- Phụ thuộc: TDP-002, TDP-022.
- Mục tiêu: ảnh gửi thủ công chỉ gồm thông tin cần đặt hàng.
- Nội dung tối thiểu: mã bếp, ngày, tên hàng, số lượng, ĐVT, NCC, ghi chú.
- Không có: tồn tủ, giá mua, thành tiền, tổng cần mua sau trừ tồn hoặc cột kiểm soát nội bộ.
- Kiểm thử: render và so trực quan ảnh 6/`Em Thành.xlsx`; ảnh không chứa chuỗi header cấm.

#### [x] TDP-025 – Regression ranh giới mua/bán

- Phụ thuộc: TDP-020, TDP-021, TDP-022, TDP-023, TDP-024.
- Mục tiêu: khóa bằng test rằng mọi thao tác NCC không sửa order khách, doanh thu, phải thu hoặc kho hóa đơn.
- Kiểm thử bắt buộc: import file sửa, checklist, dồn, tạo ảnh, undo, giá lần hai và `Kho` giá 0.

#### [x] TDP-012 – Chốt dữ liệu ngày lần hai mà không phá sổ mua/bán

- Phụ thuộc: TDP-011, TDP-014, TDP-020, TDP-021, TDP-025.
- Mục tiêu: cập nhật đúng batch/ngày cũ với giá bán, lượng thực giao và dữ liệu đã chốt; phần mua đi vào luồng riêng.
- Thiết kế an toàn đã chốt cho Goal A:
  - Nếu workbook có cả sheet ngày và `đặt hàng`, preview phải trình bày thành hai phạm vi độc lập: **bán/giao** và **mua/phải trả**.
  - Người vận hành chọn và confirm rõ từng phạm vi ngay trong lần import; không có mặc định âm thầm ghi cả hai.
  - Đây là lựa chọn vận hành ở runtime, không phải câu hỏi khiến Goal phải chờ chủ dự án trong lúc phát triển.
- Thực hiện:
  - Preview diff dòng thêm/sửa/không đổi/xung đột trước khi confirm.
  - Không cho sheet `đặt hàng` ghi ngược vào lượng khách đặt, thực giao, doanh thu hoặc phải thu.
  - Các thay đổi giá bán giao dịch không ghi ngược bảng giá kỳ nếu là ngoại lệ.
  - Có khóa chống stale preview và replay.
- Kiểm thử: nạp lần một → chốt lần hai theo từng phạm vi → nạp lại; không nhân đôi, tổng mua và tổng bán tách đúng.

### Giai đoạn 3 – Công nợ phải trả ưu tiên cao

#### [x] TDP-030 – Sổ phải trả chi tiết theo dòng/NCC/ngày/bếp

- Phụ thuộc: TDP-021.
- Mục tiêu: mỗi dòng mua đã chốt trở thành nguồn phải trả có thể cộng dồn tháng/năm và truy ngược nguồn.
- Thực hiện:
  - Chi tiết: ngày, batch, bếp, mã/tên hàng, số lượng thực tế, ĐVT, giá mua, thành tiền, NCC.
  - Idempotent theo source line; không cộng trùng khi chốt/nạp lại.
  - Giữ import lịch sử 9.975 dòng và cutoff chống double count.
  - Phân biệt `open`, `partially_paid`, `paid`, `reversed`; không xóa ledger.
- Kiểm thử: current orders + historical import, period boundary, repeat import, supplier rename/reference.

#### [x] TDP-031 – Thanh toán toàn phần/một phần và phân bổ

- Phụ thuộc: TDP-030.
- Mục tiêu: khoản đã trả biến mất khỏi góc nhìn còn phải trả nhưng lịch sử vẫn tra được.
- Thiết kế an toàn cho Goal A:
  - Người dùng chọn rõ các dòng nợ và nhập số tiền phân bổ cho từng dòng.
  - Không tự dùng FIFO, phân bổ tỷ lệ, tự chọn dòng cũ nhất hoặc tự tạo overpayment/credit.
  - Quy tắc phân bổ tự động nâng cao chỉ làm sau nếu khách chốt riêng.
- Thực hiện:
  - Số tiền, ngày thanh toán, nội dung, phương thức/mã tham chiếu nếu có.
  - Phân bổ transaction vào dòng/cụm dòng có audit; reversal thay vì delete.
  - Chặn overpayment trong Goal A.
- Kiểm thử: full/partial/multiple payments/reversal/concurrency/period filters.

#### [x] TDP-032 – Excel phải trả theo NCC và lịch sử thanh toán

- Phụ thuộc: TDP-030; phần paid detail phụ thuộc TDP-031.
- Mục tiêu: xuất tại mọi thời điểm, có tổng hợp kỳ và sheet chi tiết từng NCC theo mẫu khách.
- Thực hiện: đối chiếu `Công nợ phải trả Thành Đạt Phát.xlsx`; giữ cột/thứ tự/định dạng có căn cứ, không bê công thức lỗi.
- Kiểm thử: tổng sheet = tổng chi tiết; open + paid history reconcile; workbook topology và print setup.

#### [x] TDP-033 – UI công nợ phải trả và lịch sử

- Phụ thuộc: TDP-030, TDP-031/032 tùy phần.
- Mục tiêu: filter NCC/kỳ/trạng thái; xem từng dòng; ghi nhận và hoàn tác thanh toán có kiểm soát.
- Kiểm thử: keyboard/basic browser smoke, refresh state, lỗi không ghi dở dang.

### Giai đoạn 4 – Công nợ phải thu vận hành

#### [x] TDP-040 – Sổ phải thu từ lượng thực giao và giá bán giao dịch

- Phụ thuộc: TDP-012, TDP-013.
- Mục tiêu: phải thu vận hành theo ngày/tháng, nhà thầu và bếp; tách khỏi hóa đơn đỏ.
- Thực hiện: source line idempotency, điều chỉnh có audit, số dư đầu kỳ/thu/chi theo cơ chế hiện có nhưng không trộn payable.
- Kiểm thử: ordered khác delivered; override giá; khách trả/giảm giao; nhiều batch một kỳ.

#### [x] TDP-041 – Excel phải thu tách riêng từng nhà thầu

- Phụ thuộc: TDP-040, TDP-002.
- Mục tiêu: mỗi nhà thầu một file; sheet đầu là tổng nhà thầu, các sheet sau là từng bếp thuộc nhà thầu.
- Thực hiện: tên sheet hợp lệ/không trùng, bếp mới tự xuất hiện, tổng sheet con khớp sheet đầu.
- Kiểm thử: nhiều nhà thầu, nhiều bếp, tên dài/ký tự cấm, kỳ tùy chọn và dữ liệu rỗng.

#### [x] TDP-042 – UI phải thu và đối soát

- Phụ thuộc: TDP-040, TDP-041.
- Mục tiêu: xem/lọc/tải theo nhà thầu, bếp và kỳ; nhãn rõ đây là công nợ vận hành, không phải đề nghị thanh toán hóa đơn đỏ.

### Giai đoạn 5 – Báo giá độc lập theo kỳ/phiên bản/nhà thầu

#### [x] TDP-050 – Import báo giá riêng có kỳ hiệu lực và phiên bản

- Phụ thuộc: TDP-001, TDP-010.
- Mục tiêu: báo giá không bị nhập lẫn với workbook đơn hàng hằng ngày.
- Thực hiện:
  - Preview/confirm riêng; kỳ hiệu lực, source hash, phiên bản điều chỉnh và audit.
  - Một ngày có thể chuẩn bị giá kỳ sau trong khi order vẫn dùng kỳ hiện tại.
  - Không ghi đè lịch sử giá đã dùng cho giao dịch cũ.
  - Giá mua từ báo giá được ưu tiên; giá trống chỉ được bổ sung bởi mua thực tế theo rule hiện hành.
- Kiểm thử: hai kỳ song song, version 1/2, replay, stale confirm và rollback.

#### [x] TDP-051 – Chọn đúng cột nhà thầu, lọc X/rỗng và chống trùng mã

- Phụ thuộc: TDP-050.
- Mục tiêu: không lấy nhầm giá/trạng thái giữa các nhà thầu.
- Thực hiện:
  - Mapping contractor column bằng mã/header xác định, không dựa vị trí mơ hồ.
  - Dòng `X` hoặc rỗng không xuất.
  - Một mã không xuất hai dòng; xung đột cùng mã phải preview rõ và không tự chọn.
  - Giá 0 không tự loại; vẫn hiện rõ trong preview/output theo quyết định an toàn ở mục 9.1.
- Kiểm thử: Toyota cột Q, contractor khác, mã trùng cùng/khác giá, X/rỗng/0.

#### [x] TDP-052 – Xuất báo giá Toyota đúng golden

- Phụ thuộc: TDP-002, TDP-051.
- Golden: `BÁO GIÁ TOYOTA T09-2026.xlsx` và sheet `BÁO GIÁ` trong `Em Thành.xlsx`.
- Mục tiêu:
  - Một sheet `all`.
  - A4 ngang, repeat header.
  - Đúng thông tin pháp nhân, tiêu đề tháng/năm, kính gửi.
  - Sáu cột STT/Mã/Tên TĐP/ĐVT/Giá chưa VAT/Thuế.
  - Dòng nhóm nền xanh; mã A–Z trong nhóm; vùng ghi chú và xác nhận bên bán.
- Kiểm thử: dữ liệu + topology + render; không có công thức/external link trong output độc lập.

#### [x] TDP-053 – Xuất báo giá mọi nhà thầu

- Phụ thuộc: TDP-052.
- Mục tiêu: dùng cùng engine nhưng đúng pháp nhân/giá/trạng thái từng nhà thầu, không hard-code Toyota.
- Kiểm thử: ít nhất ba nhà thầu có cấu hình khác nhau; không rò giá giữa nhà thầu.

### Giai đoạn 6 – Biểu mẫu cố định theo `Em Thành.xlsx`

#### [x] TDP-060 – Engine template-preserving cho Excel output

- Phụ thuộc: TDP-002.
- Mục tiêu: đổ dữ liệu vào bản sao cấu trúc golden thay vì tự thiết kế workbook mới.
- Thực hiện: giữ style, merged cells, row/column sizes, print setup, signatures, formulas an toàn; output không giữ external link lỗi; tương thích với `print_bundle.py`/`pdf_documents.py` mà không làm hỏng A4/A5 đã nghiệm thu.
- Kiểm thử: template không bị mutate; hai lần sinh cùng dữ liệu cho topology/tổng giống nhau.

#### [x] TDP-061 – Phiếu giao đúng mẫu đã duyệt

- Phụ thuộc: TDP-040, TDP-060.
- Golden: sheet `đơn hàng đi giao`, ảnh 5.
- Mục tiêu: tách từng bếp; đúng pháp nhân, địa chỉ, ngày, bảng hàng, tổng, bốn vùng ký và vùng in.
- Quy tắc giá: chỉ bếp/nhà thầu Nhựa được hiện giá; nơi khác ẩn giá theo đúng biến thể mẫu.
- Trước khi code: tra `T.chiếu`, danh mục bếp/nhà thầu và database để tìm mã ổn định của Nhựa. Nếu có nhiều ứng viên thì tạo cấu hình bắt buộc, không fuzzy-match tên và không tự bật hiển thị giá.
- Kiểm thử: phiếu có giá/không giá, font đủ lớn, A4/print bundle không hồi quy.

#### [x] TDP-062 – Bảng kê thu mua tổng đúng golden

- Phụ thuộc: TDP-021, TDP-030, TDP-060.
- Golden: sheet `bảng kê tổng` và bộ CCCD chỉ dùng nội bộ.
- Nguồn: các dòng mua/BK đã chốt có người bán và thông tin định danh hợp lệ; **không lấy từ sổ phải thu**.
- Mục tiêu: đúng cách tách người bán/NCC/bếp, đủ ngày, tổng mua khớp; không lộ CCCD vào log/test artifact.

#### [x] TDP-063 – Biên nhận đúng golden

- Phụ thuộc: TDP-021, TDP-030, TDP-060, TDP-062.
- Golden: sheet `biên nhận` trong `Em Thành.xlsx`; chính sheet này là đúng, output hiện tại là sai.
- Nguồn: dòng thu mua theo người bán/CCCD và số lượng thực nhận/giá mua đã chốt; không dùng doanh thu/phải thu.
- Kiểm thử: tiêu đề/câu chữ/thông tin pháp nhân/vùng ký/cột/dòng/tổng/vùng in và render.

#### [x] TDP-064 – Báo cáo tổng hợp động theo nhà thầu/bếp

- Phụ thuộc: TDP-030, TDP-040, TDP-060.
- Golden: sheet `báo cáo tổng hợp`, ảnh 15.
- Mục tiêu: trước tiên ánh xạ đầy đủ tiêu đề/công thức của sheet golden để xác định cột nào là mua, bán, lợi nhuận hoặc tổng khác; sau đó tự thêm bếp mới, giữ phân cấp nhà thầu/bếp, dòng tổng nhóm và `TỔNG THÁNG` nền xanh.
- Kiểm thử: thêm bếp mới không sửa công thức thủ công; tổng nhóm và tổng tháng reconcile.

### Giai đoạn 7 – Bàn làm việc hóa đơn đầu vào + đầu ra và khớp mã

#### [x] TDP-069 – Khung chung tải hóa đơn hai chiều theo khoảng ngày

- Phụ thuộc: TDP-000.
- Nguồn yêu cầu: tin nhắn khách ngày 02/09/2026 lúc 10:56–10:59; khách cần làm phần này trước để khớp tháng 08/2026.
- Mục tiêu: trên phần mềm có một khu vực rõ ràng với hai tab `Đầu vào`/`Đầu ra`, cùng bộ chọn `từ ngày–đến ngày`, tiến độ batch và số lượng theo trạng thái.
- Thực hiện:
  - Khoảng ngày inclusive, kiểm tra `từ <= đến`, không hard-code tháng 08/2026.
  - Filter tối thiểu: chưa ghép, khác ĐVT/cần kiểm tra, sẵn sàng, đã ghi kho, lỗi/bất thường.
  - Hiển thị nguồn, ngày, ký hiệu/số hóa đơn, đối tác, mã/tên/ĐVT nguồn, mã TĐP, số lượng quy đổi và trạng thái kho.
  - Contract connector chỉ-read/import; không mở thao tác ký, phát hành, sửa hoặc hủy hóa đơn bên ngoài.
  - Batch có source/type/date-range/hash hoặc cursor, audit và trạng thái để retry an toàn.
- Kiểm thử: validation ngày, chuyển tab không mất filter/mapping, refresh giữ batch, không log payload/credential và UI phân biệt tuyệt đối đầu vào với đầu ra.

#### [x] TDP-070 – Đồng bộ hóa đơn đầu vào mSMI theo khoảng ngày và idempotency

- Phụ thuộc: TDP-069.
- Mục tiêu: truyền đúng `INPUT_ELECTRONIC_INVOICE` và `từ ngày–đến ngày` vào client; đồng bộ lại không nhân đôi và không mất mapping đã chốt.
- Thực hiện: bỏ hard-code khoảng ngày ở route/UI, giữ connector read-only, paging production, quarantine chứng từ bất thường và freeze chứng từ đã post.
- Kiểm thử: khoảng 01/08/2026–31/08/2026 trên fixture, biên ngày inclusive, paging, repeat, partial page failure rollback, discount/khuyến mại; mặc định dùng mock/fixture, không kéo payload production vào log Goal.

#### [x] TDP-074 – Đồng bộ hóa đơn đầu ra đã phát hành và hàng chờ khớp

- Phụ thuộc: TDP-069.
- Mục tiêu: đọc M-Invoice đầu ra theo ký hiệu và `từ ngày–đến ngày`, lưu từng dòng vào hàng chờ ghép mã trước khi được phép trừ kho.
- Thực hiện:
  - Dùng connector read-only hiện có; định danh idempotent bằng nguồn + remote ID và khóa nghiệp vụ ký hiệu/số/ngày khi có.
  - Chỉ trạng thái nguồn đã được ánh xạ/chứng minh là phát hành hợp lệ mới có thể sang `sẵn sàng`; draft/chờ ký/không rõ trạng thái phải quarantine.
  - Hóa đơn hủy, thay thế hoặc điều chỉnh tạo sự kiện đối chiếu/reversal có audit; không xóa hoặc sửa im lặng bút toán đã post.
  - Chưa ghép đủ dòng có ảnh hưởng kho thì toàn hóa đơn chưa được post kho; dòng điều chỉnh tài chính không có số lượng phải được phân loại riêng.
- Connector M-Invoice đã qua probe production chỉ-read và fixture/integration đầy đủ; không gọi write API production. Trạng thái không rõ luôn fail-closed và đối soát toàn kỳ thật vẫn là thao tác nghiệm thu vận hành, không phải yêu cầu nghiệp vụ còn thiếu.
- Kiểm thử: khoảng 01/08/2026–31/08/2026, paging/retry/repeat, cùng số khác ký hiệu, trạng thái không rõ, draft, hủy/thay thế/điều chỉnh và payload lỗi.

#### [x] TDP-071 – UI ghép mã hai chiều dùng bàn phím, tô màu và filter lỗi

- Phụ thuộc: TDP-070, TDP-074.
- Mục tiêu: ở cả tab đầu vào và đầu ra, dòng chưa mã/khác ĐVT nổi bật; tìm/chọn bằng keyboard + Enter; filter chưa ghép/lỗi/khác ĐVT.
- Thực hiện: không fuzzy-confirm; gợi ý chỉ là gợi ý, người dùng phải xác nhận mã. Mapping lưu đúng scope nguồn/đối tác/chiều hóa đơn và không tự lan sang scope không tương thích.
- Kiểm thử: browser/DOM smoke cho hai tab, không cần chuột cho happy path, refresh vẫn giữ mapping và mapping đầu vào không làm sai đầu ra.

#### [x] TDP-072 – Mapping quy đổi ĐVT có audit và ghi nhớ

- Phụ thuộc: TDP-070, TDP-071.
- Mục tiêu: người dùng nhập `1 thùng = 30 gói`, hệ thống tính đúng số lượng kho cho chiều nhập hoặc xuất và đơn giá kho cho chiều nhập; không tự đoán.
- Thực hiện: mapping scope theo tenant + chiều hóa đơn + đối tác + mã/tên nguồn + source unit + target product/unit; effective dates nếu cần.
- Áp dụng cả dòng khuyến mại; khác ĐVT phải confirm rõ.
- Kiểm thử: conversion >1/<1, giá/quantity reconciliation, mapping conflict, repeat sync, unit change và rollback.

#### [x] TDP-073 – Tạo phiếu nhập sau quy đổi

- Phụ thuộc: TDP-072.
- Mục tiêu: chỉ dòng đã ghép/đã quy đổi hợp lệ mới tăng kho; điều chỉnh tài chính không ghi kho.
- Kiểm thử: stock/value reconcile, receipt idempotent, posted invoice frozen, DB integrity.

### Giai đoạn 8 – TĐK–NXT, BK và ghi giảm kho theo hóa đơn đầu ra

#### [x] TDP-080 – Khóa source of truth cho kho hóa đơn và hóa đơn đã phát hành

- Phụ thuộc: TDP-071, TDP-073, TDP-074.
- Mục tiêu: một contract rõ cho `Tồn đầu + Nhập hợp lệ − Hóa đơn đỏ đã phát hành`.
- Thực hiện:
  - Tách ledger vận hành và ledger hóa đơn.
  - Hóa đơn đầu vào đã post tạo nhập; hóa đơn đầu ra đã phát hành, ghép/đổi ĐVT đủ và được người dùng confirm mới tạo xuất.
  - Draft chỉ reserve; dữ liệu đầu ra đồng bộ nhưng chưa đủ trạng thái/mapping/xác nhận không được xuất kho.
  - Hủy/thay thế/điều chỉnh dùng reversal/event idempotent, không xóa ledger cũ.
  - Adapter đối chiếu hóa đơn đỏ chỉ-read, không mở quyền ký/phát hành.
- Goal A dùng dữ liệu fixture cho test và cho phép cơ chế xác nhận/post thủ công có audit. Không tự gọi live API hay write API production; unknown status phải chờ xử lý thay vì tự coi là đã phát hành.
- Kiểm thử: backfill 01/08/2026–31/08/2026 trên database tạm/bản sao, chạy lại không nhân đôi, `Tồn đầu + Nhập − Xuất = Tồn cuối`, không âm kho và mọi bút toán truy ngược được hóa đơn/dòng/mapping/confirm.

#### [x] TDP-081 – Giá bình quân và sổ TĐK–NXT

- Phụ thuộc: TDP-080.
- Mục tiêu: tính giá trị tồn bằng giá bình quân có kiểm tra kỳ và không dùng giá vốn làm giá bán.
- Thực hiện: định nghĩa rounding, negative legacy opening, backdated transaction và rebuild/determinism.
- Kiểm thử: opening + nhiều lần nhập + xuất + backdate + zero quantity; quantity/value reconcile.

#### [x] TDP-082 – Bốn file TĐK, Nhập, Xuất và NXT

- Phụ thuộc: TDP-002, TDP-081.
- Mục tiêu: xuất đủ bốn góc nhìn trong kỳ, tổng liên kết và giá bình quân đúng.
- Golden chính thức: `_HANDOFF/EXTERNAL_INPUTS/TĐK T8-2026.xlsx thụy.xlsx`, sheet `Ton 7 (2)`. Dùng hệ cột/hình thức này làm gốc cho cả bộ bốn file; NXT là báo cáo suy ra từ cùng projection, không cần khách cung cấp một workbook NXT riêng.
- Hoàn thành khi cả bốn file cùng kỳ/cùng contract, Nhập/Xuất truy ngược được nguồn, NXT giữ các trường nhận diện của golden và từng mã thỏa `Tồn đầu + Nhập − Xuất = Tồn cuối`; topology/render/test/QC đều đạt.
- Trạng thái hiện hành: hoàn tất implementation, regression, QC và render; bốn file được sinh từ cùng projection và đối chiếu đúng công thức tồn.

#### [x] TDP-083 – Import dòng `BK` an toàn

- Phụ thuộc: TDP-080.
- Mục tiêu: có file mẫu/import riêng, mã hàng rõ, idempotent và không bỏ qua stock gate.
- Quyết định nghiệp vụ đã khóa: cờ `bk` ở nguồn xác định dòng đầu vào TĐP theo bảng kê mua vào không có hóa đơn; hệ thống là bên cấp mẫu import. Giá nhập mặc định bằng 95% giá bán của chính dòng/kỳ tương ứng và phải hiện để người dùng kiểm tra trước xác nhận.
- Confirm hợp lệ ghi tăng canonical invoice inventory ledger theo đúng mã TĐP; bắt buộc preview, xác nhận rõ, idempotency, audit, chống CCCD trong log và reversal có lý do. Dòng thiếu mã/số lượng/giá hợp lệ bị chặn; không tự phát hành hóa đơn hoặc bỏ qua cổng không âm kho.
- Trạng thái hiện hành: hoàn tất mẫu trắng/tự điền, giá 95%, preview/confirm canonical, chống trùng, audit/reversal, regression, QC và render.

#### [x] TDP-084 – Readiness/draft nhiều vòng tách theo nhà thầu

- Phụ thuộc: TDP-040, TDP-080.
- Mục tiêu: cần 10 có 7 thì draft 7, giữ 3; mọi danh sách và vòng chạy riêng từng nhà thầu.
- Thực hiện: hiển thị tổng cần, đã draft/đã xuất, có thể lập, còn thiếu; mã hàng bắt buộc.
- Xuất được danh sách còn thiếu theo nhà thầu và khoảng ngày/tháng, gồm mã hàng, số lượng và giá trị cần xử lý để vài ngày chạy lại hoặc cuối tháng xin luân chuyển.
- Kiểm thử: hai vòng nhập/xuất, nhiều nhà thầu, backdated/future reservation, cancel nhả tồn, không xuất trùng/âm kho.

#### [x] TDP-085 – File hóa đơn theo bốn mẫu thuế thật

- Phụ thuộc: TDP-002, TDP-084.
- Golden:
  - `thue 8.xlsx`.
  - `thue 0.xlsx` = KKKNT mã nội bộ `-2`, không phải VAT 0%.
  - `thue 10.xlsx`.
  - `thue 10 có khuyến mại.xlsx`.
- Mục tiêu: output tách theo nhà thầu và đúng mẫu, không gộp khác pháp nhân/thuế.
- Kiểm thử: 26 dòng canonical hiện có + test nhiều vòng + khuyến mại blank hợp lệ.

#### [x] TDP-086 – Luân chuyển/mặt hàng thay thế có xác nhận

- Phụ thuộc: TDP-050, TDP-081, TDP-084.
- Mục tiêu: xuất danh sách thiếu; người dùng tự chọn mã thay thế; lưu xác nhận/audit; dùng giá bán đúng kỳ/nhà thầu.
- Không được: tự gợi ý thành quyết định, dùng giá nhập/bình quân làm giá bán hoặc sửa lịch sử hàng gốc.
- Kiểm thử: thiếu giá kỳ bị chặn, tồn thay thế không đủ, undo/reversal, nhiều vòng.

#### [x] TDP-087 – Đề nghị thanh toán chính thức từ hóa đơn đỏ

- Phụ thuộc: TDP-080, TDP-084, TDP-085.
- Mục tiêu: tuyệt đối không dùng phải thu vận hành chưa phát hành làm giấy tờ chính thức.
- Mẫu chính thức: `C:\Users\DELL\Downloads\Đề nghị Thanh toán TĐP (T04.26).xlsx`; sinh XLSX sáu cột và Bảng tổng hợp giao nhận mười cột bằng giá trị tĩnh từ phạm vi hóa đơn đỏ đã phát hành.

#### [x] TDP-088 – Bảng kê giao hàng/chứng từ đối chiếu chính thức theo hóa đơn đỏ

- Phụ thuộc: TDP-080, TDP-084, TDP-085.
- Mục tiêu: tách rõ với `bảng kê tổng` thu mua ở TDP-062; bảng kê/chứng từ gửi khách ở task này chỉ lấy các hóa đơn đỏ đầu ra đã phát hành của đúng nhà thầu.
- Thực hiện:
  - Mỗi nhà thầu một phạm vi; không trộn nhiều pháp nhân.
  - Đối chiếu ngày, ký hiệu, số hóa đơn, tiền trước thuế, thuế, tổng và phần chênh lệch.
  - Giữ contract hiện có: chênh lệch vượt ngưỡng cho phép phải chặn xuất, không tự cân số.
- Kiểm thử: đã phát hành/chưa phát hành, nhiều vòng, nhiều nhà thầu, tổng hóa đơn = tổng bảng kê và mismatch bị chặn.

### Giai đoạn 9 – Bảo toàn Xưởng cơm/PO và Chấm công/lương

#### [x] TDP-090 – Regression Xưởng cơm/PO sau đại cập nhật

- Phụ thuộc: TDP-010, TDP-030, TDP-080.
- Mục tiêu: giữ đủ import menu/cost, đa thực đơn, XCOM, PO nháp/đã duyệt, chấm suất và đề nghị thanh toán.
- Kiểm thử golden hiện có: 5 kế hoạch, 54 nguyên liệu, MAZDA 46 suất, 3 sheet XCOM/MAZDA/TTS, tổng thực phẩm 3.851.200 VNĐ.

#### [x] TDP-091 – Regression Chấm công/lương sau đại cập nhật

- Phụ thuộc: TDP-010, TDP-030, TDP-080.
- Mục tiêu: giữ import/chỉnh công, phụ cấp/BHXH/tạm ứng/điều chỉnh và bảng lương; không ẩn menu.
- Kiểm thử: toàn bộ test attendance/payroll hiện có + browser smoke.

#### [x] TDP-092 – Giữ nguyên Xưởng cơm/PO và Chấm công/lương

- Chủ dự án đã đính chính rõ hai module này vẫn phải có. `Phần làm thêm.docx` được tạm bỏ khỏi đợt nghiệm thu; không xóa/ẩn hai module vận hành hiện tại.

#### [x] TDP-116 – Xuất Excel hóa đơn đầu vào ngay sau khi kéo

- Phụ thuộc: TDP-069, TDP-070.
- Mục tiêu: từ mỗi phiên hóa đơn đầu vào đã kéo, tải được Excel danh sách + chi tiết + đối chiếu trước khi ghép mã/post kho.
- Ranh giới: không tự ghi kho, không chứa raw payload/mã từ xa/bí mật kết nối, có audit tối thiểu và được đóng gói vào portable.

### Giai đoạn 10 – Dùng nhiều máy/hosting: chỉ thiết kế khi đủ quyết định

#### [ ] TDP-100 – Decision record kiến trúc triển khai nhiều nơi

- Phụ thuộc: Q-010.
- Mục tiêu: chốt người dùng, vai trò, domain, HTTPS, hosting, backup/restore, monitoring, chi phí và trách nhiệm.
- Không được: đặt SQLite trên Google Drive để nhiều máy mở trực tiếp; tự deploy public; tự mở LAN/Internet.
- Task này nằm ngoài Goal A; chỉ tạo decision record và threat model khi Q-010 đã được chốt. Implementation/deployment là Goal/phạm vi riêng sau khi được duyệt.

### Giai đoạn 11 – Tích hợp, migration và phát hành

#### [x] TDP-110 – Hợp nhất UI và ngôn ngữ nghiệp vụ

- Phụ thuộc: TDP-023, TDP-033, TDP-042, TDP-050, TDP-071, TDP-082, TDP-084.
- Mục tiêu: tên màn/nhãn đúng nghiệp vụ (`TĐK–NXT`, công nợ vận hành, hóa đơn đỏ, đã đặt/chưa đặt), keyboard flow và trạng thái lỗi rõ ràng.
- Không redesign tùy hứng; ảnh locator dùng để xác định vùng cần sửa, không phải golden UI.

#### [x] TDP-111 – Dry-run migration trên bản sao database thật

- Phụ thuộc: TDP-010, TDP-020, TDP-030, TDP-040, TDP-050, TDP-072, TDP-080, TDP-081.
- Mục tiêu: nâng cấp bản sao `tdp.sqlite3`, không đổi database nguồn; kiểm tra counts, balances, integrity và khả năng mở bằng source mới.
- Bằng chứng: backup path, hash trước/sau của bản sao, migration log không chứa dữ liệu nhạy cảm, `integrity_check=ok`.

#### [x] TDP-112 – Full regression và QC mở rộng

- Phụ thuộc: mọi task code thuộc Goal A đã hoàn thành hoặc được ghi `[!]` vì thiếu đầu vào bên ngoài; TDP-090, TDP-091, TDP-110 và TDP-111 phải hoàn thành.
- Bắt buộc:
  - Toàn bộ 97 test nền + test mới.
  - `python -m tdp_system.qc_system`.
  - `/health` source.
  - Syntax/static checks frontend.
  - Golden workbook three-layer checks.
  - Kiểm tra source test không đổi database thật.
- Hoàn thành khi: không bỏ qua test, không sửa test chỉ để che lỗi và mọi warning mới đều được phân loại.

#### [x] TDP-113 – Smoke end-to-end theo kịch bản vận hành đại diện

- Phụ thuộc: TDP-112.
- Môi trường: database tạm/bản sao và bản sao read-only của file khách; không ghi database thật, không gọi write API production và không phát hành/in thật.
- Kịch bản tối thiểu:
  1. Nạp workbook ngày lần một.
  2. Soạn/giao/đặt NCC.
  3. Checklist toàn bộ NCC và hoàn tác một NCC.
  4. Chốt mua lần hai, phát sinh payable.
  5. Chốt giao/giá bán, phát sinh receivable.
  6. Xuất phải thu/phải trả.
  7. Chọn 01/08/2026–31/08/2026, tải fixture đầu vào + đầu ra, ghép mã hai chiều và quy đổi ĐVT cần thiết.
  8. Post đầu vào hợp lệ, post đầu ra đã phát hành hợp lệ; chạy lại cùng khoảng ngày và xác nhận không nhân đôi/không âm kho.
  9. Reconcile `Tồn đầu + Nhập − Xuất = Tồn cuối`, rồi kiểm tra readiness hóa đơn vòng một/vòng hai theo nhà thầu.
  10. Xuất báo giá và bốn biểu mẫu golden.
  11. Lập bảng kê/chứng từ đối chiếu đầu ra chỉ từ hóa đơn đỏ đã xác nhận phát hành và reconcile tổng.
  12. Kiểm tra Xưởng cơm/PO và Chấm công/lương còn hoạt động.

#### [x] TDP-114 – Build portable và gói bàn giao sau đính chính cuối

- Phụ thuộc: TDP-112, TDP-113 và **chỉ đạo rõ của chủ dự án**.
- Phạm vi: ngoài Goal A; đã thực hiện theo chỉ đạo phát hành của chủ dự án.
- Bản build/gói `BAN_GIAO_TDP_20260903_FINAL` trước đính chính được giữ làm lịch sử nhưng không còn là artifact bàn giao cuối. Trước build lại: backup đúng database, giữ EXE/gói cũ, không tuyên bố EXE mới nếu chưa copy/test đúng artifact.
- Sau build: hash EXE, `/health` bằng database portable tách riêng, smoke import/export, kiểm tra gói không chứa `.env`, QC/page nội bộ hay file khách nhạy cảm ngoài phạm vi.
- Kết quả hiện hành: `BAN_GIAO_TDP_20260903_100PCT` và ZIP cùng tên đã qua allowlist/hash/integrity; xem log phát hành cuối ở mục 12.

#### [x] TDP-115 – Xác nhận cấu hình in/khay không còn blocker kỹ thuật

- Phụ thuộc: cấu hình vận hành đã được chủ dự án xác nhận trực tiếp.
- Phạm vi hiện hành: không yêu cầu tác nhân kỹ thuật tiếp tục kiểm tra phần cứng/máy in trong đợt sửa source này.
- Thiết bị đã chốt: Canon Generic Plus UFR II, LBP242/243, `IP_192.168.1.190`; A4 Drawer 1 duplex long-edge; A5 Multi-purpose Tray simplex.
- Ngày 03/09/2026, chủ dự án xác nhận các khay đã cấu hình xong và yêu cầu không coi máy in là việc còn thiếu. Xác nhận này đóng cổng kỹ thuật TDP-115; ký nhận giấy nếu có là thủ tục vận hành/bàn giao, không chặn source, build hoặc gói phát hành.

## 9. Quyết định và dữ kiện chưa khóa – Goal không được tự đoán

### 9.1. Các điểm đã có thiết kế an toàn, không chặn Goal A

| Nội dung | Quyết định dùng trong Goal A |
|---|---|
| Chốt ngày lần hai | Preview tách phạm vi bán/giao và mua/phải trả; người vận hành confirm rõ phạm vi ở runtime. |
| Thanh toán NCC một phần | Chọn dòng và nhập phân bổ thủ công; không FIFO/tỷ lệ/overpayment tự động. |
| Xác nhận hóa đơn đỏ đã phát hành | Ghi nhận cục bộ khóa draft và tiếp tục giữ tồn chờ đối soát; chỉ hóa đơn M-Invoice đã đồng bộ, ghép mã, trạng thái hợp lệ và được người dùng xác nhận mới ghi sổ TĐK–NXT. |
| Báo giá trùng/giá 0 | Xung đột cùng mã chặn confirm; giá 0 không tự loại; X/rỗng không xuất. |
| BK | **Đã khóa, Q-004 được giải quyết:** cờ `bk` là đầu vào TĐP; hệ thống cấp mẫu; giá mặc định 95% giá bán của chính dòng; confirm mới ghi tăng kho, có idempotency/audit/reversal. |
| TĐK–NXT | **Đã khóa, Q-005 được giải quyết:** golden TĐK tháng 08/2026 đủ để sinh chính thức TĐK, Nhập, Xuất và NXT từ cùng projection. |
| Máy in/khay | Chủ dự án xác nhận đã cấu hình đầy đủ; không còn blocker kỹ thuật hoặc câu hỏi cần gửi khách. |

### 9.2. Điểm đã tự điều tra và giải quyết từ nguồn local

| ID | Cần xác minh | Task | Cách xử lý |
|---|---|---|---|
| Q-002 | **Đã giải quyết:** “Nhựa” được khóa đúng hai mã `NHUAHP` và `NHUAHAIPHONG`. | TDP-061 | Dùng mã chính xác + test; không fuzzy-match và không cần hỏi lại khách. |

### 9.3. Các quyết định đã giải quyết và phạm vi ngoài hợp đồng

| ID | Cần chốt | Task bị ảnh hưởng | Hướng an toàn khi chưa chốt | Có chặn Goal A? |
|---|---|---|---|---|
| Q-008 | **Đã giải quyết 03/09/2026:** khách cung cấp `Đề nghị Thanh toán TĐP (T04.26).xlsx`. | TDP-087 | Dùng form sáu cột + BK mười cột; bỏ công thức/liên kết/dữ liệu kỳ cũ. | Không còn chặn. |
| Q-009 | **Đã giải quyết:** chủ dự án chốt Xưởng cơm/PO và Chấm công/lương vẫn phải có; chỉ tạm bỏ `Phần làm thêm.docx`. | TDP-092 | Giữ nguyên và regression hai module. | Không còn chặn. |
| Q-010 | Người dùng/vai trò/nơi dùng/domain/hosting/backup/chi phí | TDP-100 | Chạy local/LAN an toàn; không public hoặc đặt SQLite trên Drive. | Ngoài Goal A. |
| Q-011 | **Đã giải quyết 03/09/2026:** connector M-Invoice đầu ra và ánh xạ phát hành/nháp/hủy/thay thế/điều chỉnh đã được kiểm chứng bằng live probe chỉ-read và fixture/integration. | TDP-074, TDP-080 | Giữ connector read-only, fail-closed và không post kho khi status còn `unknown`; kéo/đối soát cả kỳ thật là bước nghiệm thu vận hành. | Không còn chặn. |

Quy tắc: task bị một điểm Q chặn phải ghi `[!]` kèm bằng chứng đã điều tra và phần đã hoàn thành. Goal tiếp tục task độc lập khác. Goal A vẫn được coi là đạt nếu toàn bộ source có thể làm an toàn đã hoàn thành, test xanh và phần còn lại chỉ phụ thuộc đúng các Q bên ngoài ở bảng trên.

## 10. Cổng chất lượng theo milestone

Sau mỗi giai đoạn có thay đổi code:

1. Chạy test mục tiêu và các test module liên quan.
2. Kiểm tra `git diff --check` và tự review diff.
3. Không để task `[x]` nếu test bị skip hoặc chỉ kiểm tra happy path.

Sau các milestone lớn:

- M1 sau Giai đoạn 2: full unit test + QC + `/health`; khóa ranh giới mua/bán.
- M2 sau Giai đoạn 4: full unit test + QC; reconcile payable/receivable.
- M3 sau Giai đoạn 6: golden workbook three-layer suite.
- M4 sau Giai đoạn 8: full unit test + QC + inventory/invoice reconciliation.
- M5 sau Giai đoạn 9: xác nhận hai module Xưởng cơm/PO và Chấm công/lương không hồi quy.
- Source candidate/Goal A: toàn bộ TDP-112/113.
- Release/Goal B: TDP-114 đã đạt trên source đính chính; TDP-115 đã được chủ dự án đóng vì cấu hình máy in/khay đã hoàn tất.

## 11. Definition of Done

### 11.1. Goal A – source candidate đã kiểm chứng

Goal A được coi là hoàn thành khi:

1. Mọi task source có thể triển khai an toàn là `[x]`; BK và NXT không được để `[!]` vì Q-004/Q-005 đã được giải quyết. Q-011 cũng đã đóng bằng kiểm chứng kỹ thuật chỉ-read; Q-002 phải được giải bằng cấu hình/mã local, không hỏi lại khách khi đã có dữ kiện duy nhất.
2. Workbook ngày khách gửi được nạp trực tiếp, idempotent và không nhập nhầm sheet cố định.
3. Đặt NCC dùng mẫu chuẩn, có điều chỉnh thực tế, checklist chống sót, undo và ảnh gửi đúng cột.
4. Phải trả và phải thu có sổ chi tiết, file đối soát đúng cấu trúc và không trộn nguồn.
5. Báo giá tách theo nhà thầu đúng kỳ/phiên bản và đạt golden Toyota.
6. Phiếu giao, bảng kê thu mua, biên nhận và báo cáo tổng hợp đạt cả dữ liệu, topology và render theo `Em Thành.xlsx`; bảng kê/chứng từ chính thức theo hóa đơn đỏ được tách riêng.
7. Màn hóa đơn có hai chiều đầu vào/đầu ra, date range, keyboard mapping, filter, quy đổi ĐVT có audit và idempotency; backfill fixture tháng 08/2026 chạy lại không nhân đôi.
8. Bộ bốn file TĐK–Nhập–Xuất–NXT là output chính thức theo golden TĐK, cùng projection và thỏa `Tồn đầu + Nhập − Xuất = Tồn cuối`; BK có mẫu do hệ thống cấp, giá mặc định 95% giá bán, confirm/reversal idempotent và ghi đúng canonical ledger. Connector M-Invoice đã được kiểm chứng chỉ-read và luôn fail-closed với trạng thái không hợp lệ/không rõ.
9. Xưởng cơm/PO và Chấm công/lương vẫn hoạt động và có regression xanh.
10. Tất cả unit test cũ + mới, QC, `/health` và smoke end-to-end đạt.
11. Không có bí mật/CCCD trong log hoặc artifact QC; không gọi write API production.
12. Không commit/push/deploy/build EXE trong Goal A.

### 11.2. Bản bàn giao cuối

Bản bàn giao cuối đã đạt TDP-114 trên source hoàn tất BK/NXT/M-Invoice: full test/QC/browser, build đúng source candidate, smoke đúng source và EXE, gói không chứa bí mật và có hash mới. TDP-115 đã được chủ dự án đóng bằng xác nhận cấu hình in/khay; không còn yêu cầu in giấy thật như một gate kỹ thuật.

## 12. Mẫu nhật ký hoàn thành Goal phải cập nhật

Mỗi dòng hoàn thành dùng mẫu:

```text
- YYYY-MM-DD HH:mm – TDP-XXX [x]
  - Thay đổi: <mô tả ngắn>
  - File: <file chính>
  - Test: <lệnh và kết quả>
  - Golden/QC: <artifact hoặc số đối chiếu, không chứa PII>
  - Rủi ro còn lại: <không có hoặc ID Q-xxx>
```

### Nhật ký hoàn thành

- 2026-09-02 14:34 – TDP-000 [x]
  - Thay đổi: thêm lệnh baseline tái lập có guard SHA-256 quanh unit test, QC và source `/health`; thêm test bắt database thiếu/rỗng hoặc bị sửa.
  - File: `tdp_system/goal_a_baseline.py`, `tdp_system/test_goal_a_baseline.py`, `BIG_PLAN_TDP.md`.
  - Test: `python -m tdp_system.goal_a_baseline` → 99/99 unit test đạt, QC `ok=true`, `/health` `ok=true`, `database_ready=true`, `schema_ready=true`, `integrity=ok`.
  - Golden/QC: database nguồn `tdp_system/data/tdp.sqlite3` giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf` qua mọi bước; QC dùng database test và dọn artifact sau chạy.
  - Rủi ro còn lại: chỉ có cảnh báo openpyxl đã biết về Conditional Formatting extension trong nguồn Excel; không ảnh hưởng kết quả và không sửa file khách.
- 2026-09-02 14:38 – TDP-001 [x]
  - Thay đổi: thêm generator manifest metadata-only cho 9 nguồn bắt buộc và artifact JSON ổn định; ghi vai trò input/output golden/reference/history, hash, kích thước và topology OOXML mà không đọc ra giá trị ô/nội dung Word.
  - File: `tdp_system/golden_manifest.py`, `tdp_system/golden_manifest.json`, `tdp_system/test_golden_manifest.py`, `BIG_PLAN_TDP.md`.
  - Test: 3 test manifest đạt; sinh manifest hai lần cho SHA-256 giống nhau; full baseline 102/102 test đạt, QC `ok=true`, `/health` xanh và database nguồn giữ nguyên.
  - Golden/QC: đủ 9 artifact, 28 sheet và 15 media Word; hash `Em Thành.xlsx`, file ngày, báo giá Toyota và Note Word khớp kiểm chứng ban đầu; manifest SHA-256 `B3C5A7BB372EFE1A1A2FCAEF4C3CD74341A2D7B5F3C6DF612BDF09F934C90E33`.
  - Rủi ro còn lại: tên sheet `CCCD` được giữ vì là topology bắt buộc, nhưng không có số CCCD hay nội dung ô trong manifest.
- 2026-09-02 14:42 – TDP-002 [x]
  - Thay đổi: thêm harness QC ba lớp cho dữ liệu chuẩn hóa, topology/style workbook và render PDF→PNG bằng renderer đã kiểm chứng; report không chứa giá trị ô và chặn render sheet nhận diện cá nhân.
  - File: `tdp_system/golden_workbook_qc.py`, `tdp_system/test_golden_workbook_qc.py`, `BIG_PLAN_TDP.md`.
  - Test: 4 test harness đạt; fixture bắt được sai thứ tự cột tại A1, sai tổng tại B3 và sai print area; renderer self-test bằng Microsoft Excel COM đạt cả ca hai file giống nhau và ca cố ý sai (1 trang, pixel-difference bắt được); full baseline 106/106 test đạt.
  - Golden/QC: renderer `Microsoft Excel COM` + PyMuPDF/Pillow được xác nhận khả dụng; QC `ok=true`, `/health` xanh, database nguồn giữ nguyên hash.
  - Rủi ro còn lại: so pixel chỉ được tuyên bố đạt khi dùng dữ liệu fixture/golden có cùng nội dung dự kiến hoặc có cấu hình tolerance/mask phù hợp; không dùng pixel diff thô để phán sai các ô dữ liệu động.
- 2026-09-02 14:54 – TDP-069 [x]
  - Thay đổi: thêm module/schema batch hóa đơn riêng, API chuẩn bị/list phiên idempotent và UI hai tab đầu vào/đầu ra với `từ ngày–đến ngày`, filter trạng thái, số đếm, audit và lưu bộ lọc qua reload; chưa gọi nguồn ngoài hoặc ghi kho.
  - File: `tdp_system/invoice_workbench.py`, `tdp_system/test_invoice_workbench.py`, `tdp_system/browser_smoke_invoice_workbench.js`, `tdp_system/server.py`, `tdp_system/static/index.html`, `tdp_system/static/app.js`, `tdp_system/static/real.css`, `BIG_PLAN_TDP.md`.
  - Test: 6 test domain/API/UI/server-wiring đạt; Node syntax đạt; Edge headless browser smoke trên source/database tạm đạt cho chuyển hai tab, khoảng 01–31/08/2026, tạo phiên, reload giữ filter; full baseline 112/112 test đạt.
  - Golden/QC: source tạm `/health` xanh; QC `ok=true`; database nguồn giữ nguyên SHA-256; test server/Edge đã dừng sau smoke.
  - Rủi ro còn lại: TDP-069 mới chuẩn bị batch/read-only workbench; việc kéo hóa đơn đầu vào và cập nhật tiến độ batch thuộc TDP-070, đầu ra thuộc TDP-074, chưa được coi là đã ghi kho.
- 2026-09-02 15:04 – TDP-070 [x]
  - Thay đổi: thêm đồng bộ mSMI đầu vào theo batch và khoảng ngày inclusive; mỗi lần gọi đều truyền `INPUT_ELECTRONIC_INVOICE` + `from/to`, cursor anchor riêng từng batch, paging/reconcile idempotent, link batch–hóa đơn, đếm trạng thái, quarantine, freeze chứng từ đã post và rollback nguyên lần gọi; khóa route đồng bộ toàn cục không có ngày. UI đầu vào tạo batch rồi tải, đầu ra vẫn chỉ chuẩn bị cho TDP-074.
  - File: `tdp_system/invoice_input_sync.py`, `tdp_system/invoice_workbench.py`, `tdp_system/contract_modules.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/test_invoice_input_sync.py`, `tdp_system/browser_fixture_invoice_input_server.py`, `tdp_system/browser_smoke_invoice_input_sync.js`, `BIG_PLAN_TDP.md`.
  - Test: 21 test tập trung đạt; full baseline 117/117 test đạt; Node syntax đạt; Edge headless browser smoke trên source/database tạm đạt cho thao tác tải đầu vào 01–31/08/2026 và hiển thị hóa đơn chờ ghép mã.
  - Golden/QC: QC `ok=true`, source tạm `/health` xanh; database nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; audit chỉ chứa khoảng ngày/counter/error code, API không lộ cursor remote ID hay payload; server/Edge tạm đã dừng.
  - Rủi ro còn lại: chưa gọi tài khoản mSMI thật theo ranh giới Goal; hóa đơn đầu ra và ánh xạ trạng thái phát hành/hủy/thay thế thuộc TDP-074, nghiệm thu nguồn live còn Q-011.
- 2026-09-02 15:14 – TDP-074 [x]
  - Thay đổi: thêm kho chờ đầu ra và dòng nguồn tách khỏi đầu vào, định danh idempotent theo source + remote ID và hash khóa ký hiệu/số/ngày, đồng bộ `OUTPUT_ELECTRONIC_INVOICE` theo khoảng ngày/cursor batch, API hàng chờ đã lọc raw/remote ID và UI tải/hiển thị đầu ra. Cổng trạng thái là deny-by-default: chỉ field + allow-list được cấu hình rõ mới công nhận `issued`; draft/unknown bị chặn, hủy/thay thế/điều chỉnh tạo event đối chiếu, dữ liệu đã post được đóng băng và chuyển `reversal_required` thay vì sửa/xóa.
  - File: `tdp_system/invoice_output_sync.py`, `tdp_system/invoice_workbench.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/test_invoice_output_sync.py`, `tdp_system/browser_fixture_invoice_input_server.py`, `tdp_system/browser_smoke_invoice_workbench.js`, `BIG_PLAN_TDP.md`.
  - Test: 8 test TDP-074 và 19 test lát invoice workbench đạt; full baseline 125/125 test đạt; Edge headless browser source smoke trên database/connector fixture đạt cho tab đầu ra, khoảng 01–31/08/2026, queue issued và reload giữ filter.
  - Golden/QC: QC `ok=true`, source tạm `/health` xanh; database nguồn giữ nguyên SHA-256; cùng số khác ký hiệu tạo hai business key, retry không nhân đôi invoice/event, lỗi trang sau rollback nguyên lần; audit không có payload/remote ID và server/Edge tạm đã dừng.
  - Rủi ro còn lại: Q-011 vẫn chặn duy nhất nghiệm thu connector/trường trạng thái trên tài khoản thật. Source candidate không đoán status production; khi chưa cấu hình, toàn bộ đầu ra được tải ở trạng thái `unknown` và không thể trừ kho.
- 2026-09-02 15:22 – TDP-071 [x]
  - Thay đổi: thêm mapping được người dùng xác nhận với scope `tenant + source + chiều hóa đơn + đối tác + mã/tên/ĐVT nguồn`, áp dụng/recover sau re-sync nhưng tuyệt đối không lan giữa đầu vào và đầu ra; API chung hai chiều, UI tìm mã và Enter để lưu, tô màu mapped/unmapped/unit-review, filter dòng chưa ghép/khác ĐVT/lỗi. ĐVT không trùng chỉ ghi `unit_review`, không làm hóa đơn sẵn sàng.
  - File: `tdp_system/invoice_mapping.py`, `tdp_system/invoice_workbench.py`, `tdp_system/invoice_input_sync.py`, `tdp_system/invoice_output_sync.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/static/real.css`, `tdp_system/test_invoice_mapping.py`, hai browser smoke fixture, `BIG_PLAN_TDP.md`.
  - Test: 6 test mapping domain/API/UI đạt; full baseline 131/131 test đạt; Edge headless source smoke riêng cho cả tab đầu vào và đầu ra đạt thao tác gõ `P-BROWSER` + Enter, refresh state và hiển thị mapping.
  - Golden/QC: QC `ok=true`, `/health` xanh, database nguồn giữ nguyên SHA-256; test chứng minh cùng partner + source line vẫn tạo hai mapping riêng theo chiều, mapping sống qua re-sync, mapping đã post/reversal bị đóng băng và audit không chứa partner/tên hàng nguồn.
  - Rủi ro còn lại: TDP-071 chỉ công nhận mapping khi ĐVT nguồn = ĐVT đích; nhập hệ số quy đổi, số lượng/đơn giá sau quy đổi và effective mapping thuộc TDP-072.
- 2026-09-02 15:30 – TDP-072 [x]
  - Thay đổi: thêm hệ số quy đổi dương được xác nhận, khoảng hiệu lực tùy chọn và revision append-only; snapshot từng dòng giữ nguyên số nguồn đồng thời lưu `conversion_factor`, `stock_qty = source_qty × factor` và `stock_unit_price = amount / stock_qty`. Áp dụng hai chiều, sống qua re-sync, chặn overlap/invalid/frozen; UI hiện phép tính `1 ĐVT nguồn = hệ số ĐVT kho`, lưu và cập nhật SL/giá kho.
  - File: `tdp_system/invoice_mapping.py`, `tdp_system/invoice_workbench.py`, `tdp_system/contract_modules.py`, `tdp_system/invoice_output_sync.py`, `tdp_system/static/app.js`, `tdp_system/static/real.css`, `tdp_system/test_invoice_mapping.py`, browser fixtures/smokes, `BIG_PLAN_TDP.md`.
  - Test: 11 test mapping/quy đổi đạt, gồm factor 30 và 0,5, effective range, conflict, invalid/rollback, promo, hai chiều và API; full baseline 136/136 test đạt. Browser source smoke cả hai tab đạt chuỗi keyboard mapping → khác ĐVT → hệ số 30 → `SL kho 30`.
  - Golden/QC: QC `ok=true`, `/health` xanh, database nguồn giữ nguyên SHA-256; input `1 kg = 30 thùng` fixture cho SL kho 30 và giá kho 333,333333; output factor 0,5 cho SL 0,5; khuyến mại factor 30 cho SL kho 60 nhưng giá kho 0; audit không chứa payload/credential.
  - Rủi ro còn lại: TDP-072 mới tạo snapshot đủ điều kiện; endpoint phiếu nhập cũ vẫn dùng qty/unit_price nguồn và phải được thay bằng snapshot quy đổi, khóa idempotent/audit ở TDP-073 trước khi coi là ghi kho đúng.
- 2026-09-02 15:36 – TDP-073 [x]
  - Thay đổi: thay route phiếu nhập bằng engine atomic kiểm tra lại mapping/effective conversion hiện hành rồi chỉ ghi `stock_qty/stock_unit_price`; giữ source qty/amount để reconcile, bỏ dòng tài chính khỏi kho, đưa promo có SL vào kho với giá 0, phát hiện ledger conflict và stale snapshot, retry theo source key không trùng. Route mapping cũ được đưa qua mapping engine mới để không còn đường bypass snapshot.
  - File: `tdp_system/invoice_receipt.py`, `tdp_system/invoice_mapping.py`, `tdp_system/contract_modules.py`, `tdp_system/test_invoice_receipt.py`, `tdp_system/browser_smoke_invoice_input_sync.js`, `BIG_PLAN_TDP.md`.
  - Test: 5 test receipt đạt; full baseline 141/141 test đạt; QC flow `msmiIdempotentSyncMappingReceipt=passed`; Edge headless source smoke đạt toàn chuỗi tải → keyboard mapping → factor 30 → SL kho 30 → tạo phiếu nhập → trạng thái posted.
  - Golden/QC: QC `ok=true`, `/health` xanh, database nguồn giữ nguyên SHA-256; fixture 2 thùng × 30 = 60 gói ở giá kho 166,666667 và 1 thùng promo = 30 gói giá 0, discount không có bút toán; lỗi dòng thứ hai rollback cả dòng đầu và giữ invoice `ready`.
  - Rủi ro còn lại: TDP-073 chỉ khóa chiều nhập. TDP-080 phải hợp nhất source-of-truth nhập/xuất và triển khai reversal idempotent cho trạng thái đầu ra sau khi post; Q-011 vẫn chặn nghiệm thu status nguồn live nhưng không chặn domain/fixture.
- 2026-09-02 15:48 – TDP-080 [x]
  - Thay đổi: thêm ledger hóa đơn append-only tách khỏi ledger vận hành; view tồn chuẩn chỉ lấy `OPENING` từ ledger cũ rồi cộng nhập hóa đơn đã post, trừ đầu ra đã phát hành + ghép/đổi ĐVT đủ + người dùng xác nhận. Draft/reservation và projection `MSMI_INPUT` không bị tính hai lần; output thiếu trạng thái/mapping/xác nhận/tồn đều bị chặn. Hủy/thay thế/điều chỉnh thêm reversal tham chiếu bút toán gốc, giữ nguyên lịch sử; ghi lùi ngày kiểm tra mọi số dư ngày về sau; mọi event truy ngược được invoice/dòng/revision mapping/confirmation. UI có hai nút xác nhận rõ và API tồn/trace chỉ đọc.
  - File: `tdp_system/invoice_inventory.py`, `tdp_system/invoice_receipt.py`, `tdp_system/invoice_mapping.py`, `tdp_system/invoice_output_sync.py`, `tdp_system/invoice_workbench.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/test_invoice_inventory.py`, browser fixture/smoke, `BIG_PLAN_TDP.md`.
  - Test: 7 test TDP-080 và 31 test lát invoice liên quan đạt; full baseline 148/148 unit test đạt; Node syntax đạt; Edge headless source smoke trên database/connector fixture đạt chuỗi tải đầu ra 01–31/08/2026 → keyboard mapping → factor 30 → xác nhận xuất → API sổ chuẩn còn 970 từ tồn đầu 1.000.
  - Golden/QC: QC `ok=true`, `/health` `ok=true`, `database_ready=true`, `schema_ready=true`, `integrity=ok`; công thức fixture `10 + 5 − 4 = 11`, retry không nhân đôi, reversal đưa tồn về 10, lỗi dòng thứ hai rollback cả confirmation/event/trạng thái; database nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf` và server/Edge tạm đã dừng.
  - Rủi ro còn lại: Q-011 chỉ còn chặn nghiệm thu field/status connector trên tài khoản thật; khi chưa cấu hình rõ, output vẫn `unknown` và không thể trừ kho. Giá trị xuất chưa lấy giá bán làm giá vốn; valuation giá bình quân thuộc TDP-081.
- 2026-09-02 15:55 – TDP-081 [x]
  - Thay đổi: thêm projection TĐK–NXT read-only rebuild tất định từ opening snapshot + ledger hóa đơn bất biến, dùng bình quân gia quyền di động; input cùng ngày được xếp trước output, reversal sau output. Tiền làm tròn `ROUND_HALF_UP` 0,01 theo movement, SL và đơn giá hiển thị 6 số lẻ; output lưu snapshot giá bình quân để reversal qua kỳ nhưng report luôn rebuild, không lấy giá bán hóa đơn. Chỉ snapshot tồn đầu gần nhất được dùng, không cộng dồn nhiều kỳ; range đi xuyên snapshot mới và post chứng từ lùi trước snapshot mới đều bị chặn. Tồn âm legacy được giữ dấu/giá trị và gắn `negative_opening_review`; SL 0 không chia 0.
  - File: `tdp_system/invoice_valuation.py`, `tdp_system/invoice_inventory.py`, `tdp_system/invoice_receipt.py`, `tdp_system/server.py`, `tdp_system/test_invoice_valuation.py`, `BIG_PLAN_TDP.md`.
  - Test: 6 test valuation/API đạt, gồm opening + hai lần nhập + hai lần xuất, backdate/rebuild lặp lại giống hệt, latest opening snapshot, range crossing, input/output lùi kỳ bị chặn, tồn âm/zero quantity và reversal qua kỳ; full baseline 154/154 unit test đạt.
  - Golden/QC: fixture `10×100 + 10×200 + 5×300 − (5×150 + 5×187,5) = 15×187,5 = 2.812,5`; giá bán 10.000/20.000 không đi vào giá vốn; backdate đổi projection output từ 100 thành 200 nhưng ledger gốc giữ nguyên; QC `ok=true`, `/health` xanh và database nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`.
  - Rủi ro còn lại: file Excel TĐK/Nhập/Xuất/NXT thuộc TDP-082; hình thức NXT cuối vẫn phụ thuộc Q-005, còn domain/số liệu đã đủ căn cứ để tiếp tục.
- 2026-09-02 16:01 – TDP-010 [x]
  - Thay đổi: thêm contract/migration mở rộng bốn bảng cho workday, version workbook, scope xác nhận và row identity mà không sửa cấu trúc/dữ liệu `batches/orders` cũ. Cùng `work_date + sheet ngày` dùng một batch; hash workbook/phase/scope/state tạo version idempotent. Khóa dòng dùng ngày + scope + nhà thầu/bếp/mã hoặc tên hàng/ĐVT/occurrence, không dùng SL/giá nên lần chốt sau cập nhật đúng dòng; payload chỉ lưu hash. Vòng đời `picking/finalized` tách khỏi approval cũ; `customer_orders` và `purchase_orders` cấp hai write capability riêng, state-hash chống stale, audit chỉ hash/counter/version/thời điểm. Migration, prepare, confirm và finalize đều có rollback nguyên khối.
  - File: `tdp_system/daily_import_lifecycle.py`, `tdp_system/server.py`, `tdp_system/test_daily_import_lifecycle.py`, `BIG_PLAN_TDP.md`.
  - Test: 9 test contract/migration đạt: fresh/legacy/repeat, DDL fail giữa chừng rollback, replay/đồng thời logic không tạo batch mới, workbook thay đổi thành version mới cùng batch, identity sống qua đổi SL, scope độc lập + stale lock, prepare/confirm/finalize rollback và integrity `ok`; full baseline 163/163 unit test đạt.
  - Golden/QC: QC `ok=true`, `/health` xanh và phát hiện được schema lifecycle dở dang nếu đã bắt đầu migration; audit fixture không chứa tên hàng, ghi chú khách hay CCCD; database nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`.
  - Rủi ro còn lại: TDP-010 mới khóa contract, chưa nối parser/token/UI vào workbook khách. TDP-011 chịu trách nhiệm preview/confirm trực tiếp `Đơn hàng 01.09.2026.xlsx`; TDP-012 mới thực hiện lần chốt thứ hai theo scope.
- 2026-09-02 16:15 – TDP-011 [x]
  - Thay đổi: thêm nhận diện workbook theo cấu trúc + ngày, phân vai sheet ngày/đặt NCC/tham chiếu mà không dựa vị trí; preview chỉ trả metadata an toàn cùng số dòng lỗi/cảnh báo/phạm vi ghi. Luồng strict khóa `đặt hàng` và mọi sheet tham chiếu, dùng state-hash + token một lần; confirm `customer_orders` tạo/cập nhật đúng một lifecycle batch trong `BEGIN IMMEDIATE`, thay scope nguyên khối khi workbook đổi và rollback toàn phần khi lỗi. Luồng workbook legacy được giữ tương thích; UI tự chọn duy nhất sheet ngày có quyền ghi.
  - File: `tdp_system/daily_workbook_import.py`, `tdp_system/daily_import_lifecycle.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/test_daily_workbook_import.py`, `tdp_system/qc_system.py`, `tdp_system/dry_run_real_migration.py`, `BIG_PLAN_TDP.md`.
  - Test: 6 test strict mới + 7 test legacy tập trung đạt; full regression 169/169 đạt; Node syntax đạt; failure trigger ở INSERT order trả 500 có chủ đích và chứng minh rollback cả batch/order/receipt/workday/version/scope/row về 0; `git diff --check` không có lỗi nội dung.
  - Golden/QC: đúng file `Đơn hàng 01.09.2026.xlsx` nhận `01.09` = 323/323 dòng và `đặt hàng` = 259 dòng chỉ-preview; sáu vai trò tham chiếu được loại, gồm `gộp đơn`; preview báo 163 dòng lỗi + 57 dòng cảnh báo mà không lộ giá trị CCCD. Confirm trên bản sao DB tạo 323 order/323 lifecycle row; đổi tên cùng bytes trả cùng batch/import-key, không nhân đôi. QC `ok=true`, `/health` xanh, DB nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`.
  - Rủi ro còn lại: TDP-014 tiếp tục khóa contract sử dụng riêng cho sáu sheet tham chiếu; ghi/round-trip sheet `đặt hàng` thuộc TDP-020 và lần chốt thứ hai thuộc TDP-012, nên TDP-011 cố ý không cấp quyền ghi hai phần đó.
- 2026-09-02 16:26 – TDP-014 [x]
  - Thay đổi: gắn policy rõ cho sáu sheet reference ngay trong preview đơn ngày. `CCCD` chỉ dành cho chứng từ, `BÁO GIÁ` khóa tới TDP-050 và `gộp đơn` chỉ là trung gian; cả ba không có parser ghi. `T.chiếu`, `danh mục hàng hóa` và `danh mục nhà cc` dùng API preview/confirm tách biệt theo đúng role, state-hash gắn DB snapshot, token một lần, receipt theo role+bytes không phụ thuộc tên file và `BEGIN IMMEDIATE`; blank cache không xóa master. Product confirm chỉ được đổi tên/ĐVT/thuế/nhóm/tên hóa đơn; supplier mapping chỉ đổi NCC; mọi giá mua/giá bán/CCCD/seller và trường ngoài scope được bảo toàn. Audit chỉ role/hash/count.
  - File: `tdp_system/daily_reference_import.py`, `tdp_system/daily_workbook_import.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/test_daily_reference_import.py`, `tdp_system/test_daily_workbook_import.py`, `BIG_PLAN_TDP.md`.
  - Test: 7 test reference mới và 19 test lát daily/reference/legacy đạt; gồm khóa ba role không được ghi, order confirm không đổi sáu nhóm master, stale state/token, database đổi giữa chừng, replay đổi tên file, product/supplier field boundary và failure trigger rollback contractor+kitchen+receipt+audit. Full regression 176/176 đạt; Node syntax và `git diff --check` đạt.
  - Golden/QC: trên `Đơn hàng 01.09.2026.xlsx`, preview riêng `T.chiếu` nhận 23 dòng khớp hoàn toàn; `danh mục hàng hóa` nhận 1.249 dòng và fail-closed vì 4 lỗi; `danh mục nhà cc` nhận 1.027 dòng có NCC, 178 diff và fail-closed vì 6 lỗi. Confirm riêng sheet ngày trên bản sao tạo 323 order nhưng digest toàn bộ contractors/kitchens/products/product_prices/suppliers/people không đổi. QC `ok=true`, `/health` xanh và database nguồn giữ nguyên SHA-256.
  - Rủi ro còn lại: bốn lỗi catalog và sáu lỗi supplier trong file thật phải được sửa/duyệt ở runtime trước khi reference confirm; giá kỳ vẫn chỉ được xử lý ở TDP-050, dữ liệu CCCD chỉ đi vào nghiệp vụ chứng từ chuyên trách, không qua importer reference.
- 2026-09-02 16:38 – TDP-013 [x]
  - Thay đổi: thêm chỉnh giá bán ngay trên lưới bằng Enter cho từng dòng hoặc nút lưu các dòng đã đổi; bắt buộc người thực hiện/lý do, revision optimistic và transaction atomic. Mọi thay đổi ghi lịch sử riêng cùng audit; generic edit/bulk API không thể đi vòng qua audit. Giá override chỉ nằm trên order, không sửa `product_prices`; grid/modal khóa đúng đường sửa và hiển thị nguồn/revision.
  - File: `tdp_system/order_price_override.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/static/real.css`, `tdp_system/test_order_price_override.py`, `tdp_system/test_final_safety_regressions.py`, `tdp_system/browser_fixture_order_price_server.py`, `tdp_system/browser_smoke_order_price.js`, `BIG_PLAN_TDP.md`.
  - Test: 6 test TDP-013 và 13 test lát giá/safety đạt; full regression 182/182 đạt; kiểm tra Python/Node syntax và `git diff --check` đạt. Test gồm chỉnh một dòng, bulk rollback khi lỗi dòng thứ hai, stale revision, giá NaN/âm/0 sai rule, khuyến mại khác 0, actor/lý do và chặn hai đường bypass.
  - Golden/QC: Edge headless source smoke trên database tạm đạt chuỗi giá 12.000 → Enter 15.000 revision 2 → bulk 16.000 revision 3, doanh thu 32.000 và hai lịch sử đúng actor/lý do. Phải thu kỳ sau duyệt dùng 30.000 cho 2 × 15.000; price book chuẩn giữ nguyên. QC `ok=true`; `/health` trả `ok/database_ready/schema_ready=true`, `integrity=ok`; database nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; server/Edge tạm đã dừng.
  - Rủi ro còn lại: không có trong phạm vi TDP-013; override trên phiên đã duyệt bị khóa theo lifecycle hiện hành và muốn sửa phải thao tác khi phiên còn mở.
- 2026-09-02 17:03 – TDP-020 [x]
  - Thay đổi: thay biểu mẫu NCC tự thiết kế bằng một sheet `đặt hàng` canonical bám đúng bố cục khách C:P; A/B/Q được ẩn để giữ tương thích và identity dòng ổn định. Thêm ledger mua riêng 15 trường nghiệp vụ, parser canonical + migration file nội bộ 13 cột, preview/confirm atomic với state-hash, stale/replay guard và dòng mua độc lập không buộc tạo order bán giả. Giá/lượng/supplier phần mua chỉ tạo phải trả từ ledger mua, tuyệt đối không ghi ngược order khách, doanh thu, phải thu hoặc kho hóa đơn. Export/preview UI, hướng dẫn sử dụng và projection PDF cùng dùng contract mới; PDF tự tính công thức chưa có cache thay vì in chuỗi công thức.
  - File: `tdp_system/contract_modules.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/print_bundle.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `tdp_system/test_purchase_order_roundtrip.py`, `tdp_system/browser_fixture_purchase_bridge_server.py`, `tdp_system/browser_smoke_purchase_bridge.js`, `BIG_PLAN_TDP.md`.
  - Test: 11 test round-trip mua đạt, gồm golden 259 dòng, 6 dòng mua độc lập, file legacy 13 cột, replay idempotent, stale preview và failure trigger rollback; full regression 185/185 đạt; `git diff --check` không có lỗi nội dung. Edge headless source smoke đạt chuỗi tải file → preview → confirm 7 × 50.000 = 350.000; order bán vẫn 10 × 30.000, phải thu 300.000 và phải trả 350.000.
  - Golden/QC: file thật `Đơn hàng 01.09.2026.xlsx` nhận đúng 259 dòng; export lại giữ nguyên tổng khi chưa sửa, ba cột identity ẩn, công thức O/P đúng và PDF đọc được giá trị số. QC `ok=true`; source `/health` trên DB tạm trả `ok/database_ready/schema_ready=true`, `integrity=ok`; database nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; server/Edge tạm đã dừng.
  - Rủi ro còn lại: golden có một dòng mua ngoài số lượng dương nhưng chưa có giá; TDP-020 chỉ cảnh báo để hoàn tất cầu nối. TDP-021 đang làm sẽ chặn confirm/chốt theo đúng quy tắc giá, chuẩn hóa dấu bốn điều chỉnh và VND rounding.
- 2026-09-02 18:29 – TDP-021 [x]
  - Thay đổi: chốt công thức canonical theo formula/cache của file khách: `SL thực tế = Số lượng + Thêm − Hỏng − Giảm − Thiếu`; parser đối chiếu cả công thức lẫn giá trị cache/static, tính `Thành tiền = SL thực tế × giá mua chốt` bằng HALF_UP VND. Mua ngoài có lượng dương nhưng giá không hợp lệ bị chặn; `Kho` vẫn được phép giá 0. Ledger lưu nguyên từng thành phần và thêm lịch sử revision append-only cùng tổng thành phần trong audit; confirm chỉ ghi dòng thực sự đổi, replay không sinh lịch sử thừa và stale preview bị khóa.
  - File: `tdp_system/contract_modules.py`, `tdp_system/static/app.js`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `tdp_system/test_purchase_order_roundtrip.py`, `tdp_system/browser_fixture_purchase_bridge_server.py`, `tdp_system/browser_smoke_purchase_bridge.js`, `BIG_PLAN_TDP.md`.
  - Test: 13 test round-trip mua đạt; full regression 187/187 đạt trong 79,890 giây. Bao phủ riêng hỏng/thêm/giảm/thiếu, tổ hợp, HALF_UP VND, âm/NaN, công thức sai, cache tĩnh stale, giá ngoài bằng 0/âm, rollback, replay, stale preview và revision chỉ tăng ở dòng đổi; `git diff --check` không có lỗi nội dung.
  - Golden/QC: toàn bộ 259 công thức/cached value O/P của file `Đơn hàng 01.09.2026.xlsx` khớp dấu và phép nhân; đúng một dòng mua ngoài lượng dương thiếu giá bị fail-closed như thiết kế. Edge headless source smoke trên DB tạm đạt 7 + thêm 3 − hỏng 1 − giảm 1 − thiếu 0 = 8 và 8 × 50.000 = 400.000; order bán vẫn 10 × 30.000, phải thu 300.000, phải trả 400.000. QC UTF-8 `ok=true`; `/health` trả `ok/database_ready/schema_ready=true`, `integrity=ok`; database nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; hai listener tạm đã dừng.
  - Rủi ro còn lại: dòng thiếu giá trong file khách phải được người dùng sửa trước khi confirm; đây là dữ liệu đầu vào bị chặn có chủ đích, không phải lỗi source. Chính sách dồn dòng khi trình bày/gửi NCC được xử lý riêng ở TDP-022, không làm thay đổi ledger dòng gốc.
- 2026-09-02 18:38 – TDP-022 [x]
  - Thay đổi: chuẩn hóa danh tính NCC không phân biệt dấu/hoa-thường và tiền tố `Nhà`; cố định đúng rule Hoài chỉ dồn Cà rốt, Thu/Kỳ/Tân/Phượng/Dung/Kho dồn tên hàng giống nhau, NCC khác không tự dồn. API từ chối ghi đè rule cố định; NCC ngoài policy vẫn được người dùng chủ động gom bếp nhưng không tự dồn dòng. Payload tách rõ dòng gốc/dòng trình bày, giữ `source_refs`, số dòng gốc và số dòng gửi; UI hiện badge rule thay cho nút đổi vô hiệu, đồng thời giải thích đủ rule đã chốt.
  - File: `tdp_system/contract_modules.py`, `tdp_system/static/app.js`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `tdp_system/qc_system.py`, `tdp_system/test_purchase_order_roundtrip.py`, `tdp_system/browser_fixture_supplier_merge_server.py`, `tdp_system/browser_smoke_supplier_merge.js`, `BIG_PLAN_TDP.md`.
  - Test: 15/15 test round-trip mua đạt; full regression 189/189 đạt trong 57,060 giây. Bao phủ đủ sáu NCC dồn toàn bộ, Hoài Cà rốt/ngoài Cà rốt, tên giống/khác, khác bếp, NCC ngoài whitelist, biến thể Unicode/hoa-thường/tiền tố `Nhà`, khóa override và xác nhận đọc presentation không sửa 11 dòng ledger gốc; `git diff --check` không có lỗi nội dung.
  - Runtime/QC: Edge headless source smoke trên DB tạm nhận 8 dòng gốc thành 6 dòng gửi: Dung 2→1, Cà rốt Hoài 2→1, Rau muống Hoài giữ hai nhóm, Hương giữ hai nhóm. Gọi đổi rule Dung trả 409; gộp thủ công Hương tạo một thẻ bếp nhưng vẫn hai dòng. QC UTF-8 `ok=true`; source `/health` trả `ok/database_ready/schema_ready=true`, `integrity=ok`; database nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; bốn listener tạm đều đã dừng.
  - Rủi ro còn lại: không có trong phạm vi rule dồn. Trạng thái đã đặt/chưa đặt và hoàn tác là state machine riêng của TDP-023; ảnh Zalo đúng cột/mẫu được khóa tiếp ở TDP-024.
- 2026-09-02 18:48 – TDP-023 [x]
  - Thay đổi: thêm state machine checklist theo khóa `(batch, NCC chuẩn hóa)` với `pending/ordered/reopened`, revision optimistic, timestamp và audit từng chuyển trạng thái. Dòng chưa có record mặc định là pending; thao tác hợp lệ là pending/reopened→ordered và ordered→reopened. Payload trả checklist theo NCC và đưa reopened/pending lên trước ordered; mọi nhóm của cùng NCC dùng chung trạng thái. UI có badge/nút chủ đích, giữ nguyên thẻ đã đặt ở cuối, giải thích rõ tải/sao chép ảnh không tự đánh dấu và bust cache asset source.
  - File: `tdp_system/contract_modules.py`, `tdp_system/static/app.js`, `tdp_system/static/real.css`, `tdp_system/static/index.html`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `tdp_system/test_supplier_order_checklist.py`, `tdp_system/browser_smoke_supplier_checklist.js`, `tdp_system/browser_fixture_supplier_merge_server.py`, `BIG_PLAN_TDP.md`.
  - Test: 3 test checklist chuyên biệt và 18 test lát mua/checklist đạt; full regression 192/192 đạt trong 60,100 giây. Bao phủ ordered→reopened→ordered, client mới/reload, giữ nguyên nhiều nhóm và dòng gốc, audit ba bước, hai request đồng thời cùng revision chỉ một request thắng, stale 409, transition sai/mất revision, supplier không thuộc batch và hai batch độc lập; `git diff --check` không có lỗi nội dung.
  - Runtime/QC: Edge headless source smoke trên DB tạm chứng minh 3 NCC pending; tải PNG không đổi trạng thái; đánh dấu Dung chuyển xuống cuối; reload giữ ordered revision 1; hoàn tác đưa reopened lên đầu; đánh dấu lại thành ordered revision 3. Sáu thẻ/tám dòng gốc vẫn nguyên. QC UTF-8 `ok=true`; source `/health` trả `ok/database_ready/schema_ready=true`, `integrity=ok`; database nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; toàn bộ listener tạm đã dừng.
  - Rủi ro còn lại: không có trong state machine checklist. Nội dung pixel của ảnh gửi NCC vẫn là phạm vi TDP-024; TDP-023 cố ý không tự đánh dấu từ hành động ảnh.
- 2026-09-02 18:58 – TDP-024 [x]
  - Thay đổi: khóa contract ảnh gửi NCC ở backend và renderer đúng bảy trường `Mã bếp`, `Ngày`, `Tên hàng`, `Số lượng`, `ĐVT`, `NCC`, `Ghi chú`; bỏ dòng tổng sau trừ tồn và không đưa giá, thành tiền, tồn hay thành phần kiểm soát nội bộ vào canvas. Renderer nhận danh sách cột từ contract, hỗ trợ xuống dòng tên hàng/ghi chú; hướng dẫn vận hành ghi rõ ranh giới dữ liệu ảnh.
  - Nguồn chuẩn: giải nén trực tiếp `Note công việc.docx` và xác nhận `word/media/image6.png` theo thứ tự quan hệ trong document; đối chiếu trực quan ảnh 6 với đúng các dòng `Cà pháo tươi`, `Đỗ đũa`, `Quả bầu` tại sheet `gộp đơn`/`đặt hàng` của `Em Thành.xlsx`, không dùng ảnh chụp rời làm nguồn suy đoán.
  - File: `tdp_system/contract_modules.py`, `tdp_system/static/app.js`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `tdp_system/test_supplier_order_checklist.py`, `tdp_system/browser_fixture_supplier_merge_server.py`, `tdp_system/browser_smoke_supplier_checklist.js`, `BIG_PLAN_TDP.md`.
  - Test: kiểm tra syntax JS/Python đạt; 18 test lát mua/checklist đạt; full regression 192/192 đạt trong 54,464 giây; `git diff --check` không có lỗi nội dung. Test contract khóa chính xác bảy key/label và toàn bộ header cấm.
  - Runtime/QC: Edge headless trên source/DB tạm tải PNG thật 2.800×548; instrumentation canvas bắt đủ bảy header và dữ liệu `POT, BIA`, `01/09/2026`, `Cà rốt`, `5`, `kg`, `Nhà Dũng`, `Giao trước 06:00`, đồng thời không bắt được bất kỳ chuỗi cấm nào. Soi trực quan PNG xác nhận bảng rõ, đủ cột, không có dòng tổng/giá/tồn; tải ảnh không đổi checklist. QC UTF-8 `ok=true`; `/health` trả `ok/database_ready/schema_ready=true`, `integrity=ok`; database nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; hai listener tạm đã dừng.
  - Rủi ro còn lại: không có trong phạm vi nội dung ảnh. TDP-025 tiếp tục khóa bất biến mua/bán xuyên suốt import, dồn, checklist, tạo ảnh, hoàn tác và cập nhật giá lần hai.
- 2026-09-02 19:06 – TDP-025 [x]
  - Thay đổi: thêm regression xuyên biên mua/bán với snapshot bất biến gồm toàn bộ batch/order khách, sổ thanh toán–dư đầu kỳ–điều chỉnh công nợ, summary doanh thu, phải thu khách, tồn kho hóa đơn legacy/canonical và draft/dòng hóa đơn đầu ra. Snapshot được so lại sau từng bước NCC; chỉ purchase workbook/revision, checklist/audit và phải trả NCC được phép đổi.
  - Chuỗi bắt buộc: export rồi import file mua đã sửa với công thức `7 + thêm 2 − hỏng 1 = 8`, thêm dòng Dũng bếp BIA 3 kg và dòng `Kho` 4 kg giá 0; dồn hai dòng Dũng thành một dòng trình bày 11 kg; đọc payload tạo ảnh; ordered→reopened; export/import lần hai đổi riêng giá POT 50.000→60.000. Phải trả đổi đúng 550.000→630.000, còn doanh thu/phải thu khách giữ 460.000 và tồn hóa đơn giữ 52.
  - File: `tdp_system/test_purchase_sales_boundary.py`, `tdp_system/browser_fixture_supplier_merge_server.py`, `tdp_system/browser_smoke_supplier_checklist.js`, `BIG_PLAN_TDP.md`.
  - Test: regression chuyên biệt 1/1 đạt; lát mua/checklist/biên 19/19 đạt; full regression 193/193 đạt trong 55,079 giây; syntax Python/JS và `git diff --check` đạt. Snapshot được so sau confirm file sửa, sau dồn/payload ảnh, sau ordered, sau undo và sau confirm giá lần hai; dòng `Kho` kết thúc `(actual_qty=4, buy_price=0, amount=0)`, bốn revision đúng ba dòng đầu + một dòng đổi giá.
  - Runtime/QC: Edge headless trên source/DB tạm tải PNG thật rồi chạy ordered→reload→reopened→ordered; trước/sau giữ nguyên order, doanh thu 300.000, phải thu 300.000 và tồn hóa đơn 52, trong khi checklist đạt revision 3 và tám dòng mua gốc vẫn nguyên. QC UTF-8 `ok=true`; `/health` trả `ok=true`, `integrity=ok`; database nguồn giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; listener tạm đã dừng.
  - Rủi ro còn lại: không có trong regression ranh giới mua/bán đã chốt. TDP-012 tiếp tục xây cơ chế chốt dữ liệu ngày lần hai theo hai phạm vi bán/giao và mua/phải trả độc lập, có diff/stale/replay.
- 2026-09-02 19:34 – TDP-012 [x]
  - Thay đổi: lần nạp workbook mới cho cùng ngày/sheet nhận lại đúng lifecycle workday và batch cũ, chuyển sang phase `finalization` rồi hiển thị hai capability độc lập `customer_orders` (Bán/giao) và `purchase_orders` (Mua/phải trả). Preview trả diff thêm/sửa/giữ nguyên/bỏ/xung đột; UI không chọn sẵn phạm vi nào và API cũng từ chối danh sách rỗng. State hash khóa toàn bộ dữ liệu có thể ảnh hưởng parse/apply, token chỉ dùng một lần, source bytes được kiểm tra lại, phiên bản cũ bị chặn và replay đúng bytes/dữ liệu là idempotent.
  - Ranh giới/atomicity: Bán/giao chỉ cập nhật trường đơn khách, lượng thực giao, giá bán giao dịch, thuế/tính chất/note theo đúng identity ổn định; giữ nguyên NCC, giá mua và các trường mua, không ghi `product_prices`. Mua/phải trả dùng chung engine canonical/revision của sheet `đặt hàng`, không sửa order/doanh thu/phải thu/kho hóa đơn. Khi chọn cả hai, Bán được áp dụng trước rồi sheet Mua được parse lại trong cùng `BEGIN IMMEDIATE` để dòng mua mới gắn đúng `order_id`; content hash phải giữ nguyên và lỗi ở bất kỳ scope nào rollback cả hai scope lẫn lifecycle/receipt.
  - File: `tdp_system/contract_modules.py`, `tdp_system/daily_workbook_import.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `tdp_system/test_daily_workbook_import.py`, `tdp_system/browser_fixture_daily_finalization_server.py`, `tdp_system/browser_smoke_daily_finalization.js`, `BIG_PLAN_TDP.md`.
  - Test: 11/11 test daily workbook đạt; lát daily/lifecycle/purchase/boundary 35/35 đạt; full regression hiện tại 206/206 đạt trong 55,847 giây. Bao phủ nạp lần một→chốt Mua riêng→stale DB bị chặn→chốt Bán riêng→replay, không chọn scope, conflict khi bỏ order đã liên kết, rollback hai scope khi trigger lỗi, dòng bán mới không phát sinh phải trả và trường hợp cả hai sheet cùng thêm dòng mới: hai purchase line đều gắn đúng hai order, replay vẫn chỉ hai dòng.
  - Runtime/QC: Edge headless chạy source/DB tạm đạt `scope_defaults=none`; chốt Mua giữ doanh thu 120.000 và tạo phải trả 99.000, chốt Bán sau đưa doanh thu lên 128.000 nhưng phải trả vẫn 99.000. `/health` trả `ok=true`, `database_ready=true`, `schema_ready=true`, `integrity=ok`; QC UTF-8 `ok=true`; Python/Node syntax và `git diff --check` đạt. Database nguồn trước/sau giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; các listener tạm đã dừng.
  - Rủi ro còn lại: không có trong phạm vi chốt dữ liệu ngày lần hai. TDP-030 tiếp tục biến từng dòng mua đã chốt thành ledger phải trả chi tiết, có trạng thái và cutoff lịch sử chống cộng trùng.
- 2026-09-02 20:05 – TDP-030 [x]
  - Thay đổi: thêm module riêng `payable_ledger.py` với hai bảng `payable_ledger_lines` và `payable_ledger_revisions`. Mỗi nguồn mua giữ khóa dòng ổn định, ngày/batch/bếp/mã và tên hàng/số lượng thực tế/ĐVT/giá mua/thành tiền/NCC, nguồn truy vết và snapshot hash; trạng thái gồm `open`, `partially_paid`, `paid`, `reversed`. Nguồn bị bỏ, batch mở lại, dòng chưa chốt, hàng Kho nội bộ hoặc current line nằm trong cutoff lịch sử đều chuyển `reversed` và append revision, không xóa ledger.
  - Tích hợp/ranh giới: init/migration source tạo schema rồi đồng bộ; duyệt batch, sửa/xóa order, import sheet `đặt hàng`, chốt mua lần hai và import snapshot lịch sử đều refresh ledger trong cùng transaction. `/api/debts/payables/ledger` lọc kỳ/NCC/trạng thái và trả chi tiết + tổng; route revision truy ngược toàn bộ thay đổi. `/api/debts` dùng cùng một projection mua/cutoff để không còn hai cách cộng khác nhau. Mã NCC master được giữ ổn định qua đổi tên; mã hợp lệ khác nhau như `DUNG`/`dũng` không bị gộp do so khớp bỏ dấu; tên cũ được NCC khác dùng lại cũng không cướp tham chiếu đã chốt.
  - Lịch sử/idempotency: snapshot khách vẫn giữ 9.975 dòng phải trả; current line đến hết cutoff bị triệt tiêu khỏi số active nhưng còn audit. Nạp lại cùng nguồn không thêm dòng/revision; snapshot thay thế cập nhật cùng source row, thêm dòng mới và chỉ reverse dòng bị bỏ. Hook `set_payable_allocation_total` chỉ duy trì tổng đã phân bổ và chặn overpayment, chưa tự chọn/phân bổ thanh toán vì đó là TDP-031.
  - File: `tdp_system/payable_ledger.py`, `tdp_system/server.py`, `tdp_system/contract_modules.py`, `tdp_system/dry_run_real_migration.py`, `tdp_system/qc_system.py`, `tdp_system/test_payable_ledger.py`, `tdp_system/test_daily_workbook_import.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`.
  - Test: 8/8 test ledger chuyên biệt và full regression 206/206 đạt trong 55,847 giây. Bao phủ current + history, period/cutoff, repeat, replace/remove→revision/reversed, batch approve/reopen, partial/paid/overpayment, rollback transaction, đổi tên/tái sử dụng tên NCC và va chạm mã có/không dấu. Các traceback `forced ... failure` là fixture chủ động kiểm chứng rollback; không có test hỏng.
  - Runtime/QC: source hiện tại chạy trên DB/cổng tạm `18785`; `/health` trả `ok=true`, `database_ready=true`, `schema_ready=true`, `integrity=ok`; endpoint ledger trả đủ bốn trạng thái và `ok=true`; listener tạm đã dừng, listener `8765` có sẵn của người dùng không bị tác động. QC UTF-8 `ok=true`, lịch sử `9.976 source rows / 9.975 payable lines / 0 errors / repeat safe`; QC còn kiểm trực tiếp 9.975 ledger row và 9.975 revision không nhân đôi. Cảnh báo openpyxl về extension Conditional Formatting của workbook khách đã được phân loại là cảnh báo đọc file có sẵn, không làm QC hoặc ledger sai.
  - An toàn: `git diff --check` không có whitespace error; database nguồn trước/sau giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; không gọi write API production, không commit/push/build/deploy. TDP-031 tiếp tục tạo giao dịch thanh toán/phân bổ/reversal có audit, không FIFO hoặc tự chia tiền.
- 2026-09-02 20:21 – TDP-031 [x]
  - Thay đổi: mở rộng giao dịch `payments` bằng phương thức, mã tham chiếu, trạng thái, request id/hash, revision và thông tin reversal; thêm `payable_payment_allocations` giữ số tiền của từng dòng nợ cùng revision ledger trước/sau và `payable_payment_revisions` giữ snapshot create/reverse. Migration thêm cột tại chỗ, chạy lặp an toàn và bảo toàn giao dịch cũ. API riêng tạo/list/reverse/xem revisions nằm trong `payable_payments.py`; giao dịch trả NCC qua endpoint cũ cũng đi qua cùng domain contract.
  - Quy tắc an toàn: trả NCC bắt buộc người dùng gửi danh sách dòng + số tiền từng dòng + expected revision; tổng phân bổ phải bằng đúng số tiền giao dịch. Không có code FIFO, chia tỷ lệ, tự chọn dòng, credit hoặc overpayment. Mọi write dùng `BEGIN IMMEDIATE`; revision cũ bị từ chối sau writer đầu tiên. Request id cùng nội dung replay idempotent, cùng id khác nội dung bị chặn. Dòng khác NCC, đã paid/reversed, trùng lựa chọn, tiền lẻ không phải VND nguyên và phân bổ vượt còn nợ đều bị chặn trước khi ghi.
  - Trạng thái/audit: một dòng có thể nhận nhiều payment và chuyển `open → partially_paid → paid`; paid không xuất hiện trong ledger mặc định nhưng còn trong `status=all`, lịch sử payment và hai lớp revision. Reversal có lý do, đảo đúng các allocation đang posted và tính lại tổng phân bổ từ ledger; nếu nguồn mua đã reversed thì trạng thái nguồn vẫn reversed nhưng tiền phân bổ được trả về 0. Endpoint `DELETE /api/payments/<id>` từ chối khoản trả NCC với `payable_reversal_required`; không xóa transaction/allocation. Aggregate `/api/debts`, bootstrap và báo cáo cũ chỉ tính payment `posted`, nên reversal không làm giảm công nợ lần hai; thu khách hàng cũ không đổi hành vi.
  - File: `tdp_system/payable_payments.py`, `tdp_system/payable_ledger.py`, `tdp_system/server.py`, `tdp_system/contract_modules.py`, `tdp_system/qc_system.py`, `tdp_system/dry_run_real_migration.py`, `tdp_system/test_payable_payments.py`, `tdp_system/browser_fixture_payable_payment_server.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`.
  - Test: 7/7 test TDP-031 đạt; full regression 213/213 đạt trong 57,688 giây. Bao phủ full/partial, một payment nhiều dòng, nhiều payment cùng dòng, replay/conflict request id, mismatch tổng, cross-supplier, duplicate, overpayment, migration giao dịch cũ, period/status filter, true concurrent writers, reversal/replay, source đã reversed, chặn delete và trigger lỗi giữa transaction rollback sạch payment/allocation/ledger/audit. Traceback `forced allocation failure` là fixture chủ động, test vẫn xanh.
  - Runtime/QC: source/DB tạm cổng `18786` đạt `/health ok` và `integrity=ok`; dòng 100 chuyển `open → paid`, ledger mặc định từ 1 còn 0 dòng, payment history vẫn có 1; reversal trả về `open`, remaining 100 và revisions `create → reverse`. Listener `18786` đã dừng; listener `8765` có sẵn của người dùng không bị tác động. QC UTF-8 `ok=true` và thêm gate `explicit line allocation / reversal / history passed`; cảnh báo Conditional Formatting vẫn là warning input đã phân loại.
  - An toàn: database nguồn trước/sau giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; không gọi write API production, không commit/push/build/deploy. TDP-032 tiếp tục xuất Excel tổng hợp kỳ + chi tiết NCC + lịch sử payment/reversal từ ledger mới; TDP-033 mới hợp nhất thao tác chọn dòng vào UI.
- 2026-09-02 20:39 – TDP-032 [x]
  - Đối chiếu mẫu: đã đọc trực tiếp `bosung.30.8.26/Công nợ phải trả Thành Đạt Phát.xlsx` (SHA-256 `BC54C62E7B7141BA1846EB5BD7EEC9E11B9CC8DA68FB138D0EA0F0CDD7BAF473`). Giữ đúng thứ tự 14 cột nghiệp vụ có căn cứ từ mẫu: Tháng, Tên bếp, Ngày, Tên hàng, Số lượng, ĐVT, NCC, Giá mua, Hỏng, Thêm, Giảm, Thiếu, SL thực tế, Thành tiền; không sao chép lỗi tiêu đề Thành tiền là công thức, freeze `A9969`, print area dừng ở dòng 4343 hoặc công thức/cache cũ.
  - Thay đổi: thêm exporter riêng `payable_export.py` và endpoint đọc-only `GET /api/debts/payables/export?from=&to=&supplier=`. Workbook có `Tổng hợp`, một sheet cho từng NCC, `Thanh toán` và `Phân bổ`; tên sheet/tên file được làm sạch an toàn. Chi tiết thêm cột đã trả, còn phải trả, trạng thái và tham chiếu audit sau phần cột mẫu; mọi giá trị là static từ ledger, không có formula. Thanh toán lọc theo ngày giao dịch; Phân bổ lấy mọi payment gắn với dòng nợ của kỳ để đối soát số đã trả.
  - Đối soát: với từng NCC và toàn file, dòng hiệu lực luôn thỏa `Phát sinh = Đã phân bổ + Còn phải trả`; tổng sheet bằng tổng chi tiết. Allocation `posted` phải bằng `paid_amount`, lệch thì dừng xuất với mã lỗi thay vì sinh báo cáo sai. Dòng điều chỉnh âm của file khách được giữ dấu; dòng nguồn/payment/allocation đã đảo vẫn hiện riêng và không cộng vào công nợ hiệu lực. Trường hợp nguồn đã đảo nhưng payment chưa hoàn tác vẫn hiện số phân bổ riêng để không mất dấu audit.
  - Định dạng/in: A4 landscape, lặp header dòng 3, freeze `A4`, autofilter đúng vùng, fit một trang ngang, footer số trang. Sheet chi tiết chỉ in A:R đến Trạng thái để chữ đọc được; mã dòng/nguồn vẫn giữ ở các cột sau trong Excel. Microsoft Excel COM thật đã render `Tổng hợp` và `NCC S1` mỗi sheet một trang, không cắt cột nghiệp vụ.
  - File: `tdp_system/payable_export.py`, `tdp_system/test_payable_export.py`, `tdp_system/server.py`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`.
  - Test/QC/runtime: 6/6 test TDP-032 đạt; full regression 219/219 đạt trong 60,363 giây. QC UTF-8 đạt `ok=true` trên chính 9.975 dòng lịch sử: 31 sheet/28 NCC/static values/totals reconciled. Source tạm cổng `18787` đạt `/health ok`, `integrity=ok`, tải workbook 4 sheet và số còn trả 100; listener đã dừng, listener người dùng cổng `8765` giữ nguyên PID `15160`.
  - An toàn: database thật chưa migration nên kiểm tra read-only đúng kỳ vọng báo chưa có bảng ledger mới; tuyệt đối không khởi tạo/ghi vào DB thật. SHA-256 database thật trước/sau vẫn `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; QC DB đã dọn, không gọi write API production, không commit/push/build/deploy. TDP-033 tiếp tục nối bộ lọc, chọn dòng, ghi nhận/hoàn tác và tải file mới vào UI.
- 2026-09-02 20:57 – TDP-033 [x]
  - UI: “Báo cáo & công nợ” có bộ lọc Từ ngày/Đến ngày/NCC/trạng thái, sổ từng dòng mua với số gốc/đã trả/còn trả/revision, ô chọn riêng và số tiền “Phân bổ lần này” do người dùng tự nhập. Một giao dịch chỉ cho các dòng cùng NCC, tổng tiền lấy đúng tổng phân bổ VND nguyên; không FIFO, không tự chọn và không tự chia tiền. Ngày thanh toán mặc định bám ngày cuối kỳ đang xem.
  - Luồng nghiệp vụ: tách form “Thu khách hàng” khỏi form trả NCC cũ vốn không đủ allocation. Ghi trả NCC dùng request id riêng, expected revision từng dòng và confirm trước write; lỗi 409 xóa lựa chọn cũ rồi tải lại. Lịch sử hiển thị phương thức/mã tham chiếu/nội dung/revision và từng allocation; hoàn tác bắt buộc lý do + confirm, gọi endpoint reversal thay vì xóa. Bộ lọc được giữ qua `localStorage`; link Excel phải trả mang đúng kỳ và NCC đang lọc.
  - Browser thật: Edge headless qua CDP trên source/DB fixture cổng `18788` đạt smoke từ đầu đến cuối: 3 dòng/2 NCC → lọc S1 còn 2 dòng → chọn bằng checkbox, tự nhập 100.000 + 50.000 và Enter chuyển đúng ô → ghi 150.000 → refresh còn 1 dòng; reload giữ S1/trạng thái/lịch sử và link export; hoàn tác trả lại 2 dòng. Sau đó writer khác ghi 10.000 với revision hiện hành, submit UI dùng revision cũ bị 409, lựa chọn được xóa/tải lại và không sinh giao dịch thứ ba. Listener `18788`, CDP `19238` và đúng các process Edge fixture đã dừng; listener người dùng `8765` vẫn giữ PID `15160`.
  - File: `tdp_system/static/app.js`, `tdp_system/static/real.css`, `tdp_system/static/index.html`, `tdp_system/browser_fixture_payable_ui_server.py`, `tdp_system/browser_smoke_payable_ui.js`, `tdp_system/test_payable_ui.py`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`.
  - Test/QC: 22/22 test tập trung ledger/payment/export/UI đạt; `node --check` và `py_compile` đạt; full regression tăng lên 220/220 đạt trong 62,106 giây. QC UTF-8 `ok=true`, thêm gate `payableUiContract = filter / explicit manual allocation / reversal / persisted refresh contract passed`; `/health` fixture trả `database_ready=true`, `schema_ready=true`, `integrity=ok`.
  - An toàn: QC DB đã dọn, cổng tạm đã đóng, `git diff --check` không có whitespace error ngoài cảnh báo CRLF. Database thật không được mở bằng init/migration hoặc write API; SHA-256 trước/sau vẫn `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`. Không commit/push/build/deploy. Task đủ dependency tiếp theo là TDP-040.
- 2026-09-02 21:21 – TDP-040 [x]
  - Nguồn phải thu: thêm `receivable_ledger_lines` và `receivable_ledger_revisions`; chỉ dòng `orders` thuộc batch đã duyệt, có thực giao ròng dương và thành tiền dương mới active. Tiền dòng = làm tròn VND `(actual_delivered - customer_return_qty) × sell_price` rồi cộng thuế vận hành; `qty` đặt chỉ lưu để đối chiếu, không dùng thay thực giao. Ledger hoàn toàn không đọc draft/tổng tiền hóa đơn đỏ; test còn cài một hóa đơn đã phát hành giả 999.999 nhưng phải thu vẫn đúng 66.000.
  - Định danh/audit: source key ổn định theo dòng order, source hash lấy từ receipt import và mọi thay đổi ghi revision append-only. Dòng draft/không tính tiền/bị bỏ giữ trạng thái `reversed` với lý do; khi `orders.id` bị SQLite tái sử dụng sau xóa, hệ thống tạo source generation mới, không hồi sinh hay ghi đè tombstone cũ. Luồng thay workbook ghi tombstone trước khi chèn dòng mới trong cùng transaction và đồng bộ lại sau receipt để hash đúng phiên bản.
  - Tích hợp: startup/migration/backfill, import ngày strict và legacy, chốt bán/giao lần hai, thêm/sửa/xóa/bulk order, override giá và duyệt batch đều đồng bộ ledger trong cùng transaction. `/api/debts` đọc duy nhất ledger này cho nhà thầu; khoản thu chỉ nhận `party_type=contractor/kind=receipt`, khoản trả chỉ nhận `supplier/payment`, còn số dư đầu kỳ và điều chỉnh có audit giữ cơ chế tài khoản hiện hữu. API chi tiết hỗ trợ Từ ngày/Đến ngày, nhà thầu, bếp, trạng thái, phân trang và lịch sử revision.
  - Acceptance: 5/5 test TDP-040 đạt cho ordered khác delivered, khách trả, VAT, giá override không đổi bảng giá chuẩn, nhiều batch/nhà thầu/bếp trong kỳ, opening + receipt + adjustment, cross-kind/payable không trộn, filter lỗi fail-closed, source-id reuse và rollback nguyên tử khi revision insert lỗi. Ba fixture regression cũ tạo approved order bằng SQL đã được nâng để materialize/đưa ledger vào snapshot bất biến, không hạ assertion nghiệp vụ.
  - Test/QC/runtime: 29/29 test tập trung đạt; full regression cuối đạt 225/225 trong 60,821 giây. `python -X utf8 -m tdp_system.qc_system` đạt `ok=true`, gate `receivableLedger = approved net delivery / transaction price / return / tax / revision / period filters passed`; `py_compile`, `node --check` và `git diff --check` đạt (chỉ cảnh báo CRLF đã phân loại). Source tạm cổng `18789` trả `/health ok`, `database_ready=true`, `schema_ready=true`, `integrity=ok`; endpoint ledger trả đúng tuyên bố nguồn và listener đã dừng, thư mục runtime đã dọn.
  - An toàn: QC DB đã dọn; listener người dùng cổng `8765` giữ nguyên PID `15160`. Không migration/init hay write API trên database thật; SHA-256 trước/sau vẫn `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`. Không commit/push/build/deploy. Task đủ dependency tiếp theo là TDP-041.
- 2026-09-02 21:35 – TDP-041 [x]
  - Contract xuất file: thêm endpoint read-only `GET /api/debts/receivables/export`. Khi có bộ lọc nhà thầu, endpoint trả đúng một `.xlsx`; khi không lọc, trả `.zip` chứa đúng một workbook độc lập cho mỗi nhà thầu có phát sinh/số dư trong kỳ, không tạo workbook gộp nhiều nhà thầu. Kỳ không phát sinh của nhà thầu đã chọn vẫn trả workbook đối soát ổn định; gói tất cả rỗng có `KHONG_PHAT_SINH.txt` ghi rõ nguồn không dùng hóa đơn đỏ.
  - Cấu trúc/đối soát: mỗi workbook có sheet đầu `Tổng nhà thầu` với đầu kỳ + phát sinh + điều chỉnh − đã thu = cuối kỳ và bảng tổng theo bếp; các sheet sau sinh động từ từng bếp có thực giao đã duyệt trong kỳ. Mỗi sheet bếp giữ ngày, mã/tên hàng, số đặt, thực giao, khách trả, giao ròng, giá bán giao dịch, thuế, tiền và tham chiếu ledger. Tổng mọi sheet bếp bắt buộc bằng phát sinh sheet đầu và sổ tài khoản; lệch số dư/tổng thì fail-closed 409. File chỉ chứa giá trị tĩnh, không formula/external link, dùng A4 ngang, vùng in/header/freeze rõ ràng.
  - Tên/an toàn dữ liệu: tên sheet loại ký tự Excel cấm, giới hạn 31 ký tự và thêm hậu tố chống trùng không phân biệt hoa thường; tên file loại ký tự Windows cấm và chống trùng trong ZIP. Nhà thầu/bếp mới tự xuất hiện từ catalog + ledger; khoản `contractor/payment` sai loại không được dùng để nhận diện hay trừ phải thu. Export chạy trên transaction chỉ đọc; test hash database trước/sau không đổi.
  - Acceptance: 3/3 test mới đạt cho hai nhà thầu/ba bếp, hai tên bếp rất dài có ký tự `/ : [ ] *` và cùng prefix sau làm sạch, tổng 66.000 + 50.000 = 116.000, nhà thầu khác 40.000, opening 100.000 + charge 116.000 − receipt 30.000 − adjustment 5.000 = closing 181.000, ZIP mỗi nhà thầu một file, kỳ tùy chọn/rỗng, filter tên/mã, ngày/nhà thầu sai fail-closed và không tính khoản thu sai kind 999.000.
  - Test/QC/runtime: 14/14 test tập trung ledger/export phải thu/phải trả đạt; full regression 228/228 đạt trong 62,651 giây. QC UTF-8 đạt `ok=true`, thêm gate `receivableExcelExport = one workbook per contractor / summary + kitchen totals reconciled`. Source/DB tạm cổng `18790` trả `/health ok`, `database_ready=true`, `schema_ready=true`, `integrity=ok`; tải XLSX nhà thầu và ZIP tất cả đều HTTP 200 đúng MIME; listener và thư mục runtime đã dừng/dọn.
  - File: `tdp_system/receivable_export.py`, `tdp_system/test_receivable_export.py`, `tdp_system/server.py`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`. QC DB đã dọn; listener người dùng cổng `8765` giữ nguyên PID `15160`; SHA-256 database thật vẫn `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`. Không commit/push/build/deploy, không migration/init hay write API trên database thật. Task đủ dependency tiếp theo là TDP-042.
- 2026-09-02 21:46 – TDP-042 [x]
  - UI phải thu: thêm workspace “Sổ phải thu vận hành chi tiết” ngay trong “Báo cáo & công nợ”, có bộ lọc dùng chung kỳ Từ ngày/Đến ngày và bộ lọc riêng Nhà thầu/Bếp/Trạng thái hiệu lực–đã hoàn tác. Bộ lọc lưu ở `tdp.receivableFilters`, tự khôi phục sau reload; chọn nhà thầu làm mới danh sách bếp đúng phạm vi. Bảng hiện ngày, nhà thầu, bếp, hàng, số đặt, thực giao, khách trả, giao ròng, ĐVT, giá bán giao dịch, trước thuế, thuế, phải thu, trạng thái và source/revision.
  - Đối soát/ranh giới: bốn thẻ thống kê lấy từ ledger hiệu lực; khi chọn nhà thầu, UI ghi rõ công thức đầu kỳ + phát sinh + điều chỉnh − đã thu = còn thu. Nếu lọc một bếp, UI nói rõ bảng chỉ thu hẹp chi tiết còn số dư vẫn là toàn tài khoản nhà thầu. Mỗi dòng mở được lịch sử revision khởi tạo/cập nhật/hoàn tác/kích hoạt lại. Nhãn nổi bật và tiêu đề bảng đều khóa nghĩa đây là công nợ vận hành từ thực giao ròng × giá bán giao dịch + thuế, không phải đề nghị thanh toán/hóa đơn đỏ.
  - Tải file: khi chọn nhà thầu, nút chính tải XLSX toàn bộ bếp của đúng nhà thầu/kỳ và có nút ZIP mọi nhà thầu; khi không chọn, nút chính tải ZIP từng workbook độc lập. Bộ lọc bếp không cắt mất các sheet bếp khác trong file đối soát của nhà thầu. Trạng thái loading/error/truncated/empty đều có thông báo và nút tải lại; request serial loại phản hồi cũ khi đổi bộ lọc nhanh.
  - Browser thật: Edge headless/CDP trên source + DB fixture đạt chuỗi 3 dòng hiệu lực → lọc C1 còn 2 → danh sách bếp đổi đúng → lọc K2 còn 1 dòng 50.000 → link export có `contractor=C1` và không cắt theo kitchen → mở Revision 1 → chọn all thấy 2 active + 1 reversed → reload giữ C1/all. Đối soát UI hiện đúng 100.000 + 116.000 − 5.000 − 30.000 = 181.000. Smoke UI phải trả cũ được chạy lại trên fixture riêng và vẫn đạt toàn bộ chọn dòng/phân bổ/reload/hoàn tác/stale 409.
  - Test/QC: 10/10 test tập trung đạt; `node --check` và `py_compile` đạt. Full regression tăng lên 229/229, đạt trong 62,437 giây. QC UTF-8 đạt `ok=true`, thêm gate `receivableUiContract = period / contractor / kitchen / revision / export / persisted filters passed`; health đầu QC vẫn `ok/database_ready/schema_ready=true`, `integrity=ok`.
  - File: `tdp_system/static/app.js`, `tdp_system/static/real.css`, `tdp_system/static/index.html`, `tdp_system/test_receivable_ui.py`, `tdp_system/browser_fixture_receivable_ui_server.py`, `tdp_system/browser_smoke_receivable_ui.js`, `tdp_system/test_payable_ui.py`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`. Listener/Edge/profile/DB tạm cổng `18791/19241` và regression `18792/19242` đã dừng/dọn; chỉ cổng người dùng `8765` PID `15160` còn nghe. QC DB đã dọn; database thật giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; không commit/push/build/deploy, không migration/init hoặc write API trên database thật. Task đủ dependency tiếp theo là TDP-050.
- 2026-09-02 22:04 – TDP-050 [x]
  - Luồng độc lập: thêm `quote_import.py` và hai endpoint riêng `POST /api/quotes/import/preview|confirm`, không mở quyền ghi cho sheet báo giá trong importer đơn ngày. Preview bắt buộc kỳ `YYYY-MM`, đúng một sheet `BÁO GIÁ`, hash bytes/content, nhận diện vùng giá thật đến trước cột `Thêm` và loại các cột công thức tỷ suất lặp phía sau; token dùng một lần, state hash khóa danh mục + nhóm giá + các phiên bản hiện có. Confirm dùng `BEGIN IMMEDIATE`, rollback tường minh và audit tối giản; endpoint `GET /api/quotes/versions` cho phép truy phiên bản.
  - Lưu trữ/giá: ba bảng append-only giữ phiên bản theo kỳ, snapshot sản phẩm và từng ô giá/nhóm/trạng thái. Cùng bytes+cùng kỳ replay idempotent; file khác tạo v2 nhưng không sửa v1. Đơn mới theo ngày lấy giá bán đúng kỳ/nhà thầu; giá mua có số trong báo giá được ưu tiên, còn ô không có số chỉ nhận giá mua thực tế trên dòng vận hành và không hồi sinh giá danh mục khác kỳ. Giá của order đã tạo là snapshot nên việc xác nhận v2 không viết ngược order cũ.
  - Nguồn thật: preview/confirm trên DB tạm đọc `Em Thành.xlsx` được 899 dòng nguồn, 7 nhóm `ATV/HATRAN/BIADAUVOI/NGUYENGIA/SUPPY/TOYOTA/NHUAHAIPHONG` và 6.293 ô giá; 21 công thức số học hằng có cache được lấy thành giá trị số, công thức tham chiếu/hàm/external hoặc không có cache bị chặn. Ghi chú cuối sheet không bị hiểu nhầm là mã hàng. Hai kỳ cùng tồn tại, replay đổi tên file không nhân bản.
  - Acceptance: 6 test mới bao phủ hai kỳ song song, v1/v2, replay, token/state sai, hai preview cạnh tranh, rollback trigger, ưu tiên giá mua và chỉ fallback mua thực tế khi trống; full regression 235/235 đạt trong 63,399 giây. QC UTF-8 `ok=true`, gate `periodQuoteImport = real matrix 899 products / 7 groups / 6,293 values / two periods / replay safe`. Source runtime cổng `18793` trả `/health ok`, `database_ready/schema_ready=true`, `integrity=ok`; preview/confirm/version HTTP đều 200.
  - File/an toàn: `tdp_system/quote_import.py`, `tdp_system/test_quote_import.py`, `tdp_system/server.py`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`. Runtime/QC DB và listener `18793` đã dừng/dọn; listener người dùng `8765` giữ nguyên PID `15160`; database thật giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`. Không commit/push/build/deploy, không migration/init hoặc write API trên database thật.
  - Ranh giới tiếp theo: source thật có 28 mã lặp/28 dòng dư; resolver hiện fail-closed khi một mã có nhiều dòng nên không tự lấy nhầm. TDP-051 đang làm sẽ map header/cột nhà thầu tuyệt đối, lọc X/rỗng, giữ 0 và hợp nhất chỉ khi không xung đột; xung đột phải hiện rõ, không được tự chọn.
- 2026-09-02 22:24 – TDP-051 [x]
  - Mapping và chống lấy nhầm: mỗi cột giá được nối bằng header chuẩn hóa khớp chính xác `contractors.code`/`price_group`, vị trí cột chỉ còn là thông tin truy vết. Header lạ, mơ hồ hoặc hai cột cùng trỏ một nhóm đều fail-closed. Preview trả cả header nguồn và số cột Excel; trên nguồn thật Toyota được xác nhận là cột `Q`, còn `ATV/HATRAN/BIADAUVOI/NGUYENGIA/SUPPY/NHUAHAIPHONG` lần lượt là `L/M/N/O/P/R`.
  - Lọc và trùng mã: resolver chạy theo từng cặp mã hàng–nhóm giá. `X`/rỗng bị loại khỏi output; giá số `0` vẫn là một dòng hợp lệ và hiện nhãn cần xác nhận. Mã lặp cùng định danh/cùng giá được gộp thành đúng một dòng và giữ mọi `source_row`; khác giá bán, khác giá mua đang áp dụng, tên/ĐVT/thuế không tương thích đều hiện thành conflict, chặn confirm/export và tuyệt đối không tự chọn. Giá mua đơn mới cũng được lấy từ đúng dòng nguồn áp dụng cho contractor đó.
  - Nguồn thật: `Em Thành.xlsx` có 899 dòng nguồn, 871 mã duy nhất và 28 mã lặp. Phân tích mới xác định 27 mã có thể gộp an toàn; riêng `A000045` xung đột giữa dòng 274/470 ở 5 nhóm `ATV/HATRAN/SUPPY/TOYOTA/NHUAHAIPHONG`, nên preview `canConfirm=false` đúng quy tắc thay vì âm thầm lấy một giá. QC dùng nguồn thật để khóa bằng chứng này rồi dùng workbook sạch cô lập để kiểm tra confirm/replay/hai kỳ.
  - UI/browser thật: màn Báo giá có kỳ hiệu lực, nút nạp riêng, mapping header→cột→nhóm giá, thống kê mã lặp/gộp/xung đột và bảng chi tiết dòng nguồn/lý do. Edge headless/CDP trên source + DB fixture cổng `18794/19244` đạt chuỗi Toyota Q → file xung đột không có nút confirm → file sạch xác nhận v1 → `2 dòng xuất`, `2 dòng X/rỗng đã loại`, P1 giá `0` vẫn hiện, P2 có giá, P3/P4 không xuất → reload vẫn giữ phiên bản.
  - Acceptance: 9/9 test backend báo giá và 2/2 test UI mới đạt; full regression 240/240 đạt trong 67,587 giây. `node --check`, `py_compile`, `git diff --check` đạt; QC UTF-8 `ok=true`, gate `periodQuoteImport = Toyota=Q / real duplicate conflict surfaced / X+blank omitted / zero retained / replay safe`.
  - File/an toàn: `tdp_system/quote_import.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/static/real.css`, `tdp_system/test_quote_import.py`, `tdp_system/test_quote_ui.py`, `tdp_system/browser_fixture_quote_ui_server.py`, `tdp_system/browser_smoke_quote_ui.js`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`. Listener/Edge/profile/DB tạm đã dừng/dọn; listener người dùng `8765` giữ nguyên PID `15160`; database thật giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`. Không commit/push/build/deploy, không migration/init hoặc write API trên database thật. Task tiếp theo TDP-052.
- 2026-09-02 22:43 – TDP-052 [x]
  - Output Toyota: thêm `quote_export.py` sinh workbook độc lập đúng hình thức golden `BÁO GIÁ TOYOTA T09-2026.xlsx`: duy nhất sheet `all`; phần pháp nhân/địa chỉ/email/điện thoại; tiêu đề tháng–năm; `KÍNH GỬI: CÔNG TY TNHH TOYOTA NANKAI HẢI PHÒNG`; sáu cột `STT/MÃ/TÊN THÀNH ĐẠT PHÁT/ĐVT/Giá chưa VAT/Thuế`; 16 nhóm A–P nền xanh; mã sắp A–Z trong từng nhóm; ghi chú giá chưa VAT và vùng xác nhận bên bán. Giá 0 được giữ là ô số 0 với định dạng kế toán của golden; X/rỗng không đi vào builder.
  - Ranh giới dữ liệu: endpoint Toyota chỉ xuất khi kỳ đã có phiên bản báo giá xác nhận; nếu chỉ còn master cũ thì trả 409 `quote_period_not_confirmed`, UI khóa nút tải và hướng dẫn nạp/xác nhận đúng kỳ. Tên file ghi kỳ/phiên bản `BAO_GIA_TOYOTA_T09-2026_V1.xlsx`; cuối bảng có dòng truy vết Toyota/kỳ/version/16 ký tự hash nguồn. Mã trùng, giá âm/NaN/Infinity, trạng thái–giá 0 lệch hoặc chuỗi công thức đều fail-closed; file không có formula/external link.
  - Topology/render: khóa Times New Roman và đúng kích thước cột của golden, header vàng, nhóm xanh `92D050`, border, dòng cao, khổ A4 ngang, scale 87, lề `0.2/0.2/0.23/0.24`, repeat row 8 và vùng ký cuối. Candidate 513 dòng/16 nhóm được render bằng Microsoft Excel COM thành đúng 16 trang như golden; đã xem trực tiếp trang 1 và 16, vị trí bảng/dòng/trang cuối khớp, chỉ bổ sung provenance nhỏ ở mép phải dòng ghi chú. QC đối chiếu golden đúng SHA-256, 513 mã duy nhất, 5 giá 0 gốc, 16 nhóm và tọa độ group row.
  - Acceptance: 3 test mới/điều chỉnh bao phủ cấu trúc, sort nhóm/mã, giữ 0, tax, provenance, thiếu version, duplicate/formula/non-finite và endpoint/tên file; 14/14 test quote/export/UI tập trung đạt. Full regression 243/243 đạt trong 65,116 giây. QC UTF-8 `ok=true`, thêm gate `toyotaGoldenQuote = 1 sheet all / 513-row golden scale / 16 green groups / A-Z / A4 landscape / repeat header / static values`. Edge/CDP source fixture xác nhận nút bị khóa trước khi có version, preview conflict, confirm v1, reload và tải XLSX đúng MIME/tên file.
  - File/an toàn: `tdp_system/quote_export.py`, `tdp_system/server.py`, `tdp_system/test_quote_export.py`, `tdp_system/test_quote_import.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/test_quote_ui.py`, `tdp_system/test_payable_ui.py`, `tdp_system/test_receivable_ui.py`, `tdp_system/browser_smoke_quote_ui.js`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`. Runtime/Edge/CDP/render/DB tạm đã dừng và dọn; chỉ listener người dùng `8765` PID `15160` còn nghe. Database thật giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; không commit/push/build/deploy, không migration/init hoặc write API trên database thật. Task tiếp theo TDP-053.
- 2026-09-02 22:59 – TDP-053 [x]
  - Engine chung: thay nhánh workbook giản lược của mọi nhà thầu bằng duy nhất engine golden sáu cột/sheet `all` đã kiểm chứng ở TDP-052. Engine nhận mã nhà thầu, người nhận và đúng một nguồn độc lập: phiên bản báo giá đã xác nhận theo kỳ hoặc phiên đơn theo ngày; không tự truy DB, không trộn nguồn và không còn hard-code Toyota trong thân builder. Tên file theo kỳ luôn có mã/kỳ/version; tên file theo ngày có mã/ngày/batch; provenance cuối bảng và metadata workbook mang cùng mã nguồn.
  - Pháp nhân/giá/trạng thái: tên người nhận được khóa bằng bằng chứng trong golden Toyota, golden ATV và `T.chiếu` của `Em Thành.xlsx`; HATRAN/GIANHAPTAY chỉ dùng đúng nhãn nguồn, không bịa loại hình pháp nhân. Có override tách biệt `settings.quote_recipient_<CODE>` để sửa tên hợp đồng mà không đổi `price_group`. Mỗi export nhóm chỉ lấy đúng cột của contractor trong version đang chọn; X/rỗng bị loại, 0 giữ rõ. GIANHAPTAY/YLKHAN bắt buộc có batch ngày; các order trùng mã chỉ gộp khi tên/ĐVT/thuế/giá giống nhau, còn khác bất kỳ chiều nào đều trả 409 cùng order/source rows, không âm thầm lấy dòng đầu.
  - Acceptance/QC/browser: 18/18 test quote/export/UI trọng tâm và full regression 247/247 đạt trong 64,358 giây. Bộ test tạo ATV/TOYOTA/NHUAHAIPHONG từ cùng matrix với giá lần lượt 11.000/22.000/33.000, xác nhận đúng ba người nhận và không rò giá; kiểm thêm override pháp nhân, unknown contractor 404, daily thiếu batch 409, gộp trùng an toàn và trùng khác giá 409. QC UTF-8 `ok=true`, gate `periodQuoteImport` bắt buộc tải/đọc ATV+SUPPY+TOYOTA độc lập với giá đầu lần lượt 17.000/19.000/17.500. Edge headless/CDP cổng `18794/19244` xác nhận sau Toyota có thể chuyển ATV, thấy đúng `KÍNH GỬI`, không mang trạng thái 0 của Toyota và tải `BAO_GIA_ATV_T09-2026_V1.xlsx`.
  - File/an toàn: `tdp_system/quote_export.py`, `tdp_system/server.py`, `tdp_system/test_quote_export.py`, `tdp_system/test_quote_import.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/test_quote_ui.py`, `tdp_system/test_payable_ui.py`, `tdp_system/test_receivable_ui.py`, `tdp_system/browser_smoke_quote_ui.js`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`. Fixture/Edge/CDP/profile/DB tạm đã dừng và thư mục run đã xóa có kiểm tra; chỉ listener người dùng `8765` PID `15160` còn nghe. Database thật trước/sau giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; không commit/push/build/deploy, không migration/init hoặc write API trên database thật. Task đủ dependency tiếp theo là TDP-060.
- 2026-09-02 23:10 – TDP-060 [x]
  - Engine template-preserving: thêm `template_workbook.py`, mỗi lần sinh đều đọc bytes golden mới, khóa SHA-256 tùy chọn, chỉ giữ đúng danh sách/tên/thứ tự sheet yêu cầu và tuyệt đối không save ngược nguồn. Clone giữ merged cells, cell style, row/column dimensions, freeze pane, print area/title, paper/orientation/scale/margins và vùng chữ ký; có primitive ghi literal, ghi formula nội bộ đã kiểm tra, nhân style dòng mẫu và ghi bảng mapping để TDP-061/062/063/064 dùng chung. Hai lần cùng template/dữ liệu cho cùng topology, tổng và công thức.
  - An toàn độc lập: load song song bản formula và `data_only`; công thức trỏ workbook ngoài, sheet không được giữ, `#REF!`, 3-D ref hoặc hàm có thể gọi ngoài bị thay bằng đúng cached value của golden. Hyperlink ngoài/defined name ngoài bị loại, `_external_links` bắt buộc rỗng và output phải mở lại/qua safety scan trước khi trả bytes. Dữ liệu động bắt đầu bằng `=` và số NaN/Infinity bị chặn; công thức mới chỉ nhận ref tới sheet còn tồn tại. Với `biên nhận` thật, engine giữ 3 SUM nội bộ, chuyển đúng 40 công thức `[1]...` sang cache, không thiếu cache và giữ 11 merged ranges.
  - Acceptance/render: 21/21 test tập trung engine/golden QC/PDF/print đạt; kiểm nguồn thật xác nhận hash `Em Thành.xlsx` không đổi, clone hai lần quyết định giống nhau, formula/link injection fail-closed và workbook engine đi qua `print_bundle.py` rồi tạo/verify được cả A4 lẫn A5. Full regression 251/251 đạt trong 65,374 giây; QC UTF-8 `ok=true`, thêm gate `templatePreservingEngine = real receipt topology / 40 external formulas cached / 3 local formulas preserved / repeat deterministic`.
  - Visual/an toàn máy: Excel COM render golden và candidate `biên nhận` đều đúng 3 trang; đã xem trực tiếp trang 1–2. OpenPyXL round-trip nguyên workbook có link tạo chênh pixel với nguồn `[4,7268%; 0,9838%; 0,2035%]`; engine an toàn so với chính round-trip chuẩn này là `[0%; 0%; 0%]`, nên bước thay external formula không gây thêm sai khác hình thức. Hai biến thể bỏ link nhưng chưa materialize external formula không mở được bằng Excel, chứng minh fail-closed/cached-value là bắt buộc. Toàn bộ thư mục render/diagnostic đã dọn; Excel người dùng đang mở `Em Thành.xlsx` PID `19780` được giữ nguyên, database thật vẫn SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`, chỉ listener `8765` PID `15160` còn nghe. Không commit/push/build/deploy, không migration/init hay write API database thật. Task tiếp theo TDP-061.
- 2026-09-02 23:36 – TDP-061 [x]
  - Chốt mã/nguồn trước code: đối chiếu trực tiếp `T.chiếu` và database thật xác nhận duy nhất `NHUAHAIPHONG / NHUAHP / CÔNG TY CỔ PHẦN NHỰA VÀ CƠ KHÍ HẢI PHÒNG / show_price=1`; toàn bảng chỉ có một dòng `show_price=1`. Quy tắc mới bắt buộc đồng thời đúng chính xác cả mã bếp `NHUAHP` lẫn nhà thầu `NHUAHAIPHONG`; tên chứa “Nhựa”, cờ `show_price` cũ hoặc chỉ đúng một trong hai mã đều fail-closed và không thể hiện giá. Tên đơn vị mua/địa chỉ lấy theo đúng mã bếp ở danh mục, có override tách biệt theo mã nếu hợp đồng đổi, không fuzzy-match.
  - Engine phiếu giao: thêm `delivery_export.py`, thay hoàn toàn workbook tự thiết kế cũ bằng clone sheet golden `đơn hàng đi giao` khóa hash. Mỗi bếp có thực giao ròng dương thành một sheet; khách trả được trừ, dòng giao ròng 0 bị bỏ. Bản mẫu ngày 27/08, công thức, giá mua G ẩn, ghi chú nội bộ dòng 37 và toàn bộ dữ liệu mẫu bị xóa trước khi ghi literal hiện tại. Nhựa giữ Đơn giá/Thành tiền/Tổng tiền; mọi bếp khác không chứa giá ngay cả khi bỏ ẩn cột H:I. Số dòng co/giãn đúng dữ liệu, 20+ dòng dời tổng/ảnh ký theo bảng và không để lại khung trắng.
  - Hình thức/in: giữ pháp nhân bên bán, font vận hành 18pt (GC động tối thiểu 14pt), ô gộp/style/kích thước và A4 dọc. Theo phản hồi khách ngày 03/09/2026, ảnh chụp chân trang đã được thay bằng chữ, ô và đường kẻ Excel thật cho đủ bốn vùng `Trực ban / Bảo vệ / Người giao hàng / Người nhận hàng`; vùng in tiếp tục bao trọn khối ký ngay sau dòng cuối và fit một trang theo chiều ngang, không ép chiều cao.
  - PDF/acceptance: `print_bundle.py` nhận diện riêng header golden không phụ thuộc màu nền, bỏ cột ẩn/trống, không đưa dòng tổng vào dữ liệu, chỉ thêm tổng cho Nhựa và tạo đúng bốn chữ ký; PDF A4 verified. 6/6 test phiếu giao mới đạt, gồm giá/ẩn giá, cờ cũ sai, trả khách, 20 dòng, formula injection, mở lại workbook/ảnh, font/A4/PDF; full regression 257/257 đạt trong 79,879 giây. QC UTF-8 `ok=true`, export fixture 408 dòng tạo workbook phiếu 197.935 byte và thêm gate `approvedDeliveryTemplate = approved sheet per kitchen / exact NHUAHP+NHUAHAIPHONG price gate / 4 signatures / no hidden price leakage / A4`.
  - File/an toàn: `tdp_system/delivery_export.py`, `tdp_system/test_delivery_export.py`, `tdp_system/server.py`, `tdp_system/print_bundle.py`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`. Database thật giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; golden giữ nguyên SHA-256 `66808cd910f63f4d543a72cc51ddaeba1c60b147e0457feafc5bad65ead26ad3`; Excel người dùng PID `19780` và listener `8765` PID `15160` được giữ nguyên. Không commit/push/build/deploy, không migration/init hoặc write API database thật. Task đủ dependency tiếp theo là TDP-062.
- 2026-09-03 00:03 – TDP-062 [x]
  - Nguồn/domain: thêm projection chỉ đọc cho bảng kê thu mua. Khi đã có `purchase_workbook_lines`, chỉ nhận dòng `confirmed`, BK, số lượng thực tế dương và dùng đúng giá mua/thành tiền đã chốt; tuyệt đối không truy bảng phải thu. Nhánh tương thích dữ liệu cũ chỉ dùng thực nhận ròng và chỉ áp tỷ lệ cấu hình 95% giá bán khi giá mua thực sự chưa có. Người bán/địa chỉ/CCCD ưu tiên danh mục nội bộ hiện hành; thiếu hoặc sai định dạng, giá không dương hay thành tiền lệch đều fail-closed bằng lỗi không lặp lại số định danh.
  - Golden/kết quả: clone duy nhất sheet `bảng kê tổng` từ `Em Thành.xlsx` với SHA-256 khóa `66808cd910f63f4d543a72cc51ddaeba1c60b147e0457feafc5bad65ead26ad3`; xóa toàn bộ dữ liệu mẫu, ghi chú hướng dẫn và dư lượng tính toán trước khi đổ literal hiện tại. Cùng ngày + cùng người bán pháp lý + cùng mặt hàng/ĐVT được gộp xuyên NCC/bếp; đơn giá là bình quân gia quyền và tổng tiền giữ chính xác. Bảng co giãn theo số dòng, giữ pháp nhân/chữ ký, đọc tiền bằng chữ, A4 ngang, fit một trang chiều rộng và lặp hàng tiêu đề 8–10. Bản render Microsoft Excel thật với dữ liệu giả đã xem trực tiếp: một trang, đủ tiêu đề/bảng/tổng/chữ ký, không `####` hoặc dòng mẫu sót lại.
  - Tích hợp/an toàn: thay output bảng kê tự thiết kế sai bằng engine golden; `print_bundle.py` hiểu đúng header hai tầng và tổng/chữ ký. Bộ in hỗn hợp bỏ qua bảng kê khi lô hoàn toàn không có dòng BK, nhưng vẫn chặn nếu có BK mà thiếu giá hoặc định danh; endpoint tải riêng vẫn báo `no_purchase_summary_rows`. Dữ liệu định danh trong test/render đều là giả và không đi vào manifest/log. QC lần đầu bắt được case lô không có BK; sửa xong 22/22 test tích hợp trọng tâm đạt.
  - Acceptance: full regression cuối cùng `264/264` đạt trong `90,290` giây; `python -X utf8 tdp_system/qc_system.py` đạt `ok=true` với gate `approvedPurchaseSummary = confirmed BK only / legal seller item merge / weighted average / exact total / no sample identity / A4`; `py_compile` và `git diff --check` đạt. Database thật giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; Excel người dùng PID `19780` và listener `8765` PID `15160` giữ nguyên. Hai thư mục render dữ liệu giả `tmp/tdp062_visual*` được giữ lại vì lớp an toàn từ chối xóa đệ quy; không chứa dữ liệu khách. Không commit/push/build/deploy, không migration/init hoặc write API database thật.
  - File: `tdp_system/purchase_summary_export.py`, `tdp_system/test_purchase_summary_export.py`, `tdp_system/server.py`, `tdp_system/contract_modules.py`, `tdp_system/print_bundle.py`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`. Task tiếp theo TDP-063.
- 2026-09-03 00:20 – TDP-063 [x]
  - Chốt golden/quy tắc: đọc trực tiếp sheet `biên nhận` xác nhận bảng C:G gồm `Tên hàng – ĐVT – Đơn giá – Số lượng – Thành tiền`, khối định danh người bán có địa chỉ/số CMT/ngày cấp/nơi cấp, hai vùng ký và ghi chú khách: số biên nhận bằng số người bán trong `bảng kê tổng`, mỗi người/ngày không quá 5.000.000 đồng. Engine tạo đúng một biên nhận cho mỗi người bán pháp lý/ngày; vượt trần bị chặn, không tự tách nhiều tờ để lách quy tắc.
  - Nguồn/identity: biên nhận dùng lại duy nhất projection mua/BK đã chốt của TDP-062, số lượng thực tế, giá mua và thành tiền; không đọc doanh thu/phải thu. Ngày/nơi cấp được enrich từ bảng `people` nội bộ và phải khớp CCCD/CMND hiện hành; thiếu/mâu thuẫn fail-closed bằng lỗi chỉ nêu dòng nguồn, không lặp số định danh. Cùng mặt hàng/ĐVT của cùng người bán/ngày được gộp với bình quân gia quyền giống bảng kê. Tên sheet chỉ là `biên nhận`, `biên nhận 02`... và title manifest luôn chung, không chứa người bán/CCCD.
  - Golden/output: thêm `receipt_export.py`, clone sheet golden đã khóa hash cùng `bảng kê tổng`, xóa toàn bộ công thức link ngoài, dữ liệu mẫu và hai dòng hướng dẫn khách; bỏ hẳn generator giản lược cũ. Số dòng bảng co/giãn, tổng/tiền bằng chữ/tuyên bố/ngày ký/vùng ký dời theo bảng; dữ liệu ghi literal, CCCD/ngày cấp giữ dạng text. Có override tách biệt cho người mua, chức vụ, địa chỉ công ty và địa điểm ký; thiếu override thì giữ nội dung golden. Mỗi receipt có print area riêng, A4 dọc, fit đúng một trang.
  - PDF/visual: `print_bundle.py` nhận diện riêng header golden C:G, đưa đủ lời mở đầu, pháp nhân, người mua, khối định danh, tuyên bố, tổng và hai chữ ký vào PDF; manifest chỉ giữ title chung/số dòng/hash. Microsoft Excel COM render thật với bảy mặt hàng và toàn bộ dữ liệu giả đạt một trang A4, không `####`, không sót công thức/ghi chú mẫu, bảng/tổng/chữ ký cân đối; Excel COM phụ đã thoát, Excel người dùng không bị can thiệp.
  - Acceptance/an toàn: 11/11 test receipt+summary, 30/30 test template/print/race và full regression cuối `268/268` đạt trong `92,277` giây. QC UTF-8 `ok=true`, thêm gate `approvedPurchaseReceipt = one golden receipt per legal seller/day / issue identity / 5m hard cap / dynamic rows / A4 / manifest-safe title`; fixture lịch sử cố ý vượt 5 triệu phải trả `receipt_daily_limit_exceeded`, còn ca dương tạo/mở lại workbook+PDF đạt. `py_compile` và `git diff --check` đạt. Database thật giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; golden được QC khóa đúng SHA-256 `66808cd910f63f4d543a72cc51ddaeba1c60b147e0457feafc5bad65ead26ad3`; Excel PID `19780` và listener `8765` PID `15160` giữ nguyên. Artifact render giả `tmp/tdp063_visual` cùng hai thư mục TDP-062 vẫn được giữ vì lớp an toàn chặn xóa file; không chứa dữ liệu khách. Không commit/push/build/deploy, không migration/init hoặc write API database thật.
  - File: `tdp_system/receipt_export.py`, `tdp_system/test_receipt_export.py`, `tdp_system/purchase_summary_export.py`, `tdp_system/test_purchase_summary_export.py`, `tdp_system/server.py`, `tdp_system/print_bundle.py`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`. Task tiếp theo TDP-064.
- 2026-09-03 00:31 – TDP-064 [x]
  - Ánh xạ golden đầy đủ: sheet `báo cáo tổng hợp` có A là Nhóm khách hàng (ô tiêu đề A2 để trống đúng mẫu), B `Khách hàng`/nhà thầu, C `Mã khách hàng`/mã bếp, D `Doanh số bán`, E `Giá vốn`, F `Lợi nhuận gộp`, G `TỔNG THANH TOÁN`; dòng subtotal nhóm và `TỔNG THÁNG` dùng nền xanh `92D050`. Đối chiếu `T.chiếu` xác nhận B/C là nhà thầu/mã bếp; map nhóm cao hơn không nằm trong `T.chiếu`, nên engine đọc trực tiếp A/B/C của golden theo mã bếp, nhận override `report_group_<MÃ_BẾP>` và dùng nhà thầu làm fallback an toàn cho bếp mới.
  - Nguồn/domain: thay báo cáo bốn sheet tự thiết kế của một phiên bằng một sheet golden theo tháng của phiên được chọn. Nguồn gồm mọi `orders` thuộc batch `approved` trong tháng; nếu phiên đang chọn là draft thì chỉ cộng riêng draft đó để preview, không lấy draft khác. Doanh số/tổng thanh toán dùng đúng `order_totals` hiện hành từ thực giao ròng, giá giao dịch và thuế; giá vốn dùng thực nhận ròng × giá mua; lợi nhuận luôn được kiểm `doanh số − giá vốn`. Không đọc payments, balances, phải thu hoặc phải trả và không trừ công nợ vào báo cáo vận hành này.
  - Generator động: thêm `report_export.py`; cộng dồn nhiều dòng cùng bếp, chặn một mã bếp thuộc nhiều nhà thầu hoặc lợi nhuận lệch. Giữ thứ tự nhóm/mã bếp có trong golden, tự chèn bếp/nhóm mới, dùng style nhóm tương ứng; nhóm có nhiều bếp sinh subtotal nền xanh và cuối file luôn có `TỔNG THÁNG` reconcile D:G. Toàn bộ giá trị xuất là literal, không còn công thức mẫu cần sửa tay; một sheet `báo cáo tổng hợp`, print area động, A4 ngang, fit một trang chiều rộng và lặp header dòng 2. Endpoint đổi tên file thành `Bao_cao_tong_hop_YYYY-MM.xlsx`.
  - PDF/visual: `print_bundle.py` có projector riêng cho header golden bị trống A2, đặt nhãn PDF `Nhóm khách hàng`, nhận diện subtotal và tách `TỔNG THÁNG` thành summary. Microsoft Excel COM render thật fixture có bếp cũ, bếp mới và ba nhóm đạt một trang: đúng bảy cột, màu vàng header, màu xanh hai subtotal + tổng tháng, thứ tự MAZDA trước POT theo golden, số không bị `####`; Excel phụ đã thoát.
  - Acceptance/an toàn: 4/4 test report mới và 29/29 test report/server/print/race trọng tâm đạt; full regression cuối `272/272` đạt trong `99,930` giây. QC UTF-8 `ok=true`, export fixture 408 dòng tạo report 12.664 byte và gate `approvedMonthlyReport = golden 7 columns / monthly approved scope / dynamic group+kitchen / group totals / TỔNG THÁNG / A4`. `py_compile` và `git diff --check` đạt. Database thật giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; golden được QC khóa SHA-256 `66808cd910f63f4d543a72cc51ddaeba1c60b147e0457feafc5bad65ead26ad3`; Excel PID `19780` và listener `8765` PID `15160` giữ nguyên. Artifact render giả `tmp/tdp064_visual` được giữ vì lớp an toàn không cho xóa file; không chứa dữ liệu khách. Không commit/push/build/deploy, không migration/init hoặc write API database thật.
  - File: `tdp_system/report_export.py`, `tdp_system/test_report_export.py`, `tdp_system/server.py`, `tdp_system/test_server_financial_guards.py`, `tdp_system/print_bundle.py`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`. Task đủ dependency tiếp theo TDP-082.
- 2026-09-03 00:49 – TDP-082 [!] domain/data hoàn tất, visual NXT chờ Q-005
  - Audit nguồn: tìm đích danh toàn bộ Downloads xác nhận snapshot có đúng `_HANDOFF/EXTERNAL_INPUTS/TĐK T8-2026.xlsx thụy.xlsx` SHA-256 `36df2ba86d13307f96bb5944fcecb19a4a81c093b4ac6a98ea71330d68204da6`, một sheet `Ton 7 (2)` với header hai tầng `MÃ TĐP/TÊN TDP/Tên trên HĐ/MÃ KHO/T/Suất/ĐVT/Tồn cuối kỳ`; không có bất kỳ file `*NXT*.xlsx`. Vì file này chỉ là sổ tồn và README/Q-005 nói rõ thiếu mẫu NXT đủ tiêu đề, không dùng nó để tự đoán hình thức NXT cuối.
  - Projection/bốn file: thêm `inventory_export.py`; từ đúng một lần rebuild `moving_average_report` tạo TĐK, Nhập trong kỳ, Xuất trong kỳ và NXT. TĐK clone mẫu thật đã khóa hash, thay tiêu đề nhóm thành tồn đầu của đúng khoảng chọn và đổ mã/tên/tên HĐ/mã kho/thuế/ĐVT/SL/giá/tiền hiện tại. Nhập/Xuất chỉ nhận event ledger hóa đơn đã post và bắt buộc truy ngược được hóa đơn + dòng nguồn; thiếu trace/mã sản phẩm hoặc nguồn lạ thì fail-closed. Reversal xuất là số lượng/giá trị âm trong chi tiết, không xóa bút toán gốc.
  - Đối chiếu: mỗi mã bị kiểm bắt buộc `TĐK + Nhập − Xuất = Tồn cuối` cho cả SL (6 số lẻ) và tiền (0,01); chi tiết event lại được cộng theo mã và so với NXT. Cả bốn workbook có cùng `CONTRACT_ID` SHA-256 và sheet `_ĐỐI_CHIẾU` veryHidden chứa kỳ, tổng, công thức và rounding; không external link/công thức động. ZIP chứa đúng bốn `.xlsx`, đồng thời có endpoint tải riêng. Giá xuất dùng moving average của TDP-081; giá bán, draft/reservation, kho vận hành cũ và công nợ không đi vào file.
  - UI/hướng dẫn: đổi menu/tiêu đề thành `TĐK–NXT / kho hóa đơn`, thêm chọn `Từ ngày – Đến ngày`, bảng TĐK/Nhập/Xuất/Tồn cuối và năm nút tải ZIP/từng file. Điều chỉnh kho vận hành được ghi rõ không tự vào ledger hóa đơn. Màn/file NXT hiện nhãn minh bạch `bố cục tạm thời chờ Q-005`; không tuyên bố visual accepted. Cache JS tăng `20260903-1`; hướng dẫn sử dụng ghi rõ nguồn, reversal, bốn file và ranh giới BK/Q-005.
  - Acceptance: 5/5 test export mới đạt, gồm tổng fixture `10×100 + 5×200 − 3×133,333333 = 12×133,333333 = 1.600`, đúng bốn file/route, template hash, contract chung, trace thiếu bị chặn, formula/link scan, UI contract và reversal `3 − 1 = 2` với giá trị xuất ròng `266,67`. Full regression cuối `277/277` đạt trong `97,720` giây. QC UTF-8 `ok=true`, thêm gate `invoiceInventoryFourFileExport = 4 XLSX / one contract id / source traces and totals reconciled` và `invoiceInventoryUiContract = period projection / four downloads / Q-005 boundary passed`; Node syntax, `py_compile`, `git diff --check` đạt.
  - An toàn/trạng thái: không chạy COM visual cho NXT vì Q-005 chưa có golden đầy đủ và Excel người dùng đang mở `Em Thành.xlsx` PID `19780`; đây là lý do duy nhất TDP-082 mang `[!]`. Listener source cũ PID `15160` vẫn `/health ok=true`, schema/database/integrity xanh. Database thật giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; không commit/push/build/deploy, không migration/init hoặc write API database thật.
  - File: `tdp_system/inventory_export.py`, `tdp_system/test_inventory_export.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, ba test UI cache-bust và `BIG_PLAN_TDP.md`. Task tiếp theo TDP-083; Q-005 chỉ giữ lại nghiệm thu hình thức NXT, không chặn task độc lập.
- 2026-09-03 01:05 – TDP-083 [!] phần an toàn/preview hoàn tất, confirm BK chờ Q-004
  - Bằng chứng nguồn/Q-004: sheet `BÁO GIÁ` trong `Em Thành.xlsx` có header hàng 2 cột H là `bk`, cột I là `Tên làm bảng kê`; file ngày `Đơn hàng 01.09.2026.xlsx` cũng mang cặp cột này. Đây chỉ chứng minh cờ ứng viên trong danh mục giá, không có file import BK chính thức, tập loại chứng từ hay quy tắc tác động kho/pháp lý. Không suy diễn cờ thành chứng từ nhập.
  - Khóa đường cũ nguy hiểm: duyệt batch trước đây gọi `post_purchase_list_inventory` và tự tạo `BK_INPUT` từ `purchase_list=1`, còn ước tính giá vốn bằng 95% giá bán. Hàm tương thích nay chỉ xóa projection cũ của đúng batch, không tạo dòng mới; mọi phép tính `inventory_rows` loại `BK_INPUT` lịch sử. Vì vậy một cờ/dòng legacy không thể tăng tồn khả dụng, mở khóa readiness hoặc tạo draft đầu ra.
  - Template/preview: thêm `bk_import.py` với một sheet `BK_IMPORT`, banner đỏ `MẪU DỰ THẢO – CHỈ PREVIEW, CHƯA ĐƯỢC NHẬP KHO (Q-004)` và 12 cột rõ nguồn: ngày, loại BK, số/dòng tham chiếu, mã hàng TĐP, tên/ĐVT, SL, giá vốn, thành tiền, mã đối tượng, ghi chú. File không có công thức/link/macro; parser giới hạn kích thước/ZIP/20.000 dòng, bắt mã danh mục, ngày, số hữu hạn, `SL × giá = tiền`, công thức/hyperlink, trùng khóa và che/chặn số dạng CCCD/CMND.
  - Idempotency/ranh giới ghi: khóa dòng là SHA-256 chuẩn hóa của `ngày + loại nguồn + số tham chiếu + dòng nguồn + mã TĐP`; cùng bytes cho cùng `sourceHash`, `contentHash`, `previewId` và `rowKey`. Preview mở DB ở `query_only`, luôn `canConfirm=false/previewOnly=true/blockedBy=Q-004`; `/api/bk-import/confirm` trả 409 `bk_confirmation_policy_pending` mà không mở kết nối DB, nên không thể ghi `inventory_transactions` hay `invoice_inventory_ledger` bằng payload khác.
  - UI/hướng dẫn: màn `TĐK–NXT / kho hóa đơn` có tải mẫu dự thảo, chọn file để preview, bảng nguồn/mã/SL/giá/tiền/lỗi và nút xác nhận disabled; nêu rõ duyệt phiên đơn không tự cộng BK. Chỉ nhận `.xlsx`; cache JS tăng `20260903-2`. Hướng dẫn sử dụng ghi quy trình, khóa Q-004 và việc loại projection legacy.
  - Acceptance: 6/6 test BK mới đạt; nhóm BK/stock gate/receivable/inventory liên quan 25/25 đạt; full regression cuối `283/283` đạt trong `100,036` giây. QC UTF-8 `ok=true`, thêm gate `bkImportSafetyContract = draft template / stable row keys / preview only / confirm 409 / no ledger write`; Node syntax, `py_compile`, `git diff --check` đạt.
  - An toàn/trạng thái: database thật giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; listener source PID `15160` vẫn `/health ok=true`, `database_ready/schema_ready/integrity` xanh; Excel người dùng PID `19780` giữ nguyên. Không commit/push/build/deploy, không migration/init hoặc write API database thật. Q-004 là lý do duy nhất task mang `[!]`; phần confirm/import thật chưa được triển khai trá hình.
  - File: `tdp_system/bk_import.py`, `tdp_system/test_bk_import.py`, `tdp_system/contract_modules.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, ba test UI cache-bust và `BIG_PLAN_TDP.md`. Task đủ dependency tiếp theo TDP-084.
- 2026-09-03 01:26 – TDP-084 [x] readiness/draft nhiều vòng và danh sách thiếu theo nhà thầu hoàn tất
  - Audit nguồn: readiness/draft cũ dùng `inventory_lookup` của kho vận hành tương thích, nên bút toán `ADJUSTMENT` hoặc nguồn legacy có thể mở khóa hóa đơn sai; đồng thời chỉ gộp `allocated`, chưa tách draft/đã phát hành, chưa có tổng theo nhà thầu và chưa xuất phần thiếu theo kỳ. TDP-080 xác định nguồn đúng phải là tồn đầu `OPENING` đã chọn cộng `invoice_inventory_ledger`; vì vậy TDP-084 chuyển hoàn toàn stock gate sang projection canonical, không lấy điều chỉnh tay, `MSMI_INPUT` tương thích hay `BK_INPUT`.
  - Domain nhiều vòng: thêm `outgoing_readiness.py`; tồn khả dụng bằng canonical closing trừ toàn bộ reservation dự thảo và hóa đơn đã xác nhận cục bộ nhưng chưa khớp bản nguồn đã post. Khi cùng ký hiệu+số+ngày đã có source invoice/ledger output chuẩn thì không trừ hai lần. Dòng thực giao dương bắt buộc có mã TĐP tồn tại và nhà thầu; phân bổ vượt demand hoặc phần khóa không còn được tồn chuẩn bảo chứng đều fail-closed. Dự thảo thay thế chỉ được cộng trả đúng hold của chính nó trên số dư thô, nên nếu tồn chuẩn giảm từ 7 xuống 2 thì draft được co về 2, không thể phục hồi nhầm 7.
  - Readiness/API/UI: `/api/outgoing-invoices/readiness/<batch>` trả riêng tổng cần, đã dự thảo, đã phát hành, có thể lập và còn thiếu cho từng dòng và từng nhà thầu. UI màn chứng từ hiển thị hai cấp tổng/chi tiết, giữ đúng quy tắc cần 10 có 7 lập 7 và giữ 3; mỗi contractor có draft/round độc lập. Cache JS tăng `20260903-3`.
  - Danh sách thiếu theo kỳ: thêm GET JSON `/api/outgoing-invoices/shortages?from=&to=&contractor=` và Excel `/api/outgoing-invoices/shortages/export?from=&to=&contractor=`. Projection duyệt batch đã duyệt theo thứ tự ngày/batch/nhà thầu/dòng, dùng một pool tồn chung nên không cấp cùng tồn cho hai nhu cầu. File `.xlsx` chỉ chứa nhóm còn thiếu, có sheet tổng + sheet riêng từng nhà thầu, mã/tên/ĐVT/ngày/bếp/batch, tổng cần, draft, phát hành, có thể lập, còn thiếu, đơn giá và giá trị thiếu; giá trị tĩnh, chống formula injection, không hyperlink/link ngoài. UI cho chọn từ ngày–đến ngày/nhà thầu, xem trước tổng và tải đúng giá trị đang nhập.
  - Kiểm thử: thêm 9 test chuyên biệt gồm hai vòng 7+3 và replay không nhân đôi, nhiều nhà thầu tách draft, future reservation chặn backdate, cancel nhả tồn, mã trống bị chặn, manual adjustment không mở khóa, canonical output làm giảm tồn, bản source đã post không bị trừ hai lần, tồn giảm sau draft co hold an toàn, lọc kỳ/nhà thầu và workbook tĩnh. Hai test roundtrip cũ chuyển fixture từ movement `MSMI` tương thích sang ledger canonical đúng TDP-080.
  - Acceptance: nhóm liên quan 39/39 đạt. Full regression cuối `292/292` đạt trong `100,820` giây. QC UTF-8 `ok=true`, thêm gate `outgoingReadinessMultiRound = canonical invoice stock / multi-round contractor split / period shortage export passed`; Node syntax, `py_compile`, `git diff --check` đạt.
  - An toàn/trạng thái: database thật giữ nguyên SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; listener source cũ PID `15160` vẫn `/health ok=true`, `database_ready/schema_ready/integrity` xanh; Excel người dùng PID `19780` giữ nguyên. Không commit/push/build/deploy, không migration/init hoặc write API database thật.
  - File: `tdp_system/outgoing_readiness.py`, `tdp_system/test_outgoing_readiness.py`, `tdp_system/contract_modules.py`, `tdp_system/test_purchase_order_roundtrip.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, ba test UI cache-bust, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BIG_PLAN_TDP.md`. Task đủ dependency tiếp theo TDP-085.
- 2026-09-03 01:41 – TDP-085 [x] file hóa đơn theo bốn mẫu thuế thật hoàn tất
  - Audit nguồn/golden: xác nhận bốn file thật trong `bosung.30.8.26` giữ nguyên hash đã khóa: KKKNT `thue 0.xlsx` `82642c99…0619` (active `Sheet2`), VAT8 `892c57a6…c573`, VAT10 `d4548d30…0de9`, VAT10 khuyến mại `243ec60b…691b` (active `Sheet 1 (2)`). Tổng 26 dòng canonical; mẫu `thue 0` dùng `% VAT=-2`, không phải VAT 0%; dòng khuyến mại mẫu có nature `2` và các ô tiền để trống.
  - Sửa lỗi nguồn số lượng: ZIP cũ chỉ kiểm có draft nhưng lại dựng từ toàn bộ `orders`, nên demand 10/draft 7 có thể xuất file 10; đồng thời chỉ cần có vòng issued là chặn mọi vòng sau. `export_invoices_zip` nay chỉ đọc `outgoing_invoice_lines` của đúng draft còn chỉnh được, bỏ issued/cancelled và trạng thái M-Invoice `saved/saving/unknown`. Vì vậy vòng 1 xuất đúng 7; sau khi phát hành và có thêm đầu vào, vòng 2 tải riêng đúng 3, không lặp vòng cũ và không lấy phần còn thiếu chưa giữ tồn.
  - Template/tách file: thêm `invoice_tax_export.py`, khóa hash từng golden trước mỗi lần dùng; tạo workbook một sheet sạch theo đúng active sheet/header/style/độ rộng cột của mẫu liên quan, không mang các sheet dữ liệu phụ của file nguồn. ZIP tách khóa `nhà thầu + round_no + thuế`; VAT10 có dòng promotion chọn đúng golden khuyến mại. VAT 0 thật/KCT không bị nhập nhằng với KKKNT và dùng fallback 13 cột riêng khi chưa có golden đích danh.
  - Số liệu/an toàn: từng dòng bắt mã/tên/ĐVT/nhà thầu, SL dương, đơn giá không âm, `SL × đơn giá = thành tiền` theo HALF_UP VND và nature chỉ 1/2. KKKNT giữ `-2`; dòng khuyến mại giữ SL và thuế nhưng để trống E/F/G/H/I/K/L. Output là giá trị tĩnh, không formula/hyperlink/external link; chuỗi dạng công thức được literal hóa; tên ZIP an toàn và entry có timestamp deterministic theo ngày phiên.
  - Runtime/UI: `BUILD_PORTABLE.ps1` được chuẩn bị để đóng gói module và đúng bốn asset golden vào `tax_templates` cho build sau, nhưng không chạy build trong Goal A. Thẻ chứng từ đổi thành “Tải ZIP vòng này”, nói rõ chỉ lấy lượng đang giữ của vòng hiện tại; cache JS tăng `20260903-4`. Hướng dẫn sử dụng ghi nguồn draft, tách contractor/round/tax, KKKNT và blank promotion.
  - Kiểm thử/acceptance: thêm 5 test chuyên biệt tái sinh đủ 26 dòng từ bốn golden, so header/style/sheet/tổng/thuế/nature, kiểm formula-free, hash drift fail-closed, tách ba file không trộn contractor/tax, asset portable và API hai vòng 7 rồi 3. Nhóm TDP-084/085 liên quan 15/15 đạt. Full regression cuối `297/297` đạt trong `103,564` giây. QC UTF-8 `ok=true`, thêm `outgoingInvoiceTaxExport = draft-line quantities / contractor+round+tax split / locked golden styles / promo blanks passed`; Node, Python/PowerShell syntax và `git diff --check` đạt.
  - An toàn/trạng thái: bốn golden giữ nguyên hash; database thật giữ SHA-256 `141ac02a9c2beb2ecb0c6305da8ccb671164b369d214b80491801abb22e4e6cf`; listener PID `15160` vẫn `/health ok=true`, schema/database/integrity xanh; Excel PID `19780` giữ nguyên. Không commit/push/build/deploy, không migration/init hoặc write API database thật.
  - File: `tdp_system/invoice_tax_export.py`, `tdp_system/test_invoice_tax_export.py`, `tdp_system/server.py`, `tdp_system/qc_system.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, ba test UI cache-bust, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BUILD_PORTABLE.ps1`, `BIG_PLAN_TDP.md`. Task đủ dependency tiếp theo TDP-086.
- 2026-09-03 02:00 – TDP-086 [x] luân chuyển/mặt hàng thay thế có xác nhận hoàn tất
  - Domain và ranh giới: thêm module riêng `outgoing_substitution.py`. Chỉ dòng thực giao của batch đã duyệt và còn thiếu mới được chọn; người dùng phải tự nhập mã thay thế khác mã gốc, cùng ĐVT, số lượng không vượt phần thiếu và tồn mã thay thế phải đủ theo đúng projection kho hóa đơn canonical của TDP-084. Không có thuật toán tự chọn/gợi ý mã thành quyết định; order gốc không bị sửa mã, tên hoặc giá.
  - Giá bán: mã thay thế chỉ lấy giá từ báo giá đã xác nhận đúng kỳ + đúng nhóm nhà thầu qua `quote_sell_price`. Giá mua danh mục, đơn giá tồn đầu, giá vốn và bình quân kho không được dùng. Khi không có giá kỳ, preview/confirm bị chặn; nhánh duy nhất là override VND dương có checkbox phê duyệt, người thực hiện và lý do riêng được lưu snapshot/audit.
  - Preview/xác nhận/idempotency: preview trả rõ gốc → thay thế, SL, tồn, ĐVT, thuế, giá/nguồn/kỳ và thành tiền. Token preview ngẫu nhiên chỉ sống 15 phút trong bộ nhớ; confirm recompute toàn bộ snapshot trong `BEGIN IMMEDIATE`, nên stock/giá/demand đổi sẽ buộc preview lại, server restart cũng fail-closed. Token đã confirm replay không nhân đôi; token cũ sau hoàn tác không tạo lại ngoài ý muốn, còn preview mới cho phép áp dụng lại hợp lệ.
  - Dự thảo/reversal: xác nhận tạo `draft_kind=substitution`, dòng hóa đơn dùng mã/tên/giá thay thế và reservation `OUTGOING_DRAFT` giữ đúng kho của mã thay thế/bếp nguồn. Dự thảo thường coi lượng thay thế là allocation khóa và không được ghi đè/cancel ngầm; nhiều lượt dùng round độc lập. Hoàn tác khi draft còn chỉnh được sẽ hủy hold, xóa dòng editable, tính lại/hủy draft và giữ action lịch sử `reversed`; draft M-Invoice `saved/saving/unknown` hoặc đã phát hành bắt buộc đi theo reversal hóa đơn chuẩn. Hủy cả draft cũng đánh dấu mọi action liên quan đã hoàn tác thay vì xóa audit.
  - UI/tài liệu/build: màn chứng từ có form tự chọn dòng thiếu và tự nhập mã, preview riêng, cảnh báo dữ liệu đổi sau preview, xác nhận cuối và bảng lịch sử/hoàn tác; cache JS tăng `20260903-5`. Danh sách thiếu theo kỳ/Excel của TDP-084 là đầu vào chuyển hàng. Hướng dẫn sử dụng ghi đủ quy tắc giá, kho, token và reversal. `BUILD_PORTABLE.ps1` chỉ được chuẩn bị thêm module/hidden import cho lần build sau; không chạy build trong Goal A.
  - Kiểm thử/acceptance: thêm 10 test chuyên biệt bao phủ thiếu giá kỳ dù có giá mua, đúng kỳ + đúng nhà thầu vào ZIP, tồn không đủ, sai ĐVT, override bắt buộc duyệt/lý do, stale stock, confirm replay, hoàn tác/reapply, chặn sau phát hành, nhiều round, draft thường không phá dòng thay thế, hủy cả draft và UI contract. Nhóm liên quan 28/28 đạt; full regression cuối `307/307` đạt trong `103,095` giây. QC UTF-8 `ok=true`, thêm gate `outgoingSubstitutionConfirmation = manual code / preview token / period-contractor sell price / canonical stock / reversal audit passed`; Node/Python/PowerShell syntax và `git diff --check` đạt.
  - An toàn/trạng thái: database thật giữ nguyên SHA-256 `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF`; `Em Thành.xlsx` giữ SHA-256 `66808CD910F63F4D543A72CC51DDAEBA1C60B147E0457FEAFC5BAD65EAD26AD3`; Excel PID `19780` và listener local PID `15160` giữ nguyên, `/health` trả `ok=true`, `database_ready=true`, `schema_ready=true`, `integrity=ok`. Không commit/push/build/deploy, không init/migration/write API database thật.
  - File: `tdp_system/outgoing_substitution.py`, `tdp_system/test_outgoing_substitution.py`, `tdp_system/contract_modules.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BUILD_PORTABLE.ps1`, ba test UI cache-bust và `BIG_PLAN_TDP.md`. Task đủ dependency tiếp theo TDP-087; Q-008 chỉ chặn hình thức mẫu đề nghị thanh toán cuối, không chặn audit nguồn/domain an toàn.
- 2026-09-03 02:12 – TDP-087 [!] domain hóa đơn đỏ hoàn tất, mẫu đề nghị thanh toán cuối chờ Q-008
  - Bằng chứng Q-008: tìm đích danh toàn bộ `C:\Users\DELL\Downloads` theo tên đề nghị/thanh toán/payment/bảng kê giao không thấy workbook/DOCX mẫu đề nghị thanh toán theo từng nhà thầu trong snapshot; chỉ có code/test. Word/README cũng ghi khách còn thiếu đề nghị thanh toán của các nhà thầu. Vì vậy không nhận DOCX tự thiết kế là biểu mẫu chính thức và giữ đúng `[!]` cho phần hình thức cuối.
  - Sửa ranh giới nguồn: thêm `invoice_payment_scope.py`. Scope chỉ lấy `outgoing_invoice_drafts.status='issued'` của đúng nhà thầu/kỳ, bắt đủ số/ngày hóa đơn và snapshot pháp lý/thanh toán đã khóa lúc phát hành; draft/chưa phát hành/cancelled, đơn khách, phiếu giao và sổ phải thu vận hành không tham gia. Nhiều snapshot khác nhau bị buộc tách kỳ; tổng phạm vi phải dương.
  - Đối chiếu hóa đơn nguồn: nếu chưa có bản nguồn khớp ký hiệu+số+ngày, từng hóa đơn ghi provenance `local_issued_confirmation`; nếu có bản nguồn thì bắt buộc `source_status_class=issued`, `sync_status=synced`, không ở `blocked/reversal_required/reversed`, khớp MST người mua và ba tổng trong 1 VNĐ. Nguồn cancelled/replaced/adjusted/unknown, trùng identity, lệch MST hoặc lệch tổng đều chặn toàn hồ sơ, không âm thầm bỏ dòng.
  - Số liệu/scope: từng dòng bắt SL dương, giá không âm và `SL × giá = thành tiền`; cộng lại trước thuế/thuế/tổng phải khớp từng hóa đơn trong 1 VNĐ. `scope_id` SHA-256 khóa invoice identity/provenance/tổng, toàn bộ chi tiết render và snapshot pháp lý; download có scope cũ sau bất kỳ thay đổi nào trả 409 thay vì sinh file khác preview.
  - Ranh giới biểu mẫu/UI: endpoint JSON `/api/outgoing-invoices/payment-scope/<contractor>` cho người dùng xem danh sách hóa đơn đỏ/tổng/nguồn xác minh trước. Output hiện có được đổi thành `Bộ kiểm soát Q-008`: tên ZIP/DOCX/XLSX, banner trong DOCX, tiêu đề hai sheet, manifest UTF-8 và HTTP header đều ghi rõ chưa phải mẫu chính thức. UI đổi từ tải trực tiếp sang xem scope trước, xác nhận cảnh báo rồi mới tải; cache JS tăng `20260903-6`. Legacy URL vẫn đi qua cùng domain gate, không còn đường lấy phải thu vận hành.
  - Kiểm thử/acceptance: thêm 7 test TDP-087 và siết 2 test document có sẵn, bao phủ unissued/cancelled/operational exclusion, local audit provenance, source-issued provenance, bốn trạng thái nguồn xấu, lệch tổng/dòng/MST, conflict snapshot, stale scope, line thay thế đã phát hành, ZIP/DOCX/XLSX/manifest/header và UI/build contract. Nhóm liên quan 59/59 đạt sau sửa cache; full regression cuối `314/314` đạt trong `105,202` giây. QC UTF-8 `ok=true`, thêm gate `invoicePaymentScopeQ008Boundary = issued invoice only / source cancellation guard / frozen snapshot / Q-008 control label passed`; Node/Python/PowerShell syntax và `git diff --check` đạt.
  - An toàn/trạng thái: database thật giữ nguyên SHA-256 `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF`; `Em Thành.xlsx` giữ SHA-256 `66808CD910F63F4D543A72CC51DDAEBA1C60B147E0457FEAFC5BAD65EAD26AD3`; Excel PID `19780`, listener PID `15160` giữ nguyên và `/health` trả `ok=true`, `database_ready=true`, `schema_ready=true`, `integrity=ok`. Không commit/push/build/deploy, không init/migration/write API database thật.
  - File: `tdp_system/invoice_payment_scope.py`, `tdp_system/test_invoice_payment_scope.py`, `tdp_system/test_invoice_payment_documents.py`, `tdp_system/contract_modules.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BUILD_PORTABLE.ps1`, ba test UI cache-bust và `BIG_PLAN_TDP.md`. TDP-088 tiếp tục khóa riêng workbook đối chiếu giao hàng theo cùng scope hóa đơn; Q-008 chỉ còn chặn template đề nghị thanh toán cuối.
- 2026-09-03 02:26 – TDP-088 [x] bảng kê giao hàng đối chiếu chính thức theo hóa đơn đỏ hoàn tất
  - Domain/output: tách exporter `invoice_delivery_statement.py` khỏi code chứng từ nguyên khối. Workbook chỉ nhận hóa đơn `issued` đủ số/ngày, đúng một nhà thầu và các dòng nằm trong scope hóa đơn đã khóa của TDP-087; nhiều vòng phát hành cùng nhà thầu được giữ thành các dòng/hóa đơn riêng. Sheet chi tiết giữ ngày giao, ngày/ký hiệu/số HĐ, bếp, mã/tên/ĐVT, SL, giá, ba tổng và cột trace ẩn; sheet đối chiếu giữ từng hóa đơn cùng provenance nguồn/local và chênh lệch.
  - Đối chiếu/an toàn: từng dòng bắt `SL × đơn giá = thành tiền`; trước thuế, thuế và tổng của từng hóa đơn phải khớp bảng kê trong 1 VNĐ. Hóa đơn nháp/hủy, mixed contractor, dòng ngoài scope, trùng line, thiếu dòng hoặc lệch trên ngưỡng đều chặn toàn file; không có nhánh tự cân. Chuỗi dạng công thức được literal hóa, workbook không formula/hyperlink/external link, A4 ngang, lặp header và chỉ chứa giá trị tĩnh.
  - Runtime/UI/ranh giới Q-008: thêm endpoint độc lập `/api/outgoing-invoices/delivery-statement/<contractor>` có `scope_id` chống stale, HTTP provenance header và audit chỉ counter/tổng/hash scope. UI sau bước xem hóa đơn có nút riêng “Tải bảng kê đối chiếu hóa đơn”; XLSX là bảng số liệu chính thức theo hóa đơn đỏ và không mang nhãn Q-008. Bộ ZIP vẫn chứa XLSX này, nhưng DOCX đề nghị thanh toán và tên bộ kiểm soát tiếp tục ghi rõ chờ Q-008. Cache JS tăng `20260903-7`; hướng dẫn phân biệt rõ với `bảng kê tổng` thu mua TDP-062.
  - Kiểm thử/acceptance: thêm 4 test exporter và 1 test API nhiều vòng/multiple contractors, mở rộng stale/UI/build assertions; nhóm trọng tâm 28/28 đạt. Full regression cuối `319/319` đạt trong `107,525` giây. Lần full đầu phát hiện test replay reference XLSX phụ thuộc timestamp package; sửa idempotency `daily_reference_import.py` sang hash nội dung role-owned, 7/7 test reference và full đều xanh. QC UTF-8 cuối `ok=true`, thêm gate `issuedInvoiceDeliveryStatement = one contractor / issued red invoices / multiple rounds / static A4 / exact totals passed`; Node/Python/PowerShell syntax và `git diff --check` đạt.
  - An toàn/trạng thái: database thật giữ nguyên SHA-256 `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF`; `Em Thành.xlsx` đọc shared-lock giữ SHA-256 `66808CD910F63F4D543A72CC51DDAEBA1C60B147E0457FEAFC5BAD65EAD26AD3`; Excel PID `19780`, listener PID `15160` giữ nguyên và `/health` trả `ok=true`, `database_ready=true`, `schema_ready=true`, `integrity=ok`. Không commit/push/build/deploy, không init/migration/write API database thật.
  - File: `tdp_system/invoice_delivery_statement.py`, `tdp_system/test_invoice_delivery_statement.py`, `tdp_system/test_invoice_payment_scope.py`, `tdp_system/test_invoice_payment_documents.py`, `tdp_system/contract_modules.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `tdp_system/daily_reference_import.py`, `BUILD_PORTABLE.ps1`, bốn test UI cache-bust và `BIG_PLAN_TDP.md`. Task đủ dependency tiếp theo TDP-090.
- 2026-09-03 02:28 – TDP-090 [x] regression Xưởng cơm/PO sau đại cập nhật đạt, không cần sửa nghiệp vụ
  - Golden/source: xác nhận `_HANDOFF/EXTERNAL_INPUTS/xưởng cơm.xlsx` giữ SHA-256 `4CCF1957C53DE932EF87EFEAEBBD398A3F45A60161FC04409BC6A471664ACE8B`; file chấm suất thật `SUẤT ĂN T8.2026.xlsx` giữ SHA-256 `1117786C6356E75CA75329926E1F3717BD8EADAE3857F8E5BED3B36B1C9E1EBF`. Menu `Xưởng cơm / PO`, form import định mức/PO, chấm suất, mapping XCOM, PO và module đề nghị thanh toán vẫn hiện trong source UI; không bị đại cập nhật ẩn/xóa.
  - Acceptance golden đã chạy trong QC trên DB test riêng: preview/confirm đúng 5 kế hoạch và 54 nguyên liệu; VINA 28, SUNBY 32, DAINAM 48, MAZDA 46, TTS 40 suất; MAZDA giữ hai thực đơn × 23 suất; toàn bộ giá có provenance `HATRAN 2026-09 · giá kỳ đã khóa`. PO nháp có đúng ba sheet `XCOM/MAZDA/TTS`, 54 dòng và tổng thực phẩm `3.851.200` VNĐ; PO thủ công chỉ đổi sang `ĐÃ DUYỆT` sau khi đủ XCOM, giá suất và giá nguyên liệu.
  - Chấm suất/thanh toán: workbook tháng thật tạo 205 dòng, 28 ngày, 6 bếp và 6.020 suất thực ăn; nhập lại đổi tên file không nhân đôi. Hồ sơ QC-BOT chỉ lấy 1.313 suất thực ăn, không lấy ordered/PO, áp đúng tariff kỳ cho trước thuế `32.825.000`, VAT `2.626.000`, tổng `35.451.000`; preview một lần, stale/expired/missing tariff và cấu hình pháp lý thiếu đều bị chặn, DOCX sinh lặp deterministic.
  - Kiểm thử: 32/32 test tập trung đạt (`test_xcom_payment_documents`, `test_xcom_payment_routes`, `test_meal_attendance_t1`, `test_attendance_import_safety`, `test_final_safety_regressions`). Full regression dùng chung sau TDP-088 đạt `319/319`; QC UTF-8 cuối `ok=true` với các gate `actualCustomerKitchenWorkbook`, `actualMealAttendanceWorkbook`, `xcomPaymentDocuments`, `kitchenMenuCostPo`, `kitchenWorkbookImport` đều passed. Không sửa code nghiệp vụ vì không phát hiện hồi quy.
  - An toàn: mọi import/confirm/regression chạy trên database tạm của test/QC, không gọi write API listener thật. Database thật/golden/Excel/listener giữ đúng bất biến đã ghi ở TDP-088. Task đủ dependency tiếp theo TDP-091.
- 2026-09-03 02:35 – TDP-091 [x] regression Chấm công/lương sau đại cập nhật đạt
  - Audit chức năng: menu `Chấm công & lương` và `Xưởng cơm / PO` cùng còn hiển thị; màn payroll vẫn có import preview/confirm, thêm/cập nhật nhân sự, chấm/sửa đủ giờ thường–tăng ca–Chủ nhật–đêm–lễ, khoản phụ cấp/trách nhiệm/BHXH/tạm ứng/khấu trừ/override và tải bảng lương. API bootstrap/payroll và workbook hai sheet vẫn được nối đầy đủ; import trực tiếp bị khóa, bắt buộc preview + xác nhận và bảo toàn dòng sửa tay khi nạp lại snapshot.
  - Browser thật: thêm fixture/smoke riêng trên source + database tạm cổng `18796`, Edge CDP `19246`. Chuỗi thao tác đạt: mở menu → thêm NV02 → chấm 8 giờ thường + 2 tăng ca + 1 Chủ nhật + 1 đêm + 1 lễ → thấy lương công thức 432.500 → thêm 100.000 phụ cấp + 50.000 trách nhiệm − 25.000 tạm ứng − 10.000 khấu trừ − 20.000 BHXH → tổng lương 582.500, thực lĩnh 527.500, BHXH công ty 30.000 → tải `Bang_luong_2026-09.xlsx` → reload vẫn giữ đúng dữ liệu. Hai listener tạm và toàn bộ process Edge của profile đã dừng; chính sách môi trường từ chối xóa đệ quy nên thư mục test cô lập `tmp/tdp091_payroll_smoke` còn lại, không được dùng làm nguồn vận hành.
  - Kiểm thử/acceptance: thêm `test_payroll_ui.py`; 26/26 test attendance/payroll/UI/financial guard tập trung đạt. Full regression cuối `320/320` đạt trong `106,315` giây; QC UTF-8 cuối `ok=true`, trong đó `attendancePayrollLegacyImport=passed` và các gate chấm suất/xưởng cơm vẫn xanh. Node/Python syntax và `git diff --check` đạt.
  - An toàn/trạng thái: browser chỉ ghi database tạm; database thật giữ SHA-256 `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF`, golden `Em Thành.xlsx` giữ `66808CD910F63F4D543A72CC51DDAEBA1C60B147E0457FEAFC5BAD65EAD26AD3`, Excel PID `19780` còn mở; listener người dùng PID `15160` ở cổng `8765` trả `/health ok=true`, database/schema/integrity xanh. Không commit/push/build/deploy, không migration/init/write API database thật.
  - File: `tdp_system/browser_fixture_payroll_server.py`, `tdp_system/browser_smoke_payroll.js`, `tdp_system/test_payroll_ui.py`, `BIG_PLAN_TDP.md`. Không phải sửa production code vì regression không phát hiện lỗi.
- 2026-09-03 02:35 – TDP-092 [!] chờ Q-009, giữ nguyên hai module
  - Ảnh/câu “2 phần không cần làm nữa” chưa chỉ ra được chính xác hai chức năng con; chủ dự án đã đính chính rõ Xưởng cơm/PO và Chấm công/lương vẫn phải có. Theo policy của task, không suy đoán và không xóa/ẩn chức năng nào. TDP-090 và TDP-091 đã chứng minh hai module vẫn hoạt động; Q-009 chỉ chặn quyết định loại hai phần chưa xác định, không chặn TDP-110 trở đi.
- 2026-09-03 02:49 – TDP-110 [x] hợp nhất UI và ngôn ngữ nghiệp vụ hoàn tất
  - Nhãn/ranh giới: giữ đúng menu `TĐK–NXT / kho hóa đơn`, `Báo cáo & công nợ`, checklist `Đã đặt/Chưa đặt/Mở lại`; đổi file từ đơn/giao thành `Bảng kê đầu ra vận hành` và ghi rõ không thay bảng kê theo hóa đơn đỏ. Vùng cấu hình đổi thành `Thông tin thanh toán mặc định`; bỏ tuyên bố sai rằng đã lấy từ mẫu khách và ghi rõ mẫu đề nghị thanh toán cuối vẫn chờ Q-008.
  - Trạng thái/lỗi: thêm ánh xạ tiếng Việt cho trạng thái nhập kho, xuất kho, đồng bộ và kế hoạch xưởng cơm; không còn render thẳng `posted/ready/reversal_required/draft`. Đổi toàn bộ câu thao tác hoàn tác xuất kho đang lộ `reversal`; lỗi từng hóa đơn và lỗi đồng bộ gần nhất hiện ngay tại đúng thẻ thay vì chỉ đổi màu. Thông báo backend có thể nổi lên UI cũng dùng `ghép mã/hoàn tác xuất kho` thay cho thuật ngữ kỹ thuật.
  - Bàn phím: luồng mã đầu vào/đầu ra tiếp tục dùng Enter; bổ sung Enter cho hệ số quy đổi ĐVT, giữ Enter lưu giá nhanh và chuyển dòng phân bổ phải trả, kèm hướng dẫn Tab/Enter tại bàn làm việc hóa đơn. Hai smoke Edge thật trên source + DB tạm đạt toàn chuỗi ghép mã → quy đổi bằng Enter → ghi kho cho cả đầu vào (`18797/19247`) và đầu ra (`18798/19248`); các cổng/process test đã dừng.
  - Kiểm thử/acceptance: thêm 3 test contract UI, 63/63 test trọng tâm đạt; full regression cuối `323/323` đạt trong `108,670` giây. QC lần đầu chỉ vướng console CP1252 không in được tiếng Việt, chạy lại với UTF-8 đạt `ok=true` và gate mới `unifiedUiBusinessLanguage = agreed screen names / operational-vs-red-invoice boundary / Vietnamese statuses / Enter mapping and conversion / explicit errors passed`. Node syntax, Python compile và `git diff --check` đạt; chỉ còn warning openpyxl Conditional Formatting và cảnh báo LF→CRLF đã biết.
  - An toàn/trạng thái: database thật giữ SHA-256 `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF`; golden `Em Thành.xlsx` đọc shared-lock giữ `66808CD910F63F4D543A72CC51DDAEBA1C60B147E0457FEAFC5BAD65EAD26AD3`; Excel PID `19780`, listener PID `15160` còn nguyên và `/health` trả database/schema/integrity xanh, hai cảnh báo trùng đều `false`. Hai thư mục fixture cô lập `tmp/tdp110_input_browser_a` và `tmp/tdp110_output_browser_a` chỉ chứa DB/profile test, không là nguồn vận hành. Không commit/push/build/deploy, không migration/init/write API database thật.
  - File: `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `tdp_system/invoice_mapping.py`, `tdp_system/invoice_output_sync.py`, `tdp_system/invoice_inventory.py`, `tdp_system/qc_system.py`, `tdp_system/test_ui_language_contract.py`, `tdp_system/test_invoice_inventory.py`, `tdp_system/test_invoice_mapping.py`, hai browser smoke hóa đơn, các test cache-bust và `BIG_PLAN_TDP.md`. Task tiếp theo TDP-111 chỉ được dry-run trên bản sao database thật.
- 2026-09-03 03:03 – TDP-111 [x] dry-run migration trên bản sao database thật hoàn tất
  - Cách ly/an toàn: `dry_run_real_migration.py` mở database nguồn bằng SQLite URI `mode=ro`, tạo online-backup riêng tại `C:\Users\DELL\AppData\Local\Temp\tdp-real-migration-dry-run-v0nn7iqa\tdp-migration-clone.sqlite3`, rồi mới trỏ source mới và toàn bộ preview/confirm vào clone. SHA-256 database thật trước/sau cùng là `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF`; không gọi write API listener thật.
  - Migration/preservation: clone trước schema `3E94FBE254098E354A3D75F6E2AD0BEBDF8D36FC8E1EE34B5089D619D19B592F`, sau schema và cuối run cùng `57720229D248F3CA8A0A3097927B8F7A8B8814EB88609A2E9BED39F2C9744566`. Chụp fingerprint theo toàn bộ cột gốc của 38 bảng nghiệp vụ trước/sau init cho kết quả không mất bảng, không đổi counts, nội dung hay giá trị tài chính; `integrity_check=ok`, khóa ngoại 0 lỗi.
  - Source mới/log: Flask test client trên clone trả `/health` HTTP 200 với database/schema/integrity xanh, hai cảnh báo identity đều false; `/api/bootstrap` HTTP 200. Báo cáo `migration-report.json` dùng allowlist, chỉ có tên bước, trạng thái, counts, hash và cờ kiểm chứng; không ghi env value, raw row, định danh cá nhân hoặc số tiền nghiệp vụ. 10/10 cổng `checks` đạt và tiến trình trả exit 0.
  - Replay nguồn: 14 bước được diễn tập; mọi bước sẵn sàng đều semantic-idempotent. `meal_attendance_2026-03` bị chặn bởi lỗi dữ liệu preview đã có; workbook đơn 29.08 không sinh một ngày duy nhất đủ điều kiện confirm theo daily-import contract mới nên được ghi `blocked`, không cưỡng ép nhập và không làm TDP-111 thất bại. Bộ dò file chấp nhận bản snapshot bị suy giảm ký tự dấu nhưng bắt buộc đúng một candidate.
  - Kiểm thử: thêm 4 test cho clone read-only, bảo toàn cột gốc khi schema mở rộng, phát hiện thay đổi số dư và lọc dữ liệu nhạy cảm; `4/4` đạt. Warning pytest cleanup junction bị từ chối quyền xuất hiện sau khi test đã exit 0, được phân loại là hạ tầng temp Windows, không phải lỗi sản phẩm.
  - File: `tdp_system/dry_run_real_migration.py`, `tdp_system/test_dry_run_real_migration.py`, `BIG_PLAN_TDP.md`. Task tiếp theo TDP-112 chạy toàn bộ regression/QC và kiểm chứng candidate.
- 2026-09-03 03:12 – TDP-112 [x] full regression và QC mở rộng hoàn tất
  - Regression: source candidate cuối đạt `327/327` test trong `120,43` giây, bao gồm toàn bộ 97 test nền và test mới; không skip. Hai warning openpyxl về Conditional Formatting là warning đã biết của thư viện khi đọc bản sao workbook. Trace cleanup `pytest-current` xuất hiện sau exit 0 do junction temp Windows từ chối quyền, không phải lỗi test/sản phẩm và không làm thay đổi workspace hay dữ liệu vận hành.
  - QC: `python -m tdp_system.qc_system` với UTF-8 trả exit 0 và `ok=true`; toàn bộ gate workbook thật, import/replay, công nợ, kho hóa đơn, báo giá, biểu mẫu, xưởng cơm, chấm công/lương, UI và Q-boundary đều xanh. Không sửa test để che lỗi; thay đổi cuối ở allowlist migration report được test riêng rồi chạy lại cả full regression và QC.
  - Static/ba lớp: `node --check tdp_system/static/app.js`, `python -m compileall -q tdp_system` và `git diff --check` đạt; chỉ có cảnh báo LF→CRLF đã biết. Renderer self-test ba lớp dùng `Microsoft Excel COM` tin cậy: cặp giống nhau không false-positive; fixture cố ý sai được bắt đúng ở data `B3`, topology/style `A1` và visual một trang. Artifact giả cô lập tại `tmp/tdp112_renderer_selftest`, không chứa dữ liệu khách và không dùng làm nguồn vận hành.
  - Bất biến cuối: database thật giữ SHA-256 `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF`; `Em Thành.xlsx` giữ `66808CD910F63F4D543A72CC51DDAEBA1C60B147E0457FEAFC5BAD65EAD26AD3`. Listener source PID `15160` trả `/health ok=true`, database/schema/integrity xanh, hai cảnh báo trùng false; Excel người dùng PID `19780` giữ nguyên. Không commit/push/build/deploy, không init/migration/write API database thật.
  - File thay đổi riêng TDP-112 chỉ là trạng thái/bằng chứng `BIG_PLAN_TDP.md`; phần siết allowlist thuộc TDP-111 nằm trong `tdp_system/dry_run_real_migration.py` và `tdp_system/test_dry_run_real_migration.py`. Task tiếp theo TDP-113 chạy smoke E2E toàn chuỗi trên môi trường tạm.
- 2026-09-03 03:24 – TDP-113 [x] smoke end-to-end đại diện hoàn tất
  - Kịch bản vận hành: thêm một smoke tự chứa trên database tạm. Một chuỗi duy nhất nạp workbook ngày lần đầu, duyệt phiên và xuất file đặt NCC; đánh dấu đủ hai NCC, mở lại rồi đặt lại một NCC; nạp lần hai và chốt tách purchase/customer scope; xác nhận hai dòng payable và hai dòng receivable, rồi mở được cả file phải trả và phải thu.
  - Hóa đơn/kho: fixture chỉ-read chạy đúng khoảng `01/08/2026–31/08/2026` cho đầu vào và đầu ra; cùng một mã TĐP được ghép độc lập hai chiều, quy đổi đầu vào `2 thùng × 5 = 10 kg` và đầu ra `1 thùng × 6 = 6 kg`. Tồn A reconcile `10 + 10 − 6 = 14`; sync/post lại không thêm ledger. Vòng một lập/phát hành 9, còn thiếu 7; nhập hợp lệ 7 cho mã B rồi lập/phát hành vòng hai 7; readiness cuối đã phát hành 16, còn thiếu 0 và mọi tồn cuối không âm.
  - Output/chức năng giữ lại: xuất/mở lại báo giá Toyota theo phiên, file đặt NCC, phiếu giao, báo cáo tổng hợp, bảng kê tổng + biên nhận và file thuế của cả hai vòng. Bảng kê đầu ra chính thức lấy đúng hai hóa đơn đã xác nhận phát hành, sheet `Đối chiếu hóa đơn` có chênh lệch 0 từng hóa đơn. Trên cùng candidate, tạo/duyệt kế hoạch xưởng cơm, tải PO; tạo nhân sự/chấm công, xem và tải bảng lương; integrity/foreign key của DB E2E sạch.
  - Kiểm thử/QC: smoke riêng đạt `1/1` trong `7,34` giây. Full regression cuối gồm smoke đạt `328/328` trong `127,03` giây, không skip; QC cuối exit 0, `ok=true`, toàn bộ gate xanh. Node syntax, compile Python và `git diff --check` đạt; warning còn lại chỉ là openpyxl Conditional Formatting, LF→CRLF và cleanup junction pytest đã được phân loại từ TDP-112.
  - An toàn/trạng thái: toàn bộ write chỉ vào `TemporaryDirectory`; golden chỉ được đưa lại cho template clone sau khi init DB tạm, không save ngược. Không gọi connector thật hay write API production, không phát hành/in thật. Database thật/golden giữ lần lượt SHA-256 `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF` và `66808CD910F63F4D543A72CC51DDAEBA1C60B147E0457FEAFC5BAD65EAD26AD3`; listener PID `15160`, Excel PID `19780`, `/health` và hai cảnh báo trùng giữ nguyên; không còn test port lắng nghe.
  - File: `tdp_system/test_goal_a_e2e.py`, `BIG_PLAN_TDP.md`. Goal A đạt Definition of Done với các phần có thể triển khai an toàn; TDP-082/Q-005, TDP-083/Q-004, TDP-087/Q-008 và TDP-092/Q-009 tiếp tục mang `[!]` đúng ranh giới, không bị giả vờ hoàn thành. TDP-100/TDP-114/TDP-115 nằm ngoài Goal A và không được thực hiện.
- 2026-09-03 10:19 – TDP-087 [x], TDP-092 [x] và TDP-116 [x] chốt phạm vi nghiệm thu mới
  - Nguồn mới: khóa hash `Đề nghị Thanh toán TĐP (T04.26).xlsx`; dùng đúng form Đề nghị thanh toán sáu cột và Bảng tổng hợp giao nhận mười cột. Không sao chép dữ liệu kỳ cũ, VnTools, công thức/liên kết ngoài hay dòng trống cố định của workbook lịch sử.
  - Hồ sơ chính thức: phạm vi vẫn chỉ gồm hóa đơn đỏ đã phát hành của đúng một nhà thầu, có snapshot pháp lý/thanh toán, kiểm tra trạng thái nguồn, chống stale scope và chặn mọi lệch tổng. ZIP nay có hai XLSX chính thức + manifest đối chiếu; DOCX kiểm soát tạm đã được rút khỏi đường tải.
  - Hóa đơn đầu vào: thêm nút `Xuất Excel` ngay tại phiên mSMI đã kéo, gồm danh sách hóa đơn, chi tiết hàng hóa và đối chiếu phiên. File dùng giá trị tĩnh, chống formula injection, không chứa raw payload/mã từ xa; response và audit xác nhận không tác động kho.
  - Phạm vi: chủ dự án tiếp tục giữ Xưởng cơm/PO và Chấm công/lương; toàn bộ `Phần làm thêm.docx` tạm loại khỏi release hợp đồng hiện tại.
  - Kiểm thử/QC: 17/17 test chức năng mới và 26/26 regression UI/liên quan đạt; `qc_system.py` chạy UTF-8 exit 0, `ok=true`, thêm gate `inputInvoiceImmediateExcelExport` và đổi gate thanh toán thành `invoicePaymentOfficialDocuments`.
  - File: `tdp_system/invoice_input_export.py`, `tdp_system/invoice_payment_documents.py`, `tdp_system/invoice_delivery_statement.py`, `tdp_system/invoice_payment_scope.py`, `tdp_system/contract_modules.py`, `tdp_system/server.py`, `tdp_system/static/app.js`, `tdp_system/static/index.html`, `tdp_system/qc_system.py`, `tdp_system/HUONG_DAN_SU_DUNG.txt`, `BUILD_PORTABLE.ps1`, test liên quan, `README-new.md`, `BIG_PLAN_TDP.md`.
- 2026-09-03 10:50 – TDP-114 [x], TDP-115 [!] chốt bản phát hành kỹ thuật
  - Regression cuối: `python -m unittest discover -s tdp_system -p 'test_*.py'` đạt `327/327`, exit 0, trong `158.001s`. Các stack trace `forced ... failure` là test rollback chủ động và toàn bộ suite kết thúc `OK`.
  - QC cuối: `python tdp_system/qc_system.py` chạy UTF-8, exit 0, `ok=true`; hai gate mới `inputInvoiceImmediateExcelExport` và `invoicePaymentOfficialDocuments` đều `passed`. `node --check`, `compileall` và `git diff --check` đạt; chỉ còn cảnh báo line ending LF→CRLF đã biết.
  - Build: `dist/TDP_Server.exe` có SHA-256 `FB550D6FA2FB5B995DF1BC9F41202FB9D0E84C6138E3D249CD419DCC24994ADA`, kích thước `76,987,185` byte. EXE cũ trong `BAN_PC_TDP` và các bản `pre_build` được giữ nguyên.
  - Smoke đúng EXE đóng gói trên bản sao database riêng, cổng `18766`: `/health ok=true`, database/schema ready, integrity `ok`; listener chỉ `127.0.0.1`; UI chứa route xuất Excel hóa đơn đầu vào và tải Đề nghị thanh toán + BK; API trả đúng `invoice_input_batch_not_found` và `issued_invoice_scope_empty` cho phạm vi giả. Server smoke đã dừng; listener source PID `15160` không bị tác động.
  - Visual: Microsoft Excel COM đã render Đề nghị thanh toán ở quy mô 1/29 hóa đơn và Bảng tổng hợp giao nhận ở quy mô 2/100 dòng; header lặp, tổng tiền, vùng ký, ngày `dd/mm/yyyy`, khổ A4 và footer nhiều trang đạt. Máy chỉ có Microsoft Print to PDF, không có Canon LBP242/243, nên chưa được phép tuyên bố đã in giấy thật.
  - Gói phát hành sạch `BAN_GIAO_TDP_20260903_FINAL` được tạo riêng, không ghi đè `BAN_PC_TDP`; không chứa `.env`, workbook mẫu khách, ảnh QC hay EXE cũ. ZIP phát hành có SHA-256 `229B2E93C38FD732FADDA201EF8B9E0CA589C062A2BE7991FD3052093928D5AC`, 9 entry và không có entry cấm. Database đưa vào gói là SQLite online backup của database source; database source giữ SHA-256 `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF` tại thời điểm chốt. `.env` vận hành gốc vẫn tồn tại và không có giá trị bí mật nào được in/log.
  - TDP-115 giữ `[!]` đúng sự thật cho tới khi in giấy thật trên Canon và khách hàng ký. Q-004 vẫn chỉ cho preview BK không ghi kho; Q-005 vẫn chỉ thiếu golden hình thức NXT vì `Em Thành.xlsx` không có sheet NXT. Hai ranh giới này không được tự suy đoán thành nghiệp vụ ghi kho hoặc mẫu khách chưa cung cấp.
- 2026-09-03 – ĐÍNH CHÍNH TRUNG GIAN – đã được log phát hành cuối phía dưới thay thế
  - Bằng chứng BK được đọc lại đầy đủ: `Note công việc.docx` nói các dòng `(bk)` là đầu vào của Thành Đạt Phát và khách **xin hệ thống cấp file mẫu**; `Em Thành.xlsx` xác định cờ `bk`/`Tên làm bảng kê`, còn sheet `bảng kê tổng` xác định đây là mua vào không có hóa đơn. Quyết định triển khai là giá nhập mặc định 95% giá bán của chính dòng, có preview/confirm/idempotency/audit/reversal và ghi canonical ledger. TDP-083 được mở lại `[~]`, không hỏi khách thêm.
  - Golden NXT đã đủ: `_HANDOFF/EXTERNAL_INPUTS/TĐK T8-2026.xlsx thụy.xlsx`, sheet `Ton 7 (2)`, có hệ cột hai tầng và các trường mã/tên/kho/thuế/ĐVT/tồn. Bốn file TĐK–Nhập–Xuất–NXT phải được sinh chính thức từ cùng projection và reconcile theo mã; không cần file có tên `NXT` riêng. TDP-082 được mở lại `[~]`, không hỏi khách thêm.
  - Bản EXE/gói đã ghi ở log 10:50 là artifact trước đính chính, được giữ làm lịch sử nhưng không còn là bản bàn giao cuối; TDP-114 trở lại `[ ]` và chỉ hoàn tất sau full regression/QC/build/smoke/hash mới.
  - Chủ dự án xác nhận các khay in đã cấu hình đầy đủ và yêu cầu không tiếp tục coi máy in là việc còn thiếu. TDP-115 chuyển `[x]` theo xác nhận chủ dự án; ký giấy nếu có là thủ tục vận hành, không phải blocker kỹ thuật.
  - Tại mốc trung gian này Q-011 chưa đóng; log phát hành cuối phía dưới đã thay thế kết luận đó bằng bằng chứng connector M-Invoice chỉ-read, mapping trạng thái, integration và fail-closed đều đạt.
- 2026-09-03 13:52 – TDP-082 [x], TDP-083 [x], TDP-114 [x], TDP-115 [x] – PHÁT HÀNH CUỐI 100% PHẠM VI HỢP ĐỒNG HIỆN TẠI
  - Nghiệp vụ: BK dùng mẫu hệ thống, giá mặc định 95% giá bán, preview/confirm/idempotency/audit/reversal và canonical ledger; bộ bốn file TĐK–Nhập–Xuất–NXT dùng cùng projection/golden và reconcile đủ số lượng–giá trị; M-Invoice đầu ra chỉ-read, paging/cursor, mapping trạng thái, fail-closed, post/reversal và fingerprint thay hold đã khóa. Q-002/Q-004/Q-005/Q-008/Q-009/Q-011 đều đã giải quyết; không hỏi lại khách. `Phần làm thêm.docx` và TDP-100/hosting ngoài phạm vi hiện tại.
  - Regression/QC: full suite `364/364`, không skip, `Ran 364 tests in 169.508s`, `OK`; `qc_system.py` exit 0, `ok=true`; Node syntax, Python compile và `git diff --check` đạt.
  - Browser: Edge/CDP trên DB/profile tạm đạt toàn bộ 13 màn hình và luồng nhập ngày, 334 mã tồn đầu, Xưởng cơm/PO, chấm suất, Chấm công/lương, công nợ, hai bộ PDF dry-run, tạo–hủy–tạo lại draft và xác nhận phát hành cục bộ; `browserErrors=0`. Canonical tồn không đổi sau local confirm, đúng ranh giới chỉ giữ hold chờ M-Invoice.
  - Migration/render/smoke: dry-run database thật trên online backup đạt `migration_passed=true`, 10/10 check, integrity `ok`, khóa ngoại 0; source smoke `18770` và EXE smoke `18774` health xanh/loopback-only. BK và NXT render Excel COM một trang ngang, không `####`, công thức/link ngoài. Lỗi nguồn `SUẤT ĂN T3-2026 .xlsx` tại `E33=125000` so với `D33=125` được chặn an toàn, không tự sửa và không chặn phạm vi tháng 08.
  - Build/artifact: `TDP_Server.exe` 77.082.006 byte, SHA-256 `76F023D61BC65B8C799A7F713C2C7DD1460665325F21E833939BA5C64F8B9FEB`. Database portable 60.338.176 byte, SHA-256 `96705D3BCD74FC0C181190315CA9F10DF6BFFF3D3EF63FE1BB327C7CA5769708`, integrity `ok`, 0 lỗi khóa ngoại, 334 mã có Mã kho/113 khác Mã TĐP/43 nhiều mã kho.
  - Gói sạch: `BAN_GIAO_TDP_20260903_100PCT.zip` 86.481.255 byte, SHA-256 `5EEFB1F1573BEE36D817485391AFAFD1F47D882B8865B2D3BFD96FA9CCD732FD`; đúng 8 entry allowlist và manifest khớp cả file ngoài lẫn stream trong ZIP. Không có `.env`, source, workbook/ảnh khách, log/QC, exports, WAL/SHM hoặc EXE lịch sử.
  - Bất biến: database vận hành thật giữ nguyên SHA-256 `141AC02A9C2BEB2ECB0C6305DA8CCB671164B369D214B80491801ABB22E4E6CF`; listener người dùng `127.0.0.1:8765` PID `15160` không bị dừng hoặc ghi qua các bài test/phát hành. TDP-114 và nghiệm thu kỹ thuật phạm vi hợp đồng hiện tại đóng 100%.
- 2026-09-03 23:55 – bổ sung tải báo giá theo phản hồi khách hàng [x]
  - Giao diện có tải Excel nhà thầu đang chọn, tải ZIP toàn kỳ và bảng lịch sử để tải lại từng lần xác nhận. Ngày giờ lịch sử hiển thị theo `dd/mm/yyyy lúc HH:mm`.
  - Backend khóa file bằng đúng kỳ + `version_id`; ZIP chỉ gồm các XLSX tách riêng từng nhà thầu. Không có workbook tổng trộn giá; xung đột mã chặn tải và đơn giá theo ngày chỉ được kèm khi batch thuộc đúng kỳ.
  - Test tập trung `15/15`, full regression `375/375`, QC UTF-8 `ok=true`; browser smoke Edge/CDP trên database tạm đạt tải Excel Toyota/ATV, tải ZIP toàn bộ và không lẫn giá. Listener test đã dừng, thư mục test đã chuyển vào Thùng rác; listener EXE người dùng ở `8765` không bị tác động.
  - Chưa build lại EXE/ZIP theo yêu cầu chủ dự án. Artifact phát hành 13:52 là bản trước cập nhật giao diện này và không được gửi như bản có tính năng mới.
- 2026-09-04 – tách riêng giao diện Công nợ theo phản hồi khách hàng [x]
  - Thanh bên tách thành hai mục độc lập `Báo cáo` và `Công nợ`. Màn Công nợ mặc định chỉ có ba lựa chọn gọn: phải thu theo bếp, phải thu tổng hợp và phải trả; bảng/biểu mẫu chi tiết chỉ render sau khi chọn mục.
  - Nghiệp vụ cũ được giữ nguyên và phân đúng nơi: lọc/xuất/lịch sử từng bếp; tổng hợp nhà thầu/ghi nhận thu/lịch sử thu; lọc NCC/phân bổ từng dòng/thanh toán/hoàn tác/nạp file/xuất phải trả. Số dư đầu kỳ và điều chỉnh nằm trong vùng mở thêm.
  - Bộ tải bất đồng bộ được giới hạn theo mục đang mở để không tải cả ba sổ cùng lúc và tránh màn hình nặng/giật. Cache source cập nhật `app.js?v=20260904-21`, `real.css?v=20260904-8`; QC khóa contract giao diện mới.
  - Test: static UI `11/11`; full regression `377/377` trong `161.757s`; QC UTF-8 `ok=true`. Browser Edge/CDP trên database tạm đạt trọn luồng phải thu và phải trả, gồm màn tổng quan ba lựa chọn, lọc, persisted filters, lịch sử, phân bổ, thanh toán, reversal và stale-revision guard. Listener/profile/database tạm đã dừng và dọn; cổng người dùng `8765` không bị tác động.
  - Chỉ cập nhật source và tài liệu; chưa build lại EXE/ZIP.

## 13. Goal prompt lịch sử – không dùng lại cho đợt đính chính hiện hành

Khối dưới đây được giữ để truy vết cách Goal A ban đầu đã chạy. Nó không còn là prompt đúng cho đợt đính chính hiện hành vì BK/NXT đã được mở khóa và TDP-114 phải build lại sau khi source hoàn tất:

```text
/goal Thực hiện Goal A trong BIG_PLAN_TDP.md để tạo source candidate đã kiểm chứng. Phạm vi tự động gồm TDP-000 đến TDP-092 và TDP-110 đến TDP-113; không thực hiện TDP-100, TDP-114 hoặc TDP-115. Trước tiên đọc lại README-new.md và các nguồn bắt buộc được Big Plan chỉ ra. Sau TDP-000/001/002, bắt buộc chạy Làn ưu tiên khẩn hóa đơn–khớp mã–kho tháng 08/2026 ở đầu mục 8 trước khi quay lại TDP-010. Tuân thủ tuyệt đối vai trò từng nguồn, ranh giới an toàn, dependency, quyết định còn mở và Definition of Done Goal A. Mỗi lần chỉ để một task ở trạng thái đang làm; hoàn thành implementation, test, tự review và ghi bằng chứng vào Nhật ký hoàn thành rồi tự tiếp tục sang task đủ điều kiện kế tiếp trong một lượt mới, không chờ người dùng gõ “tiếp”. Điều tra nguồn local trước khi hỏi; không tự suy đoán Q-xxx. Nếu một task bị chặn bởi đầu vào bên ngoài, đánh `[!]`, ghi bằng chứng và tiếp tục task độc lập khác. Không commit/push/deploy/build EXE, không ghi database thật và không gọi write API production. Chỉ dừng khi đạt Definition of Done Goal A, bị chặn toàn bộ, cần quyền mới, hoặc chủ dự án pause Goal.
```

## 14. Kết quả tự audit Big Plan ngày 02/09/2026

- Đã kiểm chứng 9 artifact chính được kế hoạch viện dẫn đều tồn tại: `Em Thành.xlsx`, workbook ngày, báo giá Toyota, Word yêu cầu, file công nợ lịch sử và bốn mẫu thuế.
- Hash/kích thước của `Đơn hàng 01.09.2026.xlsx` và `BÁO GIÁ TOYOTA T09-2026.xlsx` khớp đúng số đã ghi trong `README-new.md`.
- Baseline thực chạy: 97/97 unit test đạt, QC `ok=true`, source `/health` xanh và integrity database `ok`.
- Dependency audit sau yêu cầu mới: 55 task có ID duy nhất, không tham chiếu task không tồn tại và không còn dependency ngược thứ tự; toàn bộ Q được viện dẫn đều có định nghĩa.
- Đã sửa lỗi phân quyền nguồn: file ngày chỉ chốt contract input; `Em Thành.xlsx` chốt biểu mẫu; Toyota chốt output báo giá; ảnh locator không được dùng làm golden.
- Đã sửa nguồn nghiệp vụ `bảng kê tổng/biên nhận`: đây là chứng từ thu mua từ dòng mua/BK + người bán/CCCD, không phải sổ phải thu. Bảng kê/chứng từ gửi khách theo hóa đơn đỏ được tách thành TDP-088.
- Đã bổ sung xử lý an toàn các sheet tham chiếu trong workbook ngày, ranh giới live API/commit/deploy, giới hạn module monolith và điều kiện renderer visual.
- Đã tách Goal A (source candidate) khỏi hosting/build/in thật để Goal có điều kiện dừng đạt được và không mắc kẹt chờ quyền bên ngoài.
- Đã ghi nhận tin nhắn 10:56–10:59: bổ sung TDP-069/TDP-074, bắt Goal chạy trước lát hóa đơn đầu vào + đầu ra theo khoảng ngày, khớp mã và reconcile tháng 08/2026 trên fixture/bản sao; Q-011 cô lập phần nguồn live chưa rõ.
- Kết luận: Big Plan đủ điều kiện dùng để khởi động Goal A; các Q còn lại đã được cô lập và không cho phép Goal tự suy đoán.

## 15. Đợt sửa giao diện theo `em Thành.docx` ngày 04/09/2026

#### [x] TDP-117 – Giao diện tổng quan bốn việc và file cuối cùng là bản chuẩn

- Màn đầu đổi thành `Công việc hằng ngày`, có `Từ ngày – Đến ngày` và đúng bốn lựa chọn khách ghi trong Word.
- Thêm nhanh một dòng kế thừa bếp/nhà thầu/ngày, chỉ nhập tên hàng, số lượng và đơn vị tính.
- File cuối ngày hợp lệ tự cập nhật cả hai phạm vi và tự chốt; validation, transaction rollback, stale/superseded guard vẫn giữ nguyên.

#### [x] TDP-118 – Thu gọn các màn nghiệp vụ, không mất chức năng

- Đặt NCC thành danh sách dọc một cột; không đưa các dòng hàng ra màn ngoài. `Sao chép ảnh` tự ghi nhận `Đã đặt`, có `Mở lại` để sửa.
- Phiếu giao chỉ hiện tổng ngày và tải toàn bộ; chi tiết ẩn theo yêu cầu.
- Báo giá còn hai lối vào tổng/chi tiết; báo cáo tổng hợp còn một thẻ; công nợ mở đầu bằng ba nhóm độc lập.
- Kho hóa đơn đổi tên giao diện thành `Báo cáo vật tư hàng hóa`, ngoài màn chỉ có khoảng ngày và bộ tải TĐK–Nhập–Xuất–NXT.
- Bảng kê & hóa đơn ngoài màn chỉ giữ phân loại được/chưa được xuất, file 13 cột và bảng kê hóa đơn đỏ; xử lý sâu nằm trong vùng mở thêm.

#### [x] TDP-119 – In lại theo thời gian và từng bếp

- Bootstrap cung cấp danh sách phiếu giao theo từng batch/bếp mà không thay đổi dữ liệu.
- Endpoint tải giấy tờ đã chọn nhận danh sách ngày và, riêng phiếu giao, danh sách bếp; ZIP chỉ chứa đúng lựa chọn, chặn ID/bếp không thuộc phạm vi.
- Màn `In giấy tờ` mặc định là đơn đi giao, cho chọn tất cả hoặc từng bếp trong `Từ ngày – Đến ngày`. Luồng in thẳng Windows cũ được giữ trong vùng mở thêm.

#### [x] TDP-120 – Kiểm chứng candidate trước khi build

- Test tập trung `31/31`; full regression `384/384`, không lỗi và không skip.
- QC cuối `ok=true`; gate `customerCompactUiContract` xác nhận bốn việc, summary-first, chọn từng phiếu giao và thẩm quyền file cuối cùng.
- Chrome/CDP thật trên database/profile tạm đạt 1440×1000 và 1024×900; không tràn ngang, không nút bị cắt, không runtime exception. Đã thực hiện thật `Sao chép ảnh → Đã đặt` và bỏ chọn riêng một phiếu giao.
- Source `/health` xanh trên cổng tạm; static syntax, Python compile và `git diff --check` đạt (chỉ còn cảnh báo LF→CRLF đã biết).
- Không build EXE/ZIP. Chỉ build sau khi chủ dự án xem source và xác nhận bản giao diện này.

#### [x] TDP-121 – Build và smoke EXE một file ngày 04/09/2026

- Chủ dự án đã xác nhận source và yêu cầu build. `BUILD_SINGLE_EXE.ps1` dùng thư mục phát hành mới `BAN_GIAO_TDP_MOT_FILE_20260904`, không ghi đè artifact 03/09; metadata đổi thành `2026.09.04.0`.
- Artifact cuối `Thanh_Dat_Phat.exe` có kích thước `90.744.705` byte và SHA-256 `24AF1C0D17193729602FF0C3CF6525DFF0483F7A0671AE96CA0D3EBA0C97A136`; thư mục bàn giao có đúng một file.
- Archive onefile chứa đúng static mới, seed SQLite đã backup/integrity-check, mẫu thuế, công cụ in và cấu hình connector được lọc. Build log chỉ hiện tên biến; không in giá trị bí mật.
- Thêm khóa QA cô lập để có thể smoke EXE mới trong lúc EXE cũ vẫn chạy: chỉ cho phép khi có cờ `--smoke-test-instance`, ID hợp lệ, cổng riêng khác 8765 và cả data/DB/export đều là đường dẫn con Windows Temp. Production vẫn dùng mutex `Local\\ThanhDatPhatDesktopApplication` như cũ.
- Chính EXE cuối chạy tại `127.0.0.1:18804` trên database tạm: health/database/schema/integrity xanh; browser smoke giao diện khách đạt 1440px và 1024px, không runtime error/tràn/cắt nút, thao tác copy ảnh tự đặt và chọn từng phiếu giao đều đạt.
- Regression cuối sau thay đổi QA: `385/385`, không lỗi/không skip; QC cuối `ok=true`. Cổng smoke/Chrome đã đóng; EXE cũ cổng 8765 không bị tác động.

#### [x] TDP-122 – Tổng lượng/tổng tiền và mẫu công nợ phải trả 14 cột

- Bổ sung tổng lượng/tổng tiền tại các vùng nghiệp vụ có số lượng hàng; phải thu/phải trả có tổng theo kỳ và tổng theo bộ lọc, bảng tồn có tổng từng cột Nhập–Xuất–Tồn, hóa đơn có tổng từng bảng dòng.
- Thu gọn Excel phải trả thành một sheet duy nhất, đúng 14 cột khách cung cấp và có dòng tổng tĩnh. Không xuất cột kỹ thuật hoặc các sheet audit cho khách; lịch sử thanh toán/phân bổ/revision vẫn giữ trong database và giao diện chi tiết.
- Dòng nguồn đã hoàn tác không xuất vào mẫu khách nhưng vẫn được kiểm tra đối soát trước khi tạo file. Không build EXE trong task này.
- Full regression cuối `386/386`; QC `ok=true`; Chrome/CDP đạt giao diện thật ở 1440px và 1024px trên bản sao database; source health/database/schema/integrity đều xanh.

#### [x] TDP-123 – Căn chỉnh lại Giấy biên nhận theo phản hồi khách

- Giữ nguyên golden về nội dung pháp lý, màu chữ, bảng năm cột, dữ liệu mua/BK, tổng tiền bằng chữ và giới hạn 5 triệu/người/ngày; chỉ sửa lớp trình bày.
- Căn thẳng khối định danh người bán, thống nhất Times New Roman 12 cho bảng hàng, tăng chiều cao dòng và căn số liệu theo đúng loại cột.
- Ghép địa điểm/ngày ký thành một dòng hoàn chỉnh ở phía bên bán; chia cân hai vùng ký và căn giữa tên người bán dưới chữ ký.
- Microsoft Excel COM đã render candidate dữ liệu giả thành PDF A4 một trang và kiểm tra trực quan đạt. Full regression `386/386`; QC UTF-8 `ok=true`. Không build lại EXE.

#### [x] TDP-124 – Phiếu giao dùng hết khổ giấy và chia trang cân đối

- Xác nhận `Phiếu mua hàng (1).pdf` khách gửi thực chất là phiếu giao hàng 32 dòng, dùng làm ca đối chiếu bố cục.
- Bản Excel phiếu giao đổi sang A4 dọc căn giữa, lề đều, bảng đen trắng dùng hết chiều ngang; bỏ conditional formatting nội bộ khỏi chứng từ gửi khách.
- Giữ ngày góc phải, Tên hàng–SL–ĐVT gần nhau, chữ hàng hóa lớn và đều dòng; trang tiếp theo lặp tiêu đề cột.
- Thêm phân trang cân bằng theo số dòng. Ca 32 dòng có page break cố định sau dòng 16, trang cuối giữ đủ bốn vùng ký dạng Excel native; giá vẫn chỉ hiện đúng cặp `NHUAHP/NHUAHAIPHONG`.

#### [x] TDP-125 – Khớp lại phần đầu và vùng ký Phiếu giao theo ảnh mẫu cuối

- Tách `PHIẾU GIAO HÀNG`, `(Kiêm phiếu xuất kho)` và ngày thành ba dòng căn giữa; không đặt ngày cùng dòng với phụ đề.
- In đậm ba dòng thông tin nhà cung cấp, cho địa chỉ dài xuống dòng an toàn và bổ sung `Hình thức thanh toán: TM/CK` trước bảng.
- Tên hàng dài tự tăng chiều cao; bốn chú thích `(Ký và ghi rõ họ tên)` nằm thẳng dưới đúng bốn chức danh, không chèn ảnh.
- Excel COM đã render candidate thành PDF hai trang và kiểm tra trực quan đạt. Không build lại EXE.

#### [x] TDP-126 – Rà soát cuối toàn bộ biểu mẫu in/kết xuất ngày 04/09/2026

- Dựng lại 18 bộ PDF, tổng cộng 44 trang, bằng Microsoft Excel/Word từ đúng mã nguồn hiện tại; xem ảnh tổng quan toàn bộ và soi riêng các biểu mẫu chính ở kích thước thật.
- Sửa cột `STT` bị kéo rộng ở bảng kê đầu ra, khôi phục vùng gộp `TỔNG` ba cột trong bảng lương, bỏ ô viền trống ở phần số dư phải thu và tự chọn A4 dọc cho bảng ít cột để chữ lớn/cân trang hơn.
- Chuẩn hóa trường thời gian sửa cuối trong gói Office của hồ sơ suất ăn BOT; cùng dữ liệu/ngày lập nay luôn sinh cùng nội dung và SHA-256, kể cả khi hai lần lưu đi qua ranh giới một giây.
- Kiểm thử biểu mẫu trọng điểm `50/50`; full regression `391/391`; QC UTF-8 `ok=true`.
- Bộ đối chiếu được gom tại `KIEM_TRA_CUOI_BIEU_MAU_20260904`, gồm 18 PDF, 11 ảnh tổng quan 44 trang, báo cáo và SHA-256. Không build lại EXE.

#### [x] TDP-127 – Chốt kho tháng và tự chuyển tồn đầu kỳ

- Bổ sung preview/chốt/mở lại theo đúng tháng lịch trên sổ kho chuẩn. Tồn đầu tháng sau được materialize từ tồn cuối tháng trước theo cả số lượng và giá trị bình quân, thay trọn snapshot cũ và không cộng chồng.
- Chốt chỉ chạy sau khi tháng kết thúc, khi không có mã âm/cảnh báo valuation và chưa chốt tiếp kỳ sau. Source/target hash ngăn ghi trên preview cũ; phát sinh tháng sau được rebuild kiểm tra trong cùng giao dịch.
- Chốt lặp không nhân đôi. `Mở lại` xóa snapshot kế tiếp để cho phép nạp/sửa chứng từ lùi tháng; sau khi làm lại phải chốt lại, và không được mở ngược chuỗi khi kỳ sau đã đóng.
- Giao diện dùng ngôn từ vận hành, hiện tổng lượng/tổng tiền và cảnh báo thay tồn đầu rõ ràng. Có schema trạng thái/audit riêng; ledger hóa đơn vẫn bất biến. Chỉ sửa source, chưa build EXE.
- Kiểm chứng cuối: test mới `8/8`, full regression `399/399`, QC UTF-8 `ok=true`; Chrome/CDP trên database tạm thao tác chốt thật và đạt responsive 1440px/1024px. Không ghi database khách và không build EXE.
