"""R01: web resources via Tavily. Only returned pages are shown; search text never contains learner data; failures say 'unavailable'."""

from __future__ import annotations

import pytest

from app import db as dbm
from app.config import settings
from app.engines import resources
from .test_api import client, login  # noqa: F401


class FakeResp:
    def __init__(self, results, status=200):
        self._r, self.status_code = results, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return {"results": self._r}


RESULTS = [
    {"title": "SQL LEFT JOIN - GeeksforGeeks", "url": "https://www.geeksforgeeks.org/sql/sql-left-join", "content": "<b>LEFT JOIN</b> returns all rows from the left table...  " * 20},
    {"title": "Tutorial video", "url": "https://www.youtube.com/watch?v=abc", "content": "A video walk-through."},
    {"title": "SQLite docs: SELECT", "url": "https://www.sqlite.org/lang_select.html", "content": "The SELECT statement."},
    {"title": "Evil site", "url": "https://evil.example.com/join", "content": "not an allowed site"},
    {"title": "Plain http", "url": "http://www.w3schools.com/sql/sql_join.asp", "content": "http is refused"},
    {"title": "javascript", "url": "javascript:alert(1)", "content": "refused"},
    {"title": "Duplicate", "url": "https://www.geeksforgeeks.org/sql/sql-left-join", "content": "same url twice"},
]


@pytest.fixture()
def tav(client, monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-key-not-real")
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        return FakeResp(RESULTS)
    monkeypatch.setattr(resources.httpx, "post", fake_post)
    h = login(client)
    return client, h, calls


def test_only_safe_returned_pages_are_shown_docs_first(tav):
    client, h, calls = tav
    r = client.get("/api/resources/sql_outer_join", headers=h).json()
    assert r["status"] == "ok"
    urls = [i["url"] for i in r["items"]]
    assert urls == ["https://www.sqlite.org/lang_select.html", "https://www.geeksforgeeks.org/sql/sql-left-join", "https://www.youtube.com/watch?v=abc"]
    assert [i["kind"] for i in r["items"]] == ["docs", "article", "video"]
    assert all(len(i["snippet"]) <= 220 and "<" not in i["snippet"] for i in r["items"])
    assert "not reviewed" in r["label"] or "has not reviewed" in r["label"]


def test_search_text_has_no_learner_data_and_uses_the_key_as_a_header(tav):
    client, h, calls = tav
    me = client.get("/api/me", headers=h).json()
    client.get("/api/resources/sql_outer_join", headers=h)
    sent = str(calls[0]["json"])
    assert me["id"] not in sent and me["name"] not in sent
    assert "test-key-not-real" not in sent and calls[0]["headers"]["Authorization"] == "Bearer test-key-not-real"
    assert calls[0]["json"]["include_domains"] == resources.ALLOWED_DOMAINS


def test_results_are_cached_and_language_changes_the_search(tav):
    client, h, calls = tav
    client.get("/api/resources/sql_outer_join", headers=h)
    client.get("/api/resources/sql_outer_join", headers=h)
    assert len(calls) == 1                                         # second view comes from the cache
    client.patch("/api/me", headers=h, json={"language": "hindi"})
    client.get("/api/resources/sql_outer_join", headers=h)
    assert len(calls) == 2 and "Hindi" in calls[1]["json"]["query"]


def test_failures_say_unavailable_and_never_invent(client, monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-key-not-real")
    h = login(client)

    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(resources.httpx, "post", boom)
    r = client.get("/api/resources/sql_select", headers=h).json()
    assert r["status"] == "unavailable" and r["items"] == []
    monkeypatch.setattr(settings, "tavily_api_key", "")
    r = client.get("/api/resources/sql_filtering", headers=h).json()
    assert r["status"] == "disabled" and r["items"] == []


def test_unknown_concept_and_sign_in_required(tav):
    client, h, _ = tav
    assert client.get("/api/resources/not_a_concept", headers=h).status_code == 404
    assert client.get("/api/resources/sql_select").status_code == 401


def test_old_cache_survives_a_failed_refresh(tav, monkeypatch):
    client, h, calls = tav
    client.get("/api/resources/sql_outer_join", headers=h)
    from datetime import timedelta
    from app.models import now
    from app.models_ext.R01 import WebResourceCache
    with dbm.SessionLocal() as s:
        row = s.get(WebResourceCache, ("sql_outer_join", "en"))
        row.fetched_at = now() - timedelta(days=30)
        s.commit()

    def boom(*a, **k):
        raise RuntimeError("quota")
    monkeypatch.setattr(resources.httpx, "post", boom)
    r = client.get("/api/resources/sql_outer_join", headers=h).json()
    assert r["status"] == "ok" and len(r["items"]) == 3


def test_menu_text_is_not_shown_as_a_preview():
    junk = "+ SELECT Query2 min read + INSERT INTO4 min read + UPDATE2 min read + DELETE3 min read + WHERE2 min read"
    assert resources._snippet(junk) == ""
    assert resources._snippet("short") == ""
    ok = resources._snippet("The `LEFT JOIN` keyword returns all records from the left table, and the matched records from the right table.")
    assert "`" not in ok and ok.startswith("The LEFT JOIN keyword returns all records")
