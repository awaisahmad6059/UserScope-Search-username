"""UserScope engine runner.

Runs the UserScope search engine on a background thread and publishes
live progress to the dashboard through a small thread-safe state object.
No external service or paid API is involved.
"""

import os
import pathlib
import threading
import time
from collections import deque

from userscope import engine
from userscope.__init__ import __version__
from userscope.notify import QueryNotify
from userscope.result import QueryStatus
from userscope.sites import SitesInformation

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESOURCES = ROOT / "userscope" / "resources" / "data.json"
RESULTS_DIR = ROOT / "results"

STATUS_KEYS = ("claimed", "available", "unknown", "illegal", "waf")


class _LiveNotifier(QueryNotify):
    """QueryNotify implementation that pushes each result to a callback."""

    def __init__(self, callback):
        super().__init__()
        self._cb = callback

    def update(self, result):
        self._cb(result)

    def finish(self, message=None):
        pass


class UserScopeRunner:
    """Thread-safe runner exposing live scan state for the dashboard."""

    def __init__(self):
        self._lock = threading.RLock()
        self._run = None

    def is_busy(self):
        with self._lock:
            return bool(self._run) and self._run["state"] == "running"

    def site_count(self, include_nsfw=False):
        sites = SitesInformation(str(RESOURCES), honor_exclusions=False)
        if not include_nsfw:
            sites.remove_nsfw_sites()
        return len(sites.sites)

    def site_names(self, include_nsfw=False):
        """Sorted, display-ready list of every available platform name."""
        sites = SitesInformation(str(RESOURCES), honor_exclusions=False)
        if not include_nsfw:
            sites.remove_nsfw_sites()
        return sorted(sites.sites.keys())

    def _filter_platforms(self, site_data, sites):
        """Restrict site_data to the requested platform names (case-insensitive)."""
        if not sites:
            return site_data, None
        wanted = [s.strip() for s in sites if s and s.strip()]
        lower_map = {name.lower(): name for name in site_data}
        unknown = [w for w in wanted if w.lower() not in lower_map]
        if unknown:
            return None, "Unknown platform(s): %s. Type names exactly as in the suggestions (case doesn't matter)." % ", ".join(unknown)
        filtered = {}
        for w in wanted:
            key = lower_map[w.lower()]
            filtered[key] = site_data[key]
        return filtered, None

    def start(self, username, include_nsfw=True, timeout=30, sites=None):
        with self._lock:
            if self.is_busy():
                return False, "A search is already running. Stop or wait for it to finish."
            if not username or not username.strip():
                return False, "Username is required."
            username = username.strip()
            if len(username) > 64:
                return False, "Username is too long (max 64 characters)."
            if not any(c.isalnum() for c in username):
                return False, "Username must contain at least one letter or number."

            sites_info = SitesInformation(str(RESOURCES), honor_exclusions=False)
            if not include_nsfw:
                sites_info.remove_nsfw_sites()
            site_data = {name: site.information for name, site in sites_info.sites.items()}
            scope = None
            if sites:
                site_data, err = self._filter_platforms(site_data, sites)
                if err:
                    return False, err
                scope = ", ".join(sorted(site_data.keys()))
            if not site_data:
                return False, "No platforms selected."

            run = {
                "state": "running",
                "username": username,
                "nsfw": include_nsfw,
                "timeout": int(timeout),
                "scope": scope,
                "started_at": time.time(),
                "finished_at": None,
                "elapsed": 0.0,
                "total": len(site_data),
                "checked": 0,
                "counts": {k: 0 for k in STATUS_KEYS},
                "results": {},
                "feed": deque(maxlen=12),
                "error": None,
                "cancelled": False,
            }
            self._run = run

        thread = threading.Thread(
            target=self._work,
            args=(username, site_data, run, int(timeout)),
            daemon=True,
        )
        thread.start()
        return True, "Search started."

    def _work(self, username, site_data, run, timeout):
        def push(result):
            st = result.status.value.lower()
            key = st if st in STATUS_KEYS else "unknown"
            with self._lock:
                run["counts"][key] += 1
                run["checked"] += 1
                run["feed"].append(
                    {
                        "site": result.site_name,
                        "status": st,
                        "time_ms": None
                        if result.query_time is None
                        else round(result.query_time * 1000),
                    }
                )

        notifier = _LiveNotifier(push)
        try:
            result_map = engine.search(username, site_data, notifier, timeout=timeout)
            with self._lock:
                final = {}
                for name, meta in result_map.items():
                    qr = meta.get("status")
                    final[name] = {
                        "url_main": meta.get("url_main", ""),
                        "url_user": meta.get("url_user", ""),
                        "http_status": meta.get("http_status"),
                        "status": qr.status.value.lower() if qr else "unknown",
                        "context": qr.context if qr else None,
                        "time_ms": None
                        if qr is None or qr.query_time is None
                        else round(qr.query_time * 1000),
                    }
                run["results"] = final
        except Exception as exc:
            with self._lock:
                run["error"] = "%s: %s" % (type(exc).__name__, exc)
        finally:
            with self._lock:
                run["state"] = "finished"
                run["finished_at"] = time.time()
                run["elapsed"] = round(run["finished_at"] - run["started_at"], 2)
                counts = {"claimed": 0, "available": 0, "unknown": 0, "illegal": 0, "waf": 0}
                for name, meta in run["results"].items():
                    key = meta["status"] if meta["status"] in counts else "unknown"
                    counts[key] += 1
                run["counts"] = counts
                run["checked"] = len(run["results"])
            self._save(run)

    def cancel(self):
        with self._lock:
            if self._run and self._run["state"] == "running":
                self._run["cancelled"] = True
                if self._run["error"] is None:
                    self._run["error"] = "Cancelled by user. Current batch finishes, then scan stops."
                return True
        return False

    def status(self):
        with self._lock:
            if not self._run:
                return {
                    "running": False,
                    "state": "idle",
                    "finished": False,
                    "username": None,
                    "scope": None,
                    "total": 0,
                    "checked": 0,
                    "counts": {k: 0 for k in STATUS_KEYS},
                    "results": {},
                    "feed": [],
                    "elapsed": 0.0,
                    "error": None,
                    "cancelled": False,
                    "engine_version": __version__,
                }
            run = self._run
            return {
                "running": run["state"] == "running",
                "state": run["state"],
                "finished": run["state"] == "finished",
                "username": run["username"],
                "scope": run.get("scope"),
                "nsfw": run["nsfw"],
                "timeout": run["timeout"],
                "total": run["total"],
                "checked": run["checked"],
                "counts": dict(run["counts"]),
                "results": run["results"],
                "feed": list(run["feed"]),
                "elapsed": round(run["elapsed"] if run["finished_at"] else (time.time() - run["started_at"]), 2),
                "error": run["error"],
                "cancelled": run.get("cancelled", False),
                "engine_version": __version__,
            }

    def _save(self, run):
        """Persist the completed report next to the results folder."""
        try:
            safe = "".join(c for c in (run["username"] or "result") if c.isalnum() or c in "._-") or "result"
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            status = self.status()
            (RESULTS_DIR / (safe + ".json")).write_text(json_dumps(status), encoding="utf-8")
            lines = ["site,url_main,url_user,status,http_status,context"]
            for name, m in sorted(run["results"].items()):
                lines.append(_csv_escape(name, m))
            (RESULTS_DIR / (safe + ".csv")).write_text("\n".join(lines), encoding="utf-8")
            (RESULTS_DIR / (safe + ".txt")).write_text(_human_report(status), encoding="utf-8")
        except Exception as exc:
            run["error"] = "Report write failed: %s" % exc

    def export(self, file_format, username=None):
        """Return (ok, filename, mime, payload) for the last scan's report."""
        with self._lock:
            run = self._run
            if not run:
                return False, None, "text/plain", "No results yet."
            user = (username or run["username"] or "results").strip()
        safe = "".join(c for c in user if c.isalnum() or c in "._-") or "result"
        path = RESULTS_DIR / ("%s.%s" % (safe, file_format if file_format != "txt" else "txt"))
        path.parent.mkdir(parents=True, exist_ok=True)

        if file_format == "json":
            payload = json_dumps(self.status())
            mime = "application/json"
            ext = "json"
        elif file_format == "csv":
            lines = ["site,url_main,url_user,status,http_status,context"]
            with self._lock:
                res = dict(self._run["results"]) if self._run else {}
            for name, m in sorted(res.items()):
                lines.append(_csv_escape(name, m))
            payload = "\n".join(lines)
            mime = "text/csv"
            ext = "csv"
        else:
            with self._lock:
                st = self._run
            payload = _human_report(st)
            mime = "text/plain"
            ext = "txt"
        return True, (user + "." + ext), mime, payload


def json_dumps(obj):
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2)


def _csv_escape(name, meta):
    def esc(v):
        s = "" if v is None else str(v)
        return '"%s"' % s.replace('"', '""') if any(c in s for c in ',"\n') else s

    return ",".join(
        [esc(name), esc(meta.get("url_main")), esc(meta.get("url_user")),
         esc(meta.get("status")), esc(meta.get("http_status")), esc(meta.get("context"))]
    )


def _human_report(run):
    if not run:
        return "No results yet."
    lines = []
    lines.append("UserScope report for username: %s" % run.get("username"))
    lines.append("Engine: %s | Sites checked: %d/%d | Duration: %.1fs" % (
        run.get("engine_version", "?"), run.get("checked", 0), run.get("total", 0), run.get("elapsed", 0.0)))
    lines.append("Found: %d | Available: %d | Unknown: %d | Blocked: %d | Illegal: %d" % (
        run["counts"]["claimed"], run["counts"]["available"], run["counts"]["unknown"],
        run["counts"]["waf"], run["counts"]["illegal"]))
    lines.append("-" * 60)
    for name, m in sorted(run.get("results", {}).items(), key=lambda kv: kv[1].get("status", "")):
        lines.append("[%s] %s -> %s" % (m.get("status", "?").upper(), name, m.get("url_user") or m.get("url_main") or "-"))
    return "\n".join(lines)