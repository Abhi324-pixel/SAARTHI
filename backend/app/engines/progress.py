"""T06 — Progress-over-time history engine.

Replays the evidence log to build a time series of overall progress and
per-domain progress toward the role target. No new table is needed — the
p_before/p_after snapshots in EvidenceEvent carry the full history.

Algorithm (pure functions, trivially testable):
  1. Start with p = {cid: p_init} for every concept in the role requirements.
  2. Walk evidence rows ordered by created_at; skip those with changed_mastery == False.
  3. Set p[cid] = event.p_after; recompute overall and per-domain incrementally.
  4. Emit one point per event; downsample to ~200 points (last-point-per-day rule).
  5. Mark simulated points (grader == "simulated") so demo history is never
     mistaken for real learning.
  6. The final live value "now" uses mastery.concept_views() to include forgetting.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..models import EvidenceEvent, Learner, MisconceptionInstance, RoadmapVersion
from ..engines import mastery as mastery_engine

MAX_SERIES_POINTS = 200
MAX_MARKERS = 12


# ---------------------------------------------------------------------------
# Domain-level helpers
# ---------------------------------------------------------------------------

def _domain_sums(role_requirements: dict[str, dict], concepts: dict) -> dict[str, dict[str, float]]:
    """Pre-compute per-domain weight×target sums (denominator for each domain)."""
    totals: dict[str, float] = {}
    for cid, req in role_requirements.items():
        dom = concepts[cid].domain
        totals[dom] = totals.get(dom, 0.0) + req["weight"] * req["target"]
    return totals


def _compute_overall_and_domains(
    p: dict[str, float],
    role_requirements: dict[str, dict],
    concepts: dict,
    domain_totals: dict[str, float],
) -> tuple[float, dict[str, float]]:
    """Compute overall and per-domain progress from a current p dict."""
    total_have = total_denom = 0.0
    domain_have: dict[str, float] = {}
    for cid, req in role_requirements.items():
        w, tgt = req["weight"], req["target"]
        dom = concepts[cid].domain
        contrib = w * min(p[cid], tgt)
        total_have += contrib
        total_denom += w * tgt
        domain_have[dom] = domain_have.get(dom, 0.0) + contrib
    overall = round(total_have / total_denom, 4) if total_denom else 0.0
    by_domain = {
        dom: round(domain_have.get(dom, 0.0) / dtot, 4) if dtot else 0.0
        for dom, dtot in domain_totals.items()
    }
    return overall, by_domain


# ---------------------------------------------------------------------------
# Pure replay function (unit-testable)
# ---------------------------------------------------------------------------

class _EventRow:
    """Minimal data class to decouple the pure function from SQLAlchemy."""
    __slots__ = ("concept_id", "p_after", "changed_mastery", "grader", "created_at", "source_type")

    def __init__(self, concept_id: str, p_after: float | None, changed_mastery: bool,
                 grader: str, created_at: datetime, source_type: str):
        self.concept_id = concept_id
        self.p_after = p_after
        self.changed_mastery = changed_mastery
        self.grader = grader
        self.created_at = created_at
        self.source_type = source_type


def replay_series(
    events: list[_EventRow],
    role_requirements: dict[str, dict],
    concepts: dict,
    *,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """Pure replay: walk events and produce a (possibly downsampled) time series.

    Parameters
    ----------
    events:            ordered by created_at ASC, all mastery-changing events for the learner
    role_requirements: {concept_id: {weight, target}}
    concepts:          content.concepts dict (Concept objects)
    since:             if set, only return points at or after this datetime

    Returns list of dicts: {at, overall, by_domain, n, simulated}
    """
    # Initialise with p_init values
    p: dict[str, float] = {cid: concepts[cid].p_init for cid in role_requirements}
    domain_totals = _domain_sums(role_requirements, concepts)

    raw: list[dict[str, Any]] = []
    n = 0
    for ev in events:
        if not ev.changed_mastery:
            continue
        if ev.concept_id not in p:
            continue
        if ev.p_after is None:
            continue
        p[ev.concept_id] = ev.p_after
        overall, by_domain = _compute_overall_and_domains(p, role_requirements, concepts, domain_totals)
        n += 1
        raw.append({
            "at": ev.created_at,
            "overall": overall,
            "by_domain": by_domain,
            "n": n,
            "simulated": ev.grader == "simulated",
        })

    # Downsample: keep last-point-per-day, then trim to MAX_SERIES_POINTS
    if len(raw) > MAX_SERIES_POINTS:
        by_day: dict[str, dict] = {}
        for pt in raw:
            day_key = pt["at"].strftime("%Y-%m-%d")
            by_day[day_key] = pt  # overwrite → keep last of the day
        raw = list(by_day.values())
        # If still too many (unlikely but defensive), keep tail
        if len(raw) > MAX_SERIES_POINTS:
            raw = raw[-MAX_SERIES_POINTS:]

    # Filter by since and format timestamps
    out = []
    for pt in raw:
        if since is not None and pt["at"] < since:
            continue
        out.append({
            "at": pt["at"].isoformat(),
            "overall": pt["overall"],
            "by_domain": pt["by_domain"],
            "n": pt["n"],
            "simulated": pt["simulated"],
        })
    return out


# ---------------------------------------------------------------------------
# DB-backed functions
# ---------------------------------------------------------------------------

def history(db: Session, learner: Learner, since_days: int | None = 90) -> dict[str, Any]:
    """Build the full progress history payload for a learner."""
    content = get_content()
    role = content.role(learner.role_id or "backend_developer")
    req = role["requirements"]
    concepts = content.concepts

    # --- evidence rows (projection query as per spec §8 risk note) ---
    rows = db.execute(
        select(
            EvidenceEvent.concept_id,
            EvidenceEvent.p_after,
            EvidenceEvent.changed_mastery,
            EvidenceEvent.grader,
            EvidenceEvent.created_at,
            EvidenceEvent.source_type,
        )
        .where(EvidenceEvent.learner_id == learner.id)
        .order_by(EvidenceEvent.created_at)
    ).all()

    event_rows = [
        _EventRow(r.concept_id, r.p_after, r.changed_mastery, r.grader or "", r.created_at, r.source_type)
        for r in rows
    ]

    # Compute since cutoff
    since_dt: datetime | None = None
    if since_days is not None:
        import datetime as _dt
        now_dt = mastery_engine.learner_now(learner)
        since_dt = now_dt.replace(tzinfo=None) - _dt.timedelta(days=since_days)

    series = replay_series(event_rows, req, concepts, since=since_dt)

    # --- live "now" value (includes forgetting) ---
    views = mastery_engine.concept_views(db, learner)
    now_overall = mastery_engine.overall_mastery(views, req)
    domain_totals = _domain_sums(req, concepts)
    p_live = {cid: views[cid]["p"] for cid in req if cid in views}
    _, now_by_domain = _compute_overall_and_domains(p_live, req, concepts, domain_totals)

    # --- projection from planner summary ---
    from ..engines import planner as planner_engine
    rm = planner_engine.current(db, learner)
    proj_overall = rm["summary"].get("readiness_after", now_overall)
    proj_weeks = rm["summary"].get("total_weeks", 0)

    # --- due reviews ---
    due_reviews = sum(1 for v in views.values() if v.get("due_for_review"))

    # --- markers ---
    markers: list[dict[str, Any]] = []
    # mentor events
    mentor_rows = db.execute(
        select(EvidenceEvent.created_at)
        .where(EvidenceEvent.learner_id == learner.id, EvidenceEvent.source_type == "mentor")
        .order_by(EvidenceEvent.created_at)
    ).all()
    for mr in mentor_rows:
        markers.append({"at": mr.created_at.isoformat(), "kind": "mentor", "label": "Mentor session"})

    # resolved misconceptions
    resolved = list(db.scalars(
        select(MisconceptionInstance)
        .where(MisconceptionInstance.learner_id == learner.id, MisconceptionInstance.resolved_at.is_not(None))
        .order_by(MisconceptionInstance.resolved_at)
    ))
    for mi in resolved:
        mis_name = content.misconceptions.get(mi.misconception_id, {}).get("name", "Misconception")
        markers.append({"at": mi.resolved_at.isoformat(), "kind": "misconception_resolved",
                        "label": f"Fixed: {mis_name}"})

    # roadmap plan changes
    plan_changes = list(db.scalars(
        select(RoadmapVersion)
        .where(RoadmapVersion.learner_id == learner.id, RoadmapVersion.change_reason != "No change")
        .order_by(RoadmapVersion.created_at)
    ))
    for rv in plan_changes:
        markers.append({"at": rv.created_at.isoformat(), "kind": "plan_changed",
                        "label": rv.change_reason[:60]})

    # Sort and cap markers
    markers.sort(key=lambda m: m["at"])
    markers = markers[:MAX_MARKERS]

    return {
        "series": series,
        "markers": markers,
        "now": {"overall": round(now_overall, 4), "by_domain": now_by_domain},
        "projection": {"overall": round(proj_overall, 4), "weeks": proj_weeks},
        "due_reviews": due_reviews,
    }


def radar(db: Session, learner: Learner) -> list[dict[str, Any]]:
    """Per-domain current vs target for the radar chart."""
    content = get_content()
    role = content.role(learner.role_id or "backend_developer")
    req = role["requirements"]
    concepts = content.concepts
    views = mastery_engine.concept_views(db, learner)

    domain_have: dict[str, float] = {}
    domain_target: dict[str, float] = {}
    domain_weight: dict[str, float] = {}

    for cid, r in req.items():
        dom = concepts[cid].domain
        w, tgt = r["weight"], r["target"]
        domain_have[dom] = domain_have.get(dom, 0.0) + w * min(views.get(cid, {}).get("p", 0.0), tgt)
        domain_target[dom] = domain_target.get(dom, 0.0) + w * tgt
        domain_weight[dom] = domain_weight.get(dom, 0.0) + w

    result = []
    for dom in sorted(domain_target.keys()):
        dtot = domain_target[dom]
        result.append({
            "domain": dom,
            "current": round(domain_have[dom] / dtot, 4) if dtot else 0.0,
            "target": 1.0,  # each domain's target is 100% of its weighted requirements
        })
    return result


def sparkline(db: Session, learner: Learner, n_days: int = 14) -> list[dict[str, Any]]:
    """Last n_days daily points for the dashboard ring sparkline."""
    h = history(db, learner, since_days=n_days)
    return h["series"]
