"""Vercel serverless function: hosted lite username scan.

Not a replacement for the local app. Serverless functions cannot run the
full 462-site live scan (time limits, no threads-across-requests), so this
runs the same engine synchronously against a small, curated set of sites.

Default set is popular platforms with stable public probes. Guests hit the
datacenter IP, so bot-protected sites (WAF) will often report Blocked —
that's expected and honest.
"""

import json
import pathlib
import sys
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from userscope import engine  # noqa: E402
from userscope.notify import QueryNotify  # noqa: E402
from userscope.sites import SitesInformation  # noqa: E402

RESOURCES = ROOT / "userscope" / "resources" / "data.json"
MAX_SITES = 12
DEFAULT_SITES = [
    "Instagram", "GitHub", "YouTube", "Twitter", "TikTok", "Reddit",
    "Telegram", "Pinterest", "Twitch", "Patreon", "Steam", "Wattpad",
]

STATUS_KEYS = ("claimed", "available", "unknown", "illegal", "waf")


class _Collect(QueryNotify):
    def update(self, result):
        pass

    def finish(self, message=None):
        pass


def _serialize(result_map):
    results = {}
    counts = {k: 0 for k in STATUS_KEYS}
    for name, meta in result_map.items():
        qr = meta.get("status")
        st = qr.status.value.lower() if qr else "unknown"
        key = st if st in counts else "unknown"
        counts[key] += 1
        results[name] = {
            "url_main": meta.get("url_main", ""),
            "url_user": meta.get("url_user", ""),
            "http_status": meta.get("http_status"),
            "status": st,
            "context": qr.context if qr else None,
            "time_ms": None if qr is None or qr.query_time is None else round(qr.query_time * 1000),
        }
    return results, counts


def _scan(username, include_nsfw, sites, timeout):
    sites_info = SitesInformation(str(RESOURCES), honor_exclusions=False)
    if not include_nsfw:
        sites_info.remove_nsfw_sites()
    site_data = {name: site.information for name, site in sites_info.sites.items()}

    if sites:
        lower = {name.lower(): name for name in site_data}
        wanted = [lower[s.lower()] for s in sites if s.lower() in lower]
        if wanted:
            site_data = {name: site_data[name] for name in wanted}
    site_data = dict(list(site_data.items())[:MAX_SITES])

    started = time.time()
    result_map = engine.search(username, site_data, _Collect(), timeout=timeout)
    results, counts = _serialize(result_map)
    return {
        "running": False,
        "state": "finished",
        "finished": True,
        "username": username,
        "scope": ", ".join(sorted(results.keys())),
        "nsfw": include_nsfw,
        "timeout": timeout,
        "total": len(site_data),
        "checked": len(results),
        "counts": counts,
        "results": results,
        "feed": [],
        "elapsed": round(time.time() - started, 2),
        "error": None,
        "cancelled": False,
        "engine_version": "hosted-lite",
        "lite": True,
    }


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
        if path != "/api/hostscan":
            _send(self, 404, {"error": "Not found"})
            return
        qs = parse_qs(parsed.query)
        username = (qs.get("username") or [""])[0].strip()
        if not username:
            _send(self, 400, {"error": "Username is required."})
            return
        if not any(c.isalnum() for c in username):
            _send(self, 400, {"error": "Username must contain at least one letter or number."})
            return
        nsfw = (qs.get("nsfw") or ["0"])[0] in ("1", "true", "yes", "on")
        raw_sites = [s.strip() for s in (qs.get("sites") or [""])[0].split(",") if s.strip()]
        sites = raw_sites or DEFAULT_SITES
        timeout = 3
        try:
            timeout = max(1, min(3, int((qs.get("timeout") or ["3"])[0])))
        except ValueError:
            pass
        try:
            payload = _scan(username, nsfw, sites, timeout)
            _send(self, 200, payload)
        except Exception as exc:  # noqa: BLE001  (surface as JSON to the UI)
            _send(self, 500, {"error": "%s: %s" % (type(exc).__name__, exc)})

    do_POST = do_GET