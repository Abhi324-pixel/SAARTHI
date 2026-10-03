"""V01: resume upload (summary only, grounded) and the resume-driven practice interview."""

from __future__ import annotations

import io

import pytest
from sqlalchemy import select

from app import db as dbm
from app.llm import gateway
from app.models import EvidenceEvent
from .test_api import client, login  # noqa: F401

RESUME = (
    "Aman Verma\naman@example.com\nEducation: B.Tech Computer Science, Lucknow University, 2026\n"
    "Skills: Python, SQL, FastAPI, Docker, Git\nProjects:\nInventory API - a FastAPI service with PostgreSQL for a college store\n"
    "Experience: Intern at a local software firm, built reports with SQL. " + "Worked on tests and documentation. " * 6
)


def upload(client, h, text=RESUME, name="cv.txt"):
    return client.post("/api/resume", headers=h, files={"file": (name, io.BytesIO(text.encode()), "text/plain")})


def test_resume_keeps_only_a_grounded_summary(client, monkeypatch):
    h = login(client)
    # the model "invents" a skill and a project that are not in the file: code must drop them
    monkeypatch.setattr(gateway, "generate_json", lambda *a, **k: {
        "is_resume": True, "rejection_reason": "", "skills": ["Python", "Kubernetes"],
        "projects": [{"name": "Inventory API", "what": "store service"}, {"name": "Moon Rover", "what": "invented"}], "education": [], "experience": []})
    r = upload(client, h)
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert s["skills"] == ["Python"] and [p["name"] for p in s["projects"]] == ["Inventory API"]
    assert "aman@example.com" not in str(s)           # contact details are not kept
    assert client.get("/api/resume", headers=h).json()["summary"]["skills"] == ["Python"]
    assert client.delete("/api/resume", headers=h).json()["deleted"] is True
    assert client.get("/api/resume", headers=h).json()["summary"] is None


def test_non_resume_and_bad_files_are_refused(client, monkeypatch):
    h = login(client)
    r = upload(client, h, text="Chocolate cake: mix flour and sugar. " * 20)
    assert r.status_code == 422
    assert upload(client, h, name="x.exe").status_code == 415
    assert upload(client, h, text="short").status_code == 422
    big = client.post("/api/resume", headers=h, files={"file": ("big.txt", io.BytesIO(b"a" * 2_100_000), "text/plain")})
    assert big.status_code == 413
    assert client.post("/api/resume", files={"file": ("a.txt", io.BytesIO(b"x"), "text/plain")}).status_code == 401


def test_interview_uses_resume_and_grounds_feedback(client, monkeypatch):
    h = login(client)
    assert upload(client, h).status_code == 200
    st = client.post("/api/video-interview/start", headers=h, json={"use_resume": True})
    assert st.status_code == 200
    vid = st.json()["id"]
    answer = "I built the Inventory API with FastAPI and PostgreSQL, and I wrote the endpoints and the tests myself for the college store."
    monkeypatch.setattr(gateway, "generate_json", lambda task, *a, **k: (
        {"strengths": [{"point": "Names what they built", "quote": "I wrote all of the endpoints and every test"},      # not word for word -> dropped
                       {"point": "Says own part", "quote": "I wrote the endpoints and the tests myself"}],
         "gaps": ["No result or number given"], "next_question": "What was the hardest bug you fixed in it?"}))
    r = client.post(f"/api/video-interview/{vid}/answer", headers=h, json={"text": answer})
    assert r.status_code == 200, r.text
    j = r.json()
    assert [s["quote"] for s in j["feedback"]["strengths"]] == ["I wrote the endpoints and the tests myself"]
    assert j["next_question"] == "What was the hardest bug you fixed in it?" and j["done"] is False


def test_interview_runs_to_the_end_and_never_touches_mastery(client, monkeypatch):
    h = login(client)
    me = client.get("/api/me", headers=h).json()
    with dbm.SessionLocal() as s:
        before = len(list(s.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == me["id"]))))
    vid = client.post("/api/video-interview/start", headers=h, json={}).json()["id"]
    long_answer = "I solved a slow query problem in my project by adding an index and then I measured the result carefully afterwards."
    done = False
    for i in range(10):
        r = client.post(f"/api/video-interview/{vid}/answer", headers=h, json={"text": long_answer + f" Attempt {i}."}).json()
        done = r["done"]
        if done:
            break
    assert done and r["answered"] == 5
    rep = client.post(f"/api/video-interview/{vid}/finish", headers=h, json={"client_metrics": {
        "face_in_frame_pct": 91.234, "facing_camera_pct": 400, "voice_level_ok_pct": "high", "evil": 1, "recording_saved": True}}).json()
    assert rep["status"] == "done" and rep["summary"]["answers"] == 5
    m = rep["client_metrics"]
    assert m["face_in_frame_pct"] == 91.2 and m["facing_camera_pct"] == 100.0 and "voice_level_ok_pct" not in m and "evil" not in m
    questions = [t["question"] for t in rep["turns"]]
    assert len(set(questions)) == len(questions)                 # no repeated question
    with dbm.SessionLocal() as s:
        after = len(list(s.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == me["id"]))))
    assert after == before                                       # coaching only: no evidence, no mastery change
    assert client.post(f"/api/video-interview/{vid}/answer", headers=h, json={"text": long_answer}).status_code == 409


def test_short_answers_other_learners_and_model_outage(client, monkeypatch):
    h = login(client)
    h2 = login(client, name="Other Person")
    assert client.post("/api/video-interview/start", headers=h, json={"use_resume": True}).status_code == 409   # no resume yet
    vid = client.post("/api/video-interview/start", headers=h, json={}).json()["id"]
    assert client.get(f"/api/video-interview/{vid}", headers=h2).status_code == 404
    assert client.post(f"/api/video-interview/{vid}/answer", headers=h2, json={"text": "hello there everyone friends"}).status_code == 404
    r = client.post(f"/api/video-interview/{vid}/answer", headers=h, json={"text": "yes"}).json()
    assert r["feedback"]["status"] == "too_short" and r["next_question"]
    def boom(*a, **k):
        raise gateway.LLMUnavailable("down")
    monkeypatch.setattr(gateway, "generate_json", boom)
    r = client.post(f"/api/video-interview/{vid}/answer", headers=h, json={"text": "I fixed a bug in my project by reading the logs and writing a test."}).json()
    assert r["feedback"]["status"] == "unavailable" and r["feedback"]["strengths"] == [] and r["next_question"]   # fails closed, interview continues


def test_data_export_includes_interviews_and_resume(client):
    h = login(client)
    upload(client, h)
    client.post("/api/video-interview/start", headers=h, json={})
    ex = client.get("/api/me/export", headers=h).json()
    more = ex.get("more", ex)
    assert more["resume_summary"] and len(more["video_interviews"]) == 1


def test_voice_agent_interview_uses_the_resume_and_falls_back(client):
    from app import agent_tools
    from app.models import Learner
    h = login(client)
    me = client.get("/api/me", headers=h).json()
    long_answer = "I fixed a slow report in my project by adding an index and then I measured the speed again afterwards."
    # no resume uploaded: asking for it falls back to the normal curated interview
    with dbm.SessionLocal() as s:
        lr = s.get(Learner, me["id"])
        vs = agent_tools.start_voice_session(s, lr, "interview", None, use_resume=True)
        r = agent_tools.dispatch(s, lr, "get_next_action", {}, vs.id)
        assert r["action"] == "interview_question" and vs.state.get("vi_session_id") is None
        s.commit()
    assert upload(client, h).status_code == 200
    with dbm.SessionLocal() as s:
        lr = s.get(Learner, me["id"])
        dv = agent_tools.dynamic_variables(s, lr, "interview", None, use_resume=True)
        assert "python" in dv["learner_summary"].lower() and "aman@example.com" not in str(dv)     # the short summary only
        assert "resume" not in agent_tools.dynamic_variables(s, lr, "interview", None, use_resume=False)["learner_summary"].lower()
        vs = agent_tools.start_voice_session(s, lr, "interview", None, use_resume=True)
        r = agent_tools.dispatch(s, lr, "get_next_action", {}, vs.id)
        assert r["action"] == "interview_question" and vs.state["vi_session_id"]
        for i in range(10):
            r = agent_tools.dispatch(s, lr, "record_response", {"text": long_answer + f" Round {i}."}, vs.id)
            if r["done"]:
                break
        assert r["done"] and "practice" in r["say"]
        s.commit()
    assert len(client.get("/api/video-interview", headers=h).json()["interviews"]) == 1       # it also appears in the learner's list


# ---- report: grounded summary, focus topics, and the one-click plan change -----------------------------------------------------------

def _run_interview(client, h, monkeypatch, turns=3, gap_ids=("sql_outer_join", "not_a_real_concept")):
    vid = client.post("/api/video-interview/start", headers=h, json={}).json()["id"]
    answer = "I built a small shop report in my project, and I joined orders to customers, but I filtered with WHERE after a LEFT JOIN."
    monkeypatch.setattr(gateway, "generate_json", lambda task, *a, **k: (
        {"strengths": [{"point": "Says what they built", "quote": "I built a small shop report in my project"}],
         "gaps": ["The join logic was not explained"], "gap_concepts": list(gap_ids), "next_question": f"Question about detail {task}"}
        if task == "video_feedback" else {}))
    for i in range(turns):
        r = client.post(f"/api/video-interview/{vid}/answer", headers=h, json={"text": answer + f" Variation {i}."}).json()
        if r["done"]:
            break
    return vid


def test_report_counts_focus_topics_and_unreal_concepts_are_dropped(client, monkeypatch):
    h = login(client)
    vid = _run_interview(client, h, monkeypatch, turns=3)
    rep = client.post(f"/api/video-interview/{vid}/finish", headers=h, json={"client_metrics": {}}).json()
    assert rep["summary"]["answers"] == 3 and rep["summary"]["grounded_strengths"] == 3 and rep["summary"]["answers_with_quotes"] == 3
    assert rep["summary"]["suggestions"] == 3 and rep["summary"]["too_short"] == 0
    assert [t["concept_id"] for t in rep["focus_topics"]] == ["sql_outer_join"]          # the invented id never appears
    assert rep["focus_topics"][0]["times"] == 3 and rep["focus_topics"][0]["state"] == "addable"
    assert rep["written_summary"] is None                                                  # model gave nothing usable: no summary, nothing invented


def test_written_summary_is_kept_only_if_it_adds_no_number_or_link(client, monkeypatch):
    h = login(client)
    for text, expect_kept in (("You explained your project clearly with quotes, and the join logic is the topic to practise next.", True),
                              ("You scored 87 percent and showed great skill in your answers overall.", False),
                              ("Read more at https://example.com about joins and how to practise them every day.", False)):
        vid = _run_interview(client, h, monkeypatch, turns=2)
        real = gateway.generate_json
        monkeypatch.setattr(gateway, "generate_json", lambda task, *a, **k: {"summary": text} if task == "video_summary" else real(task, *a, **k))
        rep = client.post(f"/api/video-interview/{vid}/finish", headers=h, json={"client_metrics": {}}).json()
        assert (rep["written_summary"] == text) is expect_kept, text


def test_adding_focus_moves_topics_up_the_plan_without_touching_skill_estimates(client, monkeypatch):
    h = login(client)
    me = client.get("/api/me", headers=h).json()
    vid = _run_interview(client, h, monkeypatch, turns=2)
    client.post(f"/api/video-interview/{vid}/finish", headers=h, json={"client_metrics": {}})
    with dbm.SessionLocal() as s:
        before = len(list(s.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == me["id"]))))
    r = client.post(f"/api/video-interview/{vid}/focus", headers=h)
    assert r.status_code == 200, r.text
    assert [a["concept_id"] for a in r.json()["added"]] == ["sql_outer_join"]
    plan = client.get("/api/roadmap", headers=h).json()
    item = next(i for i in plan["items"] if i["concept_id"] == "sql_outer_join")
    assert any(x["type"] == "INTERVIEW_FOCUS" for x in item["reasons"])
    assert "interview showed a gap" in item.get("why", "") or "interview showed a gap" in str(plan)
    with dbm.SessionLocal() as s:
        after = len(list(s.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == me["id"]))))
    assert after == before                                                                   # a plan change is not evidence
    assert client.post(f"/api/video-interview/{vid}/focus", headers=h).status_code == 409    # nothing new to add the second time
    assert client.get(f"/api/video-interview/{vid}", headers=h).json()["focus_topics"][0]["state"] == "in_plan"
    h2 = login(client, name="Other Person")
    assert client.post(f"/api/video-interview/{vid}/focus", headers=h2).status_code == 404


def test_old_focus_is_ignored_and_the_boost_needs_a_real_gap():
    from datetime import timedelta
    from app.engines import planner
    from app.models import now
    assert planner._focus_recent({"at": now().isoformat()}) is True
    assert planner._focus_recent({"at": (now() - timedelta(days=45)).isoformat()}) is False
    assert planner._focus_recent({"at": "garbage"}) is False and planner._focus_recent(None) is False
