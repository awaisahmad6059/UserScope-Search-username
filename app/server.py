"""UserScope dashboard server.

A dependency-free local dashboard (http.server) that exposes the scan
engine through a small JSON API and serves the web UI. Bound to
127.0.0.1 only, so it is never reachable from outside the machine.
"""

import argparse
import json
import pathlib
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runner import UserScopeRunner
from app.phone import PhoneLookup

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4545

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml; charset=utf-8",
    ".ico": "image/x-icon",
    ".csv": "text/csv; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    runner = None
    phone = None
    site_total = 0

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def log_message(self, fmt, *args):
        pass

    # ---- routes -----------------------------------------------------------

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._send(302, b"", "text/plain", {"Location": "/ui/"})
            return
        if path == "/ui":
            self._send(302, b"", "text/plain", {"Location": "/ui/"})
            return
        if path == "/api/health":
            self._json(200, {"ok": True, "engine_version": self.server.brand["version"], "sites": self.server.brand["sites"]})
            return
        if path == "/api/status":
            self._json(200, self.runner.status())
            return
        if path == "/api/phone":
            qs = urllib.parse.parse_qs(parsed.query)
            num = (qs.get("num") or [""])[0]
            web = (qs.get("web") or ["0"])[0] in ("1", "true", "yes", "on")
            if not num.strip():
                self._json(400, {"error": "Provide a phone number in the 'num' parameter."})
                return
            data = self.phone.lookup(num)
            if web:
                data = dict(data)
                data["web"] = self.phone.web_search(num)
            self.phone.add_history(data)
            self._json(200, data)
            return
        if path == "/api/phone/history":
            self._json(200, {"items": self.phone.history()})
            return
        if path == "/api/export":
            qs = urllib.parse.parse_qs(parsed.query)
            fmt = (qs.get("format") or ["txt"])[0]
            username = (qs.get("username") or [None])[0]
            if fmt not in ("json", "csv", "txt"):
                self._json(400, {"error": "Unsupported format. Use json, csv or txt."})
                return
            ok, fname, mime, payload = self.runner.export(fmt, username)
            if not ok:
                self._json(404, {"error": payload})
                return
            extra = {"Content-Disposition": 'attachment; filename="%s"' % fname}
            self._send(200, payload, mime, extra)
            return

        ui_root = ROOT / "app" / "ui"
        if path.startswith("/ui/"):
            rel = path[len("/ui/"):]
            if not rel:
                rel = "index.html"
            candidate = (ui_root / rel).resolve()
            if candidate.is_relative_to(ui_root) and candidate.is_file():
                ctype = MIME.get(candidate.suffix.lower(), "application/octet-stream")
                self._send(200, candidate.read_bytes(), ctype)
                return
            self._send(404, "Not found", "text/plain; charset=utf-8")
            return
        self._send(404, "Unknown route", "text/plain; charset=utf-8")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/api/search":
            qs = urllib.parse.parse_qs(parsed.query)
            username = (qs.get("username") or [""])[0]
            nsfw = (qs.get("nsfw") or ["0"])[0] in ("1", "true", "yes", "on")
            sites_raw = ((qs.get("sites") or [""])[0]).split(",")
            sites = [s.strip() for s in sites_raw if s.strip()] or None
            try:
                timeout = min(120, max(5, int((qs.get("timeout") or ["30"])[0])))
            except ValueError:
                timeout = 30
            ok, msg = self.runner.start(username, include_nsfw=nsfw, timeout=timeout, sites=sites)
            self._json(200 if ok else 409, {"ok": ok, "message": msg})
            return
        if path == "/api/cancel":
            ok = self.runner.cancel()
            self._json(200, {"ok": ok, "message": "Cancellation requested." if ok else "Nothing to cancel."})
            return
        if path == "/api/phone/history/clear":
            self.phone.clear_history()
            self._json(200, {"ok": True, "message": "History cleared."})
            return
        self._json(404, {"error": "Unknown route"})


class Dashboard:
    """Owns the runner and the HTTP server."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        import userscope  # noqa: F401  (init package anyway)

        self.runner = UserScopeRunner()
        self.site_count = self.runner.site_count(False)
        try:
            from userscope import __version__
        except Exception:
            __version__ = "0.1.0"
        _Handler.runner = self.runner
        _Handler.phone = PhoneLookup()
        self.httpd = ThreadingHTTPServer((host, port), _Handler)
        self.host, self.port = self.httpd.server_address[0:2]
        self.httpd.brand = {"version": __version__, "sites": self.site_count}
        self.httpd.daemon_threads = True

    def serve(self):
        print("")
        print("  UserScope dashboard running at:")
        print("  ->  http://%s:%d/ui/" % (self.host, self.port))
        print("  Press Ctrl+C to stop.")
        print("")
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.httpd.server_close()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def main():
    parser = argparse.ArgumentParser(description="UserScope dashboard")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    dashboard = Dashboard(args.host, args.port)
    dashboard.serve()


if __name__ == "__main__":
    main()