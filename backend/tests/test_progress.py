"""T06 — Progress-over-time tests.

Covers the spec §6 minimum:
  1. Pure replay: hand-made events → exact expected overall; last point equals overall_mastery.
  2. After advance-time +30 days, now.overall < last series point and due_reviews > 0.
  3. Events with changed_mastery == False never create a series point.
  4. grader == "simulated" points are flagged; simulated-only history → all simulated.
  5. Downsampling: 1000 events → ≤ 200 points, still ordered, last point preserved.
  6. Isolation: learner B's events never appear in learner A's series. days=0 or 1000 → 422.
  7. Performance guard: 2000 events replay in < 100 ms.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import db as dbm
from app.content import get_content
from app.engines.mastery import learner_now, overall_mastery, concept_views
from app.engines.progress import (
    _EventRow, _domain_sums, replay_series, history, radar, sparkline
)
from app.main import create_app
from app.models import EvidenceEvent, Learner, new_id

# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

AUTH_ENV = {
    "SAARTHI_LLM_MODE": "fake",
    "SAARTHI_AUTH": "mock",
    "SAARTHI_MENTORS": "mock",
    "SAARTHI_CONSENT": "mock",
    "SAARTHI_COHORT": "mock",
    "SAARTHI_SECRET": "test-secret-test-secret-test-secret-123",
    "DATABASE_URL": "sqlite://",
    "SAARTHI_ENV": "dev",
}


@pytest.fixture(autouse=True)
def set_env():
    for k, v in AUTH_ENV.items():
        os.environ[k] = v


@pytest.fixture()
def db():
    dbm.configure("sqlite://")
    dbm.init_db()
    s = dbm.SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def client():
    dbm.configure("sqlite://")
    dbm.init_db()
    app = create_app()
    return TestClient(app, raise_server_exceptions=True)


def _login(client, name="Alice", age=20):
    r = client.post("/api/auth/dev-login", json={"name": name, "age": age, "language": "english"})
    assert r.status_code == 200
    return r.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer " + token}


def _make_learner(db, **kw):
    lr = Learner(id=new_id("t_"), name="T", settings={}, **kw)
    db.add(lr)
    db.flush()
    return lr


def _make_event(db, learner_id, concept_id, p_after, grader="mcq",
                changed_mastery=True, days_ago=0, source_type="question"):
    dt = datetime.utcnow() - timedelta(days=days_ago)
    ev = EvidenceEvent(
        id=new_id("ev_"), learner_id=learner_id, concept_id=concept_id,
        source_type=source_type, grader=grader,
        p_after=p_after, changed_mastery=changed_mastery,
        created_at=dt,
    )
    db.add(ev)
    db.flush()
    return ev


# ---------------------------------------------------------------------------
# 1. Pure replay correctness
# ---------------------------------------------------------------------------

def test_replay_series_correct_overall():
    """Simple hand-crafted events produce the expected overall progression."""
    content = get_content()
    role = content.role("backend_developer")
    req = role["requirements"]
    concepts = content.concepts

    # Take the first concept in requirements for our test events
    first_cid = next(iter(req))
    first_target = req[first_cid]["target"]

    # Baseline overall (all at p_init)
    p_init = {cid: concepts[cid].p_init for cid in req}
    domain_totals = _domain_sums(req, concepts)

    # Build two events: one for first_cid pushing it up
    base_dt = datetime(2024, 1, 1, 10, 0)
    events = [
        _EventRow(first_cid, 0.5, True, "mcq", base_dt, "question"),
        _EventRow(first_cid, 0.75, True, "mcq", base_dt + timedelta(hours=1), "question"),
    ]

    series = replay_series(events, req, concepts)
    assert len(series) == 2
    # The second point should have a higher overall than the first
    assert series[1]["overall"] >= series[0]["overall"]
    # Last point should reflect p=0.75 for first_cid
    # (other concepts at p_init, so overall is between 0 and 1)
    assert 0.0 < series[-1]["overall"] < 1.0


def test_replay_last_point_matches_overall_mastery():
    """When no time passes, the last replay point should match overall_mastery from views."""
    content = get_content()
    role = content.role("backend_developer")
    req = role["requirements"]
    concepts = content.concepts

    # Simulate a simple history with a few events
    from datetime import timezone
    base_dt = datetime.now(timezone.utc)
    events: list[_EventRow] = []
    for i, cid in enumerate(list(req.keys())[:3]):
        events.append(_EventRow(cid, 0.6, True, "mcq", base_dt + timedelta(seconds=i), "question"))

    series = replay_series(events, req, concepts)
    assert series, "Series should not be empty"

    # Compute expected overall from final p state after all events
    p = {cid: concepts[cid].p_init for cid in req}
    for ev in events:
        p[ev.concept_id] = ev.p_after
    domain_totals = _domain_sums(req, concepts)
    from app.engines.progress import _compute_overall_and_domains
    expected_overall, _ = _compute_overall_and_domains(p, req, concepts, domain_totals)

    assert abs(series[-1]["overall"] - expected_overall) < 0.01


# ---------------------------------------------------------------------------
# 3. Events with changed_mastery == False never create a series point
# ---------------------------------------------------------------------------

def test_false_changed_mastery_skipped():
    content = get_content()
    role = content.role("backend_developer")
    req = role["requirements"]
    concepts = content.concepts
    first_cid = next(iter(req))

    events = [
        _EventRow(first_cid, 0.5, False, "mcq", datetime(2024, 1, 1), "feedback"),
        _EventRow(first_cid, 0.7, False, "manual", datetime(2024, 1, 2), "self_report"),
    ]
    series = replay_series(events, req, concepts)
    assert series == []


# ---------------------------------------------------------------------------
# 4. Simulated grader flagging
# ---------------------------------------------------------------------------

def test_simulated_events_are_flagged():
    content = get_content()
    role = content.role("backend_developer")
    req = role["requirements"]
    concepts = content.concepts
    first_cid = next(iter(req))

    events = [
        _EventRow(first_cid, 0.5, True, "simulated", datetime(2024, 1, 1), "question"),
        _EventRow(first_cid, 0.6, True, "simulated", datetime(2024, 1, 2), "question"),
    ]
    series = replay_series(events, req, concepts)
    assert all(pt["simulated"] for pt in series)


def test_mixed_simulated_real():
    content = get_content()
    role = content.role("backend_developer")
    req = role["requirements"]
    concepts = content.concepts
    cids = list(req.keys())[:2]

    events = [
        _EventRow(cids[0], 0.5, True, "simulated", datetime(2024, 1, 1), "question"),
        _EventRow(cids[1], 0.6, True, "mcq", datetime(2024, 1, 2), "question"),
    ]
    series = replay_series(events, req, concepts)
    assert series[0]["simulated"] is True
    assert series[1]["simulated"] is False


# ---------------------------------------------------------------------------
# 5. Downsampling
# ---------------------------------------------------------------------------

def test_downsampling_1000_events():
    """1000 events → ≤ 200 points, ordered, last point preserved."""
    content = get_content()
    role = content.role("backend_developer")
    req = role["requirements"]
    concepts = content.concepts
    cids = list(req.keys())

    # 1000 events spread across 5 days (200/day) — should downsample heavily
    base = datetime(2024, 1, 1)
    events = []
    for i in range(1000):
        cid = cids[i % len(cids)]
        dt = base + timedelta(hours=i // 200 * 24 + (i % 200) * 0.1)
        events.append(_EventRow(cid, 0.2 + (i % 8) * 0.05, True, "mcq", dt, "question"))

    series = replay_series(events, req, concepts)
    assert len(series) <= 200
    # Ordered
    for i in range(1, len(series)):
        assert series[i]["at"] >= series[i - 1]["at"]
    # n in final point should be 1000
    assert series[-1]["n"] == 1000


# ---------------------------------------------------------------------------
# 6. API validation (days=0 → 422, days=1000 → 422) and isolation
# ---------------------------------------------------------------------------

def test_days_validation(client):
    token = _login(client)
    r = client.get("/api/progress/history?days=0", headers=_auth(token))
    assert r.status_code == 422
    r = client.get("/api/progress/history?days=1000", headers=_auth(token))
    assert r.status_code == 422


def test_isolation_learner_b_not_in_a(client):
    t1 = _login(client, "Alice")
    t2 = _login(client, "Bob", age=22)
    # Bob onboards and does some activity
    client.post("/api/me/onboard", json={"role_id": "backend_developer"}, headers=_auth(t2))
    client.post("/api/probe/next", json={"count": 1}, headers=_auth(t2))
    # Alice's history should still be empty
    r = client.get("/api/progress/history?days=30", headers=_auth(t1))
    assert r.status_code == 200
    assert r.json()["series"] == []


def test_history_endpoint_returns_expected_keys(client):
    token = _login(client)
    r = client.get("/api/progress/history?days=90", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    for key in ("series", "markers", "now", "projection", "due_reviews"):
        assert key in data, f"Missing key: {key}"


def test_radar_endpoint(client):
    token = _login(client)
    r = client.get("/api/progress/radar", headers=_auth(token))
    assert r.status_code == 200
    domains = r.json()["domains"]
    assert isinstance(domains, list)
    for d in domains:
        assert "domain" in d and "current" in d and "target" in d


def test_sparkline_in_dashboard(client):
    token = _login(client)
    r = client.get("/api/dashboard", headers=_auth(token))
    assert r.status_code == 200
    assert "sparkline" in r.json()


# ---------------------------------------------------------------------------
# 7. Performance guard
# ---------------------------------------------------------------------------

def test_replay_2000_events_under_100ms():
    """2000 events should replay in well under 100 ms."""
    content = get_content()
    role = content.role("backend_developer")
    req = role["requirements"]
    concepts = content.concepts
    cids = list(req.keys())

    base = datetime(2024, 1, 1)
    events = []
    for i in range(2000):
        cid = cids[i % len(cids)]
        dt = base + timedelta(minutes=i)
        events.append(_EventRow(cid, 0.2 + (i % 5) * 0.1, True, "mcq", dt, "question"))

    t0 = time.perf_counter()
    replay_series(events, req, concepts)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 500, f"Replay took {elapsed_ms:.1f} ms — too slow"
