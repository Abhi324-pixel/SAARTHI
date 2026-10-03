"""G01: Real Knowledge Graph, Adaptive Detours, Dynamic Challenges, and Vakh Integration.

Implements database-backed graph entities, Vakh challenge definitions, and submission tracking
with idempotency to prevent duplicate evidence processing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .. import privacy
from ..models import Base, new_id, now


class KnowledgeNode(Base):
    """A node in the learning knowledge graph."""
    __tablename__ = "knowledge_nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    title_hi: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    node_type: Mapped[str] = mapped_column(String(32), default="CONCEPT")
    # SKILL | CONCEPT | TOPIC | PROJECT | PRACTICE | ASSESSMENT | RESOURCE | CHALLENGE
    domain: Mapped[str] = mapped_column(String(40), default="sql")
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner")
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=45)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class KnowledgeEdge(Base):
    """A directed edge expressing a relationship between two knowledge nodes."""
    __tablename__ = "knowledge_edges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("edge_"))
    source_node_id: Mapped[str] = mapped_column(String(64), index=True)
    target_node_id: Mapped[str] = mapped_column(String(64), index=True)
    relationship_type: Mapped[str] = mapped_column(String(32))
    # PREREQUISITE | BUILDS_ON | RELATED_TO | PART_OF | LEADS_TO | ASSESSED_BY | PRACTICED_BY | VERIFIED_BY
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class VakhChallenge(Base):
    """Structured challenge specification for project/build verification on Vakh."""
    __tablename__ = "vakh_challenges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("vch_"))
    concept_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(20), default="intermediate")
    requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    starter_code: Mapped[str] = mapped_column(Text, default="")
    expected_output: Mapped[str] = mapped_column(Text, default="")
    evaluation_criteria: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    vakh_form_id: Mapped[str] = mapped_column(String(80), default="default_challenge_form")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class VakhSubmission(Base):
    """A learner's work submitted or reviewed via Vakh."""
    __tablename__ = "vakh_submissions"
    __table_args__ = (
        UniqueConstraint("vakh_post_id", name="uq_vakh_submissions_post_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("vsub_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    challenge_id: Mapped[str] = mapped_column(String(64), index=True)
    concept_id: Mapped[str] = mapped_column(String(64), index=True)
    vakh_post_id: Mapped[str] = mapped_column(String(120), index=True)
    submission_url: Mapped[str] = mapped_column(String(400), default="")
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0.0 to 1.0
    status: Mapped[str] = mapped_column(String(24), default="submitted")  # submitted | reviewed | rejected
    reviewer_type: Mapped[str] = mapped_column(String(24), default="auto")  # mentor | peer | auto
    reviewer_feedback: Mapped[str] = mapped_column(Text, default="")
    evidence_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class DetourLog(Base):
    """Record of adaptive detours taken when a learner struggles or has an active misconception."""
    __tablename__ = "detour_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("det_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    target_concept_id: Mapped[str] = mapped_column(String(64), index=True)
    detour_concept_id: Mapped[str] = mapped_column(String(64), index=True)
    trigger: Mapped[str] = mapped_column(String(40))  # misconception | weak_prereq | repeated_failure
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | resolved | bypassed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


privacy.register_export("vakh_submissions", lambda db, learner: [
    {"challenge_id": s.challenge_id, "concept_id": s.concept_id, "score": s.score,
     "status": s.status, "reviewer_feedback": s.reviewer_feedback, "created_at": s.created_at.isoformat()}
    for s in db.query(VakhSubmission).filter(VakhSubmission.learner_id == learner.id).all()
])

privacy.register_export("detour_logs", lambda db, learner: [
    {"target": d.target_concept_id, "detour": d.detour_concept_id, "trigger": d.trigger,
     "reason": d.reason, "status": d.status, "created_at": d.created_at.isoformat()}
    for d in db.query(DetourLog).filter(DetourLog.learner_id == learner.id).all()
])
