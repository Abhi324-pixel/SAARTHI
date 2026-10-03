import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import adapters, db as dbm
from app.config import settings
from app.llm import gateway
from app.voice import elevenlabs
from tests.test_api import BAD_JOIN, GOOD_JOIN, login


@pytest.fixture()
def client(monkeypatch):
    dbm.configure("sqlite://")
    monkeypatch.setattr(settings, "llm_mode", "fake")
    adapters.reset()
    from app.main import create_app
    return TestClient(create_app())


def call(client, h, vs, tool, **args):
    r = client.post(f"/api/voice/tools/{tool}", json={"voice_session_id": vs, "args": args}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def voice(client, monkeypatch):
    monkeypatch.setattr(elevenlabs, "agent_connection", lambda: {"mode": "signed", "signed_url": "wss://example/test", "agent_id": "agent_x"})
    h = login(client)

    def connect(mode="explain_back", concept="sql_outer_join"):
        r = client.post("/api/voice/connect", json={"mode": mode, "concept_id": concept}, headers=h)
        assert r.status_code == 200, r.text
        return r.json()
    return client, h, connect


def test_connect_returns_signed_url_and_dynamic_variables(voice):
    client, h, connect = voice
    c = connect()
    assert c["signed_url"].startswith("wss://") and c["voice_session_id"]
    dv = c["dynamic_variables"]
    assert dv["learner_name"] == "Priya" and dv["current_concept"] == "sql_outer_join" and dv["session_mode"] == "explain_back"
    assert dv["goal"] == "Backend Developer" and dv["learner_summary"]
    for k in ("learner_name", "language_pref", "goal", "current_concept", "current_concept_name", "session_mode", "learner_summary"):
        assert k in dv  # exactly the variables the agent prompt references


def test_connect_without_agent_config_is_a_clear_error(client, monkeypatch):
    h = login(client)
    monkeypatch.setattr(settings, "elevenlabs_agent_id", None)
    r = client.post("/api/voice/connect", json={}, headers=h)
    assert r.status_code == 503 and "ELEVENLABS_AGENT_ID" in r.json()["detail"]


def test_all_seven_agent_tools_exist():
    from app.agent_tools import TOOLS
    assert set(TOOLS) == {"get_learner_context", "get_next_action", "explain_topic", "record_response",
                          "confirm_statement", "show_visual", "request_mentor"}


def test_explain_back_by_voice_end_to_end_updates_roadmap(voice):
    client, h, connect = voice
    c = connect()
    vs = c["voice_session_id"]
    ctx = call(client, h, vs, "get_learner_context")
    assert ctx["current_concept"]["id"] == "sql_outer_join" and ctx["goal"] == "Backend Developer"
    nxt = call(client, h, vs, "get_next_action")
    assert nxt["action"] == "explain_back" and "teach it back" in nxt["say"].lower()
    r = call(client, h, vs, "record_response", text=GOOD_JOIN, stated_confidence=3)
    if not r["done"]:
        r = call(client, h, vs, "record_response", text=GOOD_JOIN + " Also remember the NULL rows appear for unmatched customers.")
    assert r["done"] and "covered" in r["say"] and r["score_percent"] >= 50
    assert r["ui"]["panel"] == "roadmap"


def test_misconception_readback_via_tools(voice):
    client, h, connect = voice
    vs = connect()["voice_session_id"]
    call(client, h, vs, "get_next_action")
    r = call(client, h, vs, "record_response", text=BAD_JOIN)
    assert r["readback"] and "Is that right" in r["say"]
    sid = r["readback"]["statement_id"]
    out = call(client, h, vs, "confirm_statement", statement_id=sid, confirmed=True)
    assert out["status"] == "confirmed" and out["ui"]["panel"] == "join_diagram"
    assert client.get("/api/misconceptions", headers=h).json()["active"][0]["status"] == "confirmed"


def test_short_or_empty_responses_and_unknown_tool(voice):
    client, h, connect = voice
    vs = connect()["voice_session_id"]
    assert "didn't catch" in call(client, h, vs, "record_response", text="  ")["say"].lower()
    assert call(client, h, vs, "does_not_exist")["error"]
    assert call(client, h, vs, "show_visual", panel="nope")["error"]
    assert call(client, h, vs, "show_visual", panel="join_diagram")["ui"]["panel"] == "join_diagram"


def test_teach_mode_explains_first_then_asks_to_teach_back(voice):
    client, h, connect = voice
    vs = connect(mode="teach", concept="sql_outer_join")["voice_session_id"]
    a = call(client, h, vs, "get_next_action")
    assert a["action"] == "teach" and "strategy" in a
    b = call(client, h, vs, "get_next_action")
    assert b["action"] == "explain_back"
    ex = call(client, h, vs, "explain_topic", concept_id="sql_null")
    assert ex["concept"] and ex["text"]


def test_interview_by_voice(voice):
    client, h, connect = voice
    vs = connect(mode="interview", concept=None)["voice_session_id"]
    q = call(client, h, vs, "get_next_action")
    assert q["action"] == "interview_question" and "interview" in q["say"].lower()
    ans = GOOD_JOIN + " An inner join matches rows on ON and without ON you get a cartesian product with every row paired. Indexes speed up lookups but slow writes. Transactions are atomic."
    done = False
    for _ in range(10):
        r = call(client, h, vs, "record_response", text=ans)
        if r.get("done"):
            done = True
            break
    assert done and "end of the interview" in r["say"]


def test_voice_request_mentor_routes_wellbeing_to_safeguarding(voice):
    client, h, connect = voice
    vs = connect()["voice_session_id"]
    r = call(client, h, vs, "request_mentor", reason="I feel hopeless", category="technical")
    assert r["case"]["tier"] == "safeguarding" and "14416" in r["say"]
    r2 = call(client, h, vs, "request_mentor", reason="my joins still fail", category="technical")
    assert r2["case"]["tier"] == "skill_mentor"


# ---- elevenlabs REST wrappers ---------------------------------------------------------------------------------------
def test_tts_and_stt_call_the_right_endpoints(client, monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        seen[url] = kw
        if "text-to-speech" in url:
            return httpx.Response(200, content=b"ID3audio", request=httpx.Request("POST", url))
        return httpx.Response(200, json={"text": "left join keeps all rows", "language_code": "en", "audio_duration_secs": 3.2},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(settings, "elevenlabs_api_key", "k")
    monkeypatch.setattr(settings, "elevenlabs_voice_id", "voice123")
    h = login(client)
    r = client.post("/api/voice/tts", json={"text": "Namaste", "language": "hindi"}, headers=h)
    assert r.status_code == 200 and r.content == b"ID3audio" and r.headers["content-type"] == "audio/mpeg"
    url = next(u for u in seen if "text-to-speech" in u)
    assert url.endswith("/voice123") and seen[url]["headers"]["xi-api-key"] == "k"
    assert "language_code" not in seen[url]["json"]  # eleven_multilingual_v2 does not take one
    r = client.post("/api/voice/stt", files={"file": ("a.webm", b"\x1aE\xdf\xa3", "audio/webm")}, data={"language": "hindi"}, headers=h)
    assert r.status_code == 200 and r.json()["text"].startswith("left join")
    stt = seen["https://api.elevenlabs.io/v1/speech-to-text"]
    assert stt["data"]["model_id"] == "scribe_v1" and stt["data"]["language_code"] == "hi"


def test_voice_keys_missing_gives_503_not_a_crash(client, monkeypatch):
    monkeypatch.setattr(settings, "elevenlabs_api_key", None)
    h = login(client)
    assert client.post("/api/voice/tts", json={"text": "hi"}, headers=h).status_code == 503
    assert client.post("/api/voice/stt", files={"file": ("a.webm", b"xx", "audio/webm")}, headers=h).status_code == 503
    st = client.get("/api/voice/status", headers=h).json()
    assert not st["api_key"] and not st["stt_ready"]


# ---- gemini gateway ------------------------------------------------------------------------------------------------------
class _Resp:
    def __init__(self, text): self.text = text


class _Models:
    def __init__(self, behaviours): self.behaviours, self.calls = behaviours, []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        b = self.behaviours[model]
        if isinstance(b, Exception):
            raise b
        return _Resp(b)


class _Client:
    def __init__(self, behaviours): self.models = _Models(behaviours)


@pytest.fixture()
def gem(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "llm_mode", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "model", "gemini-3.5-flash-lite")
    monkeypatch.setattr(settings, "model_fallbacks", "gemini-2.5-flash")
    monkeypatch.setattr("app.llm.gateway.DATA_DIR", tmp_path)
    gateway._cooldown_until.clear()
    return monkeypatch


def test_gateway_uses_configured_model_and_parses_json(gem):
    cl = _Client({"gemini-3.5-flash-lite": json.dumps({"ok": True}), "gemini-2.5-flash": "{}"})
    gem.setattr(gateway, "_get_client", lambda: cl)
    out = gateway.generate_json("t", "sys", "p", {"type": "object"})
    assert out["ok"] and out["_model"] == "gemini-3.5-flash-lite" and cl.models.calls == ["gemini-3.5-flash-lite"]


def test_gateway_falls_back_to_the_next_model_and_cools_down(gem):
    cl = _Client({"gemini-3.5-flash-lite": RuntimeError("429 rate limit"), "gemini-2.5-flash": json.dumps({"ok": 1})})
    gem.setattr(gateway, "_get_client", lambda: cl)
    out = gateway.generate_json("t", "sys", "p1", {"type": "object"})
    assert out["_model"] == "gemini-2.5-flash"
    gateway.generate_json("t", "sys", "p2", {"type": "object"})
    assert cl.models.calls == ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash"]  # primary skipped while cooling


def test_gateway_fails_closed_when_everything_fails_or_no_key(gem):
    cl = _Client({"gemini-3.5-flash-lite": RuntimeError("boom"), "gemini-2.5-flash": RuntimeError("boom2")})
    gem.setattr(gateway, "_get_client", lambda: cl)
    with pytest.raises(gateway.LLMUnavailable):
        gateway.generate_json("t", "sys", "p", {"type": "object"})
    gem.setattr(settings, "gemini_api_key", None)
    with pytest.raises(gateway.LLMUnavailable):
        gateway.generate_json("t", "sys", "p", {"type": "object"})
    assert not gateway.available()


def test_gateway_caches_deterministic_content(gem):
    cl = _Client({"gemini-3.5-flash-lite": "hello there", "gemini-2.5-flash": "x"})
    gem.setattr(gateway, "_get_client", lambda: cl)
    a = gateway.generate_text("t", "sys", "same prompt", cache=True)
    b = gateway.generate_text("t", "sys", "same prompt", cache=True)
    assert a == b == "hello there" and len(cl.models.calls) == 1


def test_gateway_extracts_json_wrapped_in_prose(gem):
    cl = _Client({"gemini-3.5-flash-lite": 'Sure! {"a": 1} hope that helps', "gemini-2.5-flash": "{}"})
    gem.setattr(gateway, "_get_client", lambda: cl)
    assert gateway.generate_json("t", "sys", "p", {"type": "object"})["a"] == 1


# ---- grounding of model output ---------------------------------------------------------------------------------------------------
def test_model_cannot_award_credit_without_a_real_quote(gem):
    """A hallucinated 'evidence' quote must not count toward the score."""
    from app.engines import explainback
    from app.llm import tasks
    gem.setattr(tasks, "score_explain_back", lambda *a, **k: {
        "checklist": [{"id": "keepleft", "covered": True, "evidence": "LEFT JOIN keeps every row of the left table always"},
                      {"id": "nulls", "covered": True, "evidence": "unmatched rows are NULL"}],
        "misconceptions": [{"id": "left_join_as_inner", "evidence": "left join is only matching rows"}],
        "grader_confidence": 0.9, "followup_question": "?"})
    ev = explainback.evaluate_turn("sql_outer_join", "It joins two tables together using a key column and gives back some rows.", "english", set())
    assert ev["covered"] == {} and ev["misconceptions"] == [] and ev["ungrounded"] == 2
    assert ev["grader_confidence"] < 0.9


def test_quote_grounding_helper():
    from app.engines.explainback import quote_is_grounded
    t = "A left join keeps every customer even when there is no matching order"
    assert quote_is_grounded("keeps every customer", t)
    assert not quote_is_grounded("returns only inner rows", t)
    assert not quote_is_grounded("", t)


def test_gateway_unparseable_output_falls_back_to_the_next_model(gem):
    cl = _Client({"gemini-3.5-flash-lite": "I could not do that.", "gemini-2.5-flash": json.dumps({"ok": 2})})
    gem.setattr(gateway, "_get_client", lambda: cl)
    out = gateway.generate_json("t", "sys", "pp", {"type": "object"})
    assert out["ok"] == 2 and out["_model"] == "gemini-2.5-flash"


def test_gateway_retries_without_thinking_config_when_the_model_rejects_it(gem):
    calls = []

    class M:
        def generate_content(self, model, contents, config):
            calls.append(bool(getattr(config, "thinking_config", None)))
            if getattr(config, "thinking_config", None):
                raise RuntimeError("400 INVALID_ARGUMENT: thinking level not supported for this model")
            return _Resp(json.dumps({"ok": 3}))

    class C:
        models = M()
    gem.setattr(gateway, "_get_client", lambda: C())
    out = gateway.generate_json("t", "sys", "px", {"type": "object"})
    assert out["ok"] == 3 and out["_model"] == "gemini-3.5-flash-lite"
    assert calls == [True, False]
