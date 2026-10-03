"""C05 — in-app notifications and per-case "read up to here" markers.

`recipient_id` is the sign-in account id (a learner, a mentor or an admin), so there is no FK to learners. Rows hold a `kind` and
`params` (first names, topic names, counts) — never message text — and the browser renders the sentence from its own translation
dictionary. Export and deletion are registered with the privacy registry.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .. import privacy
from ..models import Base, Learner, new_id, now


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("nt_"))
    recipient_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    link: Mapped[str] = mapped_column(String(200), default="")
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    __table_args__ = (Index("ix_notifications_recipient_read", "recipient_id", "read_at"),)


class CaseRead(Base):
    __tablename__ = "case_reads"
    case_id: Mapped[str] = mapped_column(ForeignKey("mentor_cases.id", ondelete="CASCADE"), primary_key=True)
    reader_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_read_at: Mapped[datetime] = mapped_column(DateTime, default=now)


def _export(db: Session, learner: Learner) -> list[dict[str, Any]]:
    rows = db.scalars(select(Notification).where(Notification.recipient_id == learner.id).order_by(Notification.created_at))
    return [{"kind": r.kind, "params": r.params, "at": r.created_at.isoformat(timespec="minutes"), "read": r.read_at is not None} for r in rows]


def _delete(db: Session, learner: Learner) -> None:
    db.execute(delete(Notification).where(Notification.recipient_id == learner.id))
    db.execute(delete(CaseRead).where(CaseRead.reader_id == learner.id))


privacy.register_export("notifications", _export)
privacy.register_delete(_delete)
