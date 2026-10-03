"""Vakh integration safety: no forged reviews, no invented credit, no internal text in errors, nothing assumed about Vakh."""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from app import db as dbm
from app.config import settings
from app.engines import vakh_adapter
from app.models import EvidenceEvent
from app.models_ext.G01 import VakhSubmission
from .test_api import client, login  # noqa: F401

SECRET = "unit-test-secret-value-0123456789"


def _sig(raw: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


@pytest.fixture()
def vakh(client, monkeypatch):
    monkeypatch.setattr(settings, "vakh_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "vakh_base_url", "https://vakh.example")
    monkeypatch.setattr(settings, "vakh_enabled", True)
    h = login(client)
    me = client.get("/api/me", headers=h).json()
    return client, h, me["id"]


def post(client, payload, sign=True, secret=SECRET, header=None):
    raw = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if header is not None:
        headers.update(header)
    elif sign:
        headers["X-Vakh-Signature"] = _sig(raw, secret)
    return client.post("/api/vakh/webhook", content=raw, headers=headers)


def evidence_count(lid):
    with dbm.SessionLocal() as s:
        return len(list(s.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == lid, EvidenceEvent.grader.like("vakh:%")))))


def base(lid, **kw):
    return {"post_id": "p1", "learner_id": lid, "concept_id": "sql_outer_join", "score": 0.9, "status": "approved", **kw}


def test_unconfigured_server_refuses_everything(client, monkeypatch):
    monkeypatch.setattr(settings, "vakh_webhook_secret", "")
    monkeypatch.setattr(settings, "vakh_base_url", "")
    h = login(client)
    lid = client.get("/api/me", headers=h).json()["id"]
    # there is no shipped default secret: the old "dev-vakh-secret" opens nothing
    assert post(client, base(lid), header={"X-Vakh-Secret": "dev-vakh-secret"}).status_code == 503
    assert post(client, base(lid), header={"X-Vakh-Signature": "dev-vakh-secret"}).status_code == 503
    assert evidence_count(lid) == 0
    r = client.get("/api/vakh/launch/sql_outer_join", headers=h).json()
    assert r["configured"] is False and r["launch_url"] is None and r["challenge"]["title"]


def test_only_a_valid_hmac_signature_is_accepted(vakh):
    client, h, lid = vakh
    assert post(client, base(lid), sign=False).status_code == 401                                   # no signature
    assert post(client, base(lid), header={"X-Vakh-Signature": SECRET}).status_code == 401          # the secret itself is not a signature
    assert post(client, base(lid), header={"X-Vakh-Secret": SECRET}).status_code == 401             # the old header is gone
    assert post(client, base(lid), secret="some-other-secret-value").status_code == 401              # wrong key
    raw = json.dumps(base(lid)).encode()
    tampered = client.post("/api/vakh/webhook", content=raw.replace(b"0.9", b"1.0"), headers={"X-Vakh-Signature": _sig(raw)})
    assert tampered.status_code == 401                                                               # body changed after signing
    assert evidence_count(lid) == 0
    ok = post(client, base(lid))
    assert ok.status_code == 200 and ok.json()["evidence_recorded"] is True
    assert evidence_count(lid) == 1


def test_master_switch_turns_vakh_off(vakh, monkeypatch):
    client, h, lid = vakh
    monkeypatch.setattr(settings, "vakh_enabled", False)
    assert post(client, base(lid)).status_code == 503
    r = client.get("/api/vakh/launch/sql_outer_join", headers=h).json()
    assert r["configured"] is False and r["launch_url"] is None
    assert evidence_count(lid) == 0


def test_rejected_and_unscored_reviews_are_never_credited(vakh):
    client, h, lid = vakh
    r = post(client, {"post_id": "rej-1", "learner_id": lid, "concept_id": "sql_aggregates", "status": "rejected"})
    assert r.status_code == 200 and r.json()["evidence_recorded"] is False and evidence_count(lid) == 0
    with dbm.SessionLocal() as s:
        sub = s.scalars(select(VakhSubmission).where(VakhSubmission.vakh_post_id == "rej-1")).first()
        assert sub.status == "rejected" and sub.score is None and sub.evidence_event_id is None
    # approved but no score: nothing is invented
    r = post(client, {"post_id": "noscore-1", "learner_id": lid, "concept_id": "sql_aggregates", "status": "approved"})
    assert r.status_code == 422 and evidence_count(lid) == 0
    # a rejected review that carries a low score counts as the low score it is
    r = post(client, {"post_id": "rej-2", "learner_id": lid, "concept_id": "sql_aggregates", "status": "rejected", "score": 0.1})
    assert r.status_code == 200 and r.json()["evidence_recorded"] is True
    with dbm.SessionLocal() as s:
        ev = s.scalars(select(EvidenceEvent).where(EvidenceEvent.item_id == "vakh:rej-2")).first()
        assert ev.score == 0.1
    # a review that is not final yet records nothing
    r = post(client, {"post_id": "wait-1", "learner_id": lid, "concept_id": "sql_aggregates", "status": "under_review", "score": 1.0})
    assert r.status_code == 200 and r.json()["recorded"] is False


def test_bad_input_is_a_clean_4xx_with_no_internal_text(vakh):
    client, h, lid = vakh
    for payload in (base(lid, score="abc"), base(lid, score=7), base(lid, concept_id="no_such_concept"), base(lid, post_id=""),
                    {"post_id": "x1"}, base(lid, status="x" * 80)):
        r = post(client, payload)
        assert r.status_code == 422, (payload, r.text)
        assert "could not convert" not in r.text and "Traceback" not in r.text
    assert post(client, base("nobody-here", post_id="ghost-1")).status_code == 404
    raw = b"not json at all"
    assert client.post("/api/vakh/webhook", content=raw, headers={"X-Vakh-Signature": _sig(raw)}).status_code == 400
    assert client.post("/api/vakh/webhook", content=b"x" * 30000, headers={"X-Vakh-Signature": _sig(raw)}).status_code == 413
    assert client.get("/api/vakh/challenges/no_such_concept", headers=h).status_code == 404
    assert evidence_count(lid) == 0


def test_launch_link_hides_the_learner_id_and_the_state_resolves_it(vakh):
    client, h, lid = vakh
    r = client.get("/api/vakh/launch/sql_outer_join", headers=h).json()
    url = r["launch_url"]
    assert r["configured"] is True and url.startswith("https://vakh.example/forms/")
    assert lid not in url and "learner_id" not in url
    assert r["prefill_verified"] is False                       # we do not claim Vakh pre-fills anything
    state = parse_qs(urlparse(url).query)["state"][0]
    assert vakh_adapter.read_state(state) == (lid, "sql_outer_join")
    # a review that arrives with the state token needs no ids in the body, and cannot be redirected to another concept
    ok = post(client, {"post_id": "st-1", "state": state, "score": 0.8, "status": "approved"})
    assert ok.status_code == 200 and ok.json()["evidence_recorded"] is True
    assert post(client, {"post_id": "st-2", "state": state, "concept_id": "sql_select", "score": 0.8}).status_code == 422
    assert post(client, {"post_id": "st-3", "state": state[:-3] + "xyz", "score": 0.8}).status_code == 400   # tampered token
    assert evidence_count(lid) == 1


def test_duplicate_events_and_unsafe_base_url(vakh, monkeypatch):
    client, h, lid = vakh
    assert post(client, base(lid)).json()["already_processed"] is False
    assert post(client, base(lid)).json()["already_processed"] is True and evidence_count(lid) == 1
    for bad in ("http://vakh.example", "javascript:alert(1)", "ftp://x"):
        monkeypatch.setattr(settings, "vakh_base_url", bad)
        assert client.get("/api/vakh/launch/sql_outer_join", headers=h).json()["launch_url"] is None
