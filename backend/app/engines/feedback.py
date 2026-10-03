"""T03 — Difficulty & Preference Feedback Engine.

Handles "too_easy", "too_hard", "helpful", and "not_helpful" learner feedback.
Core invariant: feedback never directly moves mastery (playbook rule 1).
Mastery only moves if the learner subsequently proves knowledge by answering questions.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..content import get_content
from ..models import Learner, StrategyOutcome
from . import diagnostic, hooks, mastery, planner, strategy


SIGNALS = {"too_easy", "too_hard", "helpful", "not_helpful"}
GENTLE_STRATEGIES = ["worked_example", "code_tracing", "text", "analogy"]


def apply(
    db: Session,
    learner: Learner,
    concept_id: str,
    signal: str,
    context: str,
    item_id: Optional[str] = None,
) -> dict[str, Any]:
    """Record learner feedback, trigger pedagogical adjustment, and return action + message."""
    content = get_content()
    if concept_id not in content.concepts:
        raise KeyError(f"Unknown concept {concept_id}")
    if signal not in SIGNALS:
        raise ValueError(f"Unknown signal {signal}. Allowed: {sorted(SIGNALS)}")

    c = content.concepts[concept_id]
    domain = c.domain
    views = mastery.concept_views(db, learner)
    now = mastery.learner_now(learner)
    today_str = now.strftime("%Y-%m-%d")
    is_hi = (learner.language_pref or "english") in ("hindi", "hinglish")

    states = mastery.ensure_states(db, learner)
    cs = states[concept_id]
    current_strat = cs.last_strategy or "worked_example"

    # 1. Record EvidenceEvent (never changes mastery)
    mastery.apply_evidence(
        db,
        learner,
        concept_id,
        "feedback",
        grader="learner_click",
        detail={
            "signal": signal,
            "context": context,
            "item_id": item_id,
            "strategy": current_strat,
        },
    )

    settings = dict(learner.settings or {})
    after: Optional[dict[str, Any]] = None
    action: dict[str, Any] = {"type": "none"}
    message = ""

    # Helper: pick next untried gentle strategy
    def _pick_next_gentle() -> tuple[str, dict[str, Any]]:
        note = content.note(concept_id)
        available = [s for s in GENTLE_STRATEGIES if s != "analogy" or note.get("analogy")]
        available = [s for s in available if s != "code_tracing" or note.get("example")]
        # Pick strategy different from current
        candidates = [s for s in available if s != current_strat]
        chosen = candidates[0] if candidates else (available[0] if available else "text")
        explanation = strategy.explain(db, learner, concept_id, strategy=chosen)
        return chosen, explanation

    # Helper: find prerequisite probe
    def _prereq_probe() -> Optional[dict[str, Any]]:
        blocked = views.get(concept_id, {}).get("blocked_by", [])
        prereq_cid = blocked[0] if blocked else None
        if not prereq_cid:
            prereqs = content.prereqs(concept_id)
            if prereqs:
                prereq_cid = min(prereqs, key=lambda pid: views.get(pid, {}).get("p", 1.0))
        if prereq_cid:
            probes = diagnostic.next_probe(db, learner, count=1, concept_id=prereq_cid)
            return probes[0] if probes else None
        return None

    # Helper: nudge practice factor
    def _nudge_factor(delta: float) -> bool:
        factor_changes = dict(settings.get("factor_changes") or {})
        if factor_changes.get(concept_id) == today_str:
            return False  # at most one change per concept per day
        factors = dict(settings.get("practice_factor") or {})
        cur = float(factors.get(domain, planner.PRACTICE_FACTOR))
        new_val = round(max(1.5, min(3.0, cur + delta)), 2)
        if abs(new_val - cur) > 0.001:
            factors[domain] = new_val
            settings["practice_factor"] = factors
            factor_changes[concept_id] = today_str
            settings["factor_changes"] = factor_changes
            learner.settings = settings
            db.flush()
            return True
        return False

    # 2. Handle signals
    if signal == "too_easy":
        # Return harder probe
        probes = diagnostic.next_probe(db, learner, count=1, concept_id=concept_id, harder=True)
        if probes:
            probe_item = probes[0]
            action = {"type": "probe", "item": probe_item}
            # Record pending challenge so answering correctly nudges factor
            pending = dict(settings.get("pending_too_easy") or {})
            pending[probe_item["id"]] = {
                "concept_id": concept_id,
                "domain": domain,
                "at": now.isoformat(),
            }
            settings["pending_too_easy"] = pending
            learner.settings = settings
            db.flush()
            message = (
                "Apna gyaan dikhaiye! Yeh raha ek thoda kathin sawaal."
                if is_hi
                else "Prove it! Here is a harder question on this topic."
            )
        else:
            action = {"type": "none"}
            message = (
                "Is concept par koi aur mushkil sawaal nahi bacha — teach-back try karein!"
                if is_hi
                else "No harder question left on this concept — try the explain-back!"
            )

    elif signal == "too_hard":
        new_strat, new_ex = _pick_next_gentle()
        prereq = _prereq_probe()
        changed = _nudge_factor(+0.1)
        if changed:
            after = hooks.after_evidence(db, learner, concept_id, "feedback: too hard")
        action = {
            "type": "strategy",
            "strategy": new_strat,
            "explanation": new_ex,
            "prereq_probe": prereq,
        }
        message = (
            "Iske basic concepts check karte hain aur thoda aur waqt dete hain."
            if is_hi
            else "I'll check the basics under this and add extra practice time."
        )

    elif signal == "helpful":
        strat_key = current_strat
        helpful_map = dict(settings.get("helpful_strategies") or {})
        helpful_map[strat_key] = helpful_map.get(strat_key, 0) + 1
        settings["helpful_strategies"] = helpful_map
        learner.settings = settings
        db.flush()
        action = {"type": "none"}
        message = (
            "Samajh gaya — is tareeqe ko aage zyada use karenge."
            if is_hi
            else "Got it — we'll use this approach more often."
        )

    elif signal == "not_helpful":
        new_strat, new_ex = _pick_next_gentle()
        action = {
            "type": "strategy",
            "strategy": new_strat,
            "explanation": new_ex,
        }
        message = (
            "Doosre tareeqe se samajhte hain."
            if is_hi
            else "Let's try a different explanation style."
        )

    return {
        "message": message,
        "action": action,
        "after": after,
    }


def on_probe_answered(db: Session, learner: Learner, item_id: str, correct: bool) -> bool:
    """If item_id was offered as a 'too_easy' challenge and answered correctly, nudge factor -0.1."""
    settings = dict(learner.settings or {})
    pending = dict(settings.get("pending_too_easy") or {})
    if item_id not in pending:
        return False

    info = pending.pop(item_id)
    if not correct:
        settings["pending_too_easy"] = pending
        learner.settings = settings
        db.flush()
        return False

    concept_id = info["concept_id"]
    domain = info["domain"]
    now = mastery.learner_now(learner)
    today_str = now.strftime("%Y-%m-%d")

    factors = dict(settings.get("practice_factor") or {})
    factor_changes = dict(settings.get("factor_changes") or {})
    cur = float(factors.get(domain, planner.PRACTICE_FACTOR))
    new_val = round(max(1.5, min(3.0, cur - 0.1)), 2)
    factors[domain] = new_val
    settings["practice_factor"] = factors
    factor_changes[concept_id] = today_str
    settings["factor_changes"] = factor_changes
    settings["pending_too_easy"] = pending
    learner.settings = settings
    db.flush()
    return True


def reset_adaptations(db: Session, learner: Learner) -> dict[str, Any]:
    """Reset practice factors and helpful strategies back to defaults."""
    settings = dict(learner.settings or {})
    settings.pop("practice_factor", None)
    settings.pop("helpful_strategies", None)
    settings.pop("factor_changes", None)
    settings.pop("pending_too_easy", None)
    learner.settings = settings
    db.flush()
    after = hooks.after_evidence(db, learner, None, "feedback preferences reset")
    return {
        "ok": True,
        "message": "Feedback preferences and pacing reset to defaults.",
        "after": after,
    }
