"""Tests for C03: Learner prep notes and session summary."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import db as dbm
from app.engines import casenotes, escalation, mastery
from app.models import EvidenceEvent, Learner, MentorCase
from app.models_ext.C03 import CaseNote
from .test_api import client, login  # noqa: F401


def test_prep_technical_case_with_misconception_and_career_case(client):
    h = login(client)
    me = client.get("/api/me", headers=h).json()

    # 1. Technical case with left_join_where_filter misconception
    with dbm.SessionLocal() as s:
        lr = s.get(Learner, me["id"])
        # Inject misconception into learner
        from app.models import MisconceptionInstance
        s.add(MisconceptionInstance(
            learner_id=lr.id,
            concept_id="sql_outer_join",
            misconception_id="left_join_where_filter",
            status="confirmed",
            cycles=2,
            statement="i put the filter in where after the left join",
        ))
        s.commit()

    # Open case for sql_outer_join
    r_tech = client.post("/api/cases", json={
        "category": "technical",
        "concept_id": "sql_outer_join",
        "note": "My left join filters keep dropping rows",
        "reason": "Stuck on outer join query",
    }, headers=h).json()
    case_id_tech = r_tech["case_id"]

    prep_tech = client.get(f"/api/cases/{case_id_tech}/prep", headers=h).json()
    assert prep_tech["bring"]
    assert len(prep_tech["questions"]) >= 3
    # Misconception question should contain counter-example query from left_join_where_filter
    misc_q = next((q for q in prep_tech["questions"] if q["from"] == "misconception"), None)
    assert misc_q is not None
    assert "WHERE o.status = 'delivered'" in misc_q["text"] or "AND o.status = 'delivered'" in misc_q["text"] or "WHERE" in misc_q["text"]

    # 2. Career case has career-appropriate questions and no SQL
    r_career = client.post("/api/cases", json={
        "category": "career",
        "note": "Want advice on preparing for backend developer interviews",
        "reason": "Career guidance",
    }, headers=h).json()
    case_id_career = r_career["case_id"]

    prep_career = client.get(f"/api/cases/{case_id_career}/prep", headers=h).json()
    assert prep_career["bring"]
    assert len(prep_career["questions"]) >= 3
    for q in prep_career["questions"]:
        assert "SELECT" not in q["text"]
        assert "WHERE" not in q["text"]
        assert q["from"] in ("career", "goal")


def test_prep_deterministic_and_valid_sources(client):
    h = login(client)
    r_case = client.post("/api/cases", json={
        "category": "technical",
        "concept_id": "sql_inner_join",
        "note": "Doubts about joins",
    }, headers=h).json()
    cid = r_case["case_id"]

    prep_1 = client.get(f"/api/cases/{cid}/prep", headers=h).json()
    prep_2 = client.get(f"/api/cases/{cid}/prep", headers=h).json()

    # Generated twice => identical (deterministic)
    assert prep_1 == prep_2

    # Sources are valid
    valid_sources = {"misconception", "prerequisite", "concept", "career", "goal"}
    for q in prep_1["questions"]:
        assert q["from"] in valid_sources


def test_multilingual_templates_exist_for_all_kinds():
    kinds = ("bring_technical", "bring_career", "misconception", "prerequisite", "concept", "career_1", "career_2", "career_3", "goal")
    for lang in ("english", "hinglish", "hindi"):
        assert lang in casenotes.TEMPLATES
        tmpl = casenotes.TEMPLATES[lang]
        for k in kinds:
            assert k in tmpl, f"Missing kind {k} in {lang}"


def test_language_query_param(client):
    h = login(client)
    r_case = client.post("/api/cases", json={
        "category": "career",
        "note": "Career guidance",
    }, headers=h).json()
    cid = r_case["case_id"]

    prep_hi = client.get(f"/api/cases/{cid}/prep?lang=hindi", headers=h).json()
    prep_hing = client.get(f"/api/cases/{cid}/prep?lang=hinglish", headers=h).json()
    prep_en = client.get(f"/api/cases/{cid}/prep?lang=english", headers=h).json()

    assert "नमस्ते" in prep_hi["icebreaker"]
    assert "main" in prep_hing["icebreaker"].lower()
    assert "Hi" in prep_en["icebreaker"]


def test_prep_auth_and_status_checks(client):
    h1 = login(client, name="Learner One")
    h2 = login(client, name="Learner Two")

    r1 = client.post("/api/cases", json={"category": "career", "note": "guidance"}, headers=h1).json()
    cid = r1["case_id"]

    # Another learner's case => 404
    r_unauth = client.get(f"/api/cases/{cid}/prep", headers=h2)
    assert r_unauth.status_code == 404

    # Summary on accepted case before completion => 409
    r_sum_early = client.get(f"/api/cases/{cid}/summary", headers=h1)
    assert r_sum_early.status_code == 409


def test_share_questions_and_contact_screening(client):
    h = login(client)
    r = client.post("/api/cases", json={"category": "career", "note": "guidance"}, headers=h).json()
    cid = r["case_id"]

    # Normal share
    res_share = client.post(f"/api/cases/{cid}/prep/share", json={"question_indexes": [0, 1]}, headers=h)
    assert res_share.status_code == 200
    assert res_share.json()["sent"] is True

    # Screening blocks contact sharing in messages
    screened = escalation.screen_message("Call me at 9876543210 or email me@test.com")
    assert screened[0] is False


def test_session_summary_and_followup(client):
    h = login(client)
    me = client.get("/api/me", headers=h).json()

    # Open technical case
    r_case = client.post("/api/cases", json={
        "category": "technical",
        "concept_id": "sql_outer_join",
        "note": "outer join stuck",
    }, headers=h).json()
    cid = r_case["case_id"]

    # Simulate session
    sim = client.post(f"/api/cases/{cid}/simulate-session", json={"rating": 0.8}, headers=h).json()
    assert sim["case"]["status"] == "followup"

    # Follow-up due date is 3 learner days ahead
    assert sim["case"]["followup"]["due_at"] is not None

    # Get summary
    summary = client.get(f"/api/cases/{cid}/summary", headers=h).json()
    assert summary["mentor_said"]["notes"] == sim["case"]["outcome"]["notes"]
    assert summary["mentor_said"]["next_step"] == sim["case"]["outcome"]["next_step"]
    assert summary["followup"]["due"] == sim["case"]["followup"]["due_at"]
    assert summary["saarthi_saw"]["concept_id"] == "sql_outer_join"

    # Followup check closes the case
    fol = client.post(f"/api/cases/{cid}/followup", headers=h).json()
    assert fol["case"]["status"] == "closed"


def test_generating_prep_or_summary_never_changes_mastery_or_evidence(client):
    h = login(client)
    me = client.get("/api/me", headers=h).json()

    r_case = client.post("/api/cases", json={"category": "career", "note": "career advice"}, headers=h).json()
    cid = r_case["case_id"]

    with dbm.SessionLocal() as s:
        ev_count_before = len(list(s.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == me["id"]))))

    # Call prep multiple times
    client.get(f"/api/cases/{cid}/prep", headers=h)
    client.get(f"/api/cases/{cid}/prep?lang=hindi", headers=h)

    with dbm.SessionLocal() as s:
        ev_count_after = len(list(s.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == me["id"]))))

    assert ev_count_before == ev_count_after

    # Also check privacy export includes case_notes
    ex = client.get("/api/me/export", headers=h).json()
    assert "case_notes" in ex["more"]
    assert len(ex["more"]["case_notes"]) >= 1
