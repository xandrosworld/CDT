"""Combine original invoice PDF pages into a single printable copy."""
import io
from pypdf import PdfReader, PdfWriter


def combined_invoice_pdf(files, layout='pages'):
    if layout not in ('pages', 'invoice-per-sheet'):
        raise ValueError('Cách xếp hóa đơn không hợp lệ; tải lại trang rồi in lại.')
    writer = PdfWriter()
    pages = 0
    for index, (filename, content) in enumerate(files):
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted or not reader.pages:
                raise ValueError('PDF bị khóa hoặc không có trang')
            pages += len(reader.pages)
            if pages > 1000:
                raise ValueError('Bản in vượt 1.000 trang; hãy chọn kỳ nhỏ hơn')
            writer.append(reader, import_outline=False)
            # Each invoice begins on a new physical sheet when duplex printing.
            if layout == 'invoice-per-sheet' and len(reader.pages) % 2 and index < len(files)-1:
                last = writer.pages[-1]
                writer.add_blank_page(width=float(last.mediabox.width), height=float(last.mediabox.height))
        except Exception as exc:
            raise ValueError(f'Không ghép được hóa đơn {filename}: {exc}') from exc
    if not pages:
        raise ValueError('Không có hóa đơn để in')
    writer.add_metadata({'/Title': 'Hoa don trong de nghi thanh toan'})
    if layout == 'invoice-per-sheet':
        preferences = writer.create_viewer_preferences()
        preferences.duplex = '/DuplexFlipLongEdge'
    output_pages = len(writer.pages)
    result = io.BytesIO()
    writer.write(result)
    writer.close()
    return result.getvalue(), output_pages
