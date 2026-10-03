"""In-app notifications (spec docs/features/C05). Created only by the server, as a side effect of a real event.

A notification is `kind` + `params` (first names, topic names, counts), never message text, so nothing sensitive sits on a shared
screen and the browser can translate it. `notify` never raises into the caller: a failed notification must not fail "accept case".
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import adapters
from ..config import settings
from ..models import CaseMessage, Learner, MentorCase, now
from ..models_ext.C05 import CaseRead, Notification
from . import mastery

log = logging.getLogger("saarthi.notify")
PURGE_AFTER = timedelta(days=60)


def notify(db: Session, recipient_id: Optional[str], kind: str, params: Optional[dict[str, Any]] = None, link: str = "",
           dedupe_key: Optional[str] = None) -> None:
    if not recipient_id:
        return
    try:
        with db.begin_nested():
            if dedupe_key:
                row = db.scalars(select(Notification).where(Notification.recipient_id == recipient_id, Notification.dedupe_key == dedupe_key,
                                                            Notification.read_at.is_(None))).first()
                if row is not None:                      # ten messages become one item, with the latest details
                    row.params, row.link, row.updated_at = params or {}, link, now()
                    return
            db.add(Notification(recipient_id=recipient_id, kind=kind, params=params or {}, link=link, dedupe_key=dedupe_key))
    except Exception:  # noqa: BLE001 - cosmetic: never break the action that caused it
        log.exception("could not create notification %s", kind)


def notify_admins(db: Session, kind: str, params: Optional[dict[str, Any]] = None, link: str = "/admin", dedupe_key: Optional[str] = None) -> None:
    for admin_id in settings.admin_ids:
        notify(db, admin_id, kind, params, link, dedupe_key)


def first_name(name: Optional[str], default: str = "Someone") -> str:
    return (name or default).split()[0] if (name or "").strip() else default


# ---------------------------------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------------------------------

def unread_by_case(db: Session, reader_id: str) -> dict[str, int]:
    """Messages from the OTHER side (screened, not system) newer than the reader's last-read marker, per case."""
    cases = list(db.scalars(select(MentorCase).where(or_(MentorCase.learner_id == reader_id, MentorCase.mentor_id == reader_id))))
    if not cases:
        return {}
    marks = {r.case_id: r.last_read_at for r in db.scalars(select(CaseRead).where(CaseRead.reader_id == reader_id,
                                                                                    CaseRead.case_id.in_([c.id for c in cases])))}
    out: dict[str, int] = {}
    for c in cases:
        other = "mentor" if c.learner_id == reader_id else "learner"
        q = select(func.count()).select_from(CaseMessage).where(CaseMessage.case_id == c.id, CaseMessage.sender == other, CaseMessage.screened.is_(True))
        if c.id in marks:
            q = q.where(CaseMessage.created_at > marks[c.id])
        n = db.scalar(q) or 0
        if n:
            out[c.id] = n
    return out


def mark_case_read(db: Session, reader_id: str, case: MentorCase) -> None:
    mark = db.get(CaseRead, (case.id, reader_id))
    if mark is None:
        db.add(CaseRead(case_id=case.id, reader_id=reader_id, last_read_at=now()))
    else:
        mark.last_read_at = now()
    for n in db.scalars(select(Notification).where(Notification.recipient_id == reader_id, Notification.read_at.is_(None),
                                                   Notification.dedupe_key.like(f"case:{case.id}:msg%"))):
        n.read_at = now()
    db.flush()


def unread_count(db: Session, recipient_id: str) -> int:
    return db.scalar(select(func.count()).select_from(Notification).where(Notification.recipient_id == recipient_id, Notification.read_at.is_(None))) or 0


def listing(db: Session, recipient_id: str, limit: int, before: Optional[str]) -> list[dict[str, Any]]:
    from datetime import datetime
    db.query(Notification).filter(Notification.recipient_id == recipient_id, Notification.read_at.is_not(None),
                                  Notification.read_at < now() - PURGE_AFTER).delete(synchronize_session=False)
    q = select(Notification).where(Notification.recipient_id == recipient_id)
    if before:
        try:
            q = q.where(Notification.updated_at < datetime.fromisoformat(before))
        except ValueError:
            pass
    rows = db.scalars(q.order_by(Notification.updated_at.desc()).limit(limit))
    return [{"id": r.id, "kind": r.kind, "params": r.params, "link": r.link, "read": r.read_at is not None,
             "at": r.updated_at.isoformat(timespec="seconds")} for r in rows]


def mark_read(db: Session, recipient_id: str, ids: Optional[list[str]], everything: bool) -> int:
    q = select(Notification).where(Notification.recipient_id == recipient_id, Notification.read_at.is_(None))
    if not everything:
        q = q.where(Notification.id.in_(ids or []))
    n = 0
    for row in db.scalars(q):
        row.read_at = now()
        n += 1
    db.flush()
    return n


def reviews_due_check(db: Session, learner: Learner) -> None:
    """At most once per learner-day: if reviews are due, add one reminder. Cheap on every later poll (settings flag)."""
    today = mastery.learner_now(learner).date().isoformat()
    if (learner.settings or {}).get("reviews_checked") == today:
        return
    learner.settings = {**(learner.settings or {}), "reviews_checked": today}
    due = sum(1 for v in mastery.concept_views(db, learner).values() if v["due_for_review"])
    if due:
        notify(db, learner.id, "reviews_due", {"n": due}, "/reviews", dedupe_key=f"reviews:{today}")
    db.flush()


def recipient_is_real_account(case: MentorCase) -> bool:
    """Demo (mock) mentors are not accounts, so nobody is notified on their behalf."""
    return bool(case.mentor_id) and not adapters.mentors().is_mock
