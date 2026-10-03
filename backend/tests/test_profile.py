"""Tests for C06: Learner Profile Page ('Parichay')."""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db as dbm
from app.config import settings
from app.engines import escalation, mastery, profile_stats
from app.main import create_app
from app.models import EvidenceEvent, Learner, LearningSession, MentorCase
from app.routes.core import export_me

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
def set_env(monkeypatch):
    for k, v in AUTH_ENV.items():
        os.environ[k] = v
    monkeypatch.setattr(settings, "llm_mode", "fake")


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


def _login(client, name="Alice", age=20, email=None):
    r = client.post("/api/auth/dev-login", json={"name": name, "age": age, "language": "english", "email": email})
    assert r.status_code == 200
    return r.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_profile_patch_validation_and_immutable_fields(client, db):
    """1. PATCH validates: unknown education -> 422; institution > 80 -> 422; sending age/email/role_id leaves stored values unchanged."""
    token = _login(client, name="Bobby", age=22, email="bobby@example.com")
    lr = db.scalar(select(Learner).where(Learner.name == "Bobby"))
    orig_age = lr.age
    orig_email = lr.email
    orig_role = lr.role_id

    # 1. Invalid education -> 422
    r_bad_edu = client.patch("/api/profile", json={"education": "invalid_level"}, headers=_auth(token))
    assert r_bad_edu.status_code == 422

    # 2. Institution > 80 chars -> 422
    r_bad_inst = client.patch("/api/profile", json={"institution": "x" * 81}, headers=_auth(token))
    assert r_bad_inst.status_code == 422

    # 3. Goal > 200 chars -> 422
    r_bad_goal = client.patch("/api/profile", json={"goal_text": "g" * 201}, headers=_auth(token))
    assert r_bad_goal.status_code == 422

    # 4. Valid patch with attempts to modify age, email, role_id
    r_valid = client.patch(
        "/api/profile",
        json={
            "name": "Bobby Tables",
            "education": "undergraduate",
            "institution": "IIT Delhi",
            "goal_text": "Become a senior backend engineer",
            "age": 45,
            "email": "hacked@example.com",
            "role_id": "data_analyst",
        },
        headers=_auth(token),
    )
    assert r_valid.status_code == 200
    data = r_valid.json()
    assert data["profile"]["name"] == "Bobby Tables"
    assert data["profile"]["education"] == "undergraduate"
    assert data["profile"]["institution"] == "IIT Delhi"
    assert data["profile"]["goal_text"] == "Become a senior backend engineer"

    # Verify immutable fields in DB are UNCHANGED
    db.expire_all()
    lr_updated = db.get(Learner, lr.id)
    assert lr_updated.age == orig_age
    assert lr_updated.email == orig_email
    assert lr_updated.role_id == orig_role


def test_stats_recomputed_from_rows_and_simulated_excluded(db):
    """2. Stats equal counts from rows; grader='simulated' excluded; new learner gets zeros, not errors."""
    lr = Learner(id="lr_stats_test", email="stats@example.com", name="Stats Tester", settings={})
    db.add(lr)
    db.commit()

    # Empty learner gets clean zeros
    s_empty = profile_stats.stats(db, lr)
    assert s_empty["checks_answered"] == 0
    assert s_empty["work_products_run"] == 0
    assert s_empty["explain_backs_finished"] == 0
    assert s_empty["interviews_finished"] == 0
    assert s_empty["mentor_cases_closed"] == 0
    assert s_empty["concepts_proficient_or_better"] == 0
    assert s_empty["concepts_assessed"] == 0

    # Add genuine activities
    mastery.ensure_states(db, lr)
    db.add(EvidenceEvent(learner_id=lr.id, concept_id="sql_select", source_type="question", grader="test", correct=True))
    db.add(EvidenceEvent(learner_id=lr.id, concept_id="sql_select", source_type="work_product", grader="test", correct=True))

    # Add simulated events (must NOT count towards real activity counts)
    db.add(EvidenceEvent(learner_id=lr.id, concept_id="py_basics", source_type="question", grader="simulated", correct=True))
    db.add(EvidenceEvent(learner_id=lr.id, concept_id="py_basics", source_type="work_product", grader="simulated", correct=True))

    # Add sessions
    db.add(LearningSession(learner_id=lr.id, mode="explain_back", status="completed"))
    db.add(LearningSession(learner_id=lr.id, mode="interview", status="completed"))
    db.add(LearningSession(learner_id=lr.id, mode="explain_back", status="active"))  # active, not finished

    # Add closed case
    db.add(MentorCase(learner_id=lr.id, category="technical", tier="skill_mentor", status="closed"))
    db.add(MentorCase(learner_id=lr.id, category="career", tier="skill_mentor", status="accepted"))  # not closed
    db.commit()

    s_populated = profile_stats.stats(db, lr)
    assert s_populated["checks_answered"] == 1  # simulated excluded
    assert s_populated["work_products_run"] == 1  # simulated excluded
    assert s_populated["explain_backs_finished"] == 1
    assert s_populated["interviews_finished"] == 1
    assert s_populated["mentor_cases_closed"] == 1


def test_auth_and_isolation(client):
    """3. Another learner's data never appears; GET /api/profile without a token -> 401."""
    # Without token -> 401
    r_unauth = client.get("/api/profile")
    assert r_unauth.status_code == 401

    token_a = _login(client, name="Alice A", email="a@example.com")
    token_b = _login(client, name="Bob B", email="b@example.com")

    # Update Alice's profile
    client.patch("/api/profile", json={"institution": "Oxford"}, headers=_auth(token_a))

    # Bob's profile must not show Alice's institution
    r_b = client.get("/api/profile", headers=_auth(token_b))
    assert r_b.status_code == 200
    assert r_b.json()["profile"]["institution"] is None
    assert r_b.json()["profile"]["name"] == "Bob B"


def test_name_change_and_case_snapshots(client, db):
    """4. Name change does not alter older case reports (they are snapshots) but new cases use the new name."""
    token = _login(client, name="Charlie Brown")
    lr = db.scalar(select(Learner).where(Learner.name == "Charlie Brown"))

    # Create old case report snapshot
    old_report = escalation.build_report(db, lr, "technical", None, "trigger", "reason", "note", False)
    assert old_report["learner"]["first_name"] == "Charlie"

    case = MentorCase(learner_id=lr.id, category="technical", tier="skill_mentor", status="matched", report=old_report)
    db.add(case)
    db.commit()

    # Change name
    client.patch("/api/profile", json={"name": "Charles Xavier"}, headers=_auth(token))

    # Old case snapshot report retains 'Charlie'
    db.expire_all()
    c_loaded = db.get(MentorCase, case.id)
    assert c_loaded.report["learner"]["first_name"] == "Charlie"

    # New report generated for this learner uses 'Charles'
    new_report = escalation.build_report(db, lr, "technical", None, "trigger", "reason", "note", False)
    assert new_report["learner"]["first_name"] == "Charles"


def test_what_mentors_see_matches_build_report(client, db):
    """5. The 'what mentors see' list matches the keys produced by build_report."""
    token = _login(client, name="Devi")
    r = client.get("/api/profile", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()

    lr = db.scalar(select(Learner).where(Learner.name == "Devi"))
    sample_report = escalation.build_report(db, lr, "technical", None, "trigger", "reason", "", False)

    expected_keys = list(sample_report["learner"].keys())
    assert sorted(data["what_mentors_see"]["keys"]) == sorted(expected_keys)


def test_export_contains_profile_and_delete_removes_it(client, db):
    """6. Export contains the profile block; account delete removes the learner and profile."""
    token = _login(client, name="Eve")
    client.patch("/api/profile", json={"education": "postgraduate", "institution": "BITS Pilani"}, headers=_auth(token))

    # Export check
    r_exp = client.get("/api/me/export", headers=_auth(token))
    assert r_exp.status_code == 200
    exp_data = r_exp.json()
    assert "more" in exp_data
    assert "profile" in exp_data["more"]
    assert exp_data["more"]["profile"]["profile"]["education"] == "postgraduate"
    assert exp_data["more"]["profile"]["profile"]["institution"] == "BITS Pilani"

    # Delete check
    r_del = client.delete("/api/me", headers=_auth(token))
    assert r_del.status_code == 200

    # User no longer exists
    r_after = client.get("/api/profile", headers=_auth(token))
    assert r_after.status_code == 401
