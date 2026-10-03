"""End-to-end API tests with the offline test grader (SAARTHI_LLM_MODE=fake). Real Gemini is exercised by scripts/check_env.py."""

import pytest
from fastapi.testclient import TestClient

from app import adapters, db as dbm
from app.config import settings
from app.content import get_content


@pytest.fixture()
def client(monkeypatch):
    dbm.configure("sqlite://")
    monkeypatch.setattr(settings, "llm_mode", "fake")
    monkeypatch.setattr(settings, "auth_mode", "mock")
    monkeypatch.setattr(settings, "mentors_mode", "mock")
    monkeypatch.setattr(settings, "consent_mode", "mock")
    monkeypatch.setattr(settings, "cohort_mode", "mock")
    adapters.reset()
    from app.main import create_app
    return TestClient(create_app())


def login(client, name="Priya Sharma", age=20, language="english"):
    r = client.post("/api/auth/dev-login", json={"name": name, "age": age, "language": language})
    assert r.status_code == 200, r.text
    h = {"Authorization": "Bearer " + r.json()["token"]}
    r = client.post("/api/me/onboard", json={"role_id": "backend_developer", "weekly_hours": 6, "horizon_weeks": 12}, headers=h)
    assert r.status_code == 200, r.text
    return h


def right_option(client, h, item):
    c = get_content()
    me = client.get("/api/me", headers=h).json()
    from app.engines.diagnostic import _seed
    from app.models import Learner
    with dbm.SessionLocal() as s:
        lr = s.get(Learner, me["id"])
        opts = c.shuffled_options(c.items[item["id"]], _seed(lr))
    return next(i for i, o in enumerate(opts) if o.get("correct"))


def wrong_option(client, h, item, misconception_id=None):
    c = get_content()
    me = client.get("/api/me", headers=h).json()
    from app.engines.diagnostic import _seed
    from app.models import Learner
    with dbm.SessionLocal() as s:
        lr = s.get(Learner, me["id"])
        opts = c.shuffled_options(c.items[item["id"]], _seed(lr))
    for i, o in enumerate(opts):
        if not o.get("correct") and (misconception_id is None or o.get("misconception_id") == misconception_id):
            return i
    return next(i for i, o in enumerate(opts) if not o.get("correct"))


def test_health_and_roles(client):
    h = client.get("/api/health").json()
    assert h["ok"] and h["test_llm"] and "auth" in h["adapters"]["mock_areas"]
    assert h["counts"]["concepts"] >= 25
    assert any(r["available"] for r in client.get("/api/roles").json())


def test_auth_required(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/dashboard", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_onboarding_builds_initial_roadmap_and_dashboard(client):
    h = login(client)
    d = client.get("/api/dashboard", headers=h).json()
    assert d["role"]["title"] == "Backend Developer"
    assert len(d["graph"]["nodes"]) >= 25 and d["graph"]["edges"]
    assert d["roadmap"]["version"] == 1 and d["roadmap"]["next"]
    assert d["overall"] < 0.3


def test_probe_flow_updates_mastery_and_roadmap_with_misconception(client):
    h = login(client)
    for _ in range(3):
        items = client.post("/api/probe/next", json={"count": 1}, headers=h).json()["items"]
        it = items[0]
        r = client.post("/api/probe/answer", json={"item_id": it["id"], "option_index": right_option(client, h, it), "stated_confidence": 4}, headers=h)
        assert r.status_code == 200 and r.json()["correct"]
    # a wrong, confident answer with a misconception distractor
    it = client.post("/api/probe/next", json={"count": 1, "concept_id": "sql_outer_join"}, headers=h).json()["items"][0]
    idx = wrong_option(client, h, it, "left_join_as_inner") if it["id"] == "q_sql_outer_join_1" else wrong_option(client, h, it)
    r = client.post("/api/probe/answer", json={"item_id": it["id"], "option_index": idx, "stated_confidence": 5}, headers=h).json()
    assert not r["correct"] and r["after"]["roadmap"]["version"] >= 1
    d = client.get("/api/dashboard", headers=h).json()
    assert d["has_evidence"]
    assert d["overall"] > 0


def test_sql_work_product_creates_misconception_and_roadmap_changes_live(client):
    h = login(client)
    bad = ("SELECT c.name, COUNT(o.id) AS n_orders FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name")
    r = client.post("/api/sql/submit", json={"task_id": "t_outer_1", "query": bad, "stated_confidence": 5}, headers=h).json()
    assert r["ran"] and not r["correct"] and r["misconception"]["id"] == "left_join_as_inner"
    assert "very sure" in (r["calibration"] or "")
    assert r["after"]["roadmap"]["changed"]
    mis = client.get("/api/misconceptions", headers=h).json()["active"]
    assert mis and mis[0]["status"] == "confirmed"
    rm = client.get("/api/roadmap", headers=h).json()
    item = next(i for i in rm["items"] if i["concept_id"] == "sql_outer_join")
    assert item["kind"] == "fix_misconception" and "misconception" in item["why"].lower()
    plan = client.get("/api/misconception-library/left_join_as_inner/plan", headers=h).json()
    assert plan["steps"]
    ok = "SELECT c.name, COUNT(o.id) AS n_orders FROM customers c LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name"
    r2 = client.post("/api/sql/submit", json={"task_id": "t_outer_1", "query": ok}, headers=h).json()
    assert r2["correct"]


def test_sql_run_blocks_writes(client):
    h = login(client)
    r = client.post("/api/sql/run", json={"query": "DROP TABLE customers"}, headers=h).json()
    assert not r["ok"]
    r = client.post("/api/sql/run", json={"query": "SELECT COUNT(*) FROM customers"}, headers=h).json()
    assert r["ok"] and r["rows"] == [[8]]
    schema = client.get("/api/sql/schema", headers=h).json()
    assert {t["table"] for t in schema["tables"]} == {"customers", "orders", "order_items", "products"}


def test_teach_explain_uses_strategy_and_records_outcome(client):
    h = login(client)
    r = client.post("/api/teach/explain", json={"concept_id": "sql_outer_join"}, headers=h).json()
    assert r["strategy"] and r["text"] and r["why_strategy"] and r["source"] == "curated"
    assert r["has_rubric"] and r["has_tasks"]
    hi = client.patch("/api/me", json={"language": "hindi"}, headers=h).json()
    assert hi["language"] == "hindi"
    r2 = client.post("/api/teach/explain", json={"concept_id": "sql_outer_join", "strategy": "text"}, headers=h).json()
    assert "LEFT JOIN" in r2["text"]


GOOD_JOIN = ("A LEFT JOIN keeps every customer from the left table. If a customer has no orders the order columns are NULL. "
             "An INNER JOIN would drop the unmatched customers. A WHERE condition on the orders table removes the NULL rows so put it in ON.")
BAD_JOIN = "A left join only returns the rows that match, it is basically inner join. I think it only gives rows present in both tables."


def test_explainback_scores_with_verified_coverage(client):
    h = login(client)
    s = client.post("/api/explainback/start", json={"concept_id": "sql_outer_join"}, headers=h).json()
    out = client.post("/api/explainback/answer", json={"session_id": s["session_id"], "text": GOOD_JOIN, "stated_confidence": 3}, headers=h).json()
    assert out["done"] or out["followup"]
    if not out["done"]:
        out = client.post("/api/explainback/finish", json={"session_id": s["session_id"]}, headers=h).json()
        final = out["final"]
    else:
        final = out["final"]
    assert final["score"] >= 0.7 and len(final["covered"]) >= 3
    assert final["mastery"]["moved_mastery"]


def test_explainback_misconception_needs_a_readback_then_confirm_flows_to_roadmap(client):
    h = login(client)
    s = client.post("/api/explainback/start", json={"concept_id": "sql_outer_join"}, headers=h).json()
    out = client.post("/api/explainback/answer", json={"session_id": s["session_id"], "text": BAD_JOIN}, headers=h).json()
    assert out["readback"] and "statement" in out["readback"]
    mis = client.get("/api/misconceptions", headers=h).json()["active"]
    assert mis and mis[0]["status"] == "candidate"        # not a flag yet
    rid = out["readback"]["instance_id"]
    c = client.post(f"/api/misconceptions/{rid}/confirm", json={"confirmed": True}, headers=h).json()
    assert c["status"] == "confirmed"
    fin = client.post("/api/explainback/finish", json={"session_id": s["session_id"]}, headers=h).json()["final"]
    assert fin["score"] <= 0.6                              # a stated misconception caps the score


def test_explainback_dismissing_the_readback_removes_the_flag(client):
    h = login(client)
    s = client.post("/api/explainback/start", json={"concept_id": "sql_outer_join"}, headers=h).json()
    out = client.post("/api/explainback/answer", json={"session_id": s["session_id"], "text": BAD_JOIN}, headers=h).json()
    client.post(f"/api/misconceptions/{out['readback']['instance_id']}/confirm", json={"confirmed": False}, headers=h)
    assert client.get("/api/misconceptions", headers=h).json()["active"] == []


def test_explainback_fails_closed_when_llm_is_unavailable(client, monkeypatch):
    h = login(client)
    s = client.post("/api/explainback/start", json={"concept_id": "sql_outer_join"}, headers=h).json()
    monkeypatch.setattr(settings, "llm_mode", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", None)
    out = client.post("/api/explainback/answer", json={"session_id": s["session_id"], "text": GOOD_JOIN}, headers=h).json()
    assert out["unavailable"] and "final" not in out
    g = client.get("/api/genome", headers=h).json()
    assert not any(e["source"] == "explain_back" for e in g["evidence"])  # nothing was recorded


def test_short_answer_asks_for_more(client):
    h = login(client)
    s = client.post("/api/explainback/start", json={"concept_id": "sql_null"}, headers=h).json()
    out = client.post("/api/explainback/answer", json={"session_id": s["session_id"], "text": "idk"}, headers=h).json()
    assert out.get("insufficient")


def test_interview_mode_runs_coverage_driven_topics(client):
    h = login(client)
    st = client.post("/api/interview/start", json={"n_topics": 2}, headers=h).json()
    assert st["total"] == 2 and "mock interview" in st["question"]
    sid = st["session_id"]
    answers = {
        "sql_inner_join": "An inner join combines orders and customers where the ON condition matches the customer id. Rows without a match are not in the result. If you forget the ON condition every row pairs with every row, a cartesian product.",
    }
    done = False
    for _ in range(8):
        out = client.post("/api/interview/answer", json={"session_id": sid, "text": GOOD_JOIN + " Also an inner join matches rows on the ON condition and a missing ON gives a cartesian product with every row paired."}, headers=h).json()
        if out.get("done"):
            done = True
            break
    assert done and out["report"]["topics"]
    assert "percentile" not in str(out["report"]).lower()


def test_stuck_button_with_objective_query(client):
    h = login(client)
    q = "SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.id = NULL"
    r = client.post("/api/stuck", json={"text": "my query returns nothing", "query": q, "task_id": "t_outer_2"}, headers=h).json()
    assert r["cause"] == "misconception" and r["misconception"]["id"] == "null_comparison"
    r2 = client.post("/api/stuck", json={"text": "I get a 403 but I am logged in, why"}, headers=h).json()
    assert r2["concept_id"] and r2["explanation"]


def test_roadmap_what_if_why_not_and_genome(client):
    h = login(client)
    wi = client.post("/api/roadmap/what-if", json={"weekly_hours": 2, "horizon_weeks": 4}, headers=h).json()
    assert wi["scenario"]["n_items"] < wi["current"]["n_items"] or wi["diff"]["removed"]
    wn = client.get("/api/roadmap/why-not/sql_outer_join", headers=h).json()
    assert wn["code"] in ("IN_PLAN", "BUDGET", "LOW_PRIORITY")
    g = client.get("/api/genome", headers=h).json()
    assert "strategy_note" in g and g["goal"] == "Backend Developer"
    d = client.post("/api/genome/dispute", json={"concept_id": "sql_select", "kind": "already_know", "note": "I use it daily"}, headers=h).json()
    assert d["recheck"] and "options" in d["recheck"]


def test_dev_time_travel_creates_due_reviews(client):
    h = login(client)
    for _ in range(3):
        for t in ("t_select_1",):
            client.post("/api/sql/submit", json={"task_id": t, "query": "SELECT name, city FROM customers"}, headers=h)
    client.post("/api/dev/advance-time", json={"days": 20}, headers=h)
    due = client.get("/api/reviews/due", headers=h).json()
    assert due["due"] and due["items"]


def test_mentor_flow_adult_gets_matched_and_replies_are_labelled_mock(client):
    h = login(client, age=22)
    client.post("/api/dev/simulate-struggle", json={"concept_id": "sql_outer_join"}, headers=h)
    cases = client.get("/api/cases", headers=h).json()
    assert cases["suggestions"] and cases["suggestions"][0]["trigger"] == "persistent_struggle"
    case = client.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "still failing", "trigger": "persistent_struggle"}, headers=h).json()
    assert case["status"] == "accepted" and case["tier"] == "skill_mentor" and case["mock_mentor"]
    assert case["match_reasons"]
    detail = client.get(f"/api/cases/{case['case_id']}", headers=h).json()
    assert detail["report"]["concept"]["name"].startswith("LEFT")
    assert detail["report"]["strategies_tried"] and detail["report"]["suggested_intervention"]
    m = client.post(f"/api/cases/{case['case_id']}/messages", json={"text": "my left join drops some customers"}, headers=h).json()
    assert m["sent"] and m["mock_reply"] and "join" in m["mentor_reply"].lower()
    bad = client.post(f"/api/cases/{case['case_id']}/messages", json={"text": "call me on 9876543210 or whatsapp"}, headers=h).json()
    assert bad["blocked"]
    sim = client.post(f"/api/cases/{case['case_id']}/simulate-session", json={"rating": 0.8}, headers=h).json()
    assert sim["case"]["status"] == "followup" and sim["mastery"]["moved_mastery"]
    fu = client.post(f"/api/cases/{case['case_id']}/followup", headers=h).json()
    assert fu["status"] == "closed" and "gain" in fu["followup"]


def test_career_case_routes_to_a_margdarshak(client):
    h = login(client, age=22, language="hindi")
    case = client.post("/api/cases", json={"reason": "I need help preparing for my first job interview", "note": "career guidance"}, headers=h).json()
    assert case["tier"] == "margdarshak" and case["category"] == "career"
    assert case["mentor"]["tier"] == "margdarshak"


def test_minor_needs_guardian_consent_before_matching(client):
    h = login(client, age=16)
    case = client.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "stuck"}, headers=h).json()
    assert case["status"] == "awaiting_consent" and case["consent_required"]
    assert client.post(f"/api/cases/{case['case_id']}/messages", json={"text": "hello"}, headers=h).status_code == 409
    g = client.post("/api/consent/grant-demo", json={"scope": "mentor_sessions"}, headers=h).json()
    assert g["status"] == "granted" and g["mock"] and g["resumed"] and g["resumed"][0]["status"] == "accepted"


@pytest.fixture()
def client_real_consent(monkeypatch):
    """Same app but with the REAL consent adapter (SAARTHI_CONSENT=db): guardian approval must come from a guardian."""
    dbm.configure("sqlite://")
    monkeypatch.setattr(settings, "llm_mode", "fake")
    monkeypatch.setattr(settings, "auth_mode", "mock")
    monkeypatch.setattr(settings, "mentors_mode", "mock")
    monkeypatch.setattr(settings, "consent_mode", "db")
    monkeypatch.setattr(settings, "cohort_mode", "mock")
    adapters.reset()
    from app.main import create_app
    yield TestClient(create_app())
    adapters.reset()


def test_a_minor_cannot_approve_their_own_guardian_consent(client_real_consent):
    """Regression (security): the real consent flow used to return the signed guardian token to the minor's own session,
    who could then post it to /api/consent/guardian and approve themselves."""
    client = client_real_consent
    assert not adapters.consent().is_mock
    h = login(client, age=15)
    assert client.get("/api/me", headers=h).json()["consent"]["mentor_sessions"] == "pending"

    req = client.post("/api/consent/request", json={"scope": "mentor_sessions"}, headers=h).json()
    assert req["needs_guardian"] and "guardian_token" not in req

    case = client.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "stuck"}, headers=h).json()
    assert case["status"] == "awaiting_consent" and case["consent_required"]
    assert not case.get("guardian_token")                       # never exposed to the learner either

    # none of the learner-facing responses contains anything usable as a guardian token
    for body in (client.get("/api/consent", headers=h).text, client.get("/api/me", headers=h).text,
                 client.get(f"/api/cases/{case['case_id']}", headers=h).text):
        assert "guardian_token" not in body

    # and guessing/forging one does not work
    for forged in ("", "forged", "a.b.c"):                        # the learner-authenticated approval route no longer exists
        r = client.post("/api/consent/guardian", json={"token": forged, "scope": "mentor_sessions"}, headers=h)
        assert r.status_code in (404, 405)
        assert client.get(f"/api/guardian/preview?token={forged}").status_code == 404
    assert client.post("/api/consent/grant-demo", json={"scope": "mentor_sessions"}, headers=h).status_code == 400
    assert client.post("/api/consent/self-grant", json={"scope": "mentor_sessions"}, headers=h).status_code == 403
    assert client.get("/api/me", headers=h).json()["consent"]["mentor_sessions"] == "pending"
    assert client.post(f"/api/cases/{case['case_id']}/messages", json={"text": "hello"}, headers=h).status_code == 409


def test_wellbeing_message_goes_to_safeguarding_not_a_mentor(client):
    h = login(client, age=19)
    case = client.post("/api/cases", json={"category": "technical", "reason": "I feel hopeless and want to die"}, headers=h).json()
    assert case["category"] == "wellbeing" and case["tier"] == "safeguarding" and case["helpline"]["number"] == "14416"
    assert "mentor" not in case or not case.get("mentor")


def test_cohort_view_is_aggregated_and_marked_mock(client):
    h = login(client)
    co = client.get("/api/cohort", headers=h).json()
    assert co["is_mock"] and co["n_learners"] == 24 and co["top_misconceptions"] and co["concepts"]
    assert "transcript" in co["privacy_note"].lower()


def test_export_and_delete(client):
    h = login(client)
    client.post("/api/sql/submit", json={"task_id": "t_select_1", "query": "SELECT name, city FROM customers"}, headers=h)
    ex = client.get("/api/me/export", headers=h).json()
    assert ex["evidence"]
    assert client.delete("/api/me", headers=h).json()["deleted"]
    assert client.get("/api/me", headers=h).status_code == 401


def test_prod_mode_hides_dev_tools(client, monkeypatch):
    h = login(client)
    monkeypatch.setattr(settings, "env", "prod")
    assert client.post("/api/dev/advance-time", json={"days": 1}, headers=h).status_code == 404
    assert client.post("/api/dev/simulate-struggle", json={}, headers=h).status_code == 404


def test_users_cannot_read_each_others_cases(client):
    h1 = login(client, age=22)
    h2 = login(client, name="Other", age=22)
    case = client.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "x"}, headers=h1).json()
    assert client.get(f"/api/cases/{case['case_id']}", headers=h2).status_code == 404


def test_demo_history_seed_is_labelled_simulated_and_builds_a_starting_state(client):
    h = login(client)
    r = client.post("/api/dev/seed-demo", headers=h).json()
    assert r["seeded"]
    g = client.get("/api/genome", headers=h).json()
    assert g["evidence"] and all(e["grader"] == "simulated" for e in g["evidence"])
    d = client.get("/api/dashboard", headers=h).json()
    assert d["overall"] > 0.25 and d["levels"]["not_assessed"] < 25


def test_spa_serving_does_not_shadow_the_api_or_allow_path_traversal(client):
    assert client.get("/api/health").json()["ok"]
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and "not found" in r.text.lower()   # the wording differs when frontend/dist is not built (CI)
    r = client.get("/..%2f..%2fbackend%2f.env")
    assert r.status_code in (200, 404) and "GEMINI" not in r.text
    r = client.get("/learn/sql_outer_join")
    assert r.status_code in (200, 404)
