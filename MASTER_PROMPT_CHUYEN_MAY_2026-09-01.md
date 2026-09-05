# MASTER PROMPT CHUYỂN MÁY – THÀNH ĐẠT PHÁT

## Câu lệnh gửi nguyên văn cho Codex ở máy mới

> Bạn đang tiếp quản toàn bộ dự án vận hành Thành Đạt Phát từ một snapshot đầy đủ. Trước khi làm gì, hãy đọc hết file `MASTER_PROMPT_CHUYEN_MAY_2026-09-01.md`, sau đó đọc `README.md`, `_HANDOFF/ULTRA_HANDOFF_LAPTOP_2026-09-01.md`, `BIEN_BAN_CHOT_YEU_CAU_DEMO_2026-08-28.md` và `tdp_system/HUONG_DAN_SU_DUNG.txt`. Kiểm tra `.env` chỉ bằng sự tồn tại và tên biến; tuyệt đối không in, log hoặc gửi giá trị bí mật. Không reset, checkout, xóa hay ghi đè các thay đổi local. Source trong snapshot là bản mới hơn EXE hiện có. Hãy chạy 97 unit test, chạy `tdp_system/qc_system.py`, mở local bằng source và kiểm tra `/health`. Báo ngắn trạng thái tiếp quản rồi tiếp tục đúng từ trạng thái trong file này; không bắt người dùng kể lại dự án từ đầu.

## 1. Phạm vi và bảo mật

- Dự án: hệ thống vận hành cho **CÔNG TY TNHH THỰC PHẨM THÀNH ĐẠT PHÁT**.
- Snapshot chứa toàn bộ source, `.git`, `.env` thật, SQLite thật, file Excel/Word/PDF của khách, bản build/EXE, tài liệu nghiệp vụ, transcript và test.
- `.env` chứa token/tài khoản/cấu hình thật. Không được hiển thị nội dung, đưa vào log, commit Git hoặc upload công khai.
- Gói backup chỉ dùng để chuyển giữa các máy thuộc quyền kiểm soát của chủ dự án. Không gửi cho khách hoặc bên thứ ba.
- Git nền: nhánh `main`, commit `17a1d9f65524ba022ccd91d47af67c4a37a74996`. Snapshot có thay đổi local quan trọng mới hơn commit này; snapshot mới là nguồn tiếp quản, không được reset về Git.

## 2. Trạng thái hiện tại đã hoàn thành

### Đặt hàng nhà cung cấp

Luồng đã chốt và đã triển khai:

1. Tải file đặt NCC 13 cột.
2. Người dùng tự kiểm tra hàng thật trong tủ/kho, tự sửa `Tồn tủ đã trừ`, `Số lượng đặt NCC`, `NCC`, `Giá mua`, `Ghi chú`.
3. Nạp lại file tại màn `Đặt hàng NCC`.
4. Hệ thống xem trước, báo lỗi, sau đó người dùng mới xác nhận ghi dữ liệu.
5. Việc nạp file không được sửa số lượng khách đặt, giá bán, doanh thu hoặc công nợ phải thu.
6. Công nợ phải trả NCC dùng `Số lượng đặt NCC thực tế × Giá mua đã chốt`.
7. Kho hóa đơn/sổ sách không tự trừ vào đơn mua NCC. Tồn tủ vật lý do người dùng tự nhìn và nhập trong file.

File xuất có 13 cột ổn định:

`Mã dòng hệ thống, Mã hàng, Mã bếp, Ngày, Tên hàng, Nhu cầu từ đơn khách, Tồn tủ đã trừ, Số lượng đặt NCC, ĐVT, NCC, Giá mua, Thành tiền, Ghi chú`.

Giá mua:

- Giá đã có từ bảng báo giá/đơn gốc được ưu tiên và không bị file lần hai ghi đè.
- Nếu giá ban đầu trống hoặc bằng 0 thì lấy giá người dùng nhập trong file đặt hàng lần hai.
- Dòng có số lượng mua ngoài phải có giá mua lớn hơn 0.
- NCC `Kho` là hàng nội bộ, được phép giá 0 và không sinh công nợ phải trả NCC.

Quy tắc dồn:

- Dung, Thu, Tân, Phượng, Kỳ và Kho: dồn các dòng có **tên hàng giống nhau**.
- Hoài: chỉ dồn mặt hàng **Cà rốt**.
- Không tự mở rộng sang Hương hoặc NCC khác.
- Dồn chỉ là cách trình bày/gửi NCC; các dòng đơn gốc vẫn được giữ để truy vết.

### Hóa đơn đầu vào và đầu ra nhiều đợt

- Sau đồng bộ mSMI/tạo phiếu nhập, hệ thống tính lại theo từng dòng:
  - Tổng khách đã chốt.
  - Đã nằm trong dự thảo/đã xuất.
  - Có thể lập hóa đơn ngay theo tồn hóa đơn hiện có.
  - Còn chờ hóa đơn đầu vào.
- Cho phép lập và phát hành nhiều vòng cho cùng một batch/nhà thầu.
- Ví dụ đã test: có 4 thì xuất 4; nhập thêm 6 sau 5 ngày thì lập vòng hai cho 6 còn lại.
- Không được giữ tồn quá mức, không được xuất trùng và không được tự ký/phát hành hóa đơn.
- mSMI vẫn là luồng đọc/đồng bộ tăng dần, chống trùng. Người dùng phải ghép mã rồi mới tạo phiếu nhập.

### In

- File Excel đặt NCC 13 cột vẫn giữ nguyên để nạp lại.
- Khi đưa vào bộ PDF in, hệ thống bỏ sheet hướng dẫn và rút thành tối đa 10 cột cần thiết để không làm hỏng luồng A5/A4.
- Máy in nghiệm thu: `Canon Generic Plus UFR II`, thiết bị `LBP242/243`, cổng `IP_192.168.1.190`.
- A4: Drawer 1, duplex long edge.
- A5: Multi-purpose Tray, giấy đặt ngang nhưng khai báo `A5` (không phải A5R), simplex.

## 3. Những file source mới nhất cần giữ

- `tdp_system/contract_modules.py`: schema/migration, round-trip đặt NCC, giá mua, quy tắc dồn, công nợ NCC, readiness hóa đơn, nhiều vòng xuất.
- `tdp_system/server.py`: xuất file đặt NCC 13 cột và liên kết nghiệp vụ.
- `tdp_system/print_bundle.py`: bản in rút gọn từ workbook 13 cột.
- `tdp_system/static/app.js`: giao diện ba bước đặt NCC và bảng `xuất được/còn thiếu`.
- `tdp_system/static/index.html`, `tdp_system/static/real.css`: input/upload, layout và cache frontend bản mới.
- `tdp_system/test_purchase_order_roundtrip.py`: 8 test hồi quy mới.
- `tdp_system/test_server_financial_guards.py`: kiểm tra phân bổ tồn an toàn theo từng đợt.
- `tdp_system/qc_system.py`: QC đã cập nhật theo luồng mới.

Không sửa trực tiếp EXE. `BAN_PC_TDP/TDP_Server.exe` và `dist/` là bản cũ hơn source hiện tại vì chủ dự án đã yêu cầu **chưa build lại EXE** cho tới khi sửa triệt để.

## 4. Database nguồn chuẩn

- File chuẩn: `tdp_system/data/tdp.sqlite3`.
- Tại thời điểm trước khi đóng gói: `PRAGMA integrity_check = ok`.
- Số liệu kiểm kê gần nhất:
  - 1.253 sản phẩm.
  - 1 batch, 233 dòng đơn khách.
  - 5.240 hóa đơn mSMI và 25.206 dòng hóa đơn.
  - 334 giao dịch kho.
  - 9.975 dòng công nợ phải trả lịch sử.
  - 1.697 dòng chấm suất ăn.
- Schema mới có `purchase_order_lines`, `purchase_order_imports` và `round_no` trong `outgoing_invoice_drafts`.
- Chưa có file đặt NCC lần hai nào được người dùng xác nhận vào database thật tại thời điểm snapshot (`purchase_order_imports = 0`).
- Phiên đang chọn 29/08 có 11 dòng mua ngoài chưa có giá mua; nạp nguyên file vừa tải xuống sẽ bị chặn đúng thiết kế. Người dùng phải điền giá các dòng mua ngoài rồi nạp lại. Dòng `Kho` được phép giá 0.
- Có backup trước migration tại `tdp_system/data/tdp_manual_before_purchase_roundtrip_20260901_192605.sqlite3`.

Không thay database nguồn bằng database trong `BAN_PC_TDP` hoặc `dist`. Trước mọi sửa dữ liệu thật phải dùng SQLite backup API hoặc dừng server rồi sao lưu chính xác.

## 5. Kết quả kiểm thử cuối

- `python -m unittest discover -s tdp_system -p "test_*.py"`: **97/97 đạt**.
- `python -m tdp_system.qc_system`: **QC ok=true**.
- Local source: `/health` trả `ok=true`, `database_ready=true`, `schema_ready=true`, `integrity=ok`.
- Smoke thật: xuất workbook đặt NCC 233 dòng/13 cột thành công; API readiness trả 233 dòng; preview file round-trip hoạt động và chặn đúng các giá mua còn thiếu.

## 6. Cách chạy ở máy mới

1. Giải nén toàn bộ gói vào ổ cứng cục bộ; không chạy trực tiếp bên trong ZIP.
2. Giữ nguyên `.git`, `.env`, thư mục `tdp_system/data`, `BAN_PC_TDP`, tài liệu và file ẩn.
3. Mở PowerShell tại thư mục gốc chứa file này.
4. Chỉ kiểm tra `.env` bằng `Test-Path -LiteralPath .env`; không dùng `Get-Content .env`.
5. Cài Python 3.12 và thư viện:

```powershell
python -m pip install -r tdp_system\requirements.txt
```

6. Chạy test/QC:

```powershell
$env:PYTHONUTF8='1'
python -m unittest discover -s tdp_system -p 'test_*.py'
python -m tdp_system.qc_system
```

7. Chạy source:

```powershell
python -m tdp_system.server --no-browser
```

8. Mở `http://127.0.0.1:8765`, kiểm tra `http://127.0.0.1:8765/health`.
9. Nếu giao diện còn cache cũ, nhấn `Ctrl+F5`.

## 7. API mới quan trọng

- `GET /api/export/suppliers/<batch_id>`: tải file đặt NCC.
- `POST /api/purchase-orders/import/preview`: xem trước file nạp lại (`file`, `batch_id`).
- `POST /api/purchase-orders/import/confirm`: xác nhận bằng `token`, `confirmed=true`.
- `GET /api/supplier-needs/<batch_id>`: kế hoạch mua và nhóm NCC.
- `GET /api/outgoing-invoices/readiness/<batch_id>`: tổng cần lập, đã phân bổ, xuất được và còn thiếu.
- `POST /api/outgoing-invoices/draft/<batch_id>`: lập dự thảo theo phần tồn đang có.

## 8. Ranh giới phạm vi không được tự ý mở rộng

- Trong phạm vi hiện tại: khách tự nhìn tồn tủ, tự sửa file rồi nạp lại; dồn NCC theo quy tắc trên; giá lần hai; đồng bộ hóa đơn và tính lại xuất được/còn thiếu; tạo ảnh để người dùng tự gửi Zalo.
- Ngoài phạm vi nếu khách yêu cầu: phần mềm tự quản lý kho vật lý/tủ đông xuyên ngày, tự kiểm kê nhập–xuất; tự chạy nền phát hiện và phân bổ hóa đơn; tự gửi/đọc Zalo; tự ký/phát hành hóa đơn; biểu mẫu hoàn toàn mới không có trong hồ sơ trước ký.
- Không tự động in, gửi Zalo, ký hay phát hành nếu chưa có xác nhận rõ ràng của người dùng.

## 9. Quy tắc làm việc tiếp

- Trả lời tiếng Việt, trực tiếp, ưu tiên kết quả.
- Khi được yêu cầu sửa: kiểm tra source, triển khai, thêm test hồi quy, chạy toàn bộ unit test, QC và `/health`.
- Không tuyên bố bản EXE đã cập nhật nếu chưa build/copy và kiểm tra đúng EXE.
- Không xóa hoặc ghi đè file khách, backup hay thay đổi local không liên quan.
- Không suy đoán mã hàng, CCCD, giá theo ngày, mapping hoặc dữ liệu tài chính.
- Công nợ phải thu của khách và công nợ phải trả NCC là hai nguồn khác nhau; tuyệt đối không dùng file đặt NCC lần hai để sửa đơn khách.

## 10. Điểm bắt đầu tốt nhất ở phiên mới

Sau khi test/QC/health đều xanh, mở màn `Đặt hàng NCC` và `Bảng kê & hóa đơn` để smoke giao diện. Chưa build EXE cho tới khi chủ dự án xác nhận các bug nghiệp vụ đã hết. Nếu sửa tiếp, làm trên source trong snapshot này và giữ database thật nguyên vẹn.
