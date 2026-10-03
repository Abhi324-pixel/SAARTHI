"""Teacher / institution view (lite): aggregate, privacy-preserving class insight.

`synthetic_cohort()` produces the MOCK data; `records_from_db()` produces the same record shape from real
learners. `aggregate()` is shared, so mock and real providers cannot drift apart.
"""

from __future__ import annotations

import random
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..models import CohortMember, ConceptState, MisconceptionInstance
from . import mastery

def _sql_concepts() -> list[str]:
    return [cid for cid in get_content().order if cid.startswith("sql_")]


def synthetic_cohort(n: int = 24, seed: int = 11) -> list[dict[str, Any]]:
    c = get_content()
    rnd = random.Random(seed)
    sql = _sql_concepts()
    holders = {"left_join_as_inner": 0.42, "where_vs_having": 0.30, "null_comparison": 0.38,
               "count_star_with_left_join": 0.26, "join_fanout_sum": 0.22, "limit_without_order": 0.18}
    out: list[dict[str, Any]] = []
    for i in range(1, n + 1):
        ability = min(0.92, max(0.2, rnd.gauss(0.55, 0.18)))
        p: dict[str, float] = {}
        ne: dict[str, int] = {}
        for idx, cid in enumerate(sql):
            depth = idx / max(len(sql) - 1, 1)
            val = ability - 0.35 * depth + rnd.gauss(0, 0.08)
            p[cid] = round(min(0.97, max(0.05, val)), 3)
            ne[cid] = rnd.randint(1, 5)
        mis = [mid for mid, prob in holders.items() if rnd.random() < prob * (1.3 - ability)]
        # misconceptions drag down their own concept
        for mid in mis:
            cid = c.misconceptions[mid]["concept_id"]
            if cid in p:
                p[cid] = round(min(p[cid], 0.55), 3)
        out.append({"ref": f"mock_cohort_{i:02d}", "display_name": f"Demo learner {i:02d}", "p": p, "n_evidence": ne,
                    "misconceptions": mis})
    return out


def records_from_db(db: Session, cohort_id: str) -> list[dict[str, Any]]:
    members = list(db.scalars(select(CohortMember).where(CohortMember.cohort_id == cohort_id)))
    out = []
    for m in members:
        states = list(db.scalars(select(ConceptState).where(ConceptState.learner_id == m.learner_id)))
        mis = [mi.misconception_id for mi in db.scalars(select(MisconceptionInstance).where(
            MisconceptionInstance.learner_id == m.learner_id, MisconceptionInstance.status.in_(("confirmed", "correcting", "pending_verify"))))]
        out.append({"ref": m.learner_id, "display_name": m.display_name or m.learner_id,
                    "p": {s.concept_id: round(s.p_known, 3) for s in states if s.n_evidence > 0},
                    "n_evidence": {s.concept_id: s.n_evidence for s in states if s.n_evidence > 0}, "misconceptions": mis})
    return out


def aggregate(records: Iterable[dict[str, Any]], cohort_id: str, name: str, is_mock: bool) -> dict[str, Any]:
    c = get_content()
    recs = list(records)
    concepts = []
    all_cids = sorted({cid for r in recs for cid in r["p"]}, key=lambda x: c.order.index(x))
    for cid in all_cids:
        levels = {"unknown": 0, "developing": 0, "proficient": 0, "mastered": 0}
        ps = []
        for r in recs:
            if cid not in r["p"]:
                continue
            lvl = mastery.level_of(r["p"][cid], r["n_evidence"].get(cid, 1), ["question", "work_product"])
            levels[lvl if lvl in levels else "unknown"] += 1
            ps.append(r["p"][cid])
        concepts.append({"concept_id": cid, "name": c.concepts[cid].name, "levels": levels,
                         "n": len(ps), "avg_p": round(sum(ps) / len(ps), 3) if ps else 0.0})
    mis_count: dict[str, int] = {}
    for r in recs:
        for mid in r["misconceptions"]:
            mis_count[mid] = mis_count.get(mid, 0) + 1
    top = sorted(mis_count.items(), key=lambda kv: -kv[1])
    attention = []
    for r in recs:
        weak = [cid for cid, p in r["p"].items() if p < 0.4]
        if len(r["misconceptions"]) >= 2 or len(weak) >= 4:
            reason = []
            if r["misconceptions"]:
                reason.append(f"{len(r['misconceptions'])} active misconception(s)")
            if weak:
                reason.append(f"{len(weak)} concepts below 40%")
            attention.append({"ref": r["ref"], "display_name": r["display_name"], "reason": "; ".join(reason)})
    return {
        "cohort_id": cohort_id, "name": name, "n_learners": len(recs), "is_mock": is_mock,
        "concepts": concepts,
        "top_misconceptions": [{"misconception_id": mid, "name": c.misconceptions[mid]["name"],
                                "concept_id": c.misconceptions[mid]["concept_id"],
                                "concept_name": c.concepts[c.misconceptions[mid]["concept_id"]].name,
                                "count": n, "share": round(n / len(recs), 2) if recs else 0.0} for mid, n in top[:6]],
        "needs_attention": attention[:8],
        "privacy_note": "Aggregated view. Individual transcripts are never shown to teachers.",
    }
