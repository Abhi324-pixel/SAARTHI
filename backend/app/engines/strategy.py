"""Teaching Strategy Engine + Learning Engine (grounded explanations).

Selection is rule-based until a learner has enough outcomes; then a Beta-Bernoulli Thompson sampler picks
among strategies. The reward is a LATER learning gain on the concept's cluster (never the immediate reply),
which removes the "second attempt always looks better" bias. No learning-styles labels are ever produced.
"""

from __future__ import annotations

import random
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..llm import tasks
from ..models import Learner, StrategyOutcome
from . import mastery, misconception

STRATEGIES = ["analogy", "worked_example", "contrasting_cases", "code_tracing", "practice_first", "text"]
LABELS = {"analogy": "Analogy", "worked_example": "Worked example", "contrasting_cases": "Contrasting cases",
          "code_tracing": "Code tracing", "practice_first": "Practice first", "text": "Plain explanation"}
GAIN_SUCCESS = 0.08
BANDIT_MIN_OUTCOMES = 6
SETTLE_AFTER_SECONDS = 600  # ten minutes of learner time (the dev clock tool can fast-forward this)


def _cluster(concept_id: str) -> str:
    return get_content().concepts[concept_id].domain


def outcomes_summary(db: Session, learner_id: str) -> dict[str, dict[str, float]]:
    rows = db.scalars(select(StrategyOutcome).where(StrategyOutcome.learner_id == learner_id,
                                                    StrategyOutcome.gain.is_not(None)))
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        d = out.setdefault(r.strategy, {"n": 0, "success": 0, "gain": 0.0})
        d["n"] += 1
        d["success"] += 1 if (r.gain or 0) >= GAIN_SUCCESS else 0
        d["gain"] += r.gain or 0.0
    for d in out.values():
        d["mean_gain"] = round(d["gain"] / d["n"], 3) if d["n"] else 0.0
    return out


def choose(db: Session, learner: Learner, concept_id: str, rng: Optional[random.Random] = None) -> dict[str, Any]:
    c = get_content()
    views = mastery.concept_views(db, learner)
    v = views[concept_id]
    note = c.note(concept_id)
    rng = rng or random.Random()
    reason = ""
    active_m = misconception.describe(db, learner.id)
    has_m = any(m["concept_id"] == concept_id and m["status"] in ("confirmed", "correcting", "pending_verify") for m in active_m)
    tried = [r.strategy for r in db.scalars(select(StrategyOutcome).where(
        StrategyOutcome.learner_id == learner.id, StrategyOutcome.concept_id == concept_id)
        .order_by(StrategyOutcome.created_at))]
    summary = outcomes_summary(db, learner.id)
    total_outcomes = sum(d["n"] for d in summary.values())
    available = [s for s in STRATEGIES if s != "analogy" or note.get("analogy")]
    available = [s for s in available if s != "code_tracing" or note.get("example")]
    available = [s for s in available if s != "contrasting_cases" or c.misc_by_concept.get(concept_id)]
    available = [s for s in available if s != "practice_first" or c.tasks_by_concept.get(concept_id) or True]

    # Tie-breaker preference from learner feedback (rules phase only)
    helpful_fav = None
    if getattr(learner, "settings", None) and "helpful_strategies" in learner.settings:
        favs = sorted(learner.settings["helpful_strategies"].items(), key=lambda kv: kv[1], reverse=True)
        for s, cnt in favs:
            if cnt > 0 and s in available:
                helpful_fav = s
                break

    if has_m and "contrasting_cases" in available and tried.count("contrasting_cases") < 2:
        strategy, reason = "contrasting_cases", "A misconception is active, so showing two cases side by side works best."
    elif total_outcomes >= BANDIT_MIN_OUTCOMES:
        draws = []
        for s in available:
            d = summary.get(s, {"n": 0, "success": 0})
            draws.append((rng.betavariate(1 + d["success"], 1 + d["n"] - d["success"]), s))
        draws.sort(reverse=True)
        strategy = draws[0][1]
        reason = "Chosen from what has actually improved your later results (exploration included)."
    elif v["n_evidence"] == 0 and "analogy" in available:
        strategy, reason = "analogy", "First time on this concept: start from something familiar."
    elif tried and v["p"] < 0.6:
        nxt = [s for s in ["worked_example", "code_tracing", "practice_first", "text", "analogy"]
               if s in available and s not in tried]
        if helpful_fav and helpful_fav in nxt:
            strategy = helpful_fav
            reason = f"You previously found {LABELS.get(strategy, strategy).lower()} helpful, and it is a fresh approach here."
        else:
            strategy = nxt[0] if nxt else rng.choice(available)
            reason = f"{LABELS.get(tried[-1], tried[-1])} didn't move your score enough, so let's try a different approach."
    elif v["p"] >= 0.6:
        strategy, reason = "practice_first", "You already know the basics, so practise first and I'll explain only what you miss."
    elif helpful_fav:
        strategy = helpful_fav
        reason = f"You previously found {LABELS.get(strategy, strategy).lower()} helpful."
    else:
        strategy = "worked_example" if note.get("example") else "text"
        reason = "A worked example shows the idea in action."
    return {"strategy": strategy, "label": LABELS[strategy], "reason": reason, "available": available}


def _assemble(concept_id: str, strategy: str, language: str, misconception_id: Optional[str]) -> dict[str, Any]:
    c = get_content()
    n = c.note(concept_id)
    hi = language in ("hindi", "hinglish") and n.get("summary_hi")
    summary = n["summary_hi"] if hi else n["summary"]
    parts: list[str] = []
    visual = n.get("visual")
    if strategy == "analogy" and n.get("analogy"):
        parts += [n["analogy"], summary]
    elif strategy == "worked_example" and n.get("example"):
        parts += [summary, "Worked example:\n" + n["example"]]
    elif strategy == "contrasting_cases":
        m = c.misconceptions.get(misconception_id) if misconception_id else (c.misc_by_concept.get(concept_id) or [None])[0]
        if m:
            parts += [f"A common mix-up: \"{m['name']}\".", m["description"],
                      "Compare: " + (m["counter_example"].get("query") or "") if m["counter_example"].get("query") else "",
                      m["counter_example"]["explanation"]]
            visual = visual or ("join_diagram" if "join" in concept_id else None)
        else:
            parts += [summary]
    elif strategy == "code_tracing" and n.get("example"):
        parts += [summary, "Trace it step by step:\n" + n["example"]]
    elif strategy == "practice_first":
        parts += ["Try the practice task first. If you get stuck, come back here.", summary]
    else:
        parts += [summary]
    if n.get("pitfall"):
        parts.append("Watch out: " + n["pitfall"])
    return {"text": "\n\n".join(p for p in parts if p), "key_points": n.get("key_points", []), "visual": visual,
            "example": n.get("example")}


def explain(db: Session, learner: Learner, concept_id: str, strategy: Optional[str] = None,
            misconception_id: Optional[str] = None, record: bool = True) -> dict[str, Any]:
    c = get_content()
    if concept_id not in c.concepts:
        raise KeyError(concept_id)
    pick = {"strategy": strategy, "label": LABELS.get(strategy or "", ""), "reason": "Chosen by you."} if strategy else \
        choose(db, learner, concept_id)
    base = _assemble(concept_id, pick["strategy"], learner.language_pref, misconception_id)
    text = base["text"]
    source = "curated"
    paraphrased = tasks.rewrite_explanation(concept_id, pick["strategy"], learner.language_pref, text)
    if paraphrased:
        # keep the curated code/example intact; the model only re-voices the prose
        text = paraphrased + (("\n\n" + base["example"]) if base.get("example") and base["example"] not in paraphrased else "")
        source = "curated+llm"
    if record:
        v = mastery.concept_views(db, learner)[concept_id]
        db.add(StrategyOutcome(learner_id=learner.id, concept_id=concept_id, cluster=_cluster(concept_id),
                               strategy=pick["strategy"], p_before=v["p"]))
        cs = mastery.ensure_states(db, learner)[concept_id]
        cs.last_strategy = pick["strategy"]
        db.flush()
    return {"concept_id": concept_id, "concept_name": c.concepts[concept_id].name, "strategy": pick["strategy"],
            "strategy_label": pick["label"] or LABELS.get(pick["strategy"], ""), "why_strategy": pick["reason"],
            "text": text, "key_points": base["key_points"], "visual": base["visual"], "source": source}


def settle(db: Session, learner: Learner, concept_id: str, p_after: float) -> None:
    """Called after later evidence on a concept: record the learning gain for strategies awaiting an outcome."""
    now = mastery.learner_now(learner)
    rows = db.scalars(select(StrategyOutcome).where(
        StrategyOutcome.learner_id == learner.id, StrategyOutcome.concept_id == concept_id,
        StrategyOutcome.gain.is_(None)))
    for r in rows:
        # reward must be a LATER result, not the immediate reply to the explanation
        if (now - r.created_at).total_seconds() < SETTLE_AFTER_SECONDS:
            continue
        r.p_after = p_after
        r.gain = round(p_after - r.p_before, 4)
    db.flush()
