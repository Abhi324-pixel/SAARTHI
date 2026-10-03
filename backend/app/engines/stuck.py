""""I'm stuck": diagnose WHY, not just how to fix.

Order of evidence: (1) if a SQL query was supplied, execute it and use the objective result (task variants
and static rules); (2) otherwise ask the model to classify the message into curated concept / misconception
ids, which are validated here; (3) keyword fallback. Only objective (executed) findings can create a
confirmed misconception; a model-suggested one becomes a candidate that needs a read-back.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..content import get_content
from ..llm import gateway, tasks
from ..models import Learner
from . import diagnostic, mastery, misconception, sqlcheck


def diagnose(db: Session, learner: Learner, *, text: str, query: Optional[str] = None, task_id: Optional[str] = None,
             concept_id: Optional[str] = None) -> dict[str, Any]:
    c = get_content()
    out: dict[str, Any] = {"objective": None, "cause": "unclear", "concept_id": concept_id, "misconception": None,
                           "explanation": "", "next_step": "", "source": "none"}
    evidence_note = ""
    # 1) objective check of the supplied query
    if query and query.strip():
        if task_id and task_id in c.tasks:
            res = diagnostic.submit_work_product(db, learner, task_id, query)
            out["objective"] = {"ran": res["ran"], "correct": res["correct"], "error": res["error"], "hints": res["hints"],
                                "columns": res["columns"], "rows": res["rows"][:20]}
            out["concept_id"] = res["concept_id"]
            if res["misconception"]:
                out["cause"] = "misconception"
                out["misconception"] = res["misconception"]
                out["explanation"] = f"Your query matches a common mix-up: {res['misconception']['name']}. {res['misconception']['description']}"
                out["next_step"] = res["misconception"]["fix_hint"]
                out["source"] = "executed_query"
                return out
            if res["correct"]:
                out.update(cause="slip", explanation="Your query is actually correct — it returns the expected result.",
                           next_step="Move on to the next task.", source="executed_query")
                return out
            evidence_note = "; ".join(res["hints"]) or (res["error"] or "")
        else:
            r = sqlcheck.run_query(query)
            out["objective"] = {"ran": r.ok, "error": r.error, "columns": r.columns, "rows": r.rows[:20]}
            evidence_note = r.error or f"query ran and returned {len(r.rows)} row(s)"
            import re
            if re.search(r"(=|<>|!=)\s*null\b", query, re.I):
                m = c.misconceptions["null_comparison"]
                out.update(cause="misconception", concept_id="sql_null", source="static_rule",
                           explanation=f"{m['name']}. {m['description']}", next_step=m["fix_hint"],
                           misconception={"id": m["id"], "name": m["name"], "description": m["description"],
                                          "counter_example": m["counter_example"], "fix_hint": m["fix_hint"]})
                return out
    # 2) model classification (validated)
    hint = concept_id or tasks.concept_from_keywords(text + " " + (query or ""))
    try:
        cls = tasks.classify_stuck(text + ("\nQUERY:\n" + query if query else ""), hint, evidence_note, learner.language_pref)
        cid = cls.get("concept_id") if cls.get("concept_id") in c.concepts else (hint or "sql_select")
        out.update(concept_id=cid, cause=cls.get("cause", "unclear"), explanation=cls.get("explanation", ""),
                   next_step=cls.get("next_step", ""), source="llm")
        mid = cls.get("misconception_id")
        if cls.get("cause") == "misconception" and mid in c.misconceptions:
            m = c.misconceptions[mid]
            sig = misconception.register_signal(db, learner, mid, "explain_back", statement=text[:160])
            out["misconception"] = {"id": mid, "name": m["name"], "description": m["description"],
                                    "counter_example": m["counter_example"], "fix_hint": m["fix_hint"], "instance": sig}
        pre = cls.get("prerequisite_concept_id")
        if cls.get("cause") == "prerequisite" and pre in c.concepts:
            out["prerequisite_concept_id"] = pre
            out["prerequisite_name"] = c.concepts[pre].name
    except gateway.LLMUnavailable:
        cid = hint or "sql_select"
        views = mastery.concept_views(db, learner)
        weak_pre = next((p for p in c.prereqs(cid) if views[p]["n_evidence"] > 0 and views[p]["level"] in ("unknown", "developing")), None)
        out.update(concept_id=cid, source="rules")
        if weak_pre:
            out.update(cause="prerequisite", prerequisite_concept_id=weak_pre, prerequisite_name=c.concepts[weak_pre].name,
                       explanation=f"{c.concepts[weak_pre].name} looks shaky in your results, and {c.concepts[cid].name} builds on it.",
                       next_step=f"Revisit {c.concepts[weak_pre].name} first.")
        else:
            out.update(explanation=f"This looks related to {c.concepts[cid].name}. The AI model isn't reachable, so I can't dig deeper right now.",
                       next_step=f"Try the practice tasks for {c.concepts[cid].name}.")
    # evidence: a stuck message is a self-report (recorded, never moves mastery)
    if out.get("concept_id") in c.concepts:
        mastery.apply_evidence(db, learner, out["concept_id"], "self_report", grader="stuck_button",
                               detail={"cause": out["cause"], "text": text[:200]})
    if out.get("concept_id") in c.concepts:
        out["concept_name"] = c.concepts[out["concept_id"]].name
    return out
