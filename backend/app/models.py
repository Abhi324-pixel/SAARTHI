"""ORM models. Portable types only (String/Integer/Float/JSON/DateTime) so SQLite and Postgres behave alike.

Rules baked into the schema:
  * evidence_events is append-only and records the SOURCE TYPE of every observation. Only
    question / work_product / explain_back / mentor evidence may move mastery; `feedback` never does.
  * every mock record carries is_mock=True and a `mock_` id prefix so mock and real rows cannot mix.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


class Base(DeclarativeBase):
    pass


class Learner(Base):
    __tablename__ = "learners"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    age: Mapped[int] = mapped_column(Integer, default=20)
    language_pref: Mapped[str] = mapped_column(String(16), default="english")  # english | hindi | hinglish
    role_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    weekly_hours: Mapped[float] = mapped_column(Float, default=6.0)
    horizon_weeks: Mapped[int] = mapped_column(Integer, default=12)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # dev-only clock offset (days) so spaced review can be demonstrated; always 0 in prod
    clock_offset_days: Mapped[float] = mapped_column(Float, default=0.0)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ConceptState(Base):
    __tablename__ = "concept_states"
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), primary_key=True)
    concept_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    p_known: Mapped[float] = mapped_column(Float, default=0.2)
    n_evidence: Mapped[int] = mapped_column(Integer, default=0)
    n_success: Mapped[int] = mapped_column(Integer, default=0)
    source_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    last_evidence_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    overconfident_count: Mapped[int] = mapped_column(Integer, default=0)
    disputed: Mapped[bool] = mapped_column(Boolean, default=False)
    # concept-level learner-facing teaching state
    last_strategy: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    attempts_since_unresolved: Mapped[int] = mapped_column(Integer, default=0)


class EvidenceEvent(Base):
    __tablename__ = "evidence_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ev_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    concept_id: Mapped[str] = mapped_column(String(64), index=True)
    source_type: Mapped[str] = mapped_column(String(24))  # question | work_product | explain_back | mentor | feedback | self_report
    item_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0..1 when graded
    stated_confidence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1..5
    grader: Mapped[str] = mapped_column(String(120), default="")  # e.g. "mcq", "sql_exec", "llm:gemini-3.5-flash-lite:v1"
    grader_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p_before: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    changed_mastery: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class MisconceptionInstance(Base):
    __tablename__ = "misconception_instances"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("mi_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    concept_id: Mapped[str] = mapped_column(String(64))
    misconception_id: Mapped[str] = mapped_column(String(64))
    # candidate -> confirmed -> correcting -> resolved ; or disputed
    status: Mapped[str] = mapped_column(String(16), default="candidate")
    channel: Mapped[str] = mapped_column(String(24), default="question")
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # read-back statement shown to the learner
    cycles: Mapped[int] = mapped_column(Integer, default=0)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    verify_after: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class RoadmapVersion(Base):
    __tablename__ = "roadmap_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("rm_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    change_reason: Mapped[str] = mapped_column(Text, default="")
    diff: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class LearningSession(Base):
    __tablename__ = "learning_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ss_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(24))  # probe | explain_back | interview | stuck | review | teach | intake
    concept_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    channel: Mapped[str] = mapped_column(String(12), default="text")
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class TranscriptTurn(Base):
    __tablename__ = "transcript_turns"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("tt_"))
    session_id: Mapped[str] = mapped_column(ForeignKey("learning_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # learner | mentor_ai | system
    text: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Mentor(Base):
    """Backing table for the DB mentor directory. The mock directory reads seed/mentors.json instead;
    `scripts/seed.py` loads the same fixtures here so the two sources can be swapped."""
    __tablename__ = "mentors"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    tier: Mapped[str] = mapped_column(String(24))  # skill_mentor | margdarshak
    headline: Mapped[str] = mapped_column(String(240), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    expertise: Mapped[list[str]] = mapped_column(JSON, default=list)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    availability: Mapped[list[str]] = mapped_column(JSON, default=list)
    verification_status: Mapped[str] = mapped_column(String(16), default="unverified")
    active_case_cap: Mapped[int] = mapped_column(Integer, default=3)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)


class MentorCase(Base):
    __tablename__ = "mentor_cases"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("mc_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    mentor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tier: Mapped[str] = mapped_column(String(24))
    category: Mapped[str] = mapped_column(String(16))  # technical | career | wellbeing
    concept_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    trigger: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|matched|accepted|scheduled|held|followup|closed|escalated
    report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    match_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    scheduled_for: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    outcome: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    followup: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    p_at_open: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class CaseMessage(Base):
    __tablename__ = "case_messages"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cm_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("mentor_cases.id", ondelete="CASCADE"), index=True)
    sender: Mapped[str] = mapped_column(String(12))  # learner | mentor | system
    text: Mapped[str] = mapped_column(Text)
    screened: Mapped[bool] = mapped_column(Boolean, default=True)
    blocked_reason: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Consent(Base):
    __tablename__ = "consents"
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), primary_key=True)  # mentor_sessions | transcript_share
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | granted | revoked
    granted_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)  # learner or guardian
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class LearnerCorrection(Base):
    __tablename__ = "learner_corrections"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("lc_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    concept_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(24))  # dispute_level | dispute_misconception | already_know
    note: Mapped[str] = mapped_column(Text, default="")
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class StrategyOutcome(Base):
    __tablename__ = "strategy_outcomes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("so_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    concept_id: Mapped[str] = mapped_column(String(64))
    cluster: Mapped[str] = mapped_column(String(40), default="")
    strategy: Mapped[str] = mapped_column(String(40))
    p_before: Mapped[float] = mapped_column(Float)
    p_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # filled by a LATER evidence event
    gain: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SafeguardingReport(Base):
    __tablename__ = "safeguarding_reports"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("sr_"))
    reporter_id: Mapped[str] = mapped_column(String(64))
    case_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    category: Mapped[str] = mapped_column(String(24), default="concern")
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class CohortMember(Base):
    """Backing table for the DB cohort provider (teacher / institution view)."""
    __tablename__ = "cohort_members"
    cohort_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
