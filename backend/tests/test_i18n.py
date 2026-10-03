"""Interface translation: checked output only, cached once for everyone, personal-looking text never sent, failures leave English."""

from __future__ import annotations

import pytest

from app import db as dbm
from app.engines import ui_translate
from app.llm import gateway
from app.models_ext.I18N import UiTranslation
from .test_api import client, login  # noqa: F401


def post(client, h, lang, texts):
    return client.post("/api/i18n/translate", headers=h, json={"lang": lang, "texts": texts})


def test_validation_rules():
    v = ui_translate._valid
    assert v("hindi", "Start the quiz", "क्विज़ शुरू करें")
    assert not v("hindi", "Start the quiz", "Quiz shuru karein")                 # Hindi must be in Devanagari
    assert v("hinglish", "Start the quiz", "Quiz shuru karein")
    assert not v("hinglish", "Start the quiz", "क्विज़ शुरू करें")                  # Hinglish must not be in Devanagari
    assert not v("hinglish", "3 questions, 5 minutes", "teen sawal, paanch minute")   # numbers must survive exactly
    assert v("hinglish", "3 questions, 5 minutes", "3 sawal, 5 minute")
    assert not v("hinglish", "OK", "")
    assert not v("hinglish", "Save", "x" * 200)                                  # absurd length
    assert not v("hindi", "Save your work", "Save your work")                    # a sentence that came back unchanged was not translated
    assert not v("hindi", "Save", "Save")
    assert v("hinglish", "Skill graph", "Skill graph") and not v("hinglish", "Your progress is saved on the server", "Your progress is saved on the server")


def test_eligibility_keeps_personal_looking_and_symbol_text_out():
    e = ui_translate.eligible
    assert e("Your progress is saved on the server.") and e("Save") and e("Python basics")
    assert not e("42%") and not e("→") and not e("") and not e("INNER JOIN") and not e("SQL")      # numbers, symbols and code stay as they are
    assert not e("write to priya@example.com for help") and not e("see https://example.com")
    assert not e("call 9876543210") and not e("x" * 500)


def test_translations_are_checked_cached_and_shared(client, monkeypatch):
    h = login(client)
    calls = []
    table = {"Start": "शुरू करें", "Save": "Save", "These are 5 questions": "यह 7 सवाल हैं"}     # Save: unchanged; third: wrong number (7 instead of 5)

    def fake(task, system, prompt, schema, **k):
        import json
        items = json.loads(prompt.split("\n", 1)[1])
        calls.append(items)
        return {"translations": [table[x] for x in items]}
    monkeypatch.setattr(gateway, "generate_json", fake)
    r = post(client, h, "hindi", ["Start", "Save", "These are 5 questions"]).json()
    assert r["translations"] == ["शुरू करें", None, None]                        # unchanged and wrong-number ones stay English
    n = len(calls)
    assert post(client, h, "hindi", ["Start"]).json()["translations"] == ["शुरू करें"] and len(calls) == n          # from the cache, no model call
    h2 = login(client, name="Other Person")
    assert post(client, h2, "hindi", ["Start"]).json()["translations"] == ["शुरू करें"] and len(calls) == n          # shared by everyone
    with dbm.SessionLocal() as s:
        assert s.query(UiTranslation).count() == 1                              # only the valid one was stored


def test_personal_text_is_never_sent_to_the_model(client, monkeypatch):
    h = login(client)
    sent = []
    monkeypatch.setattr(gateway, "generate_json", lambda task, system, prompt, schema, **k: sent.append(prompt) or {"translations": []})
    r = post(client, h, "hinglish", ["Mail me at asha@example.com", "Open https://example.com/x", "Call 9876543210"]).json()
    assert r["translations"] == [None, None, None] and sent == []


def test_model_failure_and_bad_answers_leave_english(client, monkeypatch):
    h = login(client)

    def boom(*a, **k):
        raise gateway.LLMUnavailable("down")
    monkeypatch.setattr(gateway, "generate_json", boom)
    assert post(client, h, "hinglish", ["Start the quiz"]).json()["translations"] == [None]
    monkeypatch.setattr(gateway, "generate_json", lambda *a, **k: {"translations": ["a", "b", "c"]})                 # always the wrong number of items
    assert post(client, h, "hinglish", ["Start the quiz", "Stop the quiz"]).json()["translations"] == [None, None]     # refused, never guessed


def test_input_limits_and_sign_in(client):
    h = login(client)
    assert post(client, h, "french", ["Hello"]).status_code == 422
    assert post(client, h, "hindi", ["Hello"] * 41).status_code == 422
    assert post(client, h, "hindi", ["x" * 2000]).status_code == 422
    assert client.post("/api/i18n/translate", json={"lang": "hindi", "texts": ["Hello"]}).status_code == 401


def test_a_wrong_count_for_a_big_batch_still_saves_the_good_halves(client, monkeypatch):
    h = login(client)

    def fake(task, system, prompt, schema, **k):
        import json
        items = json.loads(prompt.split("\n", 1)[1])
        if len(items) > 2:
            return {"translations": ["x"]}                                    # the model loses count on a longer list
        return {"translations": [f"{x} ke liye" for x in items]}               # but is fine on short ones
    monkeypatch.setattr(gateway, "generate_json", fake)
    texts = ["Start the quiz", "Stop the quiz", "Open the map", "Close the map", "Save your work"]
    r = post(client, h, "hinglish", texts).json()["translations"]
    assert r == [f"{x} ke liye" for x in texts]


def test_texts_the_model_slipped_on_are_asked_again(client, monkeypatch):
    h = login(client)
    asked = []

    def fake(task, system, prompt, schema, **k):
        import json
        items = json.loads(prompt.split("\n", 1)[1])
        asked.append(len(items))
        # first time for a list of 3: the model copies the middle one back; asked again on its own it translates it
        return {"translations": [x if (len(items) == 3 and x.startswith("Please stop")) else f"{x} ke liye" for x in items]}
    monkeypatch.setattr(gateway, "generate_json", fake)
    r = post(client, h, "hinglish", ["Start the quiz", "Please stop the quiz now and review it", "Open the map"]).json()["translations"]
    assert r == ["Start the quiz ke liye", "Please stop the quiz now and review it ke liye", "Open the map ke liye"] and asked == [3, 1]
