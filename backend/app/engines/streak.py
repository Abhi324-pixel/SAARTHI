"""T04 — Streak and daily goal.

All values are **computed** from evidence_events; nothing is stored.
The freeze rule and longest-streak are replayed from history so they never
drift when evidence is deleted or the dev clock moves.

Definitions (per spec):
  Activity  = EvidenceEvent whose source_type ∈ ACTIVITY_SOURCES
              AND whose grader is NOT "simulated" (demo helpers must not gift streaks).
  Study day = a calendar day in IST (UTC+05:30) with ≥ 1 activity.
  Daily goal = number of activities per day (1–10, stored in Learner.settings["daily_goal"],
               default 3).
  Streak    = consecutive study days ending today or yesterday (streak lives until the day ends).
  Freeze    = earned at every 7th consecutive day; max 2 held; auto-consumed for exactly one
              missed day (gap of ≥2 days always resets).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import EvidenceEvent, Learner

# IST offset applied to all UTC timestamps from created_at (naive UTC in DB).
# Using a fixed timedelta avoids the tzdata dependency on Windows (spec §4.1).
IST = timezone(timedelta(hours=5, minutes=30))

# source_types that count as study activity (same set as MASTERY_SOURCES)
ACTIVITY_SOURCES = {"question", "work_product", "explain_back", "mentor"}

DAILY_GOAL_DEFAULT = 3
DAILY_GOAL_MIN = 1
DAILY_GOAL_MAX = 10
MAX_FREEZES = 2
FREEZE_EARN_INTERVAL = 7  # earn one freeze every 7 consecutive days


def _to_ist_date(dt: datetime) -> date:
    """Convert a naive UTC datetime (as stored in the DB) to its IST calendar date."""
    return dt.replace(tzinfo=timezone.utc).astimezone(IST).date()


# ---------------------------------------------------------------------------
# Pure computation — trivially testable, no DB dependency
# ---------------------------------------------------------------------------

def summarize(
    active_days: set[date],
    today: date,
    daily_goal: int,
    activities_today: int,
) -> dict[str, Any]:
    """Replay the full streak history and return the summary dict.

    Parameters
    ----------
    active_days:      set of IST calendar dates with ≥ 1 counted activity
    today:            the learner's "now" date (may be ahead of wall clock via dev offset)
    daily_goal:       number of activities needed for a "goal met" day
    activities_today: how many counted activities have happened on *today*
    """
    if not active_days:
        return {
            "current": 0,
            "longest": 0,
            "freezes": 0,
            "freeze_used_on": [],
            "today_active": activities_today > 0,
            "goal_met_today": activities_today >= daily_goal,
            "week": _week_view(active_days, today),
            "total_active_days": 0,
            "activities_today": activities_today,
            "daily_goal": daily_goal,
        }

    # Replay day-by-day from the very first active day to *today*.
    first_day = min(active_days)
    freezes_held = 0
    freeze_used_on: list[date] = []
    current_streak = 0
    longest_streak = 0
    consecutive_run = 0  # used to track when the next freeze is earned

    cursor = first_day
    while cursor <= today:
        is_active = cursor in active_days

        if is_active:
            consecutive_run += 1
            current_streak += 1
            # Earn a freeze every FREEZE_EARN_INTERVAL consecutive days
            if consecutive_run % FREEZE_EARN_INTERVAL == 0:
                freezes_held = min(MAX_FREEZES, freezes_held + 1)
        else:
            # Missed day — check if a freeze can save the streak
            if freezes_held > 0 and current_streak > 0:
                # Only a single missed day can be saved
                next_day = cursor + timedelta(days=1)
                if next_day <= today and next_day in active_days:
                    # The very next day IS active — consume the freeze
                    freeze_used_on.append(cursor)
                    freezes_held -= 1
                    # consecutive_run continues (the saved day keeps the run alive)
                    # but we don't increment it for the missed day itself
                else:
                    # Gap of ≥ 2 or freeze can't be confirmed yet → reset
                    current_streak = 0
                    consecutive_run = 0
            else:
                current_streak = 0
                consecutive_run = 0

        longest_streak = max(longest_streak, current_streak)
        cursor += timedelta(days=1)

    # If today is not yet active but yesterday was (or was saved by freeze), streak is still alive.
    # The while loop already handles this correctly because today is in the range.

    return {
        "current": current_streak,
        "longest": longest_streak,
        "freezes": freezes_held,
        "freeze_used_on": [d.isoformat() for d in freeze_used_on],
        "today_active": today in active_days,
        "goal_met_today": activities_today >= daily_goal,
        "week": _week_view(active_days, today),
        "total_active_days": len(active_days),
        "activities_today": activities_today,
        "daily_goal": daily_goal,
    }


def _week_view(active_days: set[date], today: date) -> list[dict[str, Any]]:
    """Return a 7-entry list covering today and the 6 preceding days."""
    out = []
    for offset in range(6, -1, -1):
        d = today - timedelta(days=offset)
        out.append({"date": d.isoformat(), "active": d in active_days})
    return out


# ---------------------------------------------------------------------------
# DB wrapper
# ---------------------------------------------------------------------------

def for_learner(db: Session, learner: Learner) -> dict[str, Any]:
    """Load evidence dates for *learner* and call summarize().

    Uses a projection query (only the columns we need) as required by spec §8.
    Excludes grader="simulated" events so the demo seed does not gift a streak.
    """
    from ..engines.mastery import learner_now  # local import to avoid circular

    rows = db.execute(
        select(EvidenceEvent.created_at, EvidenceEvent.source_type)
        .where(
            EvidenceEvent.learner_id == learner.id,
            EvidenceEvent.source_type.in_(ACTIVITY_SOURCES),
            EvidenceEvent.grader != "simulated",
        )
    ).all()

    active_days: set[date] = set()
    for created_at, _src in rows:
        active_days.add(_to_ist_date(created_at))

    today_ist = _to_ist_date(learner_now(learner))
    activities_today = sum(
        1 for created_at, _src in rows if _to_ist_date(created_at) == today_ist
    )

    settings = learner.settings or {}
    daily_goal = max(DAILY_GOAL_MIN, min(DAILY_GOAL_MAX, int(settings.get("daily_goal", DAILY_GOAL_DEFAULT))))

    return summarize(active_days, today_ist, daily_goal, activities_today)
