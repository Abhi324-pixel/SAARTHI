"""C01: mentor sign-up, human verification record, pledge. Nothing becomes 'verified' except by an admin's decision."""

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import adapters, db as dbm
from app.config import settings
from app.content import get_content
from app.engines import mentor_apply as ma
from app.models import Learner, Mentor
from app.models_ext.C01 import MentorApplication, MentorCheck

from .test_api import login


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


def profile(**over):
    p = {"tier_requested": "skill_mentor", "name": "Ravi Menon", "headline": "Backend engineer, 7 years in payments",
         "bio": "I build Python and PostgreSQL services and enjoy explaining joins and indexes to beginners.",
         "years_experience": 7, "organisation": "Acme Pay", "expertise": ["sql_outer_join", "sql", "rest_apis"],
         "languages": ["english", "hinglish"], "availability": ["Mon 18:00", "Sat 11:00"]}
    p.update(over)
    return p


def answer_screen(c, h, correct=True):
    q = c.get("/api/mentor/apply/screen", headers=h).json()
    answers = {}
    content = get_content()
    app_id = None
    with dbm.SessionLocal() as s:
        app_id = s.scalars(select(MentorApplication)).first().id
    for it in q["mcq"]:
        opts = content.shuffled_options(content.items[it["id"]], app_id)
        answers[it["id"]] = next(i for i, o in enumerate(opts) if bool(o.get("correct")) == correct)
    open_ = {o["key"]: "I would ask them to show the query, predict the rows, and find the mismatch themselves." for o in q["open"]}
    return c.post("/api/mentor/apply/screen", json={"answers": answers, "open": open_}, headers=h)


def complete_application(c, h, **over):
    assert c.put("/api/mentor/apply", json=profile(**over), headers=h).status_code == 200
    assert answer_screen(c, h).status_code == 200
    version = c.get("/api/mentor/apply", headers=h).json()["pledge"]["version"]
    assert c.post("/api/mentor/apply/pledge", json={"version": version}, headers=h).status_code == 200
    return c.post("/api/mentor/apply/submit", headers=h)


def make_admin(c, monkeypatch, name="Admin"):
    h = login(c, name=name)
    me = c.get("/api/me", headers=h).json()
    monkeypatch.setattr(settings, "admins", me["id"])
    return h, me["id"]


def test_apply_routes_are_off_while_mentors_are_mock(env):
    c, mp = env
    mp.setattr(settings, "mentors_mode", "mock")
    h = login(c)
    assert c.get("/api/mentor/apply", headers=h).status_code == 404
    assert c.put("/api/mentor/apply", json=profile(), headers=h).status_code == 404


def test_full_application_then_admin_approval_creates_a_verified_mentor(env):
    c, mp = env
    h = login(c, name="Ravi Menon")
    r = complete_application(c, h)
    assert r.status_code == 200 and r.json()["status"] == "submitted"
    ah, admin_id = make_admin(c, mp)
    apps = c.get("/api/admin/mentor-applications", headers=ah).json()["applications"]
    assert len(apps) == 1 and apps[0]["screen_result"]["mcq"]["asked"] == 5 and apps[0]["status"] == "submitted"
    d = c.post(f"/api/admin/mentor-applications/{apps[0]['id']}/decision", headers=ah,
               json={"decision": "approve", "note": "Spoke to him, references checked.", "checks": [{"kind": "identity"}, {"kind": "reference", "note": "ex-manager"}]})
    assert d.status_code == 200 and d.json()["status"] == "approved"
    with dbm.SessionLocal() as s:
        m = s.get(Mentor, apps[0]["user_id"])
        assert m.verification_status == "verified" and not m.is_mock and m.tier == "skill_mentor" and m.expertise == ["sql_outer_join", "sql", "rest_apis"]
        assert {k.kind for k in s.scalars(select(MentorCheck))} == {"identity", "reference"}
    assert any(x["name"] == "Ravi Menon" for x in c.get("/api/mentors", headers=h).json()["mentors"])   # now in the directory


def test_nothing_is_verified_without_an_admin(env):
    c, mp = env
    h = login(c, name="Ravi Menon")
    complete_application(c, h)
    with dbm.SessionLocal() as s:
        assert s.scalars(select(Mentor).where(Mentor.is_mock.is_(False))).first() is None


def test_non_admins_cannot_use_admin_routes_and_email_is_never_trusted(env):
    c, mp = env
    h = login(c, name="Someone")
    for path in ("/api/admin/mentor-applications", "/api/admin/mentors"):
        assert c.get(path, headers=h).status_code == 403
    assert c.post("/api/admin/mentors/x/suspend", json={"note": "n"}, headers=h).status_code == 403
    mp.setattr(settings, "admins", "someone@example.com")        # an e-mail in the list must not grant access
    assert c.get("/api/admin/mentor-applications", headers=h).status_code == 403
    assert c.get("/api/admin/mentor-applications").status_code == 401


def test_role_comes_from_the_server_not_from_token_metadata(env):
    c, mp = env
    h = login(c)
    forged = jwt.encode({"sub": "someone-else", "mock": True, "user_metadata": {"role": "admin"}}, settings.secret, algorithm="HS256")
    assert c.get("/api/admin/mentors", headers={"Authorization": "Bearer " + forged}).status_code == 403


def test_pledge_is_required_and_versioned(env):
    c, mp = env
    h = login(c)
    c.put("/api/mentor/apply", json=profile(), headers=h)
    answer_screen(c, h)
    assert c.post("/api/mentor/apply/submit", headers=h).status_code == 422                    # pledge missing
    assert c.post("/api/mentor/apply/pledge", json={"version": "0-old"}, headers=h).status_code == 409
    assert "code of conduct" in c.post("/api/mentor/apply/submit", headers=h).json()["detail"]
    v = c.get("/api/mentor/apply", headers=h).json()["pledge"]
    assert v["promises"] and all(p["en"] and p["hi"] for p in v["promises"])
    assert c.post("/api/mentor/apply/pledge", json={"version": v["version"]}, headers=h).status_code == 200
    assert c.post("/api/mentor/apply/submit", headers=h).status_code == 200


def test_submit_lists_what_is_missing(env):
    c, mp = env
    h = login(c)
    c.put("/api/mentor/apply", json={"tier_requested": "skill_mentor", "name": "R"}, headers=h)
    r = c.post("/api/mentor/apply/submit", headers=h)
    assert r.status_code == 422 and all(w in r.json()["detail"] for w in ("headline", "bio", "topic", "availability", "screen"))


def test_profile_validation(env):
    c, mp = env
    h = login(c)
    for bad in ({"tier_requested": "king"}, {"expertise": ["not_a_topic"]}, {"expertise": ["sql"] * 3 + [f"t{i}" for i in range(11)]},
                {"languages": ["klingon"]}, {"languages": []}, {"availability": ["Monday evening"]},
                {"availability": ["Mon 25:00"]}, {"years_experience": 99}, {"years_experience": "many"}):
        assert c.put("/api/mentor/apply", json=profile(**bad), headers=h).status_code == 422, bad
    assert c.put("/api/mentor/apply", json=profile(headline="  Backend   engineer  with spaces "), headers=h).json()["headline"] == "Backend engineer with spaces"


def test_screen_is_input_to_a_human_not_a_gate_and_never_touches_a_learner_twin(env):
    c, mp = env
    h = login(c)
    c.put("/api/mentor/apply", json=profile(), headers=h)
    r = answer_screen(c, h, correct=False)
    assert r.status_code == 200 and r.json()["mcq_correct"] == 0                         # failing answers do not block submission
    from app.models import EvidenceEvent
    with dbm.SessionLocal() as s:
        assert s.scalars(select(EvidenceEvent)).first() is None
    assert c.post("/api/mentor/apply/screen", json={"answers": {}, "open": {}}, headers=h).status_code == 422


def test_margdarshak_screen_has_open_questions_only(env):
    c, mp = env
    h = login(c)
    c.put("/api/mentor/apply", json=profile(tier_requested="margdarshak", expertise=["career", "interview"]), headers=h)
    q = c.get("/api/mentor/apply/screen", headers=h).json()
    assert q["mcq"] == [] and len(q["open"]) == 3
    r = c.post("/api/mentor/apply/screen", json={"answers": {}, "open": {o["key"]: "I would listen first, then explain the options calmly." for o in q["open"]}}, headers=h)
    assert r.status_code == 200


def test_cannot_edit_while_submitted_but_can_after_needs_info(env):
    c, mp = env
    h = login(c)
    complete_application(c, h)
    assert c.put("/api/mentor/apply", json=profile(headline="Changed headline here"), headers=h).status_code == 409
    ah, _ = make_admin(c, mp)
    app_id = c.get("/api/admin/mentor-applications", headers=ah).json()["applications"][0]["id"]
    assert c.post(f"/api/admin/mentor-applications/{app_id}/decision", json={"decision": "needs_info", "note": ""}, headers=ah).status_code == 422   # note required
    assert c.post(f"/api/admin/mentor-applications/{app_id}/decision", json={"decision": "needs_info", "note": "Please add your employer."}, headers=ah).status_code == 200
    mine = c.get("/api/mentor/apply", headers=h).json()["application"]
    assert mine["status"] == "needs_info" and mine["reviewer_note"] == "Please add your employer."
    assert c.put("/api/mentor/apply", json=profile(headline="Changed headline here"), headers=h).status_code == 200


def test_applications_are_private_to_their_owner(env):
    c, mp = env
    h1, h2 = login(c, name="One"), login(c, name="Two")
    c.put("/api/mentor/apply", json=profile(name="One Mentor"), headers=h1)
    assert c.get("/api/mentor/apply", headers=h2).json()["application"] is None
    out = c.get("/api/mentor/apply", headers=h1).json()["application"]
    assert "user_id" not in out and "email" not in out and "screen_result" not in out


def test_rejected_cannot_be_approved_and_unknown_check_kinds_are_refused(env):
    c, mp = env
    h = login(c)
    complete_application(c, h)
    ah, _ = make_admin(c, mp)
    app_id = c.get("/api/admin/mentor-applications", headers=ah).json()["applications"][0]["id"]
    assert c.post(f"/api/admin/mentor-applications/{app_id}/decision", json={"decision": "approve", "note": "x", "checks": [{"kind": "vibes"}]}, headers=ah).status_code == 422
    assert c.post(f"/api/admin/mentor-applications/{app_id}/decision", json={"decision": "reject", "note": "Not a fit."}, headers=ah).status_code == 200
    assert c.post(f"/api/admin/mentor-applications/{app_id}/decision", json={"decision": "approve", "note": "ok"}, headers=ah).status_code == 409


def approved_mentor(c, mp, checks):
    h = login(c, name="Real Mentor")
    complete_application(c, h, expertise=["sql_outer_join", "sql"], name="Real Mentor")
    ah, _ = make_admin(c, mp)
    app = c.get("/api/admin/mentor-applications", headers=ah).json()["applications"][0]
    c.post(f"/api/admin/mentor-applications/{app['id']}/decision", headers=ah,
           json={"decision": "approve", "note": "ok", "checks": [{"kind": k} for k in checks]})
    return ah, app["user_id"]


def remove_demo_mentors():
    with dbm.SessionLocal() as s:
        for m in s.scalars(select(Mentor).where(Mentor.is_mock.is_(True))):
            s.delete(m)
        s.commit()


def test_minors_only_match_real_mentors_with_all_required_checks(env):
    c, mp = env
    ah, mentor_id = approved_mentor(c, mp, ["identity"])             # not enough for minors
    remove_demo_mentors()
    adult = login(c, name="Adult", age=22)
    case = c.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "stuck"}, headers=adult).json()
    assert case["status"] == "matched" and case["mentor"]["id"] == mentor_id             # adults can be matched
    minor = login(c, name="Minor", age=15)
    c.post("/api/consent/grant-demo", json={"scope": "mentor_sessions"}, headers=minor)
    case = c.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "stuck"}, headers=minor).json()
    assert case["status"] == "open" and "mentor" not in case                              # queued: no mentor has the required checks


def test_minor_can_be_matched_once_all_checks_are_recorded(env):
    c, mp = env
    ah, mentor_id = approved_mentor(c, mp, ["identity", "reference", "police_verification"])
    remove_demo_mentors()
    minor = login(c, name="Minor", age=15)
    c.post("/api/consent/grant-demo", json={"scope": "mentor_sessions"}, headers=minor)
    case = c.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "stuck"}, headers=minor).json()
    assert case["status"] == "matched" and case["mentor"]["id"] == mentor_id
    mentors = c.get("/api/admin/mentors", headers=ah).json()
    assert mentors["mentors"][0]["can_take_minors"] is True


def test_suspending_a_mentor_removes_them_and_rematches_their_cases(env):
    c, mp = env
    ah, mentor_id = approved_mentor(c, mp, ["identity", "reference", "police_verification"])
    adult = login(c, name="Adult", age=22)
    case = c.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "stuck"}, headers=adult).json()
    first = case["mentor"]["id"]
    assert c.post(f"/api/admin/mentors/{first if first == mentor_id else mentor_id}/suspend", json={"note": ""}, headers=ah).status_code == 422
    r = c.post(f"/api/admin/mentors/{mentor_id}/suspend", json={"note": "Concern raised."}, headers=ah)
    assert r.status_code == 200 and r.json()["status"] == "suspended"
    with dbm.SessionLocal() as s:
        assert s.get(Mentor, mentor_id).verification_status == "suspended"
    again = c.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "second"}, headers=adult).json()
    assert again.get("mentor", {}).get("id") != mentor_id
    assert c.post("/api/admin/mentors/mock_sm_ananya/suspend", json={"note": "x"}, headers=ah).status_code == 404   # demo mentors are not managed here


def test_account_dependency_does_not_create_a_learner(env):
    c, mp = env
    from app.adapters.impl import MockAuth
    with dbm.SessionLocal() as s:
        tok = jwt.encode({"sub": "mock_ghost", "name": "Ghost", "mock": True}, settings.secret, algorithm="HS256")
        p = MockAuth().verify_token(tok)
        assert p.learner_id == "mock_ghost" and s.get(Learner, "mock_ghost") is None
    h = {"Authorization": "Bearer " + tok}
    assert c.get("/api/mentor/apply", headers=h).status_code == 200
    with dbm.SessionLocal() as s:
        assert s.get(Learner, "mock_ghost") is None                                       # applying did not make a learner


def test_pledge_file_is_complete():
    p = ma.pledge()
    assert "pending-review" in p["version"] and len(p["promises"]) >= 6
    assert all(x["id"] and x["en"] and x["hi"] for x in p["promises"])
    assert any(x["id"] == "inside_app" for x in p["promises"]) and any(x["id"] == "report_concerns" for x in p["promises"])
