"""D01 — real guardian consent: the request sent to a guardian and its single-use link tokens."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .. import privacy
from ..models import Base, Learner, new_id, now


class GuardianRequest(Base):
    __tablename__ = "guardian_requests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("gr_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(32), default="mentor_sessions")
    guardian_email: Mapped[str] = mapped_column(String(200), default="")   # blanked on decline / withdrawal
    lang: Mapped[str] = mapped_column(String(16), default="english")
    status: Mapped[str] = mapped_column(String(16), default="sent")        # sent | approved | declined | withdrawn | superseded
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ConsentToken(Base):
    """Bookkeeping that makes a guardian link single-use. The signed token itself is never stored."""
    __tablename__ = "consent_tokens"
    token_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ct_"))
    request_id: Mapped[str] = mapped_column(ForeignKey("guardian_requests.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(12))                       # approve | withdraw
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


def mask_email(email: str) -> str:
    if "@" not in email:
        return ""
    name, _, domain = email.partition("@")
    return (name[:1] + "***@" + domain) if name else "***@" + domain


def _export(db: Session, learner: Learner) -> list[dict[str, Any]]:
    rows = db.scalars(select(GuardianRequest).where(GuardianRequest.learner_id == learner.id).order_by(GuardianRequest.created_at))
    return [{"scope": r.scope, "status": r.status, "guardian": mask_email(r.guardian_email) or None,
             "sent_at": r.created_at.isoformat(timespec="minutes"),
             "decided_at": r.decided_at.isoformat(timespec="minutes") if r.decided_at else None} for r in rows]


privacy.register_export("guardian_consent_requests", _export)   # deletion is covered by the FK cascade
