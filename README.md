# CDT – Hệ thống vận hành Thành Đạt Phát

Ứng dụng Flask/SQLite chạy tại Windows hoặc trong mạng LAN, gồm nhập đơn Excel, đặt NCC sau khi trừ tồn, phiếu giao, kho sổ sách, công nợ, mSMI, dự thảo hóa đơn đầu ra, xưởng cơm/PO, chấm công/lương và luồng duyệt-in.

Danh mục tên xuất hóa đơn và bếp → Unit hỗ trợ nạp Excel theo hai bước xem trước/xác nhận, ghép theo mã hoặc tên duy nhất, chặn toàn bộ file khi còn lỗi và nhập lại không tạo bản ghi trùng.

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

Repo chỉ chứa source. `.env`, SQLite, file Excel/Word/PDF khách hàng, bản build và log đều bị loại khỏi Git. Máy triển khai cần được cấp riêng file danh mục, dữ liệu và cấu hình API.

Các thao tác mSMI là chỉ đọc; tạo phiếu nhập có chống trùng. Hóa đơn đầu ra chỉ tạo dự thảo và giữ tồn; người dùng vẫn phải kiểm tra, ký và phát hành. In hàng loạt luôn có bước duyệt.
