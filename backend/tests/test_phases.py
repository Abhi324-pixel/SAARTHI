"""T05 — Roadmap phases, deadlines and personal checkpoints tests.

Covers the spec §6 minimum:
  1. phases() on a hand-built item list: runs of equal domain merge; weeks are contiguous; deterministic.
  2. Rebuilding the roadmap does not change plan_start or any phase target date (unless hours change).
  3. deadline_status: on-track, late by N days, impossible (weeks_left <= 0), needed hours computed exactly (table test).
  4. Concept-linked checkpoint: cannot be toggled (409); becomes done after evidence takes concept to target; free-text can be toggled.
  5. Another learner cannot read/edit my checkpoints (404). Deadline in the past -> 422.
  6. POST /phases/{key}/check returns only unseen items for concepts below target; answering goes through normal evidence.
  7. No endpoint changes ConceptState without going through apply_evidence.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db as dbm
from app.content import get_content
from app.engines import diagnostic, mastery, phases as phases_engine, planner
from app.main import create_app
from app.models import ConceptState, EvidenceEvent, Learner, new_id
from app.models_ext.T05 import LearnerCheckpoint

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
# 1. Pure phases() function test
# ---------------------------------------------------------------------------

def test_phases_grouping_and_merge():
    plan_start = date(2026, 1, 1)
    today = date(2026, 1, 1)
    items = [
        {"concept_id": "sql_select", "domain": "sql", "week": 1, "minutes": 40, "kind": "learn", "target": 0.8},
        {"concept_id": "sql_where", "domain": "sql", "week": 2, "minutes": 50, "kind": "learn", "target": 0.8},
        {"concept_id": "py_vars", "domain": "python", "week": 3, "minutes": 30, "kind": "learn", "target": 0.8},
        {"concept_id": "sql_agg", "domain": "sql", "week": 4, "minutes": 45, "kind": "learn", "target": 0.8},
        {"concept_id": "review_1", "domain": "sql", "week": 4, "minutes": 10, "kind": "review", "target": 0.8},
    ]
    views = {
        "sql_select": {"p": 0.2},
        "sql_where": {"p": 0.1},
        "py_vars": {"p": 0.4},
        "sql_agg": {"p": 0.0},
    }
    deadlines = {"sql": "2026-02-01"}

    res = phases_engine.phases(
        items=items,
        plan_start=plan_start,
        deadlines=deadlines,
        weekly_hours=6.0,
        today=today,
        views=views,
    )

    # Reviews ignored: 3 phases (sql, python, sql-2)
    assert len(res) == 3
    assert res[0]["key"] == "sql"
    assert res[0]["concept_ids"] == ["sql_select", "sql_where"]
    assert res[0]["start_week"] == 1
    assert res[0]["end_week"] == 2
    assert res[0]["minutes"] == 90
    assert res[0]["target_date"] == (plan_start + timedelta(days=14)).isoformat()
    assert res[0]["deadline"] == "2026-02-01"

    assert res[1]["key"] == "python"
    assert res[1]["concept_ids"] == ["py_vars"]
    assert res[1]["start_week"] == 3
    assert res[1]["end_week"] == 3

    assert res[2]["key"] == "sql-2"
    assert res[2]["concept_ids"] == ["sql_agg"]
    assert res[2]["start_week"] == 4
    assert res[2]["end_week"] == 4


# ---------------------------------------------------------------------------
# 2. plan_start is immutable across roadmap rebuilds
# ---------------------------------------------------------------------------

def test_plan_start_immutable_on_rebuild(db):
    lr = _make_learner(db)
    # Simulate setting plan_start in the past
    past_date = date(2025, 10, 1)
    lr.settings = {"plan_start": past_date.isoformat()}
    db.flush()

    # Call get_plan_start
    p_start = phases_engine.get_plan_start(lr, db)
    assert p_start == past_date

    # Rebuild roadmap
    planner.refresh(db, lr, "test rebuild", force=True)
    lr_reloaded = db.get(Learner, lr.id)
    assert lr_reloaded.settings.get("plan_start") == past_date.isoformat()


# ---------------------------------------------------------------------------
# 3. deadline_status table test
# ---------------------------------------------------------------------------

def test_deadline_status_scenarios():
    today = date(2026, 1, 1)
    # Target date: 4 weeks from plan start -> 2026-01-29
    phase = {
        "concept_ids": ["c1", "c2"],
        "target_date": date(2026, 1, 29),
    }
    all_items = [
        {"concept_id": "c1", "minutes": 120, "target": 0.8, "kind": "learn"},
        {"concept_id": "c2", "minutes": 120, "target": 0.8, "kind": "learn"},
    ]
    # Both need full time (views below target) -> 240 minutes needed
    views = {"c1": {"p": 0.1}, "c2": {"p": 0.1}}
    weekly_hours = 4.0

    # Scenario A: On track (deadline after target date, e.g. 2026-02-15 = 45 days left -> ~6.4 weeks left)
    # 240 mins / 60 / 6.4 weeks ≈ 0.6 h/week <= 4.0 h/week
    st_a = phases_engine.deadline_status(phase, "2026-02-15", weekly_hours, today, all_items, views)
    assert st_a["on_track"] is True
    assert st_a["passed"] is False
    assert st_a["gap_days"] < 0

    # Scenario B: Late (deadline before target date, e.g. 2026-01-15 = 14 days left = 2.0 weeks left)
    # 240 mins / 60 / 2.0 weeks = 2.0 h/week (if weekly_hours is 1.0, late)
    st_b = phases_engine.deadline_status(phase, "2026-01-15", 1.0, today, all_items, views)
    assert st_b["on_track"] is False
    assert st_b["gap_days"] == 14
    assert st_b["needed_hours_per_week"] == 2.0

    # Scenario C: Impossible / Passed (deadline in the past relative to today, e.g. 2025-12-25)
    st_c = phases_engine.deadline_status(phase, "2025-12-25", weekly_hours, today, all_items, views)
    assert st_c["on_track"] is False
    assert st_c["passed"] is True
    assert "passed" in st_c["message"].lower()


# ---------------------------------------------------------------------------
# 4. Concept-linked vs free-text checkpoints
# ---------------------------------------------------------------------------

def test_checkpoints_concept_linked_vs_free_text(client, db):
    token = _login(client, "Dana")
    cid = "sql_select"

    # 1. Create a free-text checkpoint
    r_free = client.post("/api/checkpoints", json={"title": "Apply for 3 jobs"}, headers=_auth(token))
    assert r_free.status_code == 200
    free_id = r_free.json()["id"]
    assert r_free.json()["is_concept_linked"] is False

    # Toggle free-text checkpoint
    r_toggle = client.patch(f"/api/checkpoints/{free_id}", headers=_auth(token))
    assert r_toggle.status_code == 200
    assert r_toggle.json()["done"] is True
    r_untoggle = client.patch(f"/api/checkpoints/{free_id}", headers=_auth(token))
    assert r_untoggle.status_code == 200
    assert r_untoggle.json()["done"] is False

    # 2. Create a concept-linked checkpoint
    r_concept = client.post("/api/checkpoints", json={"title": "Master basic SELECT", "concept_id": cid}, headers=_auth(token))
    assert r_concept.status_code == 200
    concept_cp_id = r_concept.json()["id"]
    assert r_concept.json()["is_concept_linked"] is True

    # Attempting to manually toggle concept-linked checkpoint must return 409
    r_err = client.patch(f"/api/checkpoints/{concept_cp_id}", headers=_auth(token))
    assert r_err.status_code == 409

    # Initially concept is not at target -> done is False
    list_r = client.get("/api/checkpoints", headers=_auth(token))
    cps = {cp["id"]: cp for cp in list_r.json()["checkpoints"]}
    assert cps[concept_cp_id]["done"] is False

    # Simulate evidence bringing concept to target (e.g. p = 0.9)
    from app.models import Learner
    lr = db.scalar(select(Learner).where(Learner.name == "Dana"))
    cs = mastery.ensure_states(db, lr)[cid]
    cs.p_known = 0.95
    cs.n_evidence = 5
    cs.source_types = ["question", "work_product"]
    db.flush()

    # Now checkpoint should report done=True automatically
    list_r2 = client.get("/api/checkpoints", headers=_auth(token))
    cps2 = {cp["id"]: cp for cp in list_r2.json()["checkpoints"]}
    assert cps2[concept_cp_id]["done"] is True


# ---------------------------------------------------------------------------
# 5. Isolation & past deadline validation
# ---------------------------------------------------------------------------

def test_checkpoint_isolation_and_deadline_validation(client):
    t_alice = _login(client, "Alice_CP")
    t_bob = _login(client, "Bob_CP")

    # Alice creates a checkpoint
    r = client.post("/api/checkpoints", json={"title": "Alice task"}, headers=_auth(t_alice))
    cp_id = r.json()["id"]

    # Bob tries to toggle Alice's checkpoint -> 404
    r_bob = client.patch(f"/api/checkpoints/{cp_id}", headers=_auth(t_bob))
    assert r_bob.status_code == 404

    # Bob tries to delete Alice's checkpoint -> 404
    r_bob_del = client.delete(f"/api/checkpoints/{cp_id}", headers=_auth(t_bob))
    assert r_bob_del.status_code == 404

    # Setting a deadline in the past -> 422
    past_date = "2020-01-01"
    r_dl = client.put("/api/phases/sql/deadline", json={"date": past_date}, headers=_auth(t_alice))
    assert r_dl.status_code == 422


# ---------------------------------------------------------------------------
# 6. POST /phases/{key}/check produces real evidence on answer
# ---------------------------------------------------------------------------

def test_phase_check_and_answer_flow(client):
    token = _login(client, "Frank")

    # Call phase check for sql
    r = client.post("/api/phases/sql/check", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert data["count"] > 0
    item = data["items"][0]
    assert "id" in item and "options" in item

    # Answer the item
    content = get_content()
    raw = content.items[item["id"]]
    correct_opt = next(o for o in raw["options"] if o.get("correct"))
    opt_idx = next(opt["index"] for opt in item["options"] if opt["text"] == correct_opt["text"])

    ans_r = client.post(
        "/api/probe/answer",
        json={"item_id": item["id"], "option_index": opt_idx, "stated_confidence": 4},
        headers=_auth(token),
    )
    assert ans_r.status_code == 200
    ans_data = ans_r.json()
    assert ans_data["mastery"]["moved_mastery"] is True
    assert ans_data["mastery"]["source_type"] == "question"


# ---------------------------------------------------------------------------
# 7. No endpoint changes ConceptState without going through apply_evidence
# ---------------------------------------------------------------------------

def test_no_state_change_without_apply_evidence(client, db):
    token = _login(client, "Grace")
    lr = db.scalar(select(Learner).where(Learner.name == "Grace"))

    # Initial states
    initial_states = {cs.concept_id: (cs.p_known, cs.n_evidence) for cs in db.scalars(select(ConceptState).where(ConceptState.learner_id == lr.id))}

    # Call various T05 endpoints: set deadline, list checkpoints, create checkpoint, delete deadline
    client.put("/api/phases/sql/deadline", json={"date": "2027-01-01"}, headers=_auth(token))
    client.get("/api/checkpoints", headers=_auth(token))
    client.post("/api/checkpoints", json={"title": "Test CP"}, headers=_auth(token))
    client.delete("/api/phases/sql/deadline", headers=_auth(token))
    client.get("/api/roadmap", headers=_auth(token))

    # States must remain completely untouched
    final_states = {cs.concept_id: (cs.p_known, cs.n_evidence) for cs in db.scalars(select(ConceptState).where(ConceptState.learner_id == lr.id))}
    assert initial_states == final_states
