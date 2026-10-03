"""Practical challenges: curated SQL starters really run, model output is validated, personal focus is never saved."""

from __future__ import annotations

import sqlite3

import pytest

from app import db as dbm
from app.config import CONTENT_DIR
from app.engines import challenge_generator as cg
from app.llm import gateway
from app.models import Learner, MisconceptionInstance
from app.models_ext.G01 import VakhChallenge
from .test_api import client, login  # noqa: F401


def test_curated_sql_starters_run_on_the_practice_database():
    con = sqlite3.connect(":memory:")
    con.executescript((CONTENT_DIR / "shop.sql").read_text(encoding="utf-8"))
    for cid, bp in cg.CHALLENGE_BLUEPRINTS.items():
        code = bp.get("starter_code", "")
        if cid.startswith("sql_"):
            rows = con.execute(code.rstrip().rstrip(";")).fetchall()          # raises if a table or column does not exist
            assert rows is not None, cid


GOOD = {"title": "Order Totals by City", "objective": "Show how much each city spends.", "difficulty": "Intermediate",
        "requirements": ["Join orders to customers.", "Group by customers.city.", "Order by total descending."],
        "starter_code": "SELECT 1", "expected_output": "One row per city with its total.",
        "evaluation_criteria": [{"criterion": "Correct join", "weight": 2}, {"criterion": "Correct grouping", "weight": 2}]}


def test_model_challenge_is_validated_and_normalised():
    v = cg._validate(dict(GOOD), "Aggregate functions")
    assert v["difficulty"] == "intermediate" and [x["weight"] for x in v["evaluation_criteria"]] == [0.5, 0.5]
    assert cg._validate({**GOOD, "requirements": ["only one"]}, "x") is None                      # too few requirements
    assert cg._validate({**GOOD, "evaluation_criteria": []}, "x") is None
    assert cg._validate({**GOOD, "title": ""}, "x") is None
    assert cg._validate({**GOOD, "requirements": ["see https://example.com", "b", "c"]}, "x") is None   # no links
    assert cg._validate({"title": "x"}, "x") is None                                              # missing fields: refused, not repaired
    assert cg._validate({**GOOD, "difficulty": "godlike"}, "x")["difficulty"] == "intermediate"


def test_generated_challenge_is_stored_once_and_personal_focus_is_not(client, monkeypatch):
    calls = []

    def fake(task, system, prompt, schema, **kw):
        calls.append(prompt)
        return dict(GOOD)
    monkeypatch.setattr(gateway, "generate_json", fake)
    h = login(client)
    me = client.get("/api/me", headers=h).json()
    with dbm.SessionLocal() as s:
        s.add(MisconceptionInstance(learner_id=me["id"], concept_id="sql_aggregates", misconception_id="count_star_with_left_join",
                                    status="confirmed", cycles=1, statement="x"))
        s.commit()
    r1 = client.get("/api/vakh/challenges/sql_aggregates", headers=h).json()
    assert r1["title"] == "Order Totals by City" and len(calls) == 1
    assert "stationery" in calls[0].lower() or "customers" in calls[0]                            # the real practice tables were given to the model
    # a second learner gets the same stored challenge, without the first learner's personal focus
    h2 = login(client, name="Other Person")
    r2 = client.get("/api/vakh/challenges/sql_aggregates", headers=h2).json()
    assert r2["id"] == r1["id"] and len(calls) == 1 and "personal_focus" not in r2
    assert not any("Focus area for you" in x for x in r2["requirements"])
    with dbm.SessionLocal() as s:
        stored = s.query(VakhChallenge).filter_by(concept_id="sql_aggregates").one()
        assert not any("Focus area for you" in x for x in stored.requirements)                    # never saved


def test_model_down_uses_a_plain_honest_fallback(client, monkeypatch):
    def boom(*a, **k):
        raise gateway.LLMUnavailable("down")
    monkeypatch.setattr(gateway, "generate_json", boom)
    h = login(client)
    r = client.get("/api/vakh/challenges/git_basics", headers=h).json()
    assert r["title"].startswith("Build something small with") and len(r["requirements"]) == 3


def test_old_placeholder_challenge_is_replaced(client, monkeypatch):
    monkeypatch.setattr(gateway, "generate_json", lambda *a, **k: dict(GOOD))
    h = login(client)
    with dbm.SessionLocal() as s:
        s.add(VakhChallenge(concept_id="sql_sorting_limit", title="Hands-on Implementation Challenge: ORDER BY", objective="old", difficulty="beginner",
                            requirements=["a", "b", "c"], starter_code="", expected_output="old", evaluation_criteria=[], vakh_form_id="vakh_form_sql_sorting_limit"))
        s.commit()
    r = client.get("/api/vakh/challenges/sql_sorting_limit", headers=h).json()
    assert r["title"] == "Order Totals by City" and r["vakh_form_id"] == "vakh_form_sql_sorting_limit"
