"""Serve only content-addressed worksheet code with reusable, precompressed bytes."""
import re
from pathlib import Path

from flask import request, send_from_directory


def register(app, static_dir):
    directory = Path(static_dir) / 'worksheet-bundle'

    @app.get('/static/worksheet-bundle/<filename>')
    def worksheet_asset(filename):
        versioned = bool(re.fullmatch(r'worksheet-[0-9a-f]{16}\.js', filename))
        encoded = versioned and request.accept_encodings['gzip'] > 0 and (directory / (filename + '.gz')).is_file()
        response = send_from_directory(directory, filename + '.gz' if encoded else filename,
                                       conditional=False,
                                       **({'mimetype': 'text/javascript'} if versioned else {}))
        if versioned and response.status_code == 200:
            # Internal flag, never inferred from a client-controlled header.
            response._tdp_versioned_asset = True
            response.headers['Cache-Control'] = 'private, max-age=31536000, immutable'
            response.vary.add('Accept-Encoding')
            if encoded:
                response.headers['Content-Encoding'] = 'gzip'
        return response
