"""Tests for the phone lookup module and its API (offline, no network)."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from app.phone import PhoneLookup


@pytest.fixture()
def dashboard():
    from app.server import Dashboard

    d = Dashboard(host="127.0.0.1", port=0)
    thread = threading.Thread(target=d.httpd.serve_forever, daemon=True)
    thread.start()
    yield d
    d.httpd.shutdown()
    d.httpd.server_close()


def get(dashboard, path):
    url = "http://127.0.0.1:%d%s" % (dashboard.port, path)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_lookup_valid_indian_number():
    data = PhoneLookup().lookup("+919876543210")
    assert data["ok"] is True
    assert data["valid"] is True
    assert data["country_code"] == 91
    assert data["region"] == "IN"
    assert data["formats"]["e164"] == "+919876543210"


def test_lookup_invalid_input_is_safe():
    data = PhoneLookup().lookup("hello world")
    assert data["ok"] is True
    assert data["valid"] is False
    assert data["possible"] is False
    assert "error" in data


def test_lookup_empty():
    assert PhoneLookup().lookup("  ")["valid"] is False


def test_formats_are_present_for_valid_number():
    data = PhoneLookup().lookup("+12025550101")
    assert data["valid"] is True
    assert data["formats"]["e164"] == "+12025550101"
    assert data["region"] == "US"
    assert data["national_significant"] == "2025550101"


def test_api_phone_valid(dashboard):
    status, body = get(dashboard, "/api/phone?num=%2B919876543210")
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is True
    assert data["valid"] is True
    assert data["region"] == "IN"


def test_api_phone_invalid_number(dashboard):
    status, body = get(dashboard, "/api/phone?num=xyz")
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is True
    assert data["valid"] is False


def test_api_phone_missing_num(dashboard):
    status, body = get(dashboard, "/api/phone")
    assert status == 400
    assert "error" in json.loads(body)


def post(dashboard, path):
    url = "http://127.0.0.1:%d%s" % (dashboard.port, path)
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_history_saved_and_cleared(dashboard):
    get(dashboard, "/api/phone?num=%2B12025550101")
    status, body = get(dashboard, "/api/phone/history")
    items = json.loads(body)["items"]
    assert len(items) >= 1
    assert items[0]["formats"]["e164"] == "+12025550101"

    status, _ = post(dashboard, "/api/phone/history/clear")
    assert status == 200
    _, body = get(dashboard, "/api/phone/history")
    assert json.loads(body)["items"] == []