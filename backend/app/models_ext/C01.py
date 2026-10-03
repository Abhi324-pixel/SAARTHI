"""C01 — mentor applications and the record of which checks a human actually did."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base, new_id, now


class MentorApplication(Base):
    """One application per sign-in account (`user_id` is the auth user id, which becomes `Mentor.id` on approval).
    No FK to learners: a mentor does not have to be a learner."""
    __tablename__ = "mentor_applications"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ma_"))
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    tier_requested: Mapped[str] = mapped_column(String(24), default="skill_mentor")      # skill_mentor | margdarshak
    name: Mapped[str] = mapped_column(String(120), default="")
    headline: Mapped[str] = mapped_column(String(240), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    years_experience: Mapped[int] = mapped_column(Integer, default=0)
    organisation: Mapped[str] = mapped_column(String(160), default="")
    expertise: Mapped[list[str]] = mapped_column(JSON, default=list)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    availability: Mapped[list[str]] = mapped_column(JSON, default=list)
    screen_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    pledge_version: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    pledge_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")        # draft | submitted | needs_info | approved | rejected
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reviewer_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class MentorCheck(Base):
    """What a human really verified about a mentor (so a "verified" badge is auditable)."""
    __tablename__ = "mentor_checks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("mk_"))
    mentor_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(24))          # identity | reference | interview | police_verification
    done_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    done_by: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(Text, default="")
