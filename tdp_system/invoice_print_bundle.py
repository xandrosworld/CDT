"""Combine original invoice PDF pages into a single printable copy."""
import io
from pypdf import PdfReader, PdfWriter


def combined_invoice_pdf(files):
    writer = PdfWriter()
    pages = 0
    for filename, content in files:
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted or not reader.pages:
                raise ValueError('PDF bị khóa hoặc không có trang')
            pages += len(reader.pages)
            if pages > 1000:
                raise ValueError('Bản in vượt 1.000 trang; hãy chọn kỳ nhỏ hơn')
            writer.append(reader, import_outline=False)
        except Exception as exc:
            raise ValueError(f'Không ghép được hóa đơn {filename}: {exc}') from exc
    if not pages:
        raise ValueError('Không có hóa đơn để in')
    writer.add_metadata({'/Title': 'Hoa don trong de nghi thanh toan'})
    result = io.BytesIO()
    writer.write(result)
    writer.close()
    return result.getvalue(), pages
