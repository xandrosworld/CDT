"""Isolated files and database for restored inventory data-entry controls."""
import os
from pathlib import Path
from openpyxl import Workbook
from waitress import serve
from .test_bk_import import BKImportTests
from . import server

folder=Path(os.environ['TDP_FIXTURE_OUTPUT'])
BKImportTests.setUpClass()
fixture=BKImportTests()
fixture.setUp()
book=Workbook();sheet=book.active;sheet.title='Ton'
sheet.append(['MÃ TĐP','TÊN TDP','Tên trên HĐ','MÃ KHO','T/Suất','ĐVT','Số lượng','Đơn giá','Thành tiền'])
sheet.append(['BK-P1','Hàng BK','Hàng BK','BK-P1','8','kg',10.5,100,1050])
book.save(folder/'opening.xlsx');book.close()
@server.app.get('/fixture/state')
def state():
    with server.db() as conn:
        return {table:[list(row) for row in conn.execute('SELECT * FROM '+table)] for table in
                ('inventory_transactions','invoice_inventory_ledger','bk_import_documents','bk_import_lines')}
(folder/'bk.xlsx').write_bytes(fixture.template_with_rows([fixture.valid_row()]))
print('INVENTORY_TOOLS_FIXTURE_READY',flush=True)
try:serve(server.app,host='127.0.0.1',port=18853,threads=4)
finally:BKImportTests.tearDownClass()
