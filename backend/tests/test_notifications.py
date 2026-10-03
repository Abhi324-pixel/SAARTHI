"""C05: notifications and unread counts. Created by the server only, no message text, deduped, private, deleted with the account."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app import db as dbm
from app.config import settings
from app.engines import notify
from app.models import Learner, now
from app.models_ext.C05 import CaseRead, Notification

from .test_api import login
from .test_mentor_apply import complete_application, make_admin
from .test_mentor_console import env, new_real_mentor, one_mentor, open_case  # noqa: F401  (fixtures + helpers)


def inbox(c, h):
    return c.get("/api/notifications", headers=h).json()["notifications"]


def kinds(c, h):
    return [n["kind"] for n in inbox(c, h)]


def summary(c, h):
    return c.get("/api/notifications/summary", headers=h).json()


def test_the_whole_case_flow_creates_the_right_notifications(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    assert kinds(c, mh) == ["case_assigned"] and kinds(c, lh) == []
    n = inbox(c, mh)[0]
    assert n["link"] == f"/mentor-console/{cid}" and n["params"] == {"concept": "LEFT and other outer joins"} and n["read"] is False
    c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh)
    assert kinds(c, lh) == ["case_accepted"] and inbox(c, lh)[0]["params"] == {"mentor": "Real"} and inbox(c, lh)[0]["link"] == f"/mentors/{cid}"
    c.post(f"/api/cases/{cid}/messages", json={"text": "here is my query"}, headers=lh)
    assert sorted(kinds(c, mh)) == ["case_assigned", "case_message"]
    c.post(f"/api/mentor-console/cases/{cid}/messages", json={"text": "thanks, looking now"}, headers=mh)
    assert "case_message" in kinds(c, lh)
    c.post(f"/api/mentor-console/cases/{cid}/outcome", headers=mh, json={"notes": "Covered ON vs WHERE.", "demonstrated": 4})
    assert "case_outcome" in kinds(c, lh)


def test_ten_messages_are_one_deduped_notification_with_a_count_of_unread_messages(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh)
    for i in range(10):
        c.post(f"/api/cases/{cid}/messages", json={"text": f"question number {i}"}, headers=lh)
    assert kinds(c, mh).count("case_message") == 1
    assert summary(c, mh)["cases"] == {cid: 10} and summary(c, mh)["messages_unread"] == 10
    assert summary(c, lh)["cases"] == {}                                                           # own messages never count


def test_reading_a_case_clears_its_unread_count_and_message_notification(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh)
    c.post(f"/api/cases/{cid}/messages", json={"text": "hello mentor"}, headers=lh)
    assert summary(c, mh)["cases"] == {cid: 1}
    assert c.post(f"/api/cases/{cid}/read", headers=mh).status_code == 200
    s = summary(c, mh)
    assert s["cases"] == {} and next(n for n in inbox(c, mh) if n["kind"] == "case_message")["read"] is True
    c.post(f"/api/cases/{cid}/messages", json={"text": "another one"}, headers=lh)
    assert summary(c, mh)["cases"] == {cid: 1}                                                     # rises again with a new message
    assert [n["read"] for n in inbox(c, mh) if n["kind"] == "case_message"].count(False) == 1       # a fresh item, not the old one


def test_marking_read_only_touches_your_own_rows(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    open_case(c, lh)
    theirs = inbox(c, mh)[0]["id"]
    r = c.post("/api/notifications/read", json={"ids": [theirs]}, headers=lh)
    assert r.status_code == 200 and r.json()["marked"] == 0
    assert inbox(c, mh)[0]["read"] is False
    assert c.post("/api/notifications/read", json={"ids": [theirs]}, headers=mh).json()["marked"] == 1
    assert summary(c, mh)["unread"] == 0


def test_mark_all_read(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh)
    assert summary(c, lh)["unread"] == 1
    assert c.post("/api/notifications/read", json={"all": True}, headers=lh).json()["marked"] == 1
    assert summary(c, lh)["unread"] == 0


def test_case_read_requires_being_part_of_the_case(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    stranger = login(c, name="Stranger")
    assert c.post(f"/api/cases/{cid}/read", headers=stranger).status_code == 404
    assert c.post("/api/cases/nope/read", headers=lh).status_code == 404
    assert c.get("/api/notifications/summary").status_code == 401


def test_params_never_contain_message_text_or_ids(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh)
    c.post(f"/api/cases/{cid}/messages", json={"text": "my secret question about 9876 and my school"}, headers=lh)
    c.post(f"/api/mentor-console/cases/{cid}/messages", json={"text": "private mentor reply text"}, headers=mh)
    blob = str(inbox(c, mh)) + str(inbox(c, lh))
    assert "secret" not in blob and "private mentor" not in blob and "9876" not in blob and "school" not in blob
    me = c.get("/api/me", headers=lh).json()
    assert me["id"] not in str([n["params"] for n in inbox(c, mh) + inbox(c, lh)])


def test_a_failing_notification_does_not_fail_the_action(one_mentor, monkeypatch):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]

    def boom(*a, **k):
        raise RuntimeError("db hiccup")
    monkeypatch.setattr(Notification, "__init__", boom)
    r = c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh)
    assert r.status_code == 200 and r.json()["status"] == "accepted"


def test_admins_hear_about_applications_and_reports(env):
    c, mp = env
    ah, admin_id = make_admin(c, mp)
    h = login(c, name="Applicant")
    assert complete_application(c, h).status_code == 200
    assert "mentor_application" in kinds(c, ah) and inbox(c, ah)[0]["link"] == "/admin"
    lh = login(c, name="Priya", age=22)
    c.post("/api/cases", json={"category": "technical", "reason": "I feel hopeless and want to die"}, headers=lh)
    assert "safeguarding_report" in kinds(c, ah)
    case = c.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "x"}, headers=lh).json()
    c.post("/api/reports", json={"case_id": case["case_id"], "detail": "concern"}, headers=lh)
    assert kinds(c, ah).count("safeguarding_report") == 2


def test_reviews_due_reminder_once_per_day_and_never_when_nothing_is_due(env):
    c, mp = env
    h = login(c)
    c.post("/api/dev/seed-demo", headers=h)
    summary(c, h)
    assert "reviews_due" not in kinds(c, h)                                                         # nothing is due yet: checked, no reminder
    c.post("/api/dev/advance-time", json={"days": 20}, headers=h)
    with dbm.SessionLocal() as s:                                                                  # a new learner-day: the daily flag no longer matches
        lr = s.scalars(select(Learner)).first()
        lr.settings = {**(lr.settings or {}), "reviews_checked": "1999-01-01"}
        s.commit()
    summary(c, h)
    n = [x for x in inbox(c, h) if x["kind"] == "reviews_due"]
    assert len(n) == 1 and n[0]["params"]["n"] >= 1 and n[0]["link"] == "/reviews"
    summary(c, h)
    summary(c, h)
    assert [x["kind"] for x in inbox(c, h)].count("reviews_due") == 1


def test_export_and_delete_include_notifications_and_markers(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    cid = open_case(c, lh)["case_id"]
    c.post(f"/api/mentor-console/cases/{cid}/accept", json={"slot": "Mon 18:00"}, headers=mh)
    c.post(f"/api/cases/{cid}/read", headers=lh)
    ex = c.get("/api/me/export", headers=lh).json()["more"]["notifications"]
    assert ex and ex[0]["kind"] == "case_accepted" and "link" not in ex[0]
    me = c.get("/api/me", headers=lh).json()
    assert c.delete("/api/me", headers=lh).json()["deleted"]
    with dbm.SessionLocal() as s:
        assert s.scalars(select(Notification).where(Notification.recipient_id == me["id"])).first() is None
        assert s.scalars(select(CaseRead).where(CaseRead.reader_id == me["id"])).first() is None
        assert s.scalars(select(Notification).where(Notification.recipient_id == mid)).first() is not None   # the mentor's own are untouched


def test_old_read_notifications_are_purged_on_listing(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    open_case(c, lh)
    c.post("/api/notifications/read", json={"all": True}, headers=mh)
    with dbm.SessionLocal() as s:
        for n in s.scalars(select(Notification).where(Notification.recipient_id == mid)):
            n.read_at = now() - timedelta(days=61)
        s.commit()
    assert inbox(c, mh) == []


def test_pagination_cursor_and_limit(one_mentor):
    c, mp, mh, mid, ah, lh = one_mentor
    with dbm.SessionLocal() as s:
        for i in range(5):
            notify.notify(s, mid, "case_assigned", {"concept": f"c{i}"}, "/mentor-console", dedupe_key=f"x{i}")
            s.flush()
        s.commit()
    page = c.get("/api/notifications", params={"limit": 2}, headers=mh).json()["notifications"]
    assert len(page) == 2
    older = c.get("/api/notifications", params={"limit": 10, "before": page[-1]["at"]}, headers=mh).json()["notifications"]
    assert all(n["id"] not in {p["id"] for p in page} for n in older)
    assert c.get("/api/notifications", params={"limit": 1000}, headers=mh).status_code == 200


def test_demo_mentors_get_no_notifications_in_mock_mode(env):
    c, mp = env
    mp.setattr(settings, "mentors_mode", "mock")
    from app import adapters
    adapters.reset()
    lh = login(c, name="Priya", age=22)
    case = c.post("/api/cases", json={"category": "technical", "concept_id": "sql_outer_join", "reason": "stuck"}, headers=lh).json()
    c.post(f"/api/cases/{case['case_id']}/messages", json={"text": "my left join drops customers"}, headers=lh)
    with dbm.SessionLocal() as s:
        assert s.scalars(select(Notification).where(Notification.kind.in_(("case_assigned", "case_message")))).first() is None
    adapters.reset()
