"""Tests for C04: live updates in the mentor case chat (state & sync messages)."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import adapters, db as dbm
from app.config import settings
from app.models import CaseMessage, Learner, Mentor, MentorCase, now
from .test_api import login
from .test_mentor_apply import complete_application, make_admin, remove_demo_mentors


@pytest.fixture()
def env(monkeypatch):
    dbm.configure("sqlite://")
    for k, v in (
        ("llm_mode", "fake"),
        ("auth_mode", "mock"),
        ("mentors_mode", "db"),
        ("consent_mode", "mock"),
        ("cohort_mode", "mock"),
    ):
        monkeypatch.setattr(settings, k, v)
    adapters.reset()
    from app.main import create_app
    c = TestClient(create_app())
    from app.adapters.impl import seed_mentors
    with dbm.SessionLocal() as s:
        seed_mentors(s)
        s.commit()
    yield c, monkeypatch
    adapters.reset()


CHECKS = ["identity", "reference", "police_verification"]


def new_real_mentor(c, mp, name):
    h = login(c, name=name)
    complete_application(c, h, name=name, expertise=["sql_outer_join", "sql"])
    ah, _ = make_admin(c, mp, name=name + " admin")
    app = [a for a in c.get("/api/admin/mentor-applications", headers=ah).json()["applications"] if a["name"] == name][0]
    c.post(
        f"/api/admin/mentor-applications/{app['id']}/decision",
        headers=ah,
        json={"decision": "approve", "note": "ok", "checks": [{"kind": k} for k in CHECKS]},
    )
    return h, app["user_id"]


def test_case_sync_flow(env):
    c, mp = env
    mh, mid = new_real_mentor(c, mp, "Expert Mentor")
    lh = login(c, name="Student One", age=20)
    lh2 = login(c, name="Student Two", age=21)

    # 1. Open case
    res = c.post(
        "/api/cases",
        headers=lh,
        json={"category": "technical", "concept_id": "sql_outer_join", "reason": "help with join"},
    )
    assert res.status_code == 200
    case_id = res.json()["case_id"]

    # 2. Check initial state
    st_res = c.get(f"/api/cases/{case_id}/state", headers=lh)
    assert st_res.status_code == 200
    st = st_res.json()
    assert st["status"] in ("matched", "accepted", "open")
    assert st["message_count"] >= 1  # matched creates a system message
    etag1 = st_res.headers.get("ETag")
    assert etag1 is not None

    # 3. ETag returns 304 if unchanged
    st304 = c.get(f"/api/cases/{case_id}/state", headers={**lh, "If-None-Match": etag1})
    assert st304.status_code == 304

    # 4. Post a message
    msg_res = c.post(f"/api/cases/{case_id}/messages", headers=lh, json={"text": "Hello mentor!"})
    assert msg_res.status_code == 200

    # 5. ETag changes after new message
    st_res2 = c.get(f"/api/cases/{case_id}/state", headers=lh)
    assert st_res2.status_code == 200
    etag2 = st_res2.headers.get("ETag")
    assert etag1 != etag2
    assert st_res2.json()["message_count"] == st["message_count"] + 1

    # 6. Fetch messages with since cursor
    all_msgs = c.get(f"/api/cases/{case_id}/messages", headers=lh).json()
    assert len(all_msgs["messages"]) == st_res2.json()["message_count"]
    cursor = all_msgs["next_since"]
    assert cursor is not None

    # Calling since=cursor returns empty list and unchanged cursor
    since_res = c.get(f"/api/cases/{case_id}/messages?since={cursor}", headers=lh).json()
    assert since_res["messages"] == []
    assert since_res["next_since"] == cursor

    # Another message
    c.post(f"/api/cases/{case_id}/messages", headers=lh, json={"text": "Second message"})
    newer_msgs = c.get(f"/api/cases/{case_id}/messages?since={cursor}", headers=lh).json()
    assert len(newer_msgs["messages"]) == 1
    assert newer_msgs["messages"][0]["text"] == "Second message"


def test_screened_messages_hidden(env):
    c, mp = env
    lh = login(c, name="Student Screened", age=20)
    res = c.post(
        "/api/cases",
        headers=lh,
        json={"category": "technical", "concept_id": "sql_outer_join", "reason": "help with join"},
    )
    case_id = res.json()["case_id"]

    # Insert an unscreened / blocked message directly into DB
    with dbm.SessionLocal() as s:
        s.add(
            CaseMessage(
                case_id=case_id,
                sender="learner",
                text="blocked phone number 9999999999",
                screened=False,
                blocked_reason="phone",
            )
        )
        s.commit()

    # Query state and messages
    st = c.get(f"/api/cases/{case_id}/state", headers=lh).json()
    msgs = c.get(f"/api/cases/{case_id}/messages", headers=lh).json()

    # Unscreened message must never appear in count or messages
    texts = [m["text"] for m in msgs["messages"]]
    assert not any("9999999999" in t for t in texts)
    assert st["message_count"] == len(msgs["messages"])


def test_ownership_and_roles(env):
    c, mp = env
    mh, mid = new_real_mentor(c, mp, "Assigned Mentor")
    mh2, mid2 = new_real_mentor(c, mp, "Other Mentor")
    lh = login(c, name="Owner Learner", age=22)
    lh_other = login(c, name="Stranger Learner", age=22)

    res = c.post(
        "/api/cases",
        headers=lh,
        json={"category": "technical", "concept_id": "sql_outer_join", "reason": "help with join"},
    )
    case_id = res.json()["case_id"]

    # Assign case to assigned mentor in DB
    with dbm.SessionLocal() as s:
        k = s.get(MentorCase, case_id)
        k.mentor_id = mid
        s.commit()

    # Other learner accessing case => 404
    assert c.get(f"/api/cases/{case_id}/state", headers=lh_other).status_code == 404
    assert c.get(f"/api/cases/{case_id}/messages", headers=lh_other).status_code == 404

    # Assigned mentor can access mentor console state & messages
    m_st = c.get(f"/api/mentor-console/cases/{case_id}/state", headers=mh)
    assert m_st.status_code == 200
    assert m_st.json()["status"] is not None

    m_msgs = c.get(f"/api/mentor-console/cases/{case_id}/messages", headers=mh)
    assert m_msgs.status_code == 200

    # Other mentor accessing => 404
    assert c.get(f"/api/mentor-console/cases/{case_id}/state", headers=mh2).status_code == 404
    assert c.get(f"/api/mentor-console/cases/{case_id}/messages", headers=mh2).status_code == 404

    # Learner attempting to call mentor console endpoint => 403
    assert c.get(f"/api/mentor-console/cases/{case_id}/state", headers=lh).status_code == 403


def test_same_timestamp_messages(env):
    c, mp = env
    lh = login(c, name="Timestamp Learner", age=22)
    res = c.post(
        "/api/cases",
        headers=lh,
        json={"category": "technical", "concept_id": "sql_outer_join", "reason": "test"},
    )
    case_id = res.json()["case_id"]

    t0 = now() + timedelta(minutes=10)
    with dbm.SessionLocal() as s:
        # Two messages with the exact same timestamp
        s.add(CaseMessage(id="cm_test_1", case_id=case_id, sender="learner", text="msg1", created_at=t0))
        s.add(CaseMessage(id="cm_test_2", case_id=case_id, sender="mentor", text="msg2", created_at=t0))
        s.commit()

    # Query before t0
    before = (t0 - timedelta(seconds=1)).isoformat()
    res = c.get(f"/api/cases/{case_id}/messages?since={before}", headers=lh).json()
    returned_ids = [m["id"] for m in res["messages"]]
    assert "cm_test_1" in returned_ids
    assert "cm_test_2" in returned_ids
    assert res["next_since"] == t0.isoformat()


def test_status_change_updates_state(env):
    c, mp = env
    mh, mid = new_real_mentor(c, mp, "Accepting Mentor")
    lh = login(c, name="Student Accept", age=21)

    res = c.post(
        "/api/cases",
        headers=lh,
        json={"category": "technical", "concept_id": "sql_outer_join", "reason": "help with join"},
    )
    case_id = res.json()["case_id"]

    st1 = c.get(f"/api/cases/{case_id}/state", headers=lh)
    etag1 = st1.headers.get("ETag")
    status1 = st1.json()["status"]

    # Now mentor accepts case via mentor-console
    acc_res = c.post(
        f"/api/mentor-console/cases/{case_id}/accept",
        headers=mh,
        json={"slot": "Sat 10:00"},
    )
    assert acc_res.status_code == 200

    # State reflects status change and new ETag
    st2 = c.get(f"/api/cases/{case_id}/state", headers=lh)
    assert st2.status_code == 200
    assert st2.json()["status"] == "accepted"
    assert st2.headers.get("ETag") != etag1
