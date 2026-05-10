"""Lightweight local requests shim used when 'requests' isn't installed.

This module first attempts to import the real `requests` package. If
that's not available it provides a tiny `get()` wrapper using
`urllib.request` that offers `status_code` and `json()` on the
response object. It's small but sufficient for the METAR fetches in
this project and avoids import-time errors from static analyzers.
"""
"""Small `requests.get` shim implemented with urllib.

This module intentionally does not attempt to proxy to an
installed `requests` package to avoid shadowing/import recursion when
the project also contains a `requests.py` file.
"""
import urllib.request
import json


class _SimpleResponse:
    def __init__(self, code, body_bytes):
        self.status_code = code
        self._body = body_bytes

    def json(self):
        try:
            return json.loads(self._body.decode())
        except Exception:
            return None

    @property
    def text(self):
        try:
            return self._body.decode()
        except Exception:
            return ''


def get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        code = r.getcode()
        body = r.read()
        return _SimpleResponse(code, body)
