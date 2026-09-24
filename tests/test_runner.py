"""Tests for the UserScope runner (engine wrapped for live UI updates)."""

import threading
import time

import pytest

import app.runner as runner_mod
import userscope.engine as engine_mod
from userscope.result import QueryResult, QueryStatus

STATUS_CYCLE = [
    QueryStatus.CLAIMED,
    QueryStatus.AVAILABLE,
    QueryStatus.UNKNOWN,
    QueryStatus.WAF,
    QueryStatus.ILLEGAL,
]

GATE = None  # Optional threading.Event; blocks fake_search while searching.


def fake_search(username, site_data, notifier, **kw):
    if GATE is not None:
        GATE.wait(5)
    count = len(site_data)
    for i, name in enumerate(site_data):
        status = STATUS_CYCLE[i % len(STATUS_CYCLE)]
        notifier.update(
            QueryResult(
                username,
                name,
                "https://example.test/users/" + username,
                status,
                query_time=0.001 + i * 0.0001,
                context=None if status != QueryStatus.UNKNOWN else "timeout",
            )
        )
    notifier.finish()
    result_map = {}
    for i, name in enumerate(site_data):
        status = STATUS_CYCLE[i % len(STATUS_CYCLE)]
        result_map[name] = {
            "url_main": "https://example.test/",
            "url_user": "https://example.test/users/" + username,
            "status": QueryResult(
                username,
                name,
                "https://example.test/users/" + username,
                status,
                query_time=0.001 + i * 0.0001,
                context=None if status != QueryStatus.UNKNOWN else "timeout",
            ),
            "http_status": 200 if i % 2 == 0 else 404,
            "response_text": None,
        }
    return result_map


def wait_finished(manager, timeout=10):
    deadline = time.time() + timeout
    while manager.status()["state"] != "finished":
        assert time.time() < deadline, "run did not finish in time"
        time.sleep(0.02)


@pytest.fixture()
def runner(monkeypatch):
    monkeypatch.setattr(engine_mod, "search", fake_search)
    return runner_mod.UserScopeRunner()


def test_runner_completes_with_matching_counts(runner):
    ok, msg = runner.start("jdoe", include_nsfw=False, timeout=15)
    assert ok, msg
    wait_finished(runner)
    s = runner.status()
    assert s["state"] == "finished"
    assert s["username"] == "jdoe"
    assert s["total"] == s["checked"] == len(s["results"])
    assert sum(s["counts"].values()) == s["total"]
    assert s["counts"]["claimed"] > 0


def test_runner_rejects_bad_usernames(runner):
    assert runner.start("", include_nsfw=False)[0] is False
    assert runner.start("   ", include_nsfw=False)[0] is False
    assert runner.start("!!!%%%", include_nsfw=False)[0] is False
    assert runner.start("x" * 65, include_nsfw=False)[0] is False


def test_runner_rejects_second_concurrent_run(runner, monkeypatch):
    global GATE
    GATE = threading.Event()
    try:
        ok, _ = runner.start("first", include_nsfw=False)
        assert ok
        ok, msg = runner.start("second", include_nsfw=False)
        assert ok is False
    finally:
        GATE.set()
        GATE = None
    wait_finished(runner)


def test_cancel_is_best_effort(runner, monkeypatch):
    global GATE
    GATE = threading.Event()
    try:
        ok, _ = runner.start("user1", include_nsfw=False)
        assert ok
        assert runner.cancel() is True
    finally:
        GATE.set()
        GATE = None
    wait_finished(runner)
    assert runner.status()["cancelled"] is True


def test_runner_platform_filter_single(runner):
    ok, msg = runner.start("jdoe", include_nsfw=False, sites=["Instagram"])
    assert ok, msg
    wait_finished(runner)
    s = runner.status()
    assert s["total"] == 1
    assert s["scope"] == "Instagram"
    assert list(s["results"].keys()) == ["Instagram"]


def test_runner_platform_filter_multiple_case_insensitive(runner):
    ok, msg = runner.start("jdoe", include_nsfw=False, sites=["instagram", "GITHUB"])
    assert ok, msg
    wait_finished(runner)
    s = runner.status()
    assert s["total"] == 2
    assert set(s["results"].keys()) == {"Instagram", "GitHub"}


def test_runner_rejects_unknown_platform(runner):
    ok, msg = runner.start("jdoe", include_nsfw=False, sites=["Instagram", "Facebook"])
    assert ok is False
    assert "Unknown platform" in msg
    assert runner.status()["state"] == "idle"


def test_site_names_available(runner):
    names = runner.site_names(False)
    assert len(names) > 300
    assert "Instagram" in names
    assert "Facebook" not in names


def test_runner_export_formats_after_run(runner):
    ok, _ = runner.start("actor", include_nsfw=False)
    assert ok
    wait_finished(runner)
    for fmt in ("json", "csv", "txt"):
        ok, fname, mime, payload = runner.export(fmt)
        assert ok
        assert payload
        if fmt == "json":
            assert '"claimed"' in payload
        if fmt == "csv":
            assert payload.startswith("site,url_main")


def test_export_without_run(runner):
    ok, fname, mime, payload = runner.export("json")
    assert ok is False
    assert fname is None
    assert "No results" in payload