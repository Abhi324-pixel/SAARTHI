"""C06 — Learner profile statistics engine.

Computes honest, evidence-derived activity metrics for the learner profile.
No invented scores, XP, or gamified numbers.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import EvidenceEvent, Learner, LearningSession, MentorCase
from . import mastery, streak as streak_engine


def stats(db: Session, learner: Learner) -> dict[str, Any]:
    views = mastery.concept_views(db, learner)

    proficient_or_better = sum(
        1 for v in views.values() if v.get("level") in ("proficient", "mastered")
    )
    concepts_assessed = sum(
        1 for v in views.values() if v.get("level") != "not_assessed"
    )

    # Checks answered (MCQs, excluding simulated demo grader)
    checks_answered = db.scalar(
        select(func.count(EvidenceEvent.id)).where(
            EvidenceEvent.learner_id == learner.id,
            EvidenceEvent.source_type == "question",
            EvidenceEvent.grader != "simulated",
        )
    ) or 0

    # Work products run (SQL practice, excluding simulated)
    work_products_run = db.scalar(
        select(func.count(EvidenceEvent.id)).where(
            EvidenceEvent.learner_id == learner.id,
            EvidenceEvent.source_type == "work_product",
            EvidenceEvent.grader != "simulated",
        )
    ) or 0

    # Explain-backs finished
    explain_backs_finished = db.scalar(
        select(func.count(LearningSession.id)).where(
            LearningSession.learner_id == learner.id,
            LearningSession.mode == "explain_back",
            LearningSession.status.in_(("completed", "done")),
        )
    ) or 0

    # Interviews finished
    interviews_finished = db.scalar(
        select(func.count(LearningSession.id)).where(
            LearningSession.learner_id == learner.id,
            LearningSession.mode == "interview",
            LearningSession.status.in_(("completed", "done")),
        )
    ) or 0

    # Closed mentor cases
    mentor_cases_closed = db.scalar(
        select(func.count(MentorCase.id)).where(
            MentorCase.learner_id == learner.id,
            MentorCase.status == "closed",
        )
    ) or 0

    member_since = (
        learner.created_at.strftime("%Y-%m-%d")
        if learner.created_at
        else "2026-10-01"
    )

    streak_data = None
    try:
        streak_data = streak_engine.summary(db, learner)
    except Exception:
        pass

    return {
        "concepts_proficient_or_better": proficient_or_better,
        "concepts_assessed": concepts_assessed,
        "checks_answered": checks_answered,
        "work_products_run": work_products_run,
        "explain_backs_finished": explain_backs_finished,
        "interviews_finished": interviews_finished,
        "mentor_cases_closed": mentor_cases_closed,
        "member_since": member_since,
        "streak": streak_data,
    }
