"""T05 — Roadmap phases, deadlines and personal checkpoints engine.

Pure functions for grouping roadmap items into domain phases,
computing target dates from plan_start, and calculating deterministic
deadline statuses with needed hours per week.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..content import get_content
from ..models import Learner
from . import mastery

DOMAIN_TITLES = {
    "sql": "SQL & Databases",
    "python": "Python Basics",
    "backend": "APIs & Backend",
    "tools": "Developer Tools",
    "communication": "Communication & Interview",
}

DOMAIN_TITLES_HI = {
    "sql": "एसक्यूएल और डेटाबेस",
    "python": "पायथन बेसिक्स",
    "backend": "एपीआई और बैकएंड",
    "tools": "डेवलपर टूल्स",
    "communication": "बातचीत और इंटरव्यू",
}


def get_plan_start(learner: Learner, db: Optional[Session] = None) -> date:
    """Retrieve or initialize the immutable plan_start date for the learner."""
    settings = dict(learner.settings or {})
    if "plan_start" in settings:
        try:
            return date.fromisoformat(settings["plan_start"])
        except Exception:
            pass

    now_dt = mastery.learner_now(learner)
    today = now_dt.date()
    settings["plan_start"] = today.isoformat()
    learner.settings = settings
    if db:
        db.flush()
    return today


def deadline_status(
    phase: dict[str, Any],
    deadline_str: str,
    weekly_hours: float,
    today: date,
    all_items: list[dict[str, Any]],
    views: dict[str, Any],
) -> dict[str, Any]:
    """Calculate deterministic on-track status, gap days, and needed hours per week."""
    deadline = date.fromisoformat(deadline_str)
    raw_target = phase["target_date"]
    target_date = date.fromisoformat(raw_target) if isinstance(raw_target, str) else raw_target

    days_left = (deadline - today).days
    gap_days = (target_date - deadline).days  # positive if target finishes after deadline

    if days_left <= 0:
        return {
            "on_track": False,
            "passed": True,
            "projected_finish": target_date.isoformat(),
            "gap_days": gap_days,
            "needed_hours_per_week": 0.0,
            "weeks_left": 0.0,
            "minutes_needed": 0,
            "message": "This deadline has passed.",
        }

    weeks_left = days_left / 7.0

    # Calculate minutes of items in this phase and every earlier phase not yet at target
    # Find all items up to the end of this phase
    phase_cids = set(phase["concept_ids"])
    cutoff_idx = -1
    for i, it in enumerate(all_items):
        if it.get("concept_id") in phase_cids:
            cutoff_idx = i

    relevant_items = all_items[: cutoff_idx + 1] if cutoff_idx >= 0 else []

    minutes_needed = 0
    for it in relevant_items:
        if it.get("kind") == "review":
            continue
        cid = it["concept_id"]
        tgt = it.get("target", 0.8)
        p = views.get(cid, {}).get("p", 0.0)
        # Done threshold matches planner.DONE_RATIO = 0.95
        if p < 0.95 * tgt:
            minutes_needed += it.get("minutes", 0)

    hours_needed_per_week = round(minutes_needed / 60.0 / weeks_left, 1) if weeks_left > 0 else 0.0
    on_track = bool((deadline >= target_date) or (hours_needed_per_week <= weekly_hours))

    if on_track:
        msg = f"On track! At {weekly_hours:g} h/week this phase finishes around {target_date.strftime('%d %b %Y')}."
    else:
        msg = (
            f"At {weekly_hours:g} h/week this phase finishes around {target_date.strftime('%d %b %Y')} "
            f"— {gap_days} days after your deadline. To make it: {hours_needed_per_week:g} h/week or move the date."
        )

    return {
        "on_track": on_track,
        "passed": False,
        "projected_finish": target_date.isoformat(),
        "gap_days": gap_days,
        "needed_hours_per_week": hours_needed_per_week,
        "minutes_needed": minutes_needed,
        "weeks_left": round(weeks_left, 1),
        "message": msg,
    }


def phases(
    items: list[dict[str, Any]],
    plan_start: date,
    deadlines: dict[str, str],
    weekly_hours: float,
    today: date,
    views: dict[str, Any],
) -> list[dict[str, Any]]:
    """Pure grouping of ordered roadmap items into domain phases with target dates."""
    non_review = [it for it in items if it.get("kind") != "review"]
    if not non_review:
        return []

    # Group runs of identical domains
    runs: list[list[dict[str, Any]]] = []
    current_run: list[dict[str, Any]] = []

    for it in non_review:
        dom = it.get("domain", "general")
        if not current_run or current_run[0].get("domain") == dom:
            current_run.append(it)
        else:
            runs.append(current_run)
            current_run = [it]
    if current_run:
        runs.append(current_run)

    domain_counts: dict[str, int] = {}
    phase_list: list[dict[str, Any]] = []

    for run in runs:
        dom = run[0].get("domain", "general")
        domain_counts[dom] = domain_counts.get(dom, 0) + 1
        count = domain_counts[dom]
        key = dom if count == 1 else f"{dom}-{count}"

        concept_ids = [it["concept_id"] for it in run]
        start_week = min(it.get("week", 1) for it in run)
        end_week = max(it.get("week", 1) for it in run)
        total_mins = sum(it.get("minutes", 0) for it in run)
        target_date = plan_start + timedelta(days=7 * end_week)

        # Check if phase is completely done
        completed = all(
            views.get(cid, {}).get("p", 0.0) >= 0.95 * it.get("target", 0.8)
            for cid, it in zip(concept_ids, run)
        )

        dl_str = deadlines.get(key)
        dl_status = None
        if dl_str:
            try:
                dl_status = deadline_status(
                    phase={"concept_ids": concept_ids, "target_date": target_date},
                    deadline_str=dl_str,
                    weekly_hours=weekly_hours,
                    today=today,
                    all_items=items,
                    views=views,
                )
            except Exception:
                pass

        phase_list.append({
            "key": key,
            "domain": dom,
            "title": DOMAIN_TITLES.get(dom, dom.replace("_", " ").title()),
            "title_hi": DOMAIN_TITLES_HI.get(dom, dom.replace("_", " ").title()),
            "concept_ids": concept_ids,
            "start_week": start_week,
            "end_week": end_week,
            "minutes": total_mins,
            "target_date": target_date.isoformat(),
            "deadline": dl_str,
            "deadline_status": dl_status,
            "completed": completed,
        })

    return phase_list
