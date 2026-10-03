"""Every SQL task and every wrong-variant is executed against the real dataset so the content cannot silently rot."""

import json

import pytest

from app.config import CONTENT_DIR
from app.engines import sqlcheck

TASKS = json.loads((CONTENT_DIR / "sql_tasks.json").read_text(encoding="utf-8"))["tasks"]
MISC = {m["id"]: m for m in json.loads((CONTENT_DIR / "misconceptions.json").read_text(encoding="utf-8"))["misconceptions"]}


@pytest.mark.parametrize("task", TASKS, ids=[t["id"] for t in TASKS])
def test_reference_runs_and_is_correct(task):
    v = sqlcheck.evaluate(task, task["reference_query"])
    assert v.correct, (task["id"], v.hints)
    assert v.result and v.result.ok and v.result.rows is not None


@pytest.mark.parametrize("task", [t for t in TASKS if t["variants"]], ids=lambda t: t["id"])
def test_wrong_variants_are_detected_as_their_misconception(task):
    for var in task["variants"]:
        assert var["misconception_id"] in MISC, var["misconception_id"]
        verdict = sqlcheck.evaluate(task, var["query"])
        assert not verdict.correct, (task["id"], var["query"])
        assert verdict.misconception_id == var["misconception_id"], (task["id"], var, verdict)


def test_only_select_is_allowed():
    for q in ["DROP TABLE customers", "DELETE FROM orders", "SELECT 1; DROP TABLE orders",
              "ATTACH DATABASE 'x.db' AS x", "PRAGMA table_info(orders)", "INSERT INTO customers VALUES (9,'x','y','z')"]:
        r = sqlcheck.run_query(q)
        assert not r.ok, q


def test_authorizer_blocks_writes_hidden_in_cte():
    r = sqlcheck.run_query("WITH x AS (SELECT 1) SELECT * FROM x")
    assert r.ok


def test_runaway_query_is_stopped():
    r = sqlcheck.run_query("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT COUNT(*) FROM c")
    assert not r.ok


def test_structure_hint_for_missing_rows():
    task = next(t for t in TASKS if t["id"] == "t_select_1")
    v = sqlcheck.evaluate(task, "SELECT name, city FROM customers WHERE city IS NOT NULL")
    assert not v.correct and v.matched_by == "structure"
    assert any("missing" in h for h in v.hints)


def test_every_misconception_variant_references_known_ids():
    for t in TASKS:
        for var in t["variants"]:
            assert var["misconception_id"] in MISC


def test_memory_bombs_are_refused():
    r = sqlcheck.run_query("SELECT hex(zeroblob(500000000))")
    assert not r.ok
    r = sqlcheck.run_query("SELECT randomblob(900000000)")
    assert not r.ok
    r = sqlcheck.run_query("SELECT load_extension('evil')")
    assert not r.ok
