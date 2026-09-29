"""Disposable fixture for correcting an uploaded catalogue without re-upload."""
import os
import sys
from pathlib import Path
from openpyxl import Workbook


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ.update(TDP_DATA_DIR=str(output/'data'), TDP_DB_PATH=str(output/'test.sqlite3'),
                      TDP_EXPORT_DIR=str(output/'exports'), TDP_OFFLINE_TEST='1',
                      MSMI_API_BASE_URL='http://127.0.0.1:9', MINVOICE_API_BASE_URL='http://127.0.0.1:9')
    from . import server
    from .invoice_identity_policy import CONFIRMED_DELIVERED_NAMES
    from waitress import serve
    server.connector_config_paths = lambda: []
    server.MASTER_SOURCE = output/'no-master.xlsx'
    server.init_database(sync_master=False)
    with server.db() as conn:
        for (code,name),unit in zip(CONFIRMED_DELIVERED_NAMES.items(),['Lễ','Cốc','Bộ','Đĩa']):
            conn.execute("INSERT INTO products(code,name,unit,tax) VALUES(?,?,?,'0.08')",(code,name,unit))
            conn.execute("INSERT INTO outgoing_product_names VALUES(?,?,'2026-09-29')",(code,name))
    w=Workbook();s=w.active;s.title='danh mục hh'
    s.append(['Mã hàng','Tên Thành Đạt Phát','Tên xuất hóa đơn','ĐVT Thành Đạt Phát','ĐVT Xuất HĐ','Thuế'])
    for code,name in CONFIRMED_DELIVERED_NAMES.items():s.append([code,name,'Rau muống','Kg','Kg','8%'])
    w.save(output/'catalog-review.xlsx');w.close()
    serve(server.app,host='127.0.0.1',port=int(sys.argv[2]),threads=4)


if __name__=='__main__':main()
