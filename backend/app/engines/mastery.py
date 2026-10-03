"""Learner Twin mastery model: Bayesian Knowledge Tracing with evidence provenance, forgetting and flags.

Rules enforced here (and nowhere else):
  * Only question / work_product / explain_back / mentor evidence can move P(known).
  * `feedback` and `self_report` are recorded but NEVER change mastery.
  * Stated confidence is stored (for calibration) but never raises mastery.
  * "Mastered" needs P >= 0.95 AND evidence from >= 2 source types, one of them an application type
    (work_product or explain_back).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..models import ConceptState, EvidenceEvent, Learner, MisconceptionInstance, now as db_now

MASTERY_SOURCES = {"question", "work_product", "explain_back", "mentor"}
APPLICATION_SOURCES = {"work_product", "explain_back"}

# guess / slip per source, plus how strongly an observation counts as a learning opportunity
SOURCE_PARAMS: dict[str, dict[str, float]] = {
    "question": {"guess": 0.25, "slip": 0.10, "learn": 0.30},
    "work_product": {"guess": 0.05, "slip": 0.10, "learn": 1.00},
    "explain_back": {"guess": 0.08, "slip": 0.12, "learn": 1.00},
    "mentor": {"guess": 0.20, "slip": 0.15, "learn": 0.50},
}

LEVELS = ["not_assessed", "unknown", "developing", "proficient", "mastered"]
REVIEW_INTERVALS_DAYS = [1, 3, 7, 14, 30]
MIN_GRADER_CONFIDENCE = 0.45  # below this an LLM grade is shown but does not move mastery


# ---------------------------------------------------------------------------------------------------
# pure maths
# ---------------------------------------------------------------------------------------------------

def bkt_update(p: float, score: float, source: str, p_learn: float) -> float:
    """One BKT step with a soft observation `score` in [0,1] (1 = fully correct)."""
    prm = SOURCE_PARAMS[source]
    g, s = prm["guess"], prm["slip"]
    score = min(1.0, max(0.0, score))
    post_correct = p * (1 - s) / (p * (1 - s) + (1 - p) * g)
    post_wrong = p * s / (p * s + (1 - p) * (1 - g))
    post = score * post_correct + (1 - score) * post_wrong
    post = post + (1 - post) * p_learn * prm["learn"]
    return min(0.999, max(0.001, post))


def half_life_days(n_success: int) -> float:
    return float(min(45, 5 + 3 * n_success))


def decayed_p(p: float, p_floor: float, last_evidence_at: Optional[datetime], now: datetime, n_success: int) -> float:
    if last_evidence_at is None or p <= p_floor:
        return p
    days = max(0.0, (now - last_evidence_at).total_seconds() / 86400.0)
    return p_floor + (p - p_floor) * math.pow(0.5, days / half_life_days(n_success))


def level_of(p_eff: float, n_evidence: int, source_types: list[str]) -> str:
    if n_evidence == 0:
        return "not_assessed"
    if p_eff < 0.40:
        return "unknown"
    if p_eff < 0.80:
        return "developing"
    if p_eff < 0.95:
        return "proficient"
    st = set(source_types) & MASTERY_SOURCES
    if len(st) >= 2 and (st & APPLICATION_SOURCES):
        return "mastered"
    return "proficient"


def confidence_of(n_evidence: int, source_types: list[str], overconfident: int = 0) -> float:
    if n_evidence == 0:
        return 0.0
    base = 1 - math.exp(-n_evidence / 3.0)
    diversity = min(1.0, 0.7 + 0.15 * len(set(source_types) & MASTERY_SOURCES))
    return round(max(0.0, min(1.0, base * diversity - 0.05 * overconfident)), 3)


def next_review_at(last_success_at: Optional[datetime], n_success: int) -> Optional[datetime]:
    if last_success_at is None:
        return None
    idx = min(max(n_success - 1, 0), len(REVIEW_INTERVALS_DAYS) - 1)
    return last_success_at + timedelta(days=REVIEW_INTERVALS_DAYS[idx])


# ---------------------------------------------------------------------------------------------------
# learner clock (dev tool: advance time so spaced review can be shown in a demo)
# ---------------------------------------------------------------------------------------------------

def learner_now(learner: Learner) -> datetime:
    return db_now() + timedelta(days=learner.clock_offset_days or 0.0)


# ---------------------------------------------------------------------------------------------------
# state access
# ---------------------------------------------------------------------------------------------------

def ensure_states(db: Session, learner: Learner) -> dict[str, ConceptState]:
    content = get_content()
    rows = {r.concept_id: r for r in db.scalars(select(ConceptState).where(ConceptState.learner_id == learner.id))}
    for cid, c in content.concepts.items():
        if cid not in rows:
            cs = ConceptState(learner_id=learner.id, concept_id=cid, p_known=c.p_init, n_evidence=0,
                              n_success=0, source_types=[], overconfident_count=0)
            db.add(cs)
            rows[cid] = cs
    db.flush()
    return rows


def effective_p(cs: ConceptState, now: datetime) -> float:
    c = get_content().concepts[cs.concept_id]
    return decayed_p(cs.p_known, c.p_init, cs.last_evidence_at, now, cs.n_success)


def active_misconceptions(db: Session, learner_id: str, concept_id: Optional[str] = None,
                          statuses: tuple[str, ...] = ("confirmed", "correcting", "pending_verify")) -> list[MisconceptionInstance]:
    q = select(MisconceptionInstance).where(MisconceptionInstance.learner_id == learner_id,
                                            MisconceptionInstance.status.in_(statuses))
    if concept_id:
        q = q.where(MisconceptionInstance.concept_id == concept_id)
    return list(db.scalars(q))


def concept_views(db: Session, learner: Learner) -> dict[str, dict[str, Any]]:
    """Level, probability, confidence and flags for every concept, as the dashboard / planner see them."""
    content = get_content()
    now = learner_now(learner)
    states = ensure_states(db, learner)
    base: dict[str, dict[str, Any]] = {}
    for cid, cs in states.items():
        p = effective_p(cs, now)
        lvl = level_of(p, cs.n_evidence, cs.source_types or [])
        nxt = next_review_at(cs.last_success_at, cs.n_success)
        base[cid] = {
            "concept_id": cid, "name": content.concepts[cid].name, "name_hi": content.concepts[cid].name_hi,
            "domain": content.concepts[cid].domain,
            "p": round(p, 3), "p_stored": round(cs.p_known, 3), "level": lvl,
            "confidence": confidence_of(cs.n_evidence, cs.source_types or [], cs.overconfident_count),
            "n_evidence": cs.n_evidence, "source_types": list(cs.source_types or []),
            "next_review_at": nxt.isoformat() if nxt else None,
            "due_for_review": bool(nxt and now >= nxt and lvl in ("developing", "proficient", "mastered")),
            "disputed": bool(cs.disputed),
            "overconfident": cs.overconfident_count >= 2,
        }
    mis_by_concept: dict[str, list[MisconceptionInstance]] = {}
    for mi in active_misconceptions(db, learner.id):
        mis_by_concept.setdefault(mi.concept_id, []).append(mi)
    for cid, v in base.items():
        flags: list[str] = []
        if mis_by_concept.get(cid):
            flags.append("misconception")
        for pid in content.prereqs(cid):
            pv = base[pid]
            if pv["n_evidence"] > 0 and pv["level"] in ("unknown", "developing"):
                flags.append("blocked")
                break
        if v["due_for_review"]:
            flags.append("due_for_review")
        if v["disputed"]:
            flags.append("disputed")
        if v["n_evidence"] > 0 and v["confidence"] < 0.35:
            flags.append("low_confidence")
        if v["overconfident"]:
            flags.append("overconfident")
        v["flags"] = flags
        v["misconceptions"] = [m.misconception_id for m in mis_by_concept.get(cid, [])]
        v["blocked_by"] = [pid for pid in content.prereqs(cid)
                           if base[pid]["n_evidence"] > 0 and base[pid]["level"] in ("unknown", "developing")]
    return base


# ---------------------------------------------------------------------------------------------------
# applying evidence
# ---------------------------------------------------------------------------------------------------

def apply_evidence(
    db: Session,
    learner: Learner,
    concept_id: str,
    source_type: str,
    *,
    score: Optional[float] = None,
    correct: Optional[bool] = None,
    item_id: Optional[str] = None,
    stated_confidence: Optional[int] = None,
    grader: str = "",
    grader_confidence: Optional[float] = None,
    detail: Optional[dict] = None,
) -> dict[str, Any]:
    """Record one evidence event and, if the source is allowed to, move mastery. Returns before/after."""
    content = get_content()
    if concept_id not in content.concepts:
        raise KeyError(concept_id)
    states = ensure_states(db, learner)
    cs = states[concept_id]
    now = learner_now(learner)
    p_before_eff = effective_p(cs, now)
    level_before = level_of(p_before_eff, cs.n_evidence, cs.source_types or [])

    if score is None and correct is not None:
        score = 1.0 if correct else 0.0
    moves = source_type in MASTERY_SOURCES and score is not None
    low_conf = (grader_confidence is not None and grader_confidence < MIN_GRADER_CONFIDENCE)
    if low_conf:
        moves = False

    ev = EvidenceEvent(
        learner_id=learner.id, concept_id=concept_id, source_type=source_type, item_id=item_id,
        correct=correct if correct is not None else (None if score is None else score >= 0.6),
        score=score, stated_confidence=stated_confidence, grader=grader, grader_confidence=grader_confidence,
        p_before=round(p_before_eff, 4), detail=detail or {}, created_at=now,
    )

    if moves:
        # start the update from the decayed estimate, so forgetting is respected
        p_start = p_before_eff
        p_new = bkt_update(p_start, float(score), source_type, content.concepts[concept_id].p_learn)
        cs.p_known = p_new
        cs.n_evidence += 1
        cs.last_evidence_at = now
        if score >= 0.6:
            cs.n_success += 1
            cs.last_success_at = now
        st = set(cs.source_types or [])
        st.add(source_type)
        cs.source_types = sorted(st)
        ev.changed_mastery = True
    ev.p_after = round(effective_p(cs, now), 4)

    # calibration: confident and wrong
    if stated_confidence is not None and score is not None and source_type in ("question", "work_product", "explain_back"):
        if stated_confidence >= 4 and score < 0.4:
            cs.overconfident_count += 1
        elif stated_confidence >= 4 and score >= 0.8 and cs.overconfident_count > 0:
            cs.overconfident_count -= 1

    db.add(ev)
    db.flush()
    p_after = effective_p(cs, now)
    level_after = level_of(p_after, cs.n_evidence, cs.source_types or [])
    return {
        "evidence_id": ev.id, "concept_id": concept_id, "source_type": source_type,
        "moved_mastery": moves, "low_grader_confidence": low_conf,
        "p_before": round(p_before_eff, 3), "p_after": round(p_after, 3),
        "level_before": level_before, "level_after": level_after,
        "level_changed": level_before != level_after,
    }


def overall_mastery(views: dict[str, dict[str, Any]], role_requirements: dict[str, dict]) -> float:
    """Importance-weighted progress toward the role's targets, in [0,1] (TESSA 'readiness' idea)."""
    total = have = 0.0
    for cid, req in role_requirements.items():
        w, tgt = req["weight"], req["target"]
        total += w * tgt
        have += w * min(views[cid]["p"], tgt)
    return round(have / total, 4) if total else 0.0
