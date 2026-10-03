"""D01: real guardian consent. The link goes to the guardian's inbox only; the learner can never approve themselves."""

import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import adapters, db as dbm, ratelimit
from app.config import settings
from app.models import Learner, now
from app.models_ext.D01 import ConsentToken, GuardianRequest

from .test_api import login


@pytest.fixture()
def client(monkeypatch):
    dbm.configure("sqlite://")
    for k, v in (("llm_mode", "fake"), ("auth_mode", "mock"), ("mentors_mode", "mock"), ("consent_mode", "db"),
                 ("cohort_mode", "mock"), ("mail_mode", "mock")):
        monkeypatch.setattr(settings, k, v)
    monkeypatch.setattr(settings, "public_base_url", "http://saarthi.test")
    adapters.reset()
    ratelimit.reset()
    adapters.MockMailer.outbox.clear()
    from app.main import create_app
    yield TestClient(create_app())
    adapters.reset()


def guardian_token():
    msg = adapters.MockMailer.outbox[-1]
    m = re.search(r"/guardian/([\w\-\.:]+)", msg["text"])
    assert m, msg["text"]
    return m.group(1)


def ask(client, h, email="parent@example.com", lang="english"):
    return client.post("/api/consent/request", json={"scope": "mentor_sessions", "guardian_email": email, "lang": lang}, headers=h)


def status_of(client, h):
    return client.get("/api/me", headers=h).json()["consent"]["mentor_sessions"]


def age_requests(minutes):
    with dbm.SessionLocal() as s:
        for r in s.scalars(select(GuardianRequest)):
            r.created_at = now() - timedelta(minutes=minutes)
        s.commit()


def test_happy_path_request_preview_approve_resumes_the_waiting_case(client):
    h = login(client, age=15)
    case = client.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "stuck"}, headers=h).json()
    assert case["status"] == "awaiting_consent"
    r = ask(client, h)
    assert r.status_code == 200 and r.json()["status"] == "requested" and r.json()["guardian_hint"] == "p***@example.com"
    assert "guardian_token" not in r.text and status_of(client, h) == "requested"
    assert len(adapters.MockMailer.outbox) == 1 and adapters.MockMailer.outbox[0]["to"] == "parent@example.com"
    assert "http://saarthi.test/guardian/" in adapters.MockMailer.outbox[0]["text"]

    tok = guardian_token()
    pv = client.get("/api/guardian/preview", params={"token": tok}).json()
    assert pv["learner_first_name"] == "Priya" and "mentor" in pv["scope_text"] and pv["mentors_see"]
    assert set(pv) == {"learner_first_name", "lang", "scope_text", "mentors_see", "expires_at"}      # nothing else leaks

    d = client.post("/api/guardian/decision", json={"token": tok, "decision": "approve"})
    assert d.status_code == 200 and d.json()["withdraw_token"]
    assert status_of(client, h) == "granted"
    assert client.get(f"/api/cases/{case['case_id']}", headers=h).json()["status"] in ("accepted", "matched")


def test_links_are_single_use_and_all_invalid_links_look_the_same(client):
    h = login(client, age=15)
    ask(client, h)
    tok = guardian_token()
    assert client.post("/api/guardian/decision", json={"token": tok, "decision": "approve"}).status_code == 200
    posts, gets = set(), set()
    for t in (tok, "forged", "a.b.c", tok[:-2] + "xx"):
        r = client.post("/api/guardian/decision", json={"token": t, "decision": "approve"})
        pv = client.get("/api/guardian/preview", params={"token": t})
        assert r.status_code == 404 and pv.status_code == 404
        posts.add(r.text)
        gets.add(pv.text)
    assert len(posts) == 1 and len(gets) == 1


def test_an_expired_link_is_rejected(client, monkeypatch):
    h = login(client, age=15)
    ask(client, h)
    tok = guardian_token()
    import itsdangerous
    real = itsdangerous.URLSafeTimedSerializer.loads
    monkeypatch.setattr(itsdangerous.URLSafeTimedSerializer, "loads",
                        lambda self, s, max_age=None, **kw: real(self, s, max_age=-1, **kw))
    assert client.post("/api/guardian/decision", json={"token": tok, "decision": "approve"}).status_code == 404


def test_decline_blocks_mentors_and_allows_a_new_request_later(client):
    h = login(client, age=15)
    ask(client, h)
    assert client.post("/api/guardian/decision", json={"token": guardian_token(), "decision": "decline"}).status_code == 200
    assert status_of(client, h) == "declined"
    with dbm.SessionLocal() as s:
        assert s.scalars(select(GuardianRequest)).first().guardian_email == ""        # address removed once declined
    age_requests(120)
    case = client.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "x"}, headers=h).json()
    assert case["status"] == "awaiting_consent"
    assert ask(client, h, "other@example.com").status_code == 200


def test_withdraw_revokes_and_pauses_active_cases(client):
    h = login(client, age=15)
    ask(client, h)
    wt = client.post("/api/guardian/decision", json={"token": guardian_token(), "decision": "approve"}).json()["withdraw_token"]
    case = client.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "x"}, headers=h).json()
    assert case["status"] in ("accepted", "matched")
    assert client.post("/api/guardian/withdraw", json={"token": wt}).status_code == 200
    assert status_of(client, h) == "revoked"
    assert client.get(f"/api/cases/{case['case_id']}", headers=h).json()["status"] == "awaiting_consent"
    assert client.post(f"/api/cases/{case['case_id']}/messages", json={"text": "hi"}, headers=h).status_code == 409
    assert client.post("/api/guardian/withdraw", json={"token": wt}).status_code == 404       # used once
    assert client.post("/api/guardian/decision", json={"token": wt, "decision": "approve"}).status_code == 404   # wrong purpose


def test_the_approve_link_cannot_be_used_to_withdraw(client):
    h = login(client, age=15)
    ask(client, h)
    assert client.post("/api/guardian/withdraw", json={"token": guardian_token()}).status_code == 404


def test_request_validation_and_limits(client):
    h = login(client, age=15)
    assert ask(client, h, "not-an-email").status_code == 422
    with dbm.SessionLocal() as s:
        lr = s.scalars(select(Learner)).first()
        lr.email = "me@example.com"
        s.commit()
    assert ask(client, h, "ME@example.com").status_code == 422                        # not the learner's own address
    assert ask(client, h, "a@example.com").status_code == 200
    assert ask(client, h, "a@example.com").status_code == 429                         # same address within the cooldown
    assert ask(client, h, "b@example.com").status_code == 200
    assert ask(client, h, "c@example.com").status_code == 200
    assert ask(client, h, "d@example.com").status_code == 429                         # 4th request today
    assert len(adapters.MockMailer.outbox) == 3


def test_a_new_request_supersedes_the_old_link(client):
    h = login(client, age=15)
    ask(client, h)
    old = guardian_token()
    age_requests(30)
    ask(client, h, "second@example.com")
    assert client.get("/api/guardian/preview", params={"token": old}).status_code == 404
    assert client.get("/api/guardian/preview", params={"token": guardian_token()}).status_code == 200


def test_adults_do_not_need_a_guardian(client):
    h = login(client, age=22)
    r = ask(client, h).json()
    assert r["needs_guardian"] is False and not adapters.MockMailer.outbox


def test_a_minor_cannot_approve_via_any_authenticated_route(client):
    h = login(client, age=15)
    ask(client, h)
    tok = guardian_token()
    # even holding the real token (e.g. read from the dev outbox) the old authenticated route is gone
    assert client.post("/api/consent/guardian", json={"token": tok, "scope": "mentor_sessions"}, headers=h).status_code in (404, 405)
    assert client.post("/api/consent/self-grant", json={"scope": "mentor_sessions"}, headers=h).status_code == 403
    assert client.post("/api/consent/grant-demo", json={"scope": "mentor_sessions"}, headers=h).status_code == 400
    assert status_of(client, h) == "requested"


def test_public_endpoints_are_throttled(client):
    for _ in range(20):
        assert client.get("/api/guardian/preview", params={"token": "x"}).status_code == 404
    assert client.get("/api/guardian/preview", params={"token": "x"}).status_code == 429


def test_export_masks_the_address_and_delete_removes_the_rows(client):
    h = login(client, age=15)
    ask(client, h)
    ex = client.get("/api/me/export", headers=h).json()
    reqs = ex["more"]["guardian_consent_requests"]
    assert reqs[0]["guardian"] == "p***@example.com" and "parent@example.com" not in str(ex)
    assert client.delete("/api/me", headers=h).json()["deleted"]
    with dbm.SessionLocal() as s:
        assert s.scalars(select(GuardianRequest)).first() is None and s.scalars(select(ConsentToken)).first() is None


def test_audit_trail_has_the_steps_and_no_addresses(client):
    from app.models_ext.audit import AuditLog
    h = login(client, age=15)
    ask(client, h)
    client.post("/api/guardian/decision", json={"token": guardian_token(), "decision": "approve"})
    with dbm.SessionLocal() as s:
        rows = list(s.scalars(select(AuditLog).order_by(AuditLog.at)))
    assert [r.action for r in rows] == ["consent_requested", "consent_approved"]
    assert "example.com" not in str([r.detail for r in rows])


def test_dev_outbox_is_available_with_the_mock_mailer_only_outside_prod(client, monkeypatch):
    h = login(client, age=15)
    ask(client, h)
    assert client.get("/api/dev/outbox", headers=h).json()["messages"][0]["to"] == "parent@example.com"
    monkeypatch.setattr(settings, "env", "prod")
    assert client.get("/api/dev/outbox", headers=h).status_code == 404


def test_hindi_email_and_preview(client):
    h = login(client, age=15, language="hindi")
    ask(client, h, lang="hindi")
    assert "मेंटर" in adapters.MockMailer.outbox[0]["subject"] + adapters.MockMailer.outbox[0]["text"]
    assert "मेंटर" in client.get("/api/guardian/preview", params={"token": guardian_token()}).json()["scope_text"]


def test_smtp_mail_mode_refuses_to_start_without_settings(monkeypatch):
    monkeypatch.setattr(settings, "mail_mode", "smtp")
    monkeypatch.setattr(settings, "smtp_host", None)
    monkeypatch.setattr(settings, "mail_from", None)
    adapters.reset()
    with pytest.raises(RuntimeError):
        adapters.mailer()
    adapters.reset()


def test_smtp_mailer_sends_through_starttls(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["conn"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            sent["tls"] = True

        def login(self, u, p):
            sent["login"] = u

        def send_message(self, msg):
            sent["msg"] = msg

    from app.adapters import impl
    monkeypatch.setattr(impl.smtplib, "SMTP", FakeSMTP)
    for k, v in (("smtp_host", "smtp.test"), ("smtp_port", 587), ("smtp_user", "u"), ("smtp_password", "p"),
                 ("mail_from", "noreply@saarthi.test")):
        monkeypatch.setattr(settings, k, v)
    impl.SmtpMailer().send("g@example.com", "Hello — नमस्ते", "body")
    assert sent["conn"] == ("smtp.test", 587) and sent["tls"] and sent["login"] == "u"
    assert sent["msg"]["To"] == "g@example.com" and "नमस्ते" in sent["msg"]["Subject"]
