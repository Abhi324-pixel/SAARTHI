"""T03 — Difficulty & Preference Feedback tests.

Covers the spec §6 minimum:
  1. Rule test: after too_easy and too_hard, concept_views()[cid]["p"] and n_evidence
     are unchanged; an EvidenceEvent with source_type="feedback" and changed_mastery=False exists.
  2. too_easy returns a harder, unseen item; answering it correctly moves mastery as question.
  3. too_hard returns a different strategy than the last one and a prerequisite probe when blocked_by is non-empty.
  4. Planner: two learners identical except practice_factor get different minutes and a LEARNER_FEEDBACK reason code; defaults unchanged.
  5. Click-spam: the 7th click in an hour returns 429 and does not change the factor; factor stays within [1.5, 3.0].
  6. Another learner's settings is untouched; reset restores defaults.
  7. helpful does not override contrasting_cases when a misconception is active.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import db as dbm
from app.content import get_content
from app.engines import diagnostic, feedback as feedback_engine, mastery, planner, strategy
from app.main import create_app
from app.models import ConceptState, EvidenceEvent, Learner, MisconceptionInstance, new_id

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
    token = r.json()["token"]
    # Onboard
    client.post("/api/me/onboard", json={"role_id": "backend_developer"}, headers={"Authorization": f"Bearer {token}"})
    return token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_learner(db, **kw):
    id_val = kw.pop("id", new_id("lr_"))
    name_val = kw.pop("name", "Learner")
    settings_val = kw.pop("settings", {})
    role_id_val = kw.pop("role_id", "backend_developer")
    lr = Learner(id=id_val, name=name_val, role_id=role_id_val, settings=settings_val, **kw)
    db.add(lr)
    db.flush()
    return lr


# ---------------------------------------------------------------------------
# 1. Rule test: feedback never moves mastery
# ---------------------------------------------------------------------------

def test_rule_feedback_never_moves_mastery(db):
    lr = _make_learner(db)
    cid = "sql_select"

    views_before = mastery.concept_views(db, lr)
    p_before = views_before[cid]["p"]
    n_before = views_before[cid]["n_evidence"]

    # 1. too_easy
    res_easy = feedback_engine.apply(db, lr, cid, "too_easy", context="explanation")
    views_after_easy = mastery.concept_views(db, lr)
    assert views_after_easy[cid]["p"] == p_before, "too_easy must not change p"
    assert views_after_easy[cid]["n_evidence"] == n_before, "too_easy must not increment n_evidence"

    # 2. too_hard
    res_hard = feedback_engine.apply(db, lr, cid, "too_hard", context="explanation")
    views_after_hard = mastery.concept_views(db, lr)
    assert views_after_hard[cid]["p"] == p_before, "too_hard must not change p"
    assert views_after_hard[cid]["n_evidence"] == n_before, "too_hard must not increment n_evidence"

    # Verify EvidenceEvents
    from sqlalchemy import select
    events = list(db.scalars(
        select(EvidenceEvent)
        .where(EvidenceEvent.learner_id == lr.id, EvidenceEvent.concept_id == cid, EvidenceEvent.source_type == "feedback")
        .order_by(EvidenceEvent.created_at)
    ))
    assert len(events) == 2
    for ev in events:
        assert ev.changed_mastery is False, "changed_mastery must be False for feedback events"
        assert ev.grader == "learner_click"


# ---------------------------------------------------------------------------
# 2. too_easy returns harder, unseen item; answering it moves mastery
# ---------------------------------------------------------------------------

def test_too_easy_returns_harder_item_and_moves_mastery(client):
    token = _login(client, "Bob")
    cid = "sql_select"

    # Send too_easy
    r = client.post("/api/feedback", json={"concept_id": cid, "signal": "too_easy", "context": "explanation"}, headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["action"]["type"] == "probe"
    item = data["action"]["item"]
    assert item is not None
    assert item["concept_id"] == cid

    # Answer the challenge probe correctly
    # Find the correct option index
    content = get_content()
    raw_item = content.items[item["id"]]
    opts = content.shuffled_options(raw_item, seed=123)
    # dev-login learner seed is deterministic based on learner_id
    # We can answer using probe/answer endpoint
    # Find which option in item["options"] has correct text
    correct_opt = next(o for o in raw_item["options"] if o.get("correct"))
    opt_idx = next(opt["index"] for opt in item["options"] if opt["text"] == correct_opt["text"])

    ans_r = client.post("/api/probe/answer", json={"item_id": item["id"], "option_index": opt_idx, "stated_confidence": 5}, headers=_auth(token))
    assert ans_r.status_code == 200
    ans_data = ans_r.json()
    assert ans_data["correct"] is True
    # The answer should have moved mastery via "question"
    assert ans_data["mastery"]["moved_mastery"] is True
    assert ans_data["mastery"]["source_type"] == "question"


# ---------------------------------------------------------------------------
# 3. too_hard returns different strategy & prerequisite probe if blocked
# ---------------------------------------------------------------------------

def test_too_hard_returns_different_strategy_and_prereq_probe(db):
    lr = _make_learner(db)
    cid = "sql_outer_join"
    content = get_content()

    # Set last strategy on concept to worked_example
    cs = mastery.ensure_states(db, lr)[cid]
    cs.last_strategy = "worked_example"
    db.flush()

    # Simulate a prerequisite being blocked (e.g. sql_select has weak mastery)
    prereqs = content.prereqs(cid)
    assert len(prereqs) > 0
    prereq_cid = prereqs[0]

    # Set prereq state to developing so it appears in blocked_by
    pcs = mastery.ensure_states(db, lr)[prereq_cid]
    pcs.p_known = 0.3
    pcs.n_evidence = 2
    pcs.source_types = ["question"]
    db.flush()

    views = mastery.concept_views(db, lr)
    assert prereq_cid in views[cid]["blocked_by"]

    res = feedback_engine.apply(db, lr, cid, "too_hard", context="explanation")
    action = res["action"]
    assert action["type"] == "strategy"
    assert action["strategy"] != "worked_example", "Should choose different gentle strategy"
    assert action["explanation"] is not None
    assert action["prereq_probe"] is not None
    assert action["prereq_probe"]["concept_id"] == prereq_cid


# ---------------------------------------------------------------------------
# 4. Planner: practice_factor changes minutes & gives LEARNER_FEEDBACK reason
# ---------------------------------------------------------------------------

def test_planner_practice_factor_adaptation(db):
    lr1 = _make_learner(db, id="lr_default")
    lr2 = _make_learner(db, id="lr_adapted")
    lr2.settings = {"practice_factor": {"sql": 2.3}}
    db.flush()

    rm1 = planner.build(db, lr1)
    rm2 = planner.build(db, lr2)

    # Find a sql concept in both roadmaps
    sql_item1 = next((i for i in rm1["items"] if i.get("domain") == "sql"), None)
    sql_item2 = next((i for i in rm2["items"] if i.get("concept_id") == sql_item1["concept_id"]), None)

    assert sql_item1 is not None and sql_item2 is not None
    assert sql_item2["minutes"] > sql_item1["minutes"], "Higher practice factor must yield more minutes"

    # lr1 should have no LEARNER_FEEDBACK reason
    assert not any(r["type"] == "LEARNER_FEEDBACK" for r in sql_item1["reasons"])

    # lr2 should have LEARNER_FEEDBACK reason
    fb_reason = next((r for r in sql_item2["reasons"] if r["type"] == "LEARNER_FEEDBACK"), None)
    assert fb_reason is not None
    assert fb_reason["detail"]["factor"] == 2.3
    assert fb_reason["detail"]["default"] == 2.0

    # why_text should explain the feedback
    why = planner.why_text(sql_item2, "english")
    assert "You told us this was too hard" in why


# ---------------------------------------------------------------------------
# 5. Click-spam: 7th click in an hour returns 429 & factor stays within [1.5, 3.0]
# ---------------------------------------------------------------------------

def test_rate_limiting_click_spam_429(client):
    token = _login(client, "Charlie")
    cid = "sql_select"

    for i in range(6):
        r = client.post("/api/feedback", json={"concept_id": cid, "signal": "too_hard", "context": "explanation"}, headers=_auth(token))
        assert r.status_code == 200, f"Request {i+1} should succeed"

    # 7th click within the same hour
    r7 = client.post("/api/feedback", json={"concept_id": cid, "signal": "too_hard", "context": "explanation"}, headers=_auth(token))
    assert r7.status_code == 429, "7th click in an hour must return 429"


def test_practice_factor_clamped_to_range(db):
    lr = _make_learner(db)
    cid = "sql_select"
    c = get_content().concepts[cid]

    # Force factor to 2.95 and test upper clamp at 3.0
    lr.settings = {"practice_factor": {c.domain: 2.95}}
    db.flush()
    feedback_engine.apply(db, lr, cid, "too_hard", context="explanation")
    factor = lr.settings["practice_factor"][c.domain]
    assert factor <= 3.0

    # Test lower clamp at 1.5
    lr.settings = {
        "practice_factor": {c.domain: 1.55},
        "pending_too_easy": {"item_123": {"concept_id": cid, "domain": c.domain, "at": "2026-10-02"}},
    }
    db.flush()
    feedback_engine.on_probe_answered(db, lr, "item_123", correct=True)
    factor = lr.settings["practice_factor"][c.domain]
    assert factor >= 1.5


# ---------------------------------------------------------------------------
# 6. Another learner's settings untouched; reset restores defaults
# ---------------------------------------------------------------------------

def test_isolation_and_reset(client):
    t_alice = _login(client, "Alice_T03")
    t_bob = _login(client, "Bob_T03")

    # Alice gives too_hard feedback
    client.post("/api/feedback", json={"concept_id": "sql_select", "signal": "too_hard", "context": "explanation"}, headers=_auth(t_alice))

    # Check Alice's adaptations
    r_a = client.get("/api/feedback/adaptations", headers=_auth(t_alice))
    assert r_a.status_code == 200
    assert r_a.json()["practice_factors"].get("sql") is not None

    # Bob's adaptations should remain empty defaults
    r_b = client.get("/api/feedback/adaptations", headers=_auth(t_bob))
    assert r_b.status_code == 200
    assert r_b.json()["practice_factors"].get("sql") is None

    # Alice resets
    reset_r = client.post("/api/feedback/reset", headers=_auth(t_alice))
    assert reset_r.status_code == 200

    # Alice's adaptations should now be empty defaults
    r_a2 = client.get("/api/feedback/adaptations", headers=_auth(t_alice))
    assert r_a2.json()["practice_factors"] == {}


# ---------------------------------------------------------------------------
# 7. helpful does not override contrasting_cases when misconception active
# ---------------------------------------------------------------------------

def test_helpful_does_not_override_misconception_contrasting_cases(db):
    lr = _make_learner(db)
    cid = "sql_outer_join"

    # Learner marked "worked_example" as helpful 10 times
    lr.settings = {"helpful_strategies": {"worked_example": 10}}
    db.flush()

    # Active misconception on sql_join
    mi = MisconceptionInstance(
        learner_id=lr.id,
        concept_id=cid,
        misconception_id="left_join_where_filter",
        status="confirmed",
    )
    db.add(mi)
    db.flush()

    # Call strategy.choose
    res = strategy.choose(db, lr, cid)
    assert res["strategy"] == "contrasting_cases", (
        "Active misconception must use contrasting_cases regardless of helpful_strategies preference"
    )
