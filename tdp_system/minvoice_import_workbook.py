"""Keep the customer's accepted OPC package rather than resaving it with openpyxl.

The reported importer error is reproduced by opening XLSX in an editable,
fixed-size .NET stream. Re-serializing openpyxl's package can expand that
stream and fail on dispose.
This writer preserves the accepted styles, relationships and package metadata;
only cell data, shared strings and the used range are replaced.
"""
from pathlib import Path
from io import BytesIO
from xml.sax.saxutils import escape
from xml.sax.saxutils import quoteattr
import re
import zipfile

TEMPLATE = Path(__file__).resolve().parent / 'templates' / 'minvoice_import.xlsx'
NAMESPACE = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
# Styles of the accepted customer's row 2, A:M. No style is synthesized.
STYLES = (2,2,3,4,5,1,1,1,1,1,1,1,0)


def build_import_package(values, *, sheet_name='8'):
    strings=[]; indices={}; count=0; rows=[]
    for rownum, row in enumerate(values,1):
        if len(row)!=13:raise ValueError('Bảng nhập M-Invoice phải có đúng 13 cột.')
        cells=[]
        for col,value in enumerate(row):
            ref=chr(65+col)+str(rownum)
            style=(1 if col in (4,5,6,7,8,10,11) else 0) if rownum==1 else STYLES[col]
            attrs=f' r="{ref}"'+(f' s="{style}"' if style else '')
            if value is None or value=='':
                cells.append(f'<c{attrs}/>');continue
            if isinstance(value,str):
                if value not in indices:indices[value]=len(strings);strings.append(value)
                count+=1
                cells.append(f'<c{attrs} t="s"><v>{indices[value]}</v></c>')
            else:
                cells.append(f'<c{attrs}><v>{value}</v></c>')
        rows.append(f'<row r="{rownum}"'+(' ht="18"' if rownum>1 else '')+' spans="1:13">'+''.join(cells)+'</row>')
    shared=('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<sst xmlns="{NAMESPACE}" count="{count}" uniqueCount="{len(strings)}">'+
        ''.join('<si><t xml:space="preserve">'+escape(s)+'</t></si>' for s in strings)+'</sst>').encode('utf-8')
    output=BytesIO()
    with zipfile.ZipFile(TEMPLATE) as source, zipfile.ZipFile(output,'w') as target:
        for entry in source.infolist():
            data=source.read(entry.filename)
            if entry.filename=='xl/sharedStrings.xml':data=shared
            elif entry.filename=='xl/workbook.xml':
                data=re.sub(r'<sheet name="[^"]*"',lambda _: '<sheet name='+quoteattr(sheet_name),data.decode('utf-8')).encode('utf-8')
            elif entry.filename=='xl/worksheets/sheet1.xml':
                xml=data.decode('utf-8')
                xml=re.sub(r'<sheetData>.*?</sheetData>',lambda _: '<sheetData>'+''.join(rows)+'</sheetData>',xml,flags=re.S)
                xml=re.sub(r'<dimension ref="[^"]*"/>',f'<dimension ref="A1:M{len(values)}"/>',xml)
                data=xml.encode('utf-8')
            # Fast DEFLATE is standard XLSX packaging. It leaves space for the
            # importer's canonical XML rewrite without arbitrary padding or
            # changes to any invoice values. Level 6 reproduces the exception.
            target.writestr(entry,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=1)
    return output.getvalue()


def compatible_archive(data):
    """Repair historical download bytes without changing receipts or orders."""
    from openpyxl import load_workbook
    try:
        from .invoice_tax_export import INVOICE_HEADERS
    except ImportError:
        from invoice_tax_export import INVOICE_HEADERS
    output=BytesIO(); changed=False
    with zipfile.ZipFile(TEMPLATE) as template:
        accepted_styles=template.read('xl/styles.xml')
    with zipfile.ZipFile(BytesIO(data)) as source, zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as target:
        for entry in source.infolist():
            payload=source.read(entry.filename)
            if entry.filename.startswith('Bang_ke_') and entry.filename.endswith('.xlsx'):
                with zipfile.ZipFile(BytesIO(payload)) as existing:
                    if 'xl/sharedStrings.xml' in existing.namelist() and existing.read('xl/styles.xml')==accepted_styles:
                        target.writestr(entry,payload)
                        continue
                workbook=load_workbook(BytesIO(payload),read_only=True,data_only=True,keep_links=False)
                try:
                    if len(workbook.worksheets)==1:
                        sheet=workbook.active
                        rows=list(sheet.values)
                        if rows and tuple(rows[0])==INVOICE_HEADERS:
                            payload=build_import_package(rows,sheet_name=sheet.title)
                            changed=True
                finally:workbook.close()
            target.writestr(entry,payload)
    return output.getvalue() if changed else data
