"""C07: age is self-declared; until it is confirmed a learner counts as a minor. One helper decides, everywhere."""

import re
import time
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import adapters, db as dbm
from app.config import settings
from app.engines import safeguarding
from app.models import Learner

from .test_adapter_contracts import ISS, SB_URL, StaticJWKS, _ec_key
from .test_api import login


def test_no_code_outside_the_helper_compares_a_learners_age_with_18():
    offenders = []
    for f in Path(__file__).resolve().parent.parent.joinpath("app").rglob("*.py"):
        if f.name == "safeguarding.py":
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\b(lr|learner|self)\.age\s*(<|>=|<=|>)\s*18", line):
                offenders.append(f"{f.name}:{n}: {line.strip()}")
    assert not offenders, "use safeguarding.is_minor():\n" + "\n".join(offenders)


def test_is_minor_rules():
    assert safeguarding.is_minor(Learner(id="a", name="x", age=17, settings={}))
    assert not safeguarding.is_minor(Learner(id="b", name="x", age=18, settings={}))
    assert not safeguarding.is_minor(Learner(id="c", name="x", age=30, settings=None))         # old rows: no flag means confirmed
    assert safeguarding.is_minor(Learner(id="d", name="x", age=30, settings={"age_confirmed": False}))


@pytest.fixture()
def google(monkeypatch):
    """The real API in supabase auth mode with a fake JWKS; helper mints a Google-style token (no age in the metadata)."""
    monkeypatch.setattr(settings, "auth_mode", "supabase")
    monkeypatch.setattr(settings, "supabase_url", SB_URL)
    monkeypatch.setattr(settings, "supabase_jwt_secret", None)
    monkeypatch.setattr(settings, "consent_mode", "mock")
    adapters.reset()
    dbm.configure("sqlite://")
    from app.main import create_app
    c = TestClient(create_app())
    priv, jwk = _ec_key("k1")
    adapters.auth()._jwks = StaticJWKS([jwk])

    def token(sub="g-1", meta=None, provider="google"):
        claims = {"sub": sub, "aud": "authenticated", "iss": ISS, "exp": int(time.time()) + 600, "email": f"{sub}@example.com",
                  "app_metadata": {"provider": provider}, "user_metadata": meta if meta is not None else {"full_name": "Gita Rao"}}
        return {"Authorization": "Bearer " + jwt.encode(claims, priv, algorithm="ES256", headers={"kid": "k1"})}
    yield c, token
    monkeypatch.setattr(settings, "auth_mode", "mock")
    adapters.reset()


def test_google_signup_without_age_is_treated_as_a_minor_until_completed(google):
    c, token = google
    h = token()
    me = c.get("/api/me", headers=h).json()
    assert me["name"] == "Gita Rao" and me["is_minor"] is True and me["age_confirmed"] is False and me["needs_profile"] is True
    # learning features still work
    assert c.post("/api/probe/next", json={"count": 1}, headers=h).status_code == 200
    assert c.get("/api/roles", headers=h).status_code == 200
    # mentor features are blocked until the age is known
    for path, body in (("/api/cases", {"category": "technical", "concept_id": "sql_outer_join", "reason": "stuck"}),
                       ("/api/consent/request", {"scope": "mentor_sessions"}),
                       ("/api/consent/self-grant", {"scope": "transcript_share"}),
                       ("/api/consent/grant-demo", {"scope": "mentor_sessions"})):
        r = c.post(path, json=body, headers=h)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "AGE_REQUIRED", path


def test_wellbeing_help_is_never_blocked_by_an_unknown_age(google):
    c, token = google
    r = c.post("/api/cases", json={"category": "technical", "reason": "I feel hopeless and want to die"}, headers=token())
    assert r.status_code == 200 and r.json()["category"] == "wellbeing" and r.json()["helpline"]["number"] == "14416"


def test_completing_the_profile_sets_the_age_once(google):
    c, token = google
    h = token()
    c.get("/api/me", headers=h)
    r = c.post("/api/me/complete-profile", json={"age": 25, "name": "Gita R", "language": "hinglish"}, headers=h)
    me = r.json()
    assert r.status_code == 200 and me["age"] == 25 and me["is_minor"] is False and me["needs_profile"] is False
    assert me["name"] == "Gita R" and me["language"] == "hinglish"
    assert c.post("/api/me/complete-profile", json={"age": 25}, headers=h).status_code == 200          # same value: idempotent
    assert c.post("/api/me/complete-profile", json={"age": 14}, headers=h).status_code == 409          # cannot flip afterwards
    assert c.get("/api/me", headers=h).json()["age"] == 25


def test_a_minor_who_completes_the_profile_gets_the_guardian_rules(google):
    c, token = google
    h = token("g-2")
    c.get("/api/me", headers=h)
    me = c.post("/api/me/complete-profile", json={"age": 15}, headers=h).json()
    assert me["is_minor"] is True and me["needs_profile"] is False
    case = c.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "stuck"}, headers=h).json()
    assert case["status"] == "awaiting_consent"


def test_age_bounds_are_enforced(google):
    c, token = google
    h = token("g-3")
    for bad in (9, 101, "abc", None):
        assert c.post("/api/me/complete-profile", json={"age": bad}, headers=h).status_code == 422
    assert c.post("/api/me/complete-profile", json={}, headers=h).status_code == 422
    assert c.get("/api/me", headers=h).json()["needs_profile"] is True


def test_email_signup_with_an_age_is_confirmed_immediately(google):
    c, token = google
    me = c.get("/api/me", headers=token("e-1", {"name": "Eve", "age": 15, "language": "hindi"}, provider="email")).json()
    assert me["age"] == 15 and me["age_confirmed"] is True and me["needs_profile"] is False and me["is_minor"] is True
    me = c.get("/api/me", headers=token("e-2", {"name": "Adult", "age": 30}, provider="email")).json()
    assert me["is_minor"] is False


def test_nonsense_ages_in_metadata_are_not_trusted(google):
    c, token = google
    for i, age in enumerate((5, 500, "abc", None)):
        me = c.get("/api/me", headers=token(f"n-{i}", {"name": "N", "age": age})).json()
        assert me["needs_profile"] is True and me["is_minor"] is True


def test_complete_profile_requires_sign_in(google):
    c, _ = google
    assert c.post("/api/me/complete-profile", json={"age": 20}).status_code == 401


def test_mock_login_is_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "mock")
    adapters.reset()
    dbm.configure("sqlite://")
    from app.main import create_app
    c = TestClient(create_app())
    h = login(c, age=16)
    me = c.get("/api/me", headers=h).json()
    assert me["is_minor"] is True and me["needs_profile"] is False and me["age_confirmed"] is True
