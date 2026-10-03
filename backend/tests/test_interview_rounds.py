"""Tests for T08: HR / behavioural interview round, role packs, and STAR rubric."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import adapters, db as dbm
from app.config import settings
from app.content import Content, get_content
from app.engines import escalation, explainback, mastery
from app.llm import gateway
from app.models import EvidenceEvent, Learner
from .test_api import login


@pytest.fixture()
def env(monkeypatch):
    dbm.configure("sqlite://")
    for k, v in (
        ("llm_mode", "fake"),
        ("auth_mode", "mock"),
        ("mentors_mode", "mock"),
        ("consent_mode", "mock"),
        ("cohort_mode", "mock"),
    ):
        monkeypatch.setattr(settings, k, v)
    adapters.reset()
    from app.main import create_app
    c = TestClient(create_app())
    yield c, monkeypatch
    adapters.reset()


def test_content_and_packs_integrity():
    """1. Content validation: packs reference existing concept ids; every comm_* concept has notes, an MCQ and a rubric."""
    c = Content()
    errs = c.validate()
    assert errs == []

    comm_concepts = ["comm_self_intro", "comm_star_story", "comm_project_walkthrough"]
    for cid in comm_concepts:
        assert cid in c.concepts
        assert c.concepts[cid].domain == "communication"
        assert c.note(cid).get("summary")
        assert len(c.items_by_concept.get(cid, [])) >= 1
        assert c.has_rubric(cid)

    # Validate packs
    packs = c.get_packs()
    assert len(packs) >= 3
    pack_ids = {p["id"] for p in packs}
    assert {"services_fresher", "product_junior", "internship"} <= pack_ids
    for p in packs:
        assert p["duration_minutes"] > 0
        for cid in p["concept_ids"]:
            assert cid in c.concepts


def test_interview_rounds_queue_order(env):
    """2. round='behavioural' queue starts with comm_self_intro; full has self-intro + behavioural + technical; n_topics respected."""
    client, _ = env
    headers = login(client, "Sneha", 22, "english")

    # Behavioural round
    r_beh = client.post("/api/interview/start", json={"round": "behavioural", "n_topics": 3}, headers=headers).json()
    assert r_beh["round"] == "behavioural"
    assert r_beh["concept_id"] == "comm_self_intro"
    assert r_beh["total"] == 3
    assert "Introduce yourself" in r_beh["topics"][0]

    # Full round
    r_full = client.post("/api/interview/start", json={"round": "full", "n_topics": 5}, headers=headers).json()
    assert r_full["round"] == "full"
    assert r_full["concept_id"] == "comm_self_intro"
    assert r_full["total"] == 5
    # Should include both technical and behavioural
    assert any("Introduce" in t or "Behavioural" in t for t in r_full["topics"])

    # Technical round (default)
    r_tech = client.post("/api/interview/start", json={"round": "technical", "n_topics": 3}, headers=headers).json()
    assert r_tech["round"] == "technical"
    assert not r_tech["concept_id"].startswith("comm_")
    assert not any("comm_" in t for t in r_tech["topics"])


def test_interview_packs_selection(env):
    """Start interview with pack_id queues the pack's blueprint."""
    client, _ = env
    headers = login(client, "Rohan", 21, "english")

    r = client.post("/api/interview/start", json={"pack_id": "services_fresher", "n_topics": 4}, headers=headers).json()
    assert r["pack_id"] == "services_fresher"
    assert r["concept_id"] == "comm_self_intro"
    assert r["total"] == 4


def test_star_scoring_grounded_and_we_vs_i(env):
    """3. STAR scoring: situation + own action + result covers items with grounded quotes; only 'we' does not credit 'action'."""
    client, _ = env
    headers = login(client, "Aarav", 22, "english")

    # Start behavioural interview
    r_start = client.post("/api/interview/start", json={"round": "behavioural", "n_topics": 3}, headers=headers).json()
    sess_id = r_start["session_id"]

    # 1. Answer self intro
    intro_ans = (
        "I am Aarav, a final year computer science student. My core skills are Python, SQL and building backend REST APIs. "
        "Recently I built a scalable e-commerce microservice with PostgreSQL. I am very interested in this role because I want "
        "to work on high-throughput backend services."
    )
    r_intro = client.post("/api/interview/answer", json={"session_id": sess_id, "text": intro_ans}, headers=headers).json()
    assert not r_intro.get("done")
    assert r_intro.get("next_concept_id") == "comm_star_story"

    # 2. Answer STAR story with only "we" (no "I")
    we_only_ans = (
        "The situation was a massive production slowdown. The task was to fix database lock contention. "
        "We investigated the query execution plans and we added composite indexes. "
        "The result was that database latency dropped by 50% and uptime improved. "
        "From this reflection we learned to always profile queries."
    )
    r_star_we = client.post("/api/interview/answer", json={"session_id": sess_id, "text": we_only_ans}, headers=headers).json()
    checklist = r_star_we["checklist"]
    action_item = next(item for item in checklist if item["id"] == "action")
    assert not action_item["covered"], "Action using only 'we' must NOT be credited as personal action"

    # 3. Answer STAR story with explicit personal 'I' actions
    i_ans = (
        "The situation was a severe deadlock on checkout. The task was to eliminate timeouts. "
        "I investigated the lock traces, I identified circular dependency, and I refactored the transaction isolation level. "
        "The result was zero deadlock occurrences and 40% faster checkout. "
        "In reflection, I learned to keep transaction scopes minimal."
    )
    r_star_i = client.post("/api/interview/answer", json={"session_id": sess_id, "text": i_ans}, headers=headers).json()
    checklist_i = r_star_i["checklist"]
    action_item_i = next(item for item in checklist_i if item["id"] == "action")
    assert action_item_i["covered"], "Action using 'I' should be credited"
    assert "I investigated" in action_item_i["evidence"] or "I" in action_item_i["evidence"]


def test_fail_closed_llm_down(env):
    """4. Fail-closed: LLM down => unavailable, no EvidenceEvent."""
    client, monkeypatch = env
    headers = login(client, "Pooja", 23, "english")

    r_start = client.post("/api/interview/start", json={"round": "behavioural", "n_topics": 2}, headers=headers).json()
    sess_id = r_start["session_id"]

    # Mock gateway to raise LLMUnavailable
    def mock_gen(*args, **kwargs):
        raise gateway.LLMUnavailable("Model connection timed out")

    monkeypatch.setattr(gateway, "generate_json", mock_gen)

    r_ans = client.post("/api/interview/answer", json={
        "session_id": sess_id,
        "text": "I am Pooja and I study software engineering. I build backend services."
    }, headers=headers).json()

    assert r_ans.get("unavailable") is True
    assert "grading model is not reachable" in r_ans.get("message", "").lower()

    # Confirm no evidence event was written
    with dbm.SessionLocal() as s:
        events = list(s.scalars(select(EvidenceEvent)))
        assert len(events) == 0


def test_no_invented_percentile_or_scores(env):
    """5. The report contains no percentile/score_out_of_100 keys (assert absence)."""
    client, _ = env
    headers = login(client, "Kunal", 24, "english")

    # Start 1 topic interview
    r_start = client.post("/api/interview/start", json={"round": "behavioural", "n_topics": 1}, headers=headers).json()
    sess_id = r_start["session_id"]

    ans = (
        "I am Kunal, a backend developer specializing in FastAPI and SQL. "
        "I built an analytics ingestion engine that processes streaming telemetry. "
        "I want this role to work on large distributed backend systems."
    )
    r_ans = client.post("/api/interview/answer", json={"session_id": sess_id, "text": ans}, headers=headers).json()
    assert r_ans.get("done") is True
    rep = r_ans.get("report")
    assert rep is not None

    # Assert absence of made-up scores
    forbidden_keys = ["percentile", "percentile_rank", "star_method_score", "score_out_of_100", "clarity_score"]
    for k in forbidden_keys:
        assert k not in rep
        for t in rep.get("topics", []):
            assert k not in t

    assert "checklist_items_covered" in rep
    assert "checklist_items_total" in rep
    assert "behavioural_summary" in rep


def test_prompt_rotation(env):
    """7. Prompt rotation: second attempt gets a different prompt."""
    client, _ = env
    headers = login(client, "Deepak", 23, "english")

    # First attempt
    r1 = client.post("/api/interview/start", json={"round": "behavioural", "n_topics": 1}, headers=headers).json()
    q1 = r1["question"]

    # Complete it
    client.post("/api/interview/answer", json={
        "session_id": r1["session_id"],
        "text": "I am Deepak. I have built databases and REST APIs for two years. I love backend engineering."
    }, headers=headers)

    # Second attempt
    r2 = client.post("/api/interview/start", json={"round": "behavioural", "n_topics": 1}, headers=headers).json()
    q2 = r2["question"]

    assert q1 != q2, f"Prompts should rotate on second attempt! q1: '{q1}', q2: '{q2}'"


def test_persistent_weak_comm_escalation(env):
    """6. Persistent weak comm_star_story after 3 attempts => a career escalation suggestion routed to margdarshak."""
    client, _ = env
    headers = login(client, "Vikas", 22, "english")

    with dbm.SessionLocal() as s:
        lr = s.scalar(select(Learner).where(Learner.name == "Vikas"))
        assert lr is not None

        # Simulate 3 attempts with low score on comm_star_story
        for i in range(3):
            mastery.apply_evidence(
                s, lr, "comm_star_story", "explain_back",
                score=0.2, item_id=f"attempt_{i}", grader="mock", grader_confidence=0.8
            )

        triggers = escalation.check_triggers(s, lr)
        comm_triggers = [t for t in triggers if t.get("concept_id") == "comm_star_story"]
        assert len(comm_triggers) >= 1
        trig = comm_triggers[0]
        assert trig["category"] == "career"
        assert "Margdarshak" in trig["reason"]

        # Check mentor match
        matched = escalation.match_mentor(s, lr, trig["category"], "comm_star_story")
        assert matched is not None
        rec, reasons = matched
        assert rec.tier == "margdarshak"


def test_interview_ext_api_endpoints(env):
    """Packs and history endpoints return correctly."""
    client, _ = env
    headers = login(client, "Tara", 22, "english")

    # GET /api/interview/packs
    res_packs = client.get("/api/interview/packs").json()
    assert "packs" in res_packs
    assert len(res_packs["packs"]) >= 3

    # Start and finish an interview
    r_start = client.post("/api/interview/start", json={"round": "behavioural", "n_topics": 1}, headers=headers).json()
    client.post("/api/interview/answer", json={
        "session_id": r_start["session_id"],
        "text": "I am Tara. I am a backend developer. I created an inventory system."
    }, headers=headers)

    # GET /api/interview/history
    res_hist = client.get("/api/interview/history", headers=headers).json()
    assert "history" in res_hist
    assert len(res_hist["history"]) >= 1
    item = res_hist["history"][0]
    assert item["round"] == "behavioural"
    assert item["session_id"] == r_start["session_id"]
    assert "percentile" not in item
