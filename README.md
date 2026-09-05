# CDT – Hệ thống vận hành Thành Đạt Phát

> Mốc source trước khi chuyển sang Railway, ngày 05/09/2026: xem
> [README-new-2.md](README-new-2.md), đặc biệt mục 13.11–13.12, để biết kết quả
> kiểm chứng và các lỗi còn mở. Lỗi ngày hóa đơn lịch sử 257/266 đã được sửa và
> kiểm tra bằng EXE trên bản sao DB thật. Chưa nghiệm thu toàn bộ đầu vào–đầu ra.
> Chủ dự án đã chọn chuyển sang web Railway thay cho bàn giao EXE; repo hiện
> chưa được xác nhận sẵn sàng triển khai Railway. Mô tả module desktop bên dưới
> là lịch sử; phạm vi mới ở README-new-2.md được ưu tiên.

Ứng dụng Flask/SQLite chạy tại Windows hoặc trong mạng LAN, gồm nhập đơn Excel, đặt NCC sau khi trừ tồn, phiếu giao, kho sổ sách, công nợ, mSMI, dự thảo hóa đơn đầu ra, xưởng cơm/PO, chấm công/lương và luồng duyệt-in.

Danh mục tên xuất hóa đơn và bếp → XCOM (xưởng cơm) hỗ trợ nạp Excel theo hai bước xem trước/xác nhận, ghép theo mã hoặc tên duy nhất, chặn toàn bộ file khi còn lỗi và nhập lại không tạo bản ghi trùng.

Kho sổ sách hỗ trợ nạp Excel tồn đầu kỳ theo hai bước xem trước/xác nhận. Các dòng cùng mã TĐP được gộp trước khi ghi; số lượng âm và cột thành tiền sổ sách được giữ nguyên; mã mới chỉ được tạo sau khi người dùng xác nhận và không tự suy đoán nhà cung cấp.

Module xưởng cơm nhận trực tiếp file menu/cost của khách: tách bếp/ca, số thực đơn, suất/thực đơn, tổng suất, định lượng, nguyên liệu, giá suất ăn và XCOM; ưu tiên số lượng cần đã chốt trong file, tự tính lại thành tiền/cost từ chi tiết, cho xem trước trước khi ghi và cập nhật đúng kế hoạch khi nạp lại. PO được gộp theo XCOM, ghi rõ trạng thái nháp/đã duyệt và không cho duyệt kế hoạch khi thiếu XCOM, giá suất ăn hoặc giá nguyên liệu.

File chấm suất ăn tháng được nạp riêng theo ngày/bếp/ca để đối chiếu số thực ăn; dữ liệu này không tự thay đổi số suất đặt ban đầu dùng để sinh PO. Công nợ có bộ lọc nhiều kỳ, điều chỉnh có lịch sử và file Excel riêng; chấm công/lương có nhập phát sinh thủ công, khoản điều chỉnh tháng và file bảng lương.

## Chạy source

```powershell
cd tdp_system
python -m pip install -r requirements.txt
$env:PYTHONIOENCODING='utf-8'
python server.py
```

Mở `http://127.0.0.1:8765`. Chạy QC bằng:

```powershell
$env:PYTHONIOENCODING='utf-8'
python tdp_system\qc_system.py
```

## Dữ liệu và bí mật

Repo lưu source, tài liệu, kiểm thử và bốn mẫu trình bày đã bỏ dữ liệu giao dịch. `.env`, SQLite, danh mục CCCD, file Excel/Word/PDF khách hàng, bản build và log đều bị loại khỏi Git. Máy triển khai cần được cấp riêng file danh mục, dữ liệu và cấu hình API. Mốc Git là bản khôi phục mã nguồn, không thay thế sao lưu DB vận hành.

Các thao tác mSMI là chỉ đọc; đồng bộ dùng tối đa 199 hóa đơn/trang theo giới hạn production và tạo phiếu nhập có chống trùng. Hóa đơn đầu ra chỉ tạo dự thảo và giữ tồn; người dùng vẫn phải kiểm tra, ký và phát hành bên ngoài rồi mới xác nhận trong hệ thống để ghi xuất kho. Dự thảo hủy sẽ nhả tồn. In hàng loạt luôn có bước duyệt.
