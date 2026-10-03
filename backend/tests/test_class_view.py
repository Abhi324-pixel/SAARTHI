"""The class view shows only real learners who opted in, never by name, and nothing at all until enough have joined."""

from __future__ import annotations

import pytest

from app import adapters, db as dbm
from app.adapters.impl import MIN_CLASS_SIZE
from app.config import settings
from app.models import CohortMember
from .test_api import client, login  # noqa: F401


@pytest.fixture()
def real(client, monkeypatch):
    monkeypatch.setattr(settings, "cohort_mode", "db")
    adapters.reset()
    return client


def make(client, i):
    h = login(client, name=f"Real Person {i}")
    # some real evidence so the aggregate has something to show
    client.post("/api/sql/submit", json={"task_id": "t_select_1", "query": "SELECT name, city FROM customers"}, headers=h)
    return h


def test_real_mode_starts_with_nobody_and_shows_nothing(real):
    h = login(real)
    co = real.get("/api/cohort", headers=h).json()
    assert co["is_mock"] is False and co["hidden"] is True and co["n_learners"] == 0
    assert co["concepts"] == [] and co["top_misconceptions"] == [] and co["needs_attention"] == []
    st = real.get("/api/cohort/membership", headers=h).json()
    assert st == {"member": False, "joined": 0, "min_learners": MIN_CLASS_SIZE}


def test_a_small_group_stays_hidden_and_a_big_enough_one_shows_only_pseudonyms(real):
    hs = [make(real, i) for i in range(MIN_CLASS_SIZE)]
    for h in hs[:-1]:
        assert real.post("/api/cohort/membership", headers=h).json()["member"] is True
    co = real.get("/api/cohort", headers=hs[0]).json()
    assert co["hidden"] is True and co["n_learners"] == MIN_CLASS_SIZE - 1 and co["concepts"] == []        # one short of enough
    real.post("/api/cohort/membership", headers=hs[-1])
    co = real.get("/api/cohort", headers=hs[0]).json()
    assert co["hidden"] is False and co["n_learners"] == MIN_CLASS_SIZE and co["concepts"] and co["is_mock"] is False
    names = " ".join(n["display_name"] for n in co["needs_attention"])
    assert "Real Person" not in names and "Demo learner" not in names                                          # never a real or made-up name
    assert real.delete("/api/cohort/membership", headers=hs[0]).json()["member"] is False
    assert real.get("/api/cohort", headers=hs[1]).json()["hidden"] is True                                      # leaving takes effect at once


def test_joining_twice_is_harmless_and_membership_is_exported_and_deleted_with_the_account(real):
    h = login(real)
    me = real.get("/api/me", headers=h).json()
    real.post("/api/cohort/membership", headers=h)
    assert real.post("/api/cohort/membership", headers=h).json()["joined"] == 1
    ex = real.get("/api/me/export", headers=h).json()
    assert (ex.get("more", ex))["class_view_membership"] == {"in_class_view": True}
    assert real.delete("/api/me", headers=h).status_code == 200
    with dbm.SessionLocal() as s:
        assert s.query(CohortMember).filter_by(learner_id=me["id"]).count() == 0


def test_sign_in_is_required(real):
    assert real.get("/api/cohort/membership").status_code == 401
    assert real.post("/api/cohort/membership").status_code == 401
    assert real.get("/api/cohort").status_code == 401
