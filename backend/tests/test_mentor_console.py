"""C02: the mentor's side of a case. State machine, privacy projection, re-matching, safeguarding queue."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import adapters, db as dbm
from app.config import settings
from app.models import CaseMessage, EvidenceEvent, Learner, Mentor, MentorCase, SafeguardingReport, now
from app.models_ext.audit import AuditLog
from app.models_ext.C02 import CaseExclusion

from .test_api import login
from .test_mentor_apply import approved_mentor, complete_application, make_admin, profile, remove_demo_mentors


@pytest.fixture()
def env(monkeypatch):
    dbm.configure("sqlite://")
    for k, v in (("llm_mode", "fake"), ("auth_mode", "mock"), ("mentors_mode", "db"), ("consent_mode", "mock"), ("cohort_mode", "mock")):
        monkeypatch.setattr(settings, k, v)
    adapters.reset()
    from app.main import create_app
    c = TestClient(create_app())
    from app.adapters.impl import seed_mentors
    with dbm.SessionLocal() as s:
        seed_mentors(s)
        s.commit()
    yield c, monkeypatch
    adapters.reset()


CHECKS = ["identity", "reference", "police_verification"]


def new_real_mentor(c, mp, name):
    """Sign up + admin-approve one real mentor; returns (headers, mentor_id)."""
    h = login(c, name=name)
    complete_application(c, h, name=name, expertise=["sql_outer_join", "sql"])
    ah, _ = make_admin(c, mp, name=name + " admin")
    app = [a for a in c.get("/api/admin/mentor-applications", headers=ah).json()["applications"] if a["name"] == name][0]
    c.post(f"/api/admin/mentor-applications/{app['id']}/decision", headers=ah,
           json={"decision": "approve", "note": "ok", "checks": [{"kind": k} for k in CHECKS]})
    return h, app["user_id"], ah


def open_case(c, h, **over):
    body = {"category": "technical", "concept_id": "sql_outer_join", "reason": "my left join drops customers"}
    body.update(over)
    return c.post("/api/cases", json=body, headers=h).json()


@pytest.fixture()
def one_mentor(env):
    c, mp = env
    mh, mid, ah = new_real_mentor(c, mp, "Real Mentor")
    remove_demo_mentors()
    lh = login(c, name="Priya Sharma", age=22)
    return c, mp, mh, mid, ah, lh


def test_console_is_for_verified_mentors_only(env):
    c, mp = env
    learner = login(c)
    assert c.get("/api/mentor-console/me", headers=learner).status_code == 403
    mp.setattr(settings, "mentors_mode", "mock")
    assert c.get("/api/mentor-console/me", headers=learner).status_code == 404
    mp.setattr(settings, "mentors_mode", "db")
    assert c.get("/api/mentor-console/me").status_code == 401
    mh, mid, ah = new_real_mentor(c, mp, "Real Mentor")
    me = c.get("/api/mentor-console/me", headers=mh).json()
    assert me["mentor"]["id"] == mid and me["pledge"]["current"] and me["counts"] == {"new": 0, "active": 0, "followup": 0, "closed": 0}
    assert c.get("/api/me", headers=mh).json()["is_mentor"] is True and c.get("/api/me", headers=learner).json()["is_mentor"] is False


def test_the_whole_loop_matched_accept_chat_held_outcome_followup_closed(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    case = open_case(c, lh)
    assert case["status"] == "matched" and case["mentor"]["id"] == mid
    lst = c.get("/api/mentor-console/cases", params={"group": "new"}, headers=mh).json()["cases"]
    assert len(lst) == 1 and lst[0]["learner_first_name"] == "Priya" and lst[0]["age_band"] == "adult"
    cid = case["case_id"]
    assert c.post(f"/api/mentor-console/cases/{cid}/messages", json={"text": "hi"}, headers=mh).status_code == 409     # not accepted yet
    acc = c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Sat 11:00"}, headers=mh)
    assert acc.status_code == 200 and acc.json()["status"] == "accepted" and acc.json()["scheduled_for"] == "Sat 11:00"
    assert c.get(f"/api/cases/{cid}", headers=lh).json()["status"] == "accepted"                   # the learner sees it
    sent = c.post(f"/api/mentor-console/cases/{cid}/messages", json={"text": "Paste your query and tell me what you expected."}, headers=mh).json()
    assert sent["sent"] is True
    thread = c.get(f"/api/cases/{cid}", headers=lh).json()["messages"]
    assert any(m["sender"] == "mentor" and "Paste your query" in m["text"] and not m["is_mock"] for m in thread)
    reply = c.post(f"/api/cases/{cid}/messages", json={"text": "select * from customers left join orders where orders.total > 5"}, headers=lh).json()
    assert reply["sent"] and not reply["mentor_reply"]                                           # real mode: no canned replies
    assert any(m["sender"] == "learner" for m in c.get(f"/api/mentor-console/cases/{cid}", headers=mh).json()["messages"])
    assert c.post(f"/api/mentor-console/cases/{cid}/held", headers=mh).json()["status"] == "held"
    before = c.get("/api/genome", headers=lh).json()
    out = c.post(f"/api/mentor-console/cases/{cid}/outcome", headers=mh,
                 json={"notes": "Walked through ON vs WHERE with a worked example.", "next_step": "Redo task 3, then explain it back.", "demonstrated": 4})
    assert out.status_code == 200 and out.json()["status"] == "followup" and out.json()["outcome"]["next_step"].startswith("Redo")
    with dbm.SessionLocal() as s:
        ev = list(s.scalars(select(EvidenceEvent).where(EvidenceEvent.source_type == "mentor")))
        assert len(ev) == 1 and ev[0].score == 0.7 and ev[0].grader == f"mentor:{mid}"
    assert c.post(f"/api/mentor-console/cases/{cid}/outcome", headers=mh, json={"notes": "again again again", "demonstrated": 3}).status_code == 409   # once
    assert c.post(f"/api/mentor-console/cases/{cid}/messages", json={"text": "more"}, headers=mh).status_code == 409                        # thread closed for the mentor
    fu = c.post(f"/api/cases/{cid}/followup", headers=lh).json()
    assert fu["status"] == "closed"
    assert c.get("/api/mentor-console/me", headers=mh).json()["counts"]["closed"] == 1
    assert before is not None


def test_a_mentor_cannot_close_a_case_or_set_mastery_directly(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh)
    for path in ("close", "mastery", "followup", "closed"):
        assert c.post(f"/api/mentor-console/cases/{cid}/{path}", headers=mh).status_code in (404, 405)
    assert c.post(f"/api/mentor-console/cases/{cid}/outcome", headers=mh, json={"notes": "x" * 12, "demonstrated": 9}).status_code == 422
    assert c.post(f"/api/mentor-console/cases/{cid}/outcome", headers=mh, json={"notes": "short", "demonstrated": 3}).status_code == 422


def test_mentors_only_see_their_own_cases(env):
    c, mp = env
    h1, id1, _ = new_real_mentor(c, mp, "Mentor One")
    h2, id2, _ = new_real_mentor(c, mp, "Mentor Two")
    remove_demo_mentors()
    lh = login(c, name="Priya Sharma", age=22)
    case = open_case(c, lh)
    owner = h1 if case["mentor"]["id"] == id1 else h2
    other = h2 if owner is h1 else h1
    assert c.get(f"/api/mentor-console/cases/{case['case_id']}", headers=owner).status_code == 200
    assert c.get(f"/api/mentor-console/cases/{case['case_id']}", headers=other).status_code == 404
    assert c.post(f"/api/mentor-console/cases/{case['case_id']}/accept", json={"slot": "Mon 18:00"}, headers=other).status_code == 404
    assert c.get("/api/mentor-console/cases", headers=other).json()["cases"] == []


def test_the_mentor_view_has_no_learner_identity(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    me = c.get("/api/me", headers=lh).json()
    with dbm.SessionLocal() as s:
        s.get(Learner, me["id"]).email = "priya.private@example.com"
        s.commit()
    cid = open_case(c, lh, note="please help")["case_id"]
    body = c.get(f"/api/mentor-console/cases/{cid}", headers=mh).text
    assert me["id"] not in body and "priya.private" not in body and "Sharma" not in body and '"Priya"' in body
    assert "transcript_excerpts" not in body                                                       # nothing shared
    assert "mentor" not in c.get(f"/api/mentor-console/cases/{cid}", headers=mh).json()


def test_contact_details_in_a_mentor_message_are_blocked_and_audited(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh)
    r = c.post(f"/api/mentor-console/cases/{cid}/messages", json={"text": "call me on 9876543210 or whatsapp me"}, headers=mh).json()
    assert r["blocked"] and r["sent"] is False
    learner_thread = c.get(f"/api/cases/{cid}", headers=lh).json()["messages"]
    assert not any("9876543210" in m["text"] for m in learner_thread)
    with dbm.SessionLocal() as s:
        blocked = s.scalars(select(CaseMessage).where(CaseMessage.sender == "mentor", CaseMessage.screened.is_(False))).all()
        assert len(blocked) == 1 and blocked[0].blocked_reason
        assert "message_blocked" in [a.action for a in s.scalars(select(AuditLog))]


def test_decline_rematches_to_someone_else_and_never_back(env):
    c, mp = env
    h1, id1, _ = new_real_mentor(c, mp, "Mentor One")
    h2, id2, _ = new_real_mentor(c, mp, "Mentor Two")
    remove_demo_mentors()
    lh = login(c, name="Priya Sharma", age=22)
    case = open_case(c, lh)
    first = case["mentor"]["id"]
    hf, hs, second = (h1, h2, id2) if first == id1 else (h2, h1, id1)
    assert c.post(f"/api/mentor-console/cases/{case['case_id']}/decline", json={"reason": "nonsense"}, headers=hf).status_code == 422
    assert c.post(f"/api/mentor-console/cases/{case['case_id']}/decline", json={"reason": "busy"}, headers=hf).status_code == 200
    now_case = c.get(f"/api/cases/{case['case_id']}", headers=lh).json()
    assert now_case["status"] == "matched" and now_case["mentor"]["id"] == second
    assert c.post(f"/api/mentor-console/cases/{case['case_id']}/decline", json={"reason": "busy"}, headers=hs).status_code == 200
    final = c.get(f"/api/cases/{case['case_id']}", headers=lh).json()
    assert final["status"] == "open" and final["mentor"] is None                                    # nobody left: queued, never back to a decliner
    with dbm.SessionLocal() as s:
        assert {e.mentor_id for e in s.scalars(select(CaseExclusion))} == {id1, id2}


def test_a_stale_match_is_re_matched_lazily_after_24_hours(env):
    c, mp = env
    h1, id1, _ = new_real_mentor(c, mp, "Mentor One")
    h2, id2, _ = new_real_mentor(c, mp, "Mentor Two")
    remove_demo_mentors()
    lh = login(c, name="Priya Sharma", age=22)
    case = open_case(c, lh)
    first = case["mentor"]["id"]
    with dbm.SessionLocal() as s:
        s.get(MentorCase, case["case_id"]).updated_at = now() - timedelta(hours=25)
        s.commit()
    seen = c.get(f"/api/cases/{case['case_id']}", headers=lh).json()
    assert seen["status"] == "matched" and seen["mentor"]["id"] != first
    with dbm.SessionLocal() as s:
        assert "case_timeout" in [a.action for a in s.scalars(select(AuditLog))]


def test_capacity_is_checked_at_accept_time(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    with dbm.SessionLocal() as s:
        s.get(Mentor, mid).active_case_cap = 1
        s.commit()
    case = open_case(c, lh)
    with dbm.SessionLocal() as s:                                                                  # another active case sneaks in (e.g. matched earlier)
        other = Learner(id="l_other", name="O", age=22)
        s.add(other)
        s.flush()
        s.add(MentorCase(learner_id="l_other", mentor_id=mid, tier="skill_mentor", category="technical", status="accepted"))
        s.commit()
    assert c.post(f"/api/mentor-console/cases/{case['case_id']}/accept", json={"slot": "Mon 18:00"}, headers=mh).status_code == 409


def test_wellbeing_cases_never_reach_a_mentor(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    case = open_case(c, lh, reason="I feel hopeless and want to die")
    assert case["category"] == "wellbeing" and case["tier"] == "safeguarding"
    assert c.get("/api/mentor-console/cases", headers=mh).json()["cases"] == []
    assert c.get(f"/api/mentor-console/cases/{case['case_id']}", headers=mh).status_code == 404


def test_outdated_pledge_blocks_actions_until_accepted(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    with dbm.SessionLocal() as s:
        from app.models_ext.C01 import MentorApplication
        s.scalars(select(MentorApplication)).first().pledge_version = "0-old"
        s.commit()
    r = c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "PLEDGE_OUTDATED"
    me = c.get("/api/mentor-console/me", headers=mh).json()
    assert me["pledge"]["current"] is False and c.get(f"/api/mentor-console/cases/{cid}", headers=mh).status_code == 200   # reading stays possible
    assert c.post("/api/mentor-console/me/pledge", json={"version": me["pledge"]["version"]}, headers=mh).status_code == 200
    assert c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh).status_code == 200


def test_flagging_a_concern_reaches_the_safeguarding_queue_and_can_be_resolved(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    assert c.post(f"/api/mentor-console/cases/{cid}/flag", json={"detail": "short"}, headers=mh).status_code == 422
    r = c.post(f"/api/mentor-console/cases/{cid}/flag", json={"detail": "The learner mentioned being afraid to go home."}, headers=mh)
    assert r.status_code == 200
    assert c.get("/api/admin/reports", headers=lh).status_code == 403
    reports = c.get("/api/admin/reports", headers=ah).json()["reports"]
    assert len(reports) == 1 and reports[0]["category"] == "mentor_concern" and reports[0]["case_id"] == cid
    assert c.post(f"/api/admin/reports/{reports[0]['id']}/resolve", json={"note": ""}, headers=ah).status_code == 422
    assert c.post(f"/api/admin/reports/{reports[0]['id']}/resolve", json={"note": "Spoke to the learner's school counsellor."}, headers=ah).status_code == 200
    assert c.get("/api/admin/reports", headers=ah).json()["reports"] == []
    assert len(c.get("/api/admin/reports?status=resolved", headers=ah).json()["reports"]) == 1


def test_learner_reports_about_a_mentor_are_visible_to_the_lead(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    c.post("/api/reports", json={"case_id": cid, "detail": "The mentor asked for my number."}, headers=lh)
    assert any(r["case_id"] == cid for r in c.get("/api/admin/reports", headers=ah).json()["reports"])


def test_audit_trail_covers_the_steps(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh)
    c.post(f"/api/mentor-console/cases/{cid}/held", headers=mh)
    c.post(f"/api/mentor-console/cases/{cid}/outcome", headers=mh, json={"notes": "Covered the join order.", "demonstrated": 3})
    with dbm.SessionLocal() as s:
        actions = [a.action for a in s.scalars(select(AuditLog).where(AuditLog.subject_id == cid).order_by(AuditLog.at))]
    assert actions == ["case_accepted", "case_held", "case_outcome"]


def test_demo_mentors_can_be_driven_in_dev_with_the_mock_sign_in_only(env):
    c, mp = env
    r = c.post("/api/dev/mentor-login", json={"mentor_id": "mock_sm_ananya"})
    assert r.status_code == 200
    h = {"Authorization": "Bearer " + r.json()["token"]}
    me = c.get("/api/mentor-console/me", headers=h).json()
    assert me["mentor"]["name"] == "Ananya Rao" and me["mentor"]["is_demo"] is True
    assert c.post("/api/dev/mentor-login", json={"mentor_id": "nobody"}).status_code == 404
    mp.setattr(settings, "env", "prod")
    assert c.post("/api/dev/mentor-login", json={"mentor_id": "mock_sm_ananya"}).status_code == 404
    assert c.get("/api/mentor-console/me", headers=h).status_code == 403                           # and demo mentors have no console in prod


def test_suspended_mentor_loses_the_console(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    assert c.post(f"/api/admin/mentors/{mid}/suspend", json={"note": "Concern raised."}, headers=ah).status_code == 200
    assert c.get("/api/mentor-console/me", headers=mh).status_code == 403
