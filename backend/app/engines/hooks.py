"""Glue that runs after new evidence: settle strategy outcomes, refresh the roadmap, surface escalation triggers.

Keeping this in one place guarantees every channel (quiz, SQL, explain-back, voice, mentor) updates the
same things - which is what makes the roadmap visibly change after a conversation.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import Learner
from . import escalation, mastery, planner, strategy


def after_evidence(db: Session, learner: Learner, concept_id: Optional[str], trigger: str) -> dict[str, Any]:
    if concept_id:
        v = mastery.concept_views(db, learner).get(concept_id)
        if v:
            strategy.settle(db, learner, concept_id, v["p"])
    rm = planner.refresh(db, learner, trigger)
    suggestions = escalation.check_triggers(db, learner)
    return {
        "roadmap": {"version": rm["version"], "changed": rm["changed"], "diff": rm["diff"],
                    "change_reason": rm["change_reason"], "readiness_now": rm["summary"]["readiness_now"],
                    "readiness_after": rm["summary"]["readiness_after"]},
        "escalation_suggestions": suggestions,
    }
