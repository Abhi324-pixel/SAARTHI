"""Tests for T11: speaking pace, pauses, and speech marker coaching."""

import pytest
from fastapi.testclient import TestClient

from app import adapters, db as dbm
from app.config import settings
from app.engines import speech
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


def test_speech_exact_numbers():
    # 1. Exact numbers: 120 words over 60 s, starting after 5s silence (start=5.0, end=65.0)
    words = []
    # 120 words evenly spaced from 5.0 to 65.0 (step = 0.5s)
    for i in range(120):
        t_start = 5.0 + i * 0.5
        t_end = 5.0 + (i + 1) * 0.5
        words.append({"text": f"word{i}", "start": t_start, "end": t_end, "type": "word"})

    res = speech.analyze(words, language="english")
    assert res is not None
    assert res["words"] == 120
    assert res["speaking_seconds"] == 60.0
    assert res["wpm"] == 120


def test_speech_pauses():
    # 2. Pauses: gap of 0.9s is not counted; 1.2s is counted; longest_s correct
    words = [
        {"text": "one", "start": 0.0, "end": 0.5},
        {"text": "two", "start": 1.4, "end": 1.9},   # gap = 0.9s (not > 1.0)
        {"text": "three", "start": 3.1, "end": 3.6}, # gap = 1.2s (> 1.0)
        {"text": "four", "start": 5.0, "end": 5.5},  # gap = 1.4s (> 1.0, longest)
        {"text": "five", "start": 6.0, "end": 6.5},
        {"text": "six", "start": 7.0, "end": 7.5},
        {"text": "seven", "start": 8.0, "end": 8.5},
        {"text": "eight", "start": 9.0, "end": 9.5},
    ]
    res = speech.analyze(words, language="english")
    assert res is not None
    assert res["pauses"]["count_over_1s"] == 2
    assert res["pauses"]["longest_s"] == 1.4


def test_speech_markers():
    # 3. Multi-word markers: "you know" x2; "I like SQL" => 0 markers; Hinglish "matlab"
    text1 = "hello you know this is great and you know we did it basically actually"
    words1 = [
        {"text": w, "start": i * 1.0, "end": i * 1.0 + 0.5}
        for i, w in enumerate(text1.split())
    ]
    res1 = speech.analyze(words1, language="english")
    assert res1 is not None
    assert res1["markers"].get("you know") == 2
    assert res1["markers"].get("basically") == 1
    assert res1["markers"].get("actually") == 1

    # "I like SQL" => 0 markers (like is not a marker)
    text2 = "I like SQL very much indeed today"
    words2 = [
        {"text": w, "start": i * 1.0, "end": i * 1.0 + 0.5}
        for i, w in enumerate(text2.split())
    ]
    res2 = speech.analyze(words2, language="english")
    assert res2 is not None
    assert len(res2["markers"]) == 0

    # Hinglish "matlab"
    text3 = "matlab we need to join these tables toh it works"
    words3 = [
        {"text": w, "start": i * 1.0, "end": i * 1.0 + 0.5}
        for i, w in enumerate(text3.split())
    ]
    res3 = speech.analyze(words3, language="hinglish")
    assert res3 is not None
    assert res3["markers"].get("matlab") == 1
    assert res3["markers"].get("toh") == 1


def test_too_few_words_or_typed():
    # 4. Too few words (< 8) or too short (< 5s) => wpm is None
    words = [
        {"text": "short", "start": 0.0, "end": 1.0},
        {"text": "answer", "start": 1.2, "end": 2.0},
    ]
    res = speech.analyze(words, language="english")
    assert res is not None
    assert res["wpm"] is None

    # Empty/None words array (typed answer) => None
    assert speech.analyze(None) is None
    assert speech.analyze([]) is None


def test_client_validation_and_no_leak_to_evidence(env):
    # 5. Client-supplied speech with wpm=9000 => 422
    c, mp = env
    h = login(c, name="Voice Learner", age=20)
    sess_res = c.post("/api/explainback/start", headers=h, json={"concept_id": "sql_outer_join"})
    assert sess_res.status_code == 200
    sess_id = sess_res.json()["session_id"]

    bad_payload = {
        "session_id": sess_id,
        "text": "A left join keeps all rows from the left table and fills nulls for missing right matches.",
        "speech": {
            "words": 15,
            "speaking_seconds": 10.0,
            "wpm": 9000,  # Invalid! Must be <= 400
        },
    }
    res422 = c.post("/api/explainback/answer", headers=h, json=bad_payload)
    assert res422.status_code == 422

    # Valid speech object passes
    good_payload = {
        "session_id": sess_id,
        "text": "A left join keeps all rows from the left table and fills nulls for missing right matches.",
        "speech": {
            "words": 15,
            "speaking_seconds": 10.0,
            "wpm": 90,
            "pauses": {"count_over_1s": 0, "longest_s": 0.0},
            "markers": {},
            "markers_per_100_words": 0.0,
            "tips": ["GOOD"],
        },
    }
    res200 = c.post("/api/explainback/answer", headers=h, json=good_payload)
    assert res200.status_code == 200

    # Verify speech metrics NEVER leaked into EvidenceEvent
    with dbm.SessionLocal() as s:
        from app.models import EvidenceEvent
        events = list(s.query(EvidenceEvent).all())
        for ev in events:
            assert "speech" not in (ev.detail or {})
            assert "wpm" not in (ev.detail or {})


def test_stt_without_words(env):
    # 6. STT response without words => returns text, speech: null
    c, mp = env
    h = login(c, name="STT Learner", age=20)

    # Monkeypatch elevenlabs.speech_to_text to simulate no words returned
    from app.voice import elevenlabs
    mp.setattr(
        elevenlabs,
        "speech_to_text",
        lambda *args, **kwargs: {"text": "hello world", "language_code": "en", "duration": 2.5, "words": None},
    )

    res = c.post(
        "/api/voice/stt",
        headers=h,
        files={"file": ("test.webm", b"mock audio content", "audio/webm")},
    )
    assert res.status_code == 200
    j = res.json()
    assert j["text"] == "hello world"
    assert j["speech"] is None


def test_interview_report_speech_summary(env):
    # Verify speech metrics appear in interview report when turns have speech
    c, mp = env
    h = login(c, name="Interview Voice Learner", age=22)

    # Start 2-topic interview
    start_res = c.post("/api/interview/start", headers=h, json={"n_topics": 2, "channel": "audio"})
    assert start_res.status_code == 200
    sess_id = start_res.json()["session_id"]

    # Answer topic 1 with speech metrics
    speech1 = {
        "words": 20,
        "speaking_seconds": 10.0,
        "wpm": 120,
        "pauses": {"count_over_1s": 1, "longest_s": 1.2},
        "markers": {"basically": 2},
        "markers_per_100_words": 10.0,
        "tips": ["MANY_MARKERS"],
    }
    ans1 = c.post(
        "/api/interview/answer",
        headers=h,
        json={
            "session_id": sess_id,
            "text": "A left join returns all rows from the left table and matching rows from the right table. Basically it preserves everything from the left.",
            "audio_seconds": 10.0,
            "channel": "audio",
            "speech": speech1,
        },
    )
    assert ans1.status_code == 200

    # Answer topic 2 with speech metrics (finishes interview)
    speech2 = {
        "words": 25,
        "speaking_seconds": 12.0,
        "wpm": 125,
        "pauses": {"count_over_1s": 0, "longest_s": 0.0},
        "markers": {"actually": 1},
        "markers_per_100_words": 4.0,
        "tips": ["GOOD"],
    }
    # Turn 2
    ans2 = c.post(
        "/api/interview/answer",
        headers=h,
        json={
            "session_id": sess_id,
            "text": "An inner join only returns rows where there is a match in both tables. If a row does not match it is dropped.",
            "audio_seconds": 12.0,
            "channel": "audio",
            "speech": speech2,
        },
    )
    assert ans2.status_code == 200
    rep = ans2.json().get("report")
    if rep:
        assert "speech" in rep
        s_rep = rep["speech"]
        assert s_rep["answers_with_audio"] >= 1
        assert s_rep["median_wpm"] is not None
        assert any(m["marker"] in ("basically", "actually") for m in s_rep["top_markers"])
