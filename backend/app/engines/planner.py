"""Adaptation Engine: roadmap, "Why this?", "Why not X?", what-if and today's mission.

Ported ideas from TESSA's planner (importance-weighted gap, greedy budgeted coverage, topological ordering),
rebuilt on SAARTHI's concept states. The model never decides here — everything is deterministic and each
item carries machine-readable REASON CODES; prose is generated from the codes (templates, optionally
paraphrased by the LLM, never invented).
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..models import Learner, RoadmapVersion, now
from . import mastery, misconception

DONE_RATIO = 0.95  # an item is "done" when p >= 95% of its target


PRACTICE_FACTOR = 2.0  # curated minutes cover the lesson; real mastery also needs practice and review time


def _minutes(base: int, p: float, target: float, factor: float = PRACTICE_FACTOR) -> int:
    ratio = min(1.0, p / target) if target else 1.0
    return max(10, int(round(base * factor * (1.0 - 0.7 * ratio) / 5.0)) * 5)


def _focus_recent(f: Any) -> bool:
    try:
        return (now() - datetime.fromisoformat(str(f.get("at")))).days <= 30
    except (ValueError, TypeError, AttributeError):
        return False


def build(db: Session, learner: Learner, *, weekly_hours: Optional[float] = None,
          horizon_weeks: Optional[int] = None) -> dict[str, Any]:
    content = get_content()
    role = content.role(learner.role_id or "backend_developer")
    req = role["requirements"]
    views = mastery.concept_views(db, learner)
    wh = float(weekly_hours if weekly_hours is not None else learner.weekly_hours or 6.0)
    weeks = int(horizon_weeks if horizon_weeks is not None else learner.horizon_weeks or 12)
    budget = wh * 60.0 * weeks

    practice_factors = (learner.settings or {}).get("practice_factor", {}) if getattr(learner, "settings", None) else {}

    def get_factor(cid: str) -> float:
        dom = content.concepts[cid].domain
        return float(practice_factors.get(dom, PRACTICE_FACTOR))

    gap = {cid: max(0.0, r["target"] - views[cid]["p"]) * r["weight"] for cid, r in req.items()}
    active_mis = {cid: v["misconceptions"] for cid, v in views.items() if v["misconceptions"]}
    needed = {cid for cid, g in gap.items() if g > 0.03 or cid in active_mis}
    minutes = {cid: _minutes(content.concepts[cid].minutes, views[cid]["p"], req[cid]["target"], get_factor(cid)) for cid in req}

    # ---- budgeted selection (greedy by value density, always with the unmet prerequisite closure) ----
    def closure(cid: str) -> set[str]:
        return {cid} | {a for a in content.ancestors(cid) if a in needed}

    # topics the learner chose to prioritise after an interview showed a gap (only while the gap still exists, and for 30 days)
    focus_ids = {cid for cid, f in ((learner.settings or {}).get("focus", {}) or {}).items() if cid in needed and _focus_recent(f)}
    density = {cid: (gap[cid] + (0.3 if cid in active_mis else 0.0) + (0.15 if cid in focus_ids else 0.0)) / max(minutes[cid], 1) for cid in needed}
    chosen: set[str] = set()
    spent = 0.0
    dropped: list[str] = []
    for cid in sorted(needed, key=lambda c: -density[c]):
        if cid in chosen:
            continue
        add = closure(cid) - chosen
        cost = sum(minutes[a] for a in add)
        if spent + cost <= budget or not chosen and cost <= budget * 1.1:
            chosen |= add
            spent += cost
        else:
            dropped.append(cid)
    dropped = [d for d in dropped if d not in chosen]

    # ---- ordering: topological, misconception fixes and bigger gaps first among the ready ----
    # a misconception fix pulls its own prerequisite chain forward, so the learner can actually reach it
    urgent = set(c for c in chosen if c in active_mis or c in focus_ids)
    for m in list(urgent):
        urgent |= {a for a in content.ancestors(m) if a in chosen}
    dom_rank = {d: i for i, d in enumerate(role.get("domain_priority", []))}

    def prio(cid: str) -> tuple:
        return (0 if cid in urgent else 1, dom_rank.get(content.concepts[cid].domain, 9), -gap[cid], content.order.index(cid))
    ordered = content.topo_order(chosen, key=prio) if chosen else []

    # ---- due reviews (separate, short items that do not consume the learning budget) -----------------
    reviews = [cid for cid, v in views.items() if v["due_for_review"] and cid in req and cid not in chosen]

    items: list[dict[str, Any]] = []
    cum = 0.0
    week_minutes = max(wh * 60.0, 1.0)
    in_plan_deps: dict[str, list[str]] = {c: [d for d in content.dependents(c) if d in chosen] for c in chosen}
    for idx, cid in enumerate(ordered):
        v = views[cid]
        c = content.concepts[cid]
        reasons: list[dict[str, Any]] = [{
            "type": "GAP_COVERAGE",
            "detail": {"current": v["p"], "target": req[cid]["target"], "weight": req[cid]["weight"],
                       "gap": round(gap[cid], 3)},
            "contribution": round(gap[cid], 3)}]
        if cid in focus_ids:
            reasons.append({"type": "INTERVIEW_FOCUS", "detail": {}, "contribution": 0.15})
        if cid in active_mis:
            reasons.append({"type": "MISCONCEPTION_FIX", "detail": {
                "misconceptions": [content.misconceptions[m]["name"] for m in active_mis[cid]]}, "contribution": 0.3})
        deps = in_plan_deps.get(cid, [])
        if deps:
            weak_deps = [d for d in deps if views[d]["flags"] and "blocked" in views[d]["flags"]]
            reasons.append({"type": "PREREQ_FOR", "detail": {
                "concepts": [content.concepts[d].name for d in deps[:4]],
                "blocking_now": [content.concepts[d].name for d in weak_deps[:4]]}, "contribution": 0.2})
        if v["flags"] and "blocked" in v["flags"]:
            reasons.append({"type": "NEEDS_FIRST", "detail": {
                "concepts": [content.concepts[p].name for p in v["blocked_by"]]}, "contribution": 0.0})
        start_week = int(cum // week_minutes) + 1
        cum += minutes[cid]
        end_week = int(max(cum - 1, 0) // week_minutes) + 1
        reasons.append({"type": "TIME_FIT", "detail": {"minutes": minutes[cid], "start_week": start_week,
                                                       "end_week": end_week, "weekly_hours": wh}, "contribution": 0.0})
        factor = get_factor(cid)
        if abs(factor - PRACTICE_FACTOR) > 0.001:
            reasons.append({"type": "LEARNER_FEEDBACK", "detail": {
                "factor": round(factor, 2), "default": PRACTICE_FACTOR, "domain": c.domain}, "contribution": 0.0})
        steps = ["learn"]
        if content.tasks_by_concept.get(cid):
            steps.append("practice")
        else:
            steps.append("quiz")
        if content.has_rubric(cid):
            steps.append("explain_back")
        items.append({
            "item_id": f"learn:{cid}", "kind": "fix_misconception" if cid in active_mis else "learn",
            "concept_id": cid, "title": c.name, "title_hi": c.name_hi, "domain": c.domain,
            "minutes": minutes[cid], "order": idx + 1, "week": start_week, "steps": steps,
            "p_now": v["p"], "target": req[cid]["target"], "level": v["level"], "flags": v["flags"],
            "status": "done" if v["p"] >= DONE_RATIO * req[cid]["target"] else "todo",
            "reasons": reasons,
        })
    for cid in reviews:
        v = views[cid]
        items.append({
            "item_id": f"review:{cid}", "kind": "review", "concept_id": cid, "title": f"Review: {content.concepts[cid].name}",
            "title_hi": f"Review: {content.concepts[cid].name_hi}", "domain": content.concepts[cid].domain,
            "minutes": 10, "order": len(items) + 1, "week": 1, "steps": ["quiz"], "p_now": v["p"],
            "target": req.get(cid, {}).get("target", 0.8), "level": v["level"], "flags": v["flags"], "status": "todo",
            "reasons": [{"type": "REVIEW_DUE", "detail": {"since": v["next_review_at"]}, "contribution": 0.0}],
        })

    # ---- summary ---------------------------------------------------------------------------------------
    now_ready = mastery.overall_mastery(views, req)
    after_views = {cid: dict(v) for cid, v in views.items()}
    for cid in chosen:
        after_views[cid]["p"] = max(after_views[cid]["p"], req[cid]["target"])
    after_ready = mastery.overall_mastery(after_views, req)
    total_min = sum(i["minutes"] for i in items if i["kind"] != "review")
    summary = {
        "role_id": role["id"], "role_title": role["title"], "weekly_hours": wh, "horizon_weeks": weeks,
        "total_minutes": total_min, "total_weeks": int(math.ceil(total_min / week_minutes)) if total_min else 0,
        "readiness_now": now_ready, "readiness_after": after_ready,
        "n_items": len([i for i in items if i["kind"] != "review"]), "n_reviews": len(reviews),
        "dropped": [{"concept_id": d, "name": content.concepts[d].name, "minutes": minutes[d],
                     "reason": "BUDGET"} for d in dropped],
        "budget_minutes": int(budget),
    }
    return {"items": items, "summary": summary}


# ---------------------------------------------------------------------------------------------------
# prose from reason codes
# ---------------------------------------------------------------------------------------------------

def why_text(item: dict[str, Any], lang: str = "english") -> str:
    hi = lang in ("hindi", "hinglish")
    parts: list[str] = []
    for r in item["reasons"]:
        t, d = r["type"], r["detail"]
        if t == "MISCONCEPTION_FIX":
            names = ", ".join(d["misconceptions"])
            parts.append((f"Aapke kaam mein ek galat dharna dikhi: {names}. Pehle use theek karte hain." if hi
                          else f"A likely misconception showed up in your work: {names}. Fixing it comes first."))
        elif t == "GAP_COVERAGE":
            gap_pct = int(round((d["target"] - d["current"]) * 100))
            parts.append((f"Is concept mein abhi {int(d['current']*100)}% hai, target {int(d['target']*100)}% — {gap_pct} points ka gap." if hi
                          else f"You are at {int(d['current']*100)}% here and this role needs {int(d['target']*100)}% — a {gap_pct}-point gap."))
        elif t == "PREREQ_FOR":
            names = ", ".join(d["concepts"][:3])
            parts.append((f"Yeh {names} ke liye zaroori hai." if hi else f"It is a prerequisite for {names}."))
            if d.get("blocking_now"):
                bl = ", ".join(d["blocking_now"][:2])
                parts.append((f"Abhi {bl} isi ki wajah se atka hua hai." if hi else f"{bl} is currently held back by it."))
        elif t == "NEEDS_FIRST":
            names = ", ".join(d["concepts"][:2])
            parts.append((f"Isse pehle {names} majboot hona chahiye." if hi else f"It needs {names} to be solid first."))
        elif t == "INTERVIEW_FOCUS":
            parts.append("Aapke interview mein yahan gap dikha tha, isliye ise aage badhaya gaya hai." if hi
                         else "Your interview showed a gap here, so this was moved up. Your skill estimate only changes when you answer questions or do work on it.")
        elif t == "REVIEW_DUE":
            parts.append("Yaad taaza rakhne ke liye ek chhota review." if hi else "A short review to keep this fresh before it fades.")
        elif t == "TIME_FIT":
            parts.append((f"Lagbhag {d['minutes']} minute, hafta {d['start_week']}." if hi
                          else f"About {d['minutes']} minutes, scheduled for week {d['start_week']}."))
        elif t == "LEARNER_FEEDBACK":
            factor = d.get("factor", PRACTICE_FACTOR)
            if factor > PRACTICE_FACTOR:
                parts.append("Aapne ise mushkil bataya tha, isliye thoda aur waqt joda gaya hai." if hi
                             else "You told us this was too hard, so extra practice time was added.")
            elif factor < PRACTICE_FACTOR:
                parts.append("Aapne ise aasan bataya tha, isliye waqt kam kiya gaya hai." if hi
                             else "You told us this was easy, so practice time was reduced.")
    return " ".join(parts)


# ---------------------------------------------------------------------------------------------------
# versioning, diff
# ---------------------------------------------------------------------------------------------------

def latest(db: Session, learner_id: str) -> Optional[RoadmapVersion]:
    return db.scalars(select(RoadmapVersion).where(RoadmapVersion.learner_id == learner_id)
                      .order_by(RoadmapVersion.version.desc())).first()


def diff(old_items: list[dict], new_items: list[dict]) -> dict[str, Any]:
    old = {i["item_id"]: i for i in old_items}
    new = {i["item_id"]: i for i in new_items}
    added = [i for k, i in new.items() if k not in old]
    removed = [i for k, i in old.items() if k not in new]
    moved = [{"item_id": k, "concept_id": new[k]["concept_id"], "title": new[k]["title"], "from": old[k]["order"], "to": new[k]["order"]}
             for k in new if k in old and old[k]["order"] != new[k]["order"] and abs(old[k]["order"] - new[k]["order"]) >= 2]
    updated = [{"item_id": k, "concept_id": new[k]["concept_id"], "title": new[k]["title"],
                "from_kind": old[k]["kind"], "to_kind": new[k]["kind"]}
               for k in new if k in old and old[k]["kind"] != new[k]["kind"]]
    return {
        "added": [{"item_id": i["item_id"], "concept_id": i["concept_id"], "title": i["title"], "kind": i["kind"]} for i in added],
        "removed": [{"item_id": i["item_id"], "concept_id": i["concept_id"], "title": i["title"]} for i in removed],
        "moved": moved,
        "updated": updated,
    }


def change_text(d: dict[str, Any], trigger: str) -> str:
    bits: list[str] = []
    if "feedback" in trigger.lower() or "too_hard" in trigger.lower() or "too_easy" in trigger.lower():
        bits.append("Adjusted practice time based on your feedback")
    if d["added"]:
        bits.append("Added: " + ", ".join(a["title"] for a in d["added"][:4]))
    if d["removed"]:
        bits.append("Removed (now at target): " + ", ".join(r["title"] for r in d["removed"][:4]))
    if d["moved"]:
        bits.append("Re-ordered: " + ", ".join(m["title"] for m in d["moved"][:3]))
    for u in d.get("updated", [])[:3]:
        if u["to_kind"] == "fix_misconception":
            bits.append(f"{u['title']} now starts with a targeted fix for a misconception")
        elif u["from_kind"] == "fix_misconception":
            bits.append(f"{u['title']} is back to normal practice")
    if not bits:
        return f"No change to the plan after {trigger}."
    return f"After {trigger}. " + "; ".join(bits) + "."


def refresh(db: Session, learner: Learner, trigger: str = "new evidence", force: bool = False) -> dict[str, Any]:
    """Rebuild the roadmap and save a new version if it changed (or `force`)."""
    new = build(db, learner)
    prev = latest(db, learner.id)
    d = diff(prev.items, new["items"]) if prev else {"added": [], "removed": [], "moved": [], "updated": []}
    changed = bool(d["added"] or d["removed"] or d["moved"] or d["updated"]) or prev is None or force
    if not changed:
        return {"version": prev.version, "changed": False, "diff": d, **{"items": prev.items, "summary": prev.summary},
                "change_reason": prev.change_reason}
    reason = "Initial roadmap built from your placement results." if prev is None else change_text(d, trigger)
    rv = RoadmapVersion(learner_id=learner.id, version=(prev.version + 1) if prev else 1, items=new["items"],
                        summary=new["summary"], change_reason=reason, diff=d)
    db.add(rv)
    db.flush()
    return {"version": rv.version, "changed": True, "diff": d, "items": rv.items, "summary": rv.summary,
            "change_reason": reason}


def current(db: Session, learner: Learner) -> dict[str, Any]:
    rv = latest(db, learner.id)
    if rv is None:
        return refresh(db, learner, "setup")
    # statuses/p_now drift as evidence arrives; rebuild the live view but keep version metadata
    live = build(db, learner)
    prev_items = {i["item_id"]: i for i in rv.items}
    for it in live["items"]:
        it["why"] = why_text(it, learner.language_pref)
    return {"version": rv.version, "changed": False, "diff": rv.diff, "items": live["items"], "summary": live["summary"],
            "change_reason": rv.change_reason, "saved_items": len(prev_items)}


# ---------------------------------------------------------------------------------------------------
# why not / what-if / today
# ---------------------------------------------------------------------------------------------------

def why_not(db: Session, learner: Learner, concept_id: str) -> dict[str, Any]:
    content = get_content()
    if concept_id not in content.concepts:
        raise KeyError(concept_id)
    role = content.role(learner.role_id or "backend_developer")
    req = role["requirements"]
    views = mastery.concept_views(db, learner)
    live = build(db, learner)
    name = content.concepts[concept_id].name
    in_plan = next((i for i in live["items"] if i["concept_id"] == concept_id), None)
    if in_plan:
        return {"concept_id": concept_id, "in_plan": True, "code": "IN_PLAN",
                "text": f"{name} is in your plan (step {in_plan['order']}, week {in_plan['week']})."}
    if concept_id not in req:
        return {"concept_id": concept_id, "in_plan": False, "code": "NOT_IN_ROLE",
                "text": f"{name} is not required for the {role['title']} role, so it is not in the plan."}
    v = views[concept_id]
    if v["p"] >= req[concept_id]["target"] * DONE_RATIO:
        return {"concept_id": concept_id, "in_plan": False, "code": "AT_TARGET",
                "text": f"You are already at {int(v['p']*100)}% here; the role needs {int(req[concept_id]['target']*100)}%. Nothing to add."}
    dropped = next((d for d in live["summary"]["dropped"] if d["concept_id"] == concept_id), None)
    if dropped:
        return {"concept_id": concept_id, "in_plan": False, "code": "BUDGET",
                "text": f"It would need about {dropped['minutes']} minutes, and your {live['summary']['weekly_hours']:g}h/week over "
                        f"{live['summary']['horizon_weeks']} weeks is already used by higher-value items. Raise your hours to include it.",
                "minutes": dropped["minutes"]}
    return {"concept_id": concept_id, "in_plan": False, "code": "LOW_PRIORITY",
            "text": f"{name} has a small gap compared with the other topics, so it was left out for now."}


def what_if(db: Session, learner: Learner, weekly_hours: float, horizon_weeks: int) -> dict[str, Any]:
    cur = build(db, learner)
    alt = build(db, learner, weekly_hours=weekly_hours, horizon_weeks=horizon_weeks)
    d = diff(cur["items"], alt["items"])
    return {"current": cur["summary"], "scenario": alt["summary"], "diff": d, "items": alt["items"]}


def today_mission(db: Session, learner: Learner, roadmap: Optional[dict] = None, limit: int = 3) -> list[dict[str, Any]]:
    content = get_content()
    rm = roadmap or current(db, learner)
    out: list[dict[str, Any]] = []
    for m in misconception.describe(db, learner.id):
        if m["status"] in ("confirmed", "correcting", "pending_verify"):
            out.append({"type": "fix_misconception", "concept_id": m["concept_id"], "title": f"Fix: {m['name']}",
                        "minutes": 15, "reason": m["description"], "misconception_id": m["misconception_id"]})
            break
    for it in rm["items"]:
        if it["kind"] == "review" and len(out) < limit:
            out.append({"type": "review", "concept_id": it["concept_id"], "title": it["title"], "minutes": 10,
                        "reason": "Spaced review: this was learned a while ago."})
    for it in rm["items"]:
        if len(out) >= limit:
            break
        if it["kind"] in ("learn", "fix_misconception") and it["status"] != "done":
            if any(o["concept_id"] == it["concept_id"] for o in out):
                continue
            out.append({"type": "learn", "concept_id": it["concept_id"], "title": it["title"], "minutes": it["minutes"],
                        "reason": why_text(it, learner.language_pref).split(". ")[0]})
    return out[:limit]
