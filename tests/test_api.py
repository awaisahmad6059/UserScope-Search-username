"""Integration tests for the dashboard HTTP API (end-to-end, no network)."""

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

import userscope.engine as engine_mod
from tests.test_runner import fake_search


@pytest.fixture()
def dashboard(monkeypatch):
    from app.server import Dashboard

    monkeypatch.setattr(engine_mod, "search", fake_search)
    d = Dashboard(host="127.0.0.1", port=0)
    thread = threading.Thread(target=d.httpd.serve_forever, daemon=True)
    thread.start()
    yield d
    d.httpd.shutdown()
    d.httpd.server_close()


def _request(dashboard, path, method="GET"):
    url = "http://127.0.0.1:%d%s" % (dashboard.port, path)
    req = urllib.request.Request(url, data=b"" if method == "POST" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read()


def get(dashboard, path):
    return _request(dashboard, path, "GET")


def post(dashboard, path):
    return _request(dashboard, path, "POST")


def wait_finished(dashboard, timeout=10):
    deadline = time.time() + timeout
    while True:
        _, _, body = get(dashboard, "/api/status")
        st = json.loads(body)
        if st["state"] == "finished":
            return st
        assert time.time() < deadline, "run did not finish in time"
        time.sleep(0.03)


def test_health(dashboard):
    status, ctype, body = get(dashboard, "/api/health")
    assert status == 200
    assert "json" in ctype
    data = json.loads(body)
    assert data["ok"] is True
    assert data["sites"] > 300
    assert data["engine_version"]


def test_status_idle(dashboard):
    status, _, body = get(dashboard, "/api/status")
    assert status == 200
    data = json.loads(body)
    assert data["state"] == "idle"
    assert data["results"] == {}


def test_search_and_live_flow(dashboard):
    status, _, body = post(dashboard, "/api/search?username=neo&nsfw=0&timeout=15")
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is True

    st = wait_finished(dashboard)
    assert st["username"] == "neo"
    assert st["total"] == st["checked"] == len(st["results"])
    assert st["counts"]["claimed"] > 0
    assert st["counts"]["available"] > 0


def test_api_rejects_missing_username(dashboard):
    status, _, body = post(dashboard, "/api/search?nsfw=0")
    assert status == 409
    assert json.loads(body)["ok"] is False


def test_search_with_platform_filter(dashboard):
    status, _, body = post(dashboard, "/api/search?username=neo&nsfw=0&timeout=15&sites=Instagram")
    assert status == 200
    assert json.loads(body)["ok"] is True
    st = wait_finished(dashboard)
    assert st["total"] == 1
    assert list(st["results"].keys()) == ["Instagram"]


def test_search_unknown_platform_rejected(dashboard):
    status, _, body = post(dashboard, "/api/search?username=neo&sites=Facebook")
    assert status == 409
    assert json.loads(body)["ok"] is False


def test_export_format_validation(dashboard):
    status, _, _ = get(dashboard, "/api/export?format=xml")
    assert status == 400


def test_export_csv_flow(dashboard):
    post(dashboard, "/api/search?username=trinity&nsfw=0&timeout=15")
    wait_finished(dashboard)
    status, ctype, body = get(dashboard, "/api/export?format=csv&username=trinity")
    assert status == 200
    assert "text/csv" in ctype
    assert body.startswith(b"site,url_main")


def test_unknown_route(dashboard):
    status, _, _ = get(dashboard, "/api/nope")
    assert status == 404


def test_ui_root_serves_dashboard(dashboard):
    status, ctype, body = get(dashboard, "/ui/")
    assert status == 200
    assert "text/html" in ctype
    assert b"UserScope" in body


def test_static_assets(dashboard):
    status, ctype, _ = get(dashboard, "/ui/style.css")
    assert status == 200 and "text/css" in ctype
    status, ctype, _ = get(dashboard, "/ui/app.js")
    assert status == 200 and "javascript" in ctype