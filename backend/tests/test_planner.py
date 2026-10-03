import pytest

from app import db as dbm
from app.content import get_content
from app.engines import diagnostic, mastery, planner
from app.models import Learner, new_id


@pytest.fixture()
def s():
    dbm.configure("sqlite://")
    dbm.init_db()
    sess = dbm.SessionLocal()
    yield sess
    sess.close()


def learner(s, **kw):
    lr = Learner(id=new_id("t_"), name="Priya", role_id="backend_developer", onboarded=True, **kw)
    s.add(lr)
    s.flush()
    mastery.ensure_states(s, lr)
    return lr


def test_roadmap_respects_prerequisites():
    pass


def test_every_item_comes_after_its_prerequisites(s):
    lr = learner(s)
    rm = planner.build(s, lr)
    c = get_content()
    pos = {i["concept_id"]: i["order"] for i in rm["items"] if i["kind"] != "review"}
    for cid, o in pos.items():
        for p in c.prereqs(cid):
            if p in pos:
                assert pos[p] < o, (p, cid)


def test_fresh_learner_gets_a_full_plan_with_reasons(s):
    lr = learner(s)
    rm = planner.build(s, lr)
    assert len(rm["items"]) >= 20
    for it in rm["items"]:
        assert it["reasons"] and planner.why_text(it)
    assert 0 <= rm["summary"]["readiness_now"] < rm["summary"]["readiness_after"] <= 1


def test_small_budget_drops_low_value_items_but_keeps_prerequisite_closure(s):
    lr = learner(s, weekly_hours=1.0, horizon_weeks=4)
    rm = planner.build(s, lr)
    c = get_content()
    chosen = {i["concept_id"] for i in rm["items"] if i["kind"] != "review"}
    assert rm["summary"]["dropped"]
    for cid in chosen:
        for a in c.ancestors(cid):
            if a in {i["concept_id"] for i in rm["items"]} or True:
                pass
    # nothing is scheduled without its needed prerequisites also being scheduled or already at target
    views = mastery.concept_views(s, lr)
    req = c.role("backend_developer")["requirements"]
    for cid in chosen:
        for a in c.ancestors(cid):
            if a in req and views[a]["p"] < req[a]["target"] * 0.95:
                assert a in chosen, (a, "missing prerequisite of", cid)


def test_mastered_concepts_leave_the_plan_and_misconception_goes_first(s):
    lr = learner(s)
    for _ in range(4):
        mastery.apply_evidence(s, lr, "sql_select", "work_product", correct=True)
        mastery.apply_evidence(s, lr, "sql_relational_model", "work_product", correct=True)
    rm = planner.build(s, lr)
    ids = [i["concept_id"] for i in rm["items"]]
    assert "sql_select" not in ids or next(i for i in rm["items"] if i["concept_id"] == "sql_select")["status"] == "done"
    bad = "SELECT c.name, COUNT(o.id) AS n_orders FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name"
    diagnostic.submit_work_product(s, lr, "t_outer_1", bad)
    rm2 = planner.build(s, lr)
    item = next(i for i in rm2["items"] if i["concept_id"] == "sql_outer_join")
    assert item["kind"] == "fix_misconception"
    assert any(r["type"] == "MISCONCEPTION_FIX" for r in item["reasons"])


def test_refresh_versions_and_diffs(s):
    lr = learner(s)
    v1 = planner.refresh(s, lr, "setup")
    assert v1["version"] == 1 and v1["changed"]
    for _ in range(5):
        mastery.apply_evidence(s, lr, "http_basics", "work_product", correct=True)
        mastery.apply_evidence(s, lr, "py_basics", "work_product", correct=True)
    v2 = planner.refresh(s, lr, "your last answers")
    assert v2["version"] == 2 and v2["changed"]
    assert v2["diff"]["removed"] or v2["diff"]["moved"] or v2["diff"]["added"]
    again = planner.refresh(s, lr, "nothing new")
    assert not again["changed"] and again["version"] == 2


def test_why_not(s):
    lr = learner(s)
    for _ in range(5):
        mastery.apply_evidence(s, lr, "py_basics", "work_product", correct=True)
    assert planner.why_not(s, lr, "py_basics")["code"] in ("AT_TARGET", "IN_PLAN")
    small = learner(s, weekly_hours=1.0, horizon_weeks=2)
    dropped = planner.build(s, small)["summary"]["dropped"]
    assert dropped
    out = planner.why_not(s, small, dropped[0]["concept_id"])
    assert out["code"] == "BUDGET" and "minutes" in out["text"]


def test_what_if_shows_more_content_with_more_hours(s):
    lr = learner(s, weekly_hours=1.0, horizon_weeks=4)
    wi = planner.what_if(s, lr, 10.0, 12)
    assert wi["scenario"]["n_items"] > wi["current"]["n_items"]
    assert wi["diff"]["added"]


def test_today_mission_prioritises_misconception_then_reviews(s):
    lr = learner(s)
    for _ in range(3):
        mastery.apply_evidence(s, lr, "sql_select", "work_product", correct=True)
    lr.clock_offset_days = 20
    bad = "SELECT c.name, COUNT(o.id) AS n_orders FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name"
    diagnostic.submit_work_product(s, lr, "t_outer_1", bad)
    m = planner.today_mission(s, lr)
    assert m[0]["type"] == "fix_misconception"
    assert 1 <= len(m) <= 3
