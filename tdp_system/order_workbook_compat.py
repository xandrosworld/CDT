"""Narrow compatibility fix for WPS whole-row sort ranges on uploaded orders.

Only expands the sort range syntax in the temporary upload. Cell XML, cached
formula results, filters and every other ZIP member stay byte-for-byte intact.
The customer's source file is never modified.
"""
import io
import re
import zipfile


def compatible_order_bytes(payload: bytes) -> bytes:
    replacements = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in archive.namelist():
            if not re.fullmatch(r'xl/worksheets/[^/]+\.xml', name):
                continue
            original = archive.read(name)

            def expand_tag(match):
                tag = match.group(0)
                def expand_ref(ref):
                    first, last = int(ref[2]), int(ref[3])
                    if not 1 <= first <= last <= 1048576:
                        return ref[0]
                    return b'ref=' + ref[1] + f'A{first}:XFD{last}'.encode() + ref[1]
                return re.sub(rb'\bref=([\"\'])\$?(\d+):\$?(\d+)\1', expand_ref, tag)

            fixed = re.sub(rb'<(?:[A-Za-z_][\w.-]*:)?sortState\b[^>]*>', expand_tag, original)
            if fixed != original:
                replacements[name] = fixed
        if not replacements:
            return payload
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as target:
            target.comment = archive.comment
            for entry in archive.infolist():
                target.writestr(entry, replacements.get(entry.filename, archive.read(entry.filename)))
        return output.getvalue()
