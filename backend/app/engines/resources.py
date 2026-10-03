"""R01: real learning resources for a concept, found on the web with Tavily and cached.

Rules:
- Only pages Tavily actually returned are ever shown. Nothing is generated or invented. No key or a failed search means "unavailable".
- The search is built from the concept name only, never from anything about the learner.
- Results are limited to https pages on well-known learning sites, and cached for two weeks, so a page view never waits on a search.
- They are labelled as found on the web and not reviewed by SAARTHI.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import timedelta
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..content import get_content
from ..models import now
from ..models_ext.R01 import WebResourceCache

log = logging.getLogger("saarthi.resources")

TAVILY_URL = "https://api.tavily.com/search"
CACHE_DAYS = 14
MAX_ITEMS = 5

# Well-known learning sites. Official documentation first, then free tutorial sites, then video.
ALLOWED_DOMAINS = [
    "docs.python.org", "sqlite.org", "postgresql.org", "dev.mysql.com", "developer.mozilla.org", "fastapi.tiangolo.com",
    "docs.docker.com", "git-scm.com", "realpython.com", "w3schools.com", "geeksforgeeks.org", "freecodecamp.org",
    "tutorialspoint.com", "sqlbolt.com", "khanacademy.org", "youtube.com", "youtu.be",
]
DOCS = {"docs.python.org", "sqlite.org", "postgresql.org", "dev.mysql.com", "developer.mozilla.org", "fastapi.tiangolo.com", "docs.docker.com", "git-scm.com"}
VIDEO = {"youtube.com", "youtu.be"}


def configured() -> bool:
    return bool((settings.tavily_api_key or "").strip())


def _bucket(language: Optional[str]) -> str:
    return "hi" if language in ("hindi", "hinglish") else "en"


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _allowed(url: str) -> bool:
    if not url.startswith("https://"):
        return False
    d = _domain(url)
    return any(d == a or d.endswith("." + a) for a in ALLOWED_DOMAINS)


def _kind(domain: str) -> str:
    if any(domain == v or domain.endswith("." + v) for v in VIDEO):
        return "video"
    if any(domain == d or domain.endswith("." + d) for d in DOCS):
        return "docs"
    return "article"


def _clean(text: str, n: int) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return (t[: n - 1].rstrip() + "…") if len(t) > n else t


def _snippet(text: str) -> str:
    """A short readable preview. Page text that is really a menu ("+ SELECT 2 min read + INSERT ...") or markup is dropped, not shown."""
    t = str(text or "").replace("\\_", "_").replace("`", "").replace("#", " ").replace("*", " ")
    t = re.sub(r"\s+", " ", t).strip()
    if len(re.findall(r"min read", t)) >= 2 or t.count(" + ") >= 3 or t.startswith("+") or len(t) < 25:
        return ""
    return t[:219].rstrip() + "…" if len(t) > 220 else t


def _query(concept_id: str, bucket: str) -> str:
    c = get_content().concepts[concept_id]
    q = f"{c.name} {c.domain} tutorial for beginners"
    return q + (" in Hindi" if bucket == "hi" else "")


def _search(concept_id: str, bucket: str) -> list[dict[str, Any]]:
    r = httpx.post(
        TAVILY_URL,
        json={"query": _query(concept_id, bucket), "search_depth": "basic", "max_results": 10, "include_answer": False,
              "include_images": False, "include_domains": ALLOWED_DOMAINS},
        headers={"Authorization": f"Bearer {settings.tavily_api_key.strip()}"},
        timeout=25,
    )
    r.raise_for_status()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for x in r.json().get("results", []):
        url = str(x.get("url") or "")
        if not _allowed(url) or url in seen:
            continue
        seen.add(url)
        d = _domain(url)
        title = _clean(str(x.get("title") or ""), 110)
        if not title:
            continue
        out.append({"title": title, "url": url, "domain": d, "kind": _kind(d), "snippet": _snippet(_clean(str(x.get("content") or ""), 400))})
    # official docs first, then articles, then videos; Tavily's own order is kept inside each group
    rank = {"docs": 0, "article": 1, "video": 2}
    out.sort(key=lambda i: rank[i["kind"]])
    return out[:MAX_ITEMS]


def needs_search(db: Session, concept_id: str, language: Optional[str]) -> bool:
    """True when showing this concept's resources would mean a live Tavily search (no fresh cache). Used to rate-limit searches only."""
    if not configured() or concept_id not in get_content().concepts:
        return False
    row = db.get(WebResourceCache, (concept_id, _bucket(language)))
    return row is None or (now() - row.fetched_at) >= timedelta(days=CACHE_DAYS)


def _tidy(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**i, "snippet": _snippet(i.get("snippet", ""))} for i in items]


def for_concept(db: Session, concept_id: str, language: Optional[str], refresh: bool = False) -> dict[str, Any]:
    """{"status": "ok" | "unavailable" | "disabled", "items": [...], "fetched_at": ...}. Never raises for a search problem."""
    if concept_id not in get_content().concepts:
        return {"status": "unavailable", "items": [], "fetched_at": None}
    bucket = _bucket(language)
    row = db.get(WebResourceCache, (concept_id, bucket))
    fresh = row is not None and (now() - row.fetched_at) < timedelta(days=CACHE_DAYS)
    if row is not None and row.items and (fresh or not configured()):
        return {"status": "ok", "items": _tidy(row.items), "fetched_at": row.fetched_at.isoformat(timespec="minutes")}
    if not configured():
        return {"status": "disabled", "items": [], "fetched_at": None}
    if fresh and not refresh:       # a fresh but empty result is remembered too, so a quiet topic is not searched again and again
        return {"status": "ok", "items": [], "fetched_at": row.fetched_at.isoformat(timespec="minutes")}
    try:
        items = _search(concept_id, bucket)
    except Exception as e:       # network, quota, bad key: say unavailable, keep any older cache
        log.warning("Tavily search failed for %s (%s): %s", concept_id, bucket, type(e).__name__)
        if row is not None and row.items:
            return {"status": "ok", "items": _tidy(row.items), "fetched_at": row.fetched_at.isoformat(timespec="minutes")}
        return {"status": "unavailable", "items": [], "fetched_at": None}
    if row is None:
        try:
            with db.begin_nested():     # two requests may fetch the same concept at once: the second one just keeps the first one's row
                db.add(WebResourceCache(concept_id=concept_id, lang_bucket=bucket, items=items, fetched_at=now()))
                db.flush()
        except IntegrityError:
            pass
        row = db.get(WebResourceCache, (concept_id, bucket))
    else:
        row.items, row.fetched_at = items, now()
    db.flush()
    return {"status": "ok", "items": _tidy(items), "fetched_at": row.fetched_at.isoformat(timespec="minutes")}
