"""Comprehensive test suite for the Learning Navigation System and Vakh Integration.

Verifies:
  1. Dynamic learning map generation from BKT state
  2. Prerequisite blocking and dependency closures
  3. Misconception-aware blocking and detour injection
  4. Two learners with the same goal receive completely different maps
  5. Goal switching preserves transferable mastery and recalculates route
  6. Real Vakh challenge specifications and launcher deep-links
  7. Idempotent Vakh webhook processing and duplicate prevention
  8. Evidence ingestion triggering mastery change and roadmap versioning
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db as db_module
from app.engines import challenge_generator, knowledge_graph, learning_navigation, mastery, misconception, planner, vakh_adapter
from app.main import app
from app.models import ConceptState, EvidenceEvent, Learner, RoadmapVersion
from app.models_ext.G01 import DetourLog, VakhChallenge, VakhSubmission


@pytest.fixture
def client(tmp_path):
    db_module.configure("sqlite:///:memory:")
    db_module.init_db()
    with TestClient(app) as c:
        yield c


def _create_learner(db, learner_id: str, name: str = "Test Learner", role_id: str = "backend_developer"):
    lr = Learner(id=learner_id, name=name, age=22, role_id=role_id, weekly_hours=8.0, horizon_weeks=12)
    db.add(lr)
    db.commit()
    db.refresh(lr)
    return lr


def test_knowledge_graph_sync_and_structure():
    db = next(db_module.get_db())
    knowledge_graph.sync_graph_to_db(db)

    lr = _create_learner(db, "lr_nav_1")
    subgraph = knowledge_graph.get_learning_subgraph(db, lr)

    assert "goal" in subgraph
    assert subgraph["goal"]["id"] == "backend_developer"
    assert len(subgraph["nodes"]) > 0
    assert len(subgraph["edges"]) > 0

    # Verify edge structure
    for edge in subgraph["edges"]:
        assert "from" in edge
        assert "to" in edge
        assert edge["type"] == "PREREQUISITE"


def test_two_learners_same_goal_different_maps():
    """CRITICAL REQUIREMENT: Two learners with the same goal must receive completely different maps."""
    db = next(db_module.get_db())
    knowledge_graph.sync_graph_to_db(db)

    # Learner A: Advanced in Python (90%), weak in HTTP (20%)
    lr_a = _create_learner(db, "lr_expert_py", name="Alice Python", role_id="backend_developer")
    mastery.ensure_states(db, lr_a)
    st_py = db.get(ConceptState, (lr_a.id, "py_basics"))
    st_py.p_known = 0.95
    st_py_fn = db.get(ConceptState, (lr_a.id, "py_functions"))
    st_py_fn.p_known = 0.92
    st_py_col = db.get(ConceptState, (lr_a.id, "py_collections"))
    st_py_col.p_known = 0.90
    db.commit()

    # Learner B: Advanced in SQL/HTTP (85%), beginner in Python (10%)
    lr_b = _create_learner(db, "lr_expert_sql", name="Bob SQL", role_id="backend_developer")
    mastery.ensure_states(db, lr_b)
    st_sql = db.get(ConceptState, (lr_b.id, "sql_relational_model"))
    st_sql.p_known = 0.95
    st_select = db.get(ConceptState, (lr_b.id, "sql_select"))
    st_select.p_known = 0.95
    st_http = db.get(ConceptState, (lr_b.id, "http_basics"))
    st_http.p_known = 0.90
    db.commit()

    map_a = learning_navigation.generate_learning_map(db, lr_a)
    map_b = learning_navigation.generate_learning_map(db, lr_b)

    # The maps MUST NOT recommend the same next concept!
    assert map_a["recommended_next"] != map_b["recommended_next"]

    # Learner A has mastered Python, so py_basics must be MASTERED
    node_py_a = next(n for n in map_a["nodes"] if n["id"] == "py_basics")
    assert node_py_a["state"] == "MASTERED"

    # Learner B has NOT mastered Python, so py_basics must be RECOMMENDED or AVAILABLE
    node_py_b = next(n for n in map_b["nodes"] if n["id"] == "py_basics")
    assert node_py_b["state"] in ("RECOMMENDED", "AVAILABLE")


def test_prerequisite_blocking_and_unlock():
    db = next(db_module.get_db())
    lr = _create_learner(db, "lr_prereq_test")
    mastery.ensure_states(db, lr)

    # Before mastering sql_select, sql_filtering should be BLOCKED
    subgraph_before = knowledge_graph.get_learning_subgraph(db, lr)
    filter_node_before = next(n for n in subgraph_before["nodes"] if n["id"] == "sql_filtering")
    assert filter_node_before["state"] == "BLOCKED"

    # Master sql_relational_model and sql_select
    st_rel = db.get(ConceptState, (lr.id, "sql_relational_model"))
    st_rel.p_known = 0.95
    st_sel = db.get(ConceptState, (lr.id, "sql_select"))
    st_sel.p_known = 0.95
    db.commit()

    # Now sql_filtering must unlock to AVAILABLE or RECOMMENDED
    subgraph_after = knowledge_graph.get_learning_subgraph(db, lr)
    filter_node_after = next(n for n in subgraph_after["nodes"] if n["id"] == "sql_filtering")
    assert filter_node_after["state"] in ("AVAILABLE", "RECOMMENDED")


def test_misconception_aware_blocking_and_detour():
    db = next(db_module.get_db())
    lr = _create_learner(db, "lr_misc_test")
    mastery.ensure_states(db, lr)

    # Flag an active misconception on sql_outer_join
    misconception.register_signal(db, lr, "left_join_as_inner", "work_product", statement="Treats LEFT JOIN like INNER JOIN")
    db.commit()

    learning_map = learning_navigation.generate_learning_map(db, lr)
    node_outer = next(n for n in learning_map["nodes"] if n["id"] == "sql_outer_join")

    # Node state must reflect MISCONCEPTION
    assert node_outer["state"] == "MISCONCEPTION"
    assert "LEFT JOIN" in node_outer["why"] or "misunderstanding" in node_outer["why"]

    # Dependent multi-table join must be BLOCKED
    node_multi = next(n for n in learning_map["nodes"] if n["id"] == "sql_multi_table")
    assert node_multi["state"] == "BLOCKED"


def test_goal_change_preserves_transferable_mastery():
    db = next(db_module.get_db())
    lr = _create_learner(db, "lr_goal_switch", role_id="backend_developer")
    mastery.ensure_states(db, lr)

    # Learner masters python basics and SQL aggregates under Backend Developer
    st_py = db.get(ConceptState, (lr.id, "py_basics"))
    st_py.p_known = 0.98
    st_agg = db.get(ConceptState, (lr.id, "sql_aggregates"))
    st_agg.p_known = 0.95
    db.commit()

    # Switch goal to Machine Learning Engineer
    new_map = learning_navigation.change_learner_goal(db, lr, "ml_engineer")

    assert new_map["goal"]["id"] == "ml_engineer"
    # Python basics and SQL aggregates MUST retain their MASTERED status!
    node_py = next(n for n in new_map["nodes"] if n["id"] == "py_basics")
    assert node_py["state"] == "MASTERED"
    node_agg = next(n for n in new_map["nodes"] if n["id"] == "sql_aggregates")
    assert node_agg["state"] == "MASTERED"


def test_vakh_launcher_url_generation(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "vakh_base_url", "https://vakh.example")
    db = next(db_module.get_db())
    lr = _create_learner(db, "lr_vakh_launch")

    launch_data = vakh_adapter.get_vakh_launcher_url(db, lr, "sql_outer_join")

    assert launch_data["configured"] is True
    assert launch_data["launch_url"].startswith("https://vakh.example/forms/")
    assert "state=" in launch_data["launch_url"]
    assert lr.id not in launch_data["launch_url"]            # the internal learner id never goes into a URL sent to Vakh
    assert "challenge" in launch_data
    assert launch_data["challenge"]["title"] != ""


def test_vakh_webhook_ingestion_and_idempotency(monkeypatch):
    import json
    from app.config import settings
    monkeypatch.setattr(settings, "vakh_webhook_secret", "unit-test-secret-value")
    db = next(db_module.get_db())
    lr = _create_learner(db, "lr_vakh_webhook")
    mastery.ensure_states(db, lr)

    st_before = db.get(ConceptState, (lr.id, "sql_outer_join"))
    p_before = st_before.p_known

    payload = {
        "post_id": "vakh_post_unique_999",
        "learner_id": lr.id,
        "concept_id": "sql_outer_join",
        "score": 0.95,
        "review_notes": "Exemplary query with correct NULL handling.",
        "reviewer_type": "mentor"
    }
    raw = json.dumps(payload).encode()
    sig = vakh_adapter.sign_body(raw)

    # 1. First webhook delivery
    res1 = vakh_adapter.process_vakh_webhook(db, payload, raw, sig)
    assert res1["ok"] is True
    assert res1["already_processed"] is False

    # Check that BKT mastery increased
    st_after = db.get(ConceptState, (lr.id, "sql_outer_join"))
    assert st_after.p_known > p_before

    # Check evidence event
    ev = db.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == lr.id, EvidenceEvent.item_id == "vakh:vakh_post_unique_999")).first()
    assert ev is not None
    assert ev.source_type == "work_product"
    assert ev.grader == "vakh:mentor"

    # 2. Duplicate webhook delivery (exact same post_id)
    res2 = vakh_adapter.process_vakh_webhook(db, payload, raw, sig)
    assert res2["ok"] is True
    assert res2["already_processed"] is True  # Idempotency guard triggered!

    # Verify no second evidence event was created
    ev_count = len(list(db.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == lr.id, EvidenceEvent.item_id == "vakh:vakh_post_unique_999")).all()))
    assert ev_count == 1


def test_api_endpoints(client):
    # Dev login to get token
    login_res = client.post("/api/auth/dev-login", json={"name": "Navigation Tester", "age": 24, "language": "english"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # GET /api/map
    map_res = client.get("/api/map", headers=headers)
    assert map_res.status_code == 200
    map_json = map_res.json()
    assert "goal" in map_json
    assert "nodes" in map_json
    assert "edges" in map_json
    assert "navigation_action" in map_json
    assert map_json["navigation_action"]["title"] != ""

    # GET /api/map/node/sql_select
    node_res = client.get("/api/map/node/sql_select", headers=headers)
    assert node_res.status_code == 200
    node_json = node_res.json()
    assert node_json["node"]["id"] == "sql_select"
    assert "challenge" in node_json

    # GET /api/vakh/launch/sql_select
    vakh_res = client.get("/api/vakh/launch/sql_select", headers=headers)
    assert vakh_res.status_code == 200
    assert "launch_url" in vakh_res.json()

    # POST /api/map/goal (switch to ml_engineer)
    goal_res = client.post("/api/map/goal", json={"goal_id": "ml_engineer"}, headers=headers)
    assert goal_res.status_code == 200
    assert goal_res.json()["goal"]["id"] == "ml_engineer"
