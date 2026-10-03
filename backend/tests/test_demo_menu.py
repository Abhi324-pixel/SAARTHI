"""The dev-only Demo accounts menu: lists only the fixed fake accounts, and only in a local mock-auth setup."""

import pytest
from fastapi.testclient import TestClient

from app import adapters, db as dbm
from app.adapters.impl import seed_mentors
from app.config import settings
from app.models import Learner


@pytest.fixture()
def env(monkeypatch):
    dbm.configure("sqlite://")
    for k, v in (("llm_mode", "fake"), ("auth_mode", "mock"), ("mentors_mode", "db"), ("consent_mode", "mock"), ("cohort_mode", "mock")):
        monkeypatch.setattr(settings, k, v)
    adapters.reset()
    from app.main import create_app
    c = TestClient(create_app())
    with dbm.SessionLocal() as s:
        seed_mentors(s)
        s.add(Learner(id="mock_demo_riya", name="Riya (demo, age 15)", age=15, is_mock=True))
        s.add(Learner(id="mock_other", name="Someone else", age=30, is_mock=True))
        s.commit()
    yield c, monkeypatch
    adapters.reset()


def test_lists_only_fixed_demo_accounts(env):
    c, _ = env
    ids = {a["id"] for a in c.get("/api/dev/demo-accounts").json()["accounts"]}
    assert ids == {"mock_demo_riya", "mock_sm_ananya", "mock_sm_vikram"}


def test_login_gives_a_working_token_and_refuses_other_ids(env):
    c, _ = env
    r = c.post("/api/dev/demo-login", json={"mentor_id": "mock_demo_riya"})
    assert r.status_code == 200
    me = c.get("/api/me", headers={"Authorization": "Bearer " + r.json()["token"]}).json()
    assert me["id"] == "mock_demo_riya" and me["is_minor"] is True
    assert c.post("/api/dev/demo-login", json={"mentor_id": "mock_other"}).status_code == 404


def test_mentor_demo_login_opens_the_console(env):
    c, _ = env
    t = c.post("/api/dev/demo-login", json={"mentor_id": "mock_sm_ananya"}).json()["token"]
    assert c.get("/api/me", headers={"Authorization": "Bearer " + t}).json()["is_mentor"] is True


def test_hidden_in_prod_and_in_real_auth(env):
    c, mp = env
    mp.setattr(settings, "env", "prod")
    assert c.get("/api/dev/demo-accounts").status_code == 404
    assert c.post("/api/dev/demo-login", json={"mentor_id": "mock_demo_riya"}).status_code == 404
    mp.setattr(settings, "env", "dev")
    mp.setattr(settings, "auth_mode", "supabase")
    mp.setattr(settings, "supabase_url", "https://example.supabase.co")
    adapters.reset()
    assert c.get("/api/dev/demo-accounts").status_code == 404
