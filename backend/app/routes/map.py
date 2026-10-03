"""Learning Navigation Map Router: endpoints for self-generating learning maps and dynamic goals."""

from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import current_learner, get_db
from ..engines import challenge_generator, knowledge_graph, learning_navigation, mastery, misconception, planner
from ..models import EvidenceEvent, Learner, RoadmapVersion
from ..models_ext.G01 import VakhSubmission

router = APIRouter(prefix="/api/map", tags=["map"])


class GoalUpdateIn(BaseModel):
    goal_id: str = Field(description="Target role / career destination (e.g. backend_developer, data_analyst, ml_engineer)")


@router.get("")
def get_map(
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db)
):
    """Returns the complete dynamic learning navigation map computed from the learner's current state."""
    return learning_navigation.generate_learning_map(db, lr)


@router.post("/goal")
def set_goal(
    body: GoalUpdateIn,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db)
):
    """Changes the learner's goal destination, retains all transferable mastery, and recalculates the map."""
    try:
        return learning_navigation.change_learner_goal(db, lr, body.goal_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to update goal: {str(e)}")


@router.get("/node/{concept_id}")
def inspect_node(
    concept_id: str,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db)
):
    """Returns detailed inspection metadata for a single node, including blockers, BKT mastery, and Vakh challenge."""
    subgraph = knowledge_graph.get_learning_subgraph(db, lr)
    node = next((n for n in subgraph["nodes"] if n["id"] == concept_id), None)
    if not node:
        raise HTTPException(404, f"Concept '{concept_id}' not found in current learning graph")

    # Get recent evidence for this concept
    evidence_rows = list(db.scalars(
        select(EvidenceEvent)
        .where(EvidenceEvent.learner_id == lr.id, EvidenceEvent.concept_id == concept_id)
        .order_by(EvidenceEvent.created_at.desc())
        .limit(5)
    ))
    evidence_items = [
        {
            "id": ev.id,
            "source_type": ev.source_type,
            "score": ev.score,
            "grader": ev.grader,
            "at": ev.created_at.isoformat()
        }
        for ev in evidence_rows
    ]

    # Get associated Vakh challenge
    challenge = challenge_generator.get_or_create_challenge(db, concept_id, lr)

    # Get past Vakh submissions if any
    submissions = list(db.scalars(
        select(VakhSubmission)
        .where(VakhSubmission.learner_id == lr.id, VakhSubmission.concept_id == concept_id)
        .order_by(VakhSubmission.created_at.desc())
    ))
    vakh_items = [
        {
            "id": s.id,
            "score": s.score,
            "status": s.status,
            "reviewer_feedback": s.reviewer_feedback,
            "reviewer_type": s.reviewer_type,
            "at": s.created_at.isoformat()
        }
        for s in submissions
    ]

    return {
        "node": node,
        "challenge": challenge,
        "evidence_history": evidence_items,
        "vakh_submissions": vakh_items,
        "prerequisites_detail": [
            next((n for n in subgraph["nodes"] if n["id"] == p), {"id": p, "title": p, "p_known": 0.0, "state": "LOCKED"})
            for p in node.get("prerequisites", [])
        ],
        "dependents_detail": [
            next((n for n in subgraph["nodes"] if n["id"] == d), {"id": d, "title": d, "p_known": 0.0, "state": "LOCKED"})
            for d in node.get("dependents", [])
        ]
    }


@router.get("/history")
def map_history(
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db)
):
    """Returns the version history of the learning map, explaining what changed and why."""
    versions = list(db.scalars(
        select(RoadmapVersion)
        .where(RoadmapVersion.learner_id == lr.id)
        .order_by(RoadmapVersion.version.desc())
        .limit(10)
    ))
    return {
        "current_version": versions[0].version if versions else 1,
        "history": [
            {
                "version": v.version,
                "reason": v.change_reason,
                "diff": v.diff,
                "at": v.created_at.isoformat()
            }
            for v in versions
        ]
    }
