"""Vercel serverless function: hosted phone lookup.

Stateless twin of app/phone.PhoneLookup for the deployed site — offline
(phonenumbers), no API keys, no file writes. History is local-only.
Entry point: Vercel Python runtime uses the ``handler`` class.
"""

import json
import pathlib
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.phone import PhoneLookup  # noqa: E402


def _send(resp, code, body):
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    resp.send_response(code)
    resp.send_header("Content-Type", "application/json; charset=utf-8")
    resp.send_header("Content-Length", str(len(payload)))
    resp.end_headers()
    resp.wfile.write(payload)


class handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/api/phone":
            qs = parse_qs(parsed.query)
            num = (qs.get("num") or [""])[0].strip()
            if not num:
                _send(self, 400, {"error": "Provide a phone number in the 'num' parameter."})
                return
            web = (qs.get("web") or ["0"])[0] in ("1", "true", "yes", "on")
            data = PhoneLookup().lookup(num)
            if web:
                data = dict(data)
                data["web"] = PhoneLookup().web_search(num)
            _send(self, 200, data)
            return
        _send(self, 404, {"error": "Not found"})

    def do_POST(self):
        _send(self, 404, {"error": "Not found"})