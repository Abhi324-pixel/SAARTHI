import json

import pytest

from app import db as dbm
from app.config import CONTENT_DIR
from app.content import get_content
from app.engines import diagnostic, mastery, misconception
from app.models import Learner, new_id


@pytest.fixture()
def s():
    dbm.configure("sqlite://")
    dbm.init_db()
    sess = dbm.SessionLocal()
    yield sess
    sess.close()


def learner(s):
    lr = Learner(id=new_id("t_"), name="Priya", role_id="backend_developer", onboarded=True)
    s.add(lr)
    s.flush()
    mastery.ensure_states(s, lr)
    return lr


def option_index_for(lr, item_id, predicate):
    c = get_content()
    opts = c.shuffled_options(c.items[item_id], diagnostic._seed(lr))
    return next(i for i, o in enumerate(opts) if predicate(o))


def test_probe_returns_public_items_without_answers(s):
    lr = learner(s)
    items = diagnostic.next_probe(s, lr, count=3)
    assert len(items) == 3
    for it in items:
        assert "correct" not in json.dumps(it) and "misconception" not in json.dumps(it)


def test_probe_avoids_repeating_items(s):
    lr = learner(s)
    seen = set()
    for _ in range(6):
        it = diagnostic.next_probe(s, lr, count=1)[0]
        assert it["id"] not in seen
        seen.add(it["id"])
        diagnostic.grade_mcq(s, lr, it["id"], 0)


def test_correct_answer_moves_mastery_up(s):
    lr = learner(s)
    idx = option_index_for(lr, "q_sql_outer_join_1", lambda o: o.get("correct"))
    r = diagnostic.grade_mcq(s, lr, "q_sql_outer_join_1", idx, stated_confidence=3)
    assert r["correct"] and r["mastery"]["p_after"] > r["mastery"]["p_before"]


def test_distractor_creates_a_misconception_candidate_and_second_signal_confirms(s):
    lr = learner(s)
    idx = option_index_for(lr, "q_sql_outer_join_1", lambda o: o.get("misconception_id") == "left_join_as_inner")
    r = diagnostic.grade_mcq(s, lr, "q_sql_outer_join_1", idx)
    assert not r["correct"] and r["misconception"]["status"] == "candidate"
    idx2 = option_index_for(lr, "q_sql_inner_join_2", lambda o: o.get("misconception_id") == "left_join_as_inner")
    # a different concept's question that carries the same misconception id would confirm; use the same id via outer join q 2/3
    idx3 = option_index_for(lr, "q_sql_inner_join_2", lambda o: o.get("misconception_id") == "left_join_as_inner")
    r2 = diagnostic.grade_mcq(s, lr, "q_sql_inner_join_2", idx3)
    assert r2["misconception"]["status"] == "confirmed"


def test_confident_wrong_answer_gets_a_calibration_note(s):
    lr = learner(s)
    idx = option_index_for(lr, "q_sql_null_1", lambda o: o.get("misconception_id") == "null_comparison")
    r = diagnostic.grade_mcq(s, lr, "q_sql_null_1", idx, stated_confidence=5)
    assert "very sure" in r["calibration"]


def test_work_product_correct_and_misconception_flow(s):
    lr = learner(s)
    wrong = "SELECT c.name, COUNT(o.id) AS n_orders FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name"
    r = diagnostic.submit_work_product(s, lr, "t_outer_1", wrong)
    assert r["ran"] and not r["correct"]
    assert r["misconception"]["id"] == "left_join_as_inner"
    assert r["misconception"]["instance"]["status"] == "confirmed"  # objective evidence confirms immediately
    ok = "SELECT c.name, COUNT(o.id) AS n_orders FROM customers c LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name"
    r2 = diagnostic.submit_work_product(s, lr, "t_outer_1", ok)
    assert r2["correct"]
    assert any(a["status"] == "correcting" for a in r2["misconception_progress"])
    r3 = diagnostic.submit_work_product(s, lr, "t_outer_1", ok)
    assert any(a["status"] == "pending_verify" for a in r3["misconception_progress"])


def test_misconception_only_resolves_after_a_delayed_check(s):
    lr = learner(s)
    bad = "SELECT c.name FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL"
    good = "SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL"
    diagnostic.submit_work_product(s, lr, "t_outer_2", bad)
    diagnostic.submit_work_product(s, lr, "t_outer_2", good)
    diagnostic.submit_work_product(s, lr, "t_outer_2", good)  # -> pending_verify
    same_day = diagnostic.submit_work_product(s, lr, "t_outer_2", good)
    assert not any(a["status"] == "resolved" for a in same_day["misconception_progress"])
    lr.clock_offset_days = 2
    later = diagnostic.submit_work_product(s, lr, "t_outer_2", good)
    assert any(a["status"] == "resolved" for a in later["misconception_progress"])
    assert not misconception.describe(s, lr.id)


def test_error_signature_misconception_is_detected(s):
    lr = learner(s)
    r = diagnostic.submit_work_product(s, lr, "t_having_1",
                                       "SELECT customer_id, COUNT(*) AS n FROM orders WHERE COUNT(*) > 1 GROUP BY customer_id")
    assert not r["ran"] and r["misconception"]["id"] == "where_vs_having"


def test_unrunnable_query_is_not_scored_as_understanding(s):
    lr = learner(s)
    r = diagnostic.submit_work_product(s, lr, "t_select_1", "SELEC name FROM customers")
    assert not r["ran"] and r["mastery"] is None


def test_readback_dismissal(s):
    lr = learner(s)
    sig = misconception.register_signal(s, lr, "left_join_as_inner", "explain_back", statement="LEFT JOIN returns only matching rows")
    assert sig["needs_readback"] and sig["status"] == "candidate"
    out = misconception.confirm_statement(s, lr, sig["instance_id"], False)
    assert out["status"] == "dismissed"
    assert not misconception.describe(s, lr.id)


def test_all_variants_have_a_correction_plan():
    c = get_content()
    for mid in c.misconceptions:
        plan = misconception.correction_plan(mid)
        assert plan["steps"]
