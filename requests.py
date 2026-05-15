"""
Minimal requests-compatible shim using Python built-in urllib.
Provides Session, Response and get() as used by this addon.
"""
import urllib.request
import urllib.error
import http.cookiejar
import json as _json
import gzip as _gzip
import ssl as _ssl


_ssl_ctx = _ssl.create_default_context()


class Response:
    def __init__(self, status_code, content, headers=None):
        self.status_code = status_code
        self.content = content
        self._headers = headers or {}

    @property
    def text(self):
        enc = 'utf-8'
        ct = (self._headers.get('Content-Type')
              or self._headers.get('content-type') or '')
        if 'charset=' in ct:
            enc = ct.split('charset=')[-1].split(';')[0].strip()
        return self.content.decode(enc, errors='replace')


class _Cookies:
    def __init__(self):
        self._jar = http.cookiejar.CookieJar()

    def __getstate__(self):
        return {'cookies': list(self._jar)}

    def __setstate__(self, state):
        self._jar = http.cookiejar.CookieJar()
        for c in state.get('cookies', []):
            self._jar.set_cookie(c)

    def update(self, other):
        try:
            src = other._jar if hasattr(other, '_jar') else other
            for c in src:
                self._jar.set_cookie(c)
        except Exception:
            pass

    def clear(self):
        self._jar.clear()

    def __iter__(self):
        return iter(self._jar)


def _read_response(resp):
    raw = resp.read()
    enc = resp.info().get('Content-Encoding', '')
    if enc == 'gzip':
        raw = _gzip.decompress(raw)
    return raw, dict(resp.info())


class Session:
    def __init__(self):
        self.cookies = _Cookies()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=_ssl_ctx),
            urllib.request.HTTPCookieProcessor(self.cookies._jar),
        )

    def _request(self, url, data=None, headers=None):
        req = urllib.request.Request(url, data=data, headers=headers or {})
        try:
            resp = self._opener.open(req)
            raw, hdrs = _read_response(resp)
            return Response(resp.status, raw, hdrs)
        except urllib.error.HTTPError as e:
            raw = e.read()
            return Response(e.code, raw, dict(e.headers))

    def get(self, url, headers=None):
        return self._request(url, headers=headers)

    def post(self, url, json=None, data=None, headers=None):
        hdrs = dict(headers or {})
        if json is not None:
            body = _json.dumps(json).encode('utf-8')
            hdrs['Content-Type'] = 'application/json; charset=utf-8'
        elif data is not None:
            body = data.encode('utf-8') if isinstance(data, str) else data
        else:
            body = b''
        return self._request(url, data=body, headers=hdrs)


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        resp = urllib.request.urlopen(req, context=_ssl_ctx)
        raw, hdrs = _read_response(resp)
        return Response(resp.status, raw, hdrs)
    except urllib.error.HTTPError as e:
        return Response(e.code, e.read(), dict(e.headers))
