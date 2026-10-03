"""Knowledge Graph Engine: multi-relational learning graph and learner state evaluator.

Represents skills, concepts, practice tasks, assessments, and challenges with typed relationships:
  - PREREQUISITE: node A must be understood before node B
  - BUILDS_ON: inverse of PREREQUISITE
  - PART_OF: concept belongs to a domain/skill cluster
  - ASSESSED_BY: concept tested by diagnostic item
  - PRACTICED_BY: concept practiced by SQL sandbox task
  - VERIFIED_BY: concept verified by practical Vakh challenge
  - LEADS_TO: concept progresses to higher-level concept or project
  - RELATED_TO: conceptual sibling in same domain

Computes deterministic states per learner:
  MASTERED | IN_PROGRESS | AVAILABLE | RECOMMENDED | LOCKED | BLOCKED | NEEDS_REVIEW | MISCONCEPTION | DETOUR
"""

from __future__ import annotations

from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..models import Learner
from ..models_ext.G01 import KnowledgeEdge, KnowledgeNode, VakhChallenge
from . import mastery, misconception

NODE_TYPES = {
    "SKILL", "CONCEPT", "TOPIC", "PROJECT", "PRACTICE", "ASSESSMENT", "RESOURCE", "CHALLENGE"
}

RELATIONSHIP_TYPES = {
    "PREREQUISITE", "BUILDS_ON", "RELATED_TO", "PART_OF", "LEADS_TO", "ASSESSED_BY", "PRACTICED_BY", "VERIFIED_BY"
}


def sync_graph_to_db(db: Session) -> None:
    """Populates the database KnowledgeNode and KnowledgeEdge tables from curated content if empty."""
    c = get_content()
    existing_count = db.scalar(select(KnowledgeNode.id).limit(1))
    if existing_count is not None:
        return

    nodes_to_add: list[KnowledgeNode] = []
    edges_to_add: list[KnowledgeEdge] = []

    # 1. Concept nodes
    for cid, conc in c.concepts.items():
        node = KnowledgeNode(
            id=cid,
            title=conc.name,
            title_hi=conc.name_hi,
            description=f"Core concept in {conc.domain}: {conc.name}",
            node_type="CONCEPT",
            domain=conc.domain,
            difficulty="beginner" if not conc.prereqs else ("intermediate" if len(conc.prereqs) < 3 else "advanced"),
            estimated_minutes=conc.minutes,
            metadata_json={"aliases": conc.aliases, "p_init": conc.p_init, "p_learn": conc.p_learn}
        )
        nodes_to_add.append(node)

        # Prerequisite edges
        for pid in conc.prereqs:
            edges_to_add.append(KnowledgeEdge(
                source_node_id=pid,
                target_node_id=cid,
                relationship_type="PREREQUISITE",
                weight=1.0,
                required=True,
                metadata_json={"label": "Prerequisite"}
            ))
            edges_to_add.append(KnowledgeEdge(
                source_node_id=cid,
                target_node_id=pid,
                relationship_type="BUILDS_ON",
                weight=1.0,
                required=False,
                metadata_json={"label": "Builds on"}
            ))

    # 2. Add Practice and Assessment relationships
    for cid, tasks in c.tasks_by_concept.items():
        for t in tasks:
            task_node_id = f"task_{t['id']}"
            nodes_to_add.append(KnowledgeNode(
                id=task_node_id,
                title=t.get("title") or (t.get("prompt", "")[:60] + "..."),
                title_hi=t.get("title_hi"),
                description=t.get("prompt", ""),
                node_type="PRACTICE",
                domain="sql",
                difficulty="intermediate",
                estimated_minutes=15,
                metadata_json={"schema": "shop.sql"}
            ))
            edges_to_add.append(KnowledgeEdge(
                source_node_id=cid,
                target_node_id=task_node_id,
                relationship_type="PRACTICED_BY",
                weight=1.0,
                required=False
            ))

    # 3. Add Vakh Challenge Nodes for core milestones
    vakh_challenges = [
        ("sql_relational_model", "Build Normalized Bookstore Schema", "Design 3NF tables with Primary and Foreign Keys in SQLite/Postgres."),
        ("sql_select", "E-Commerce Customer Query Suite", "Write clean SELECT queries with aliases and calculated columns."),
        ("sql_filtering", "Customer Fraud & Anomaly Filter", "Filter rows using complex WHERE conditions with NULL safety."),
        ("sql_group_by", "Monthly Departmental Expense Aggregator", "Calculate department aggregates using GROUP BY and HAVING filters."),
        ("sql_inner_join", "Customer Order Fulfillment Pipeline", "Join customer and order tables to report delivered revenue."),
        ("sql_outer_join", "Zero-Order Customer Outreach Audit", "Find customers who have never placed an order using LEFT JOIN and NULL checks."),
        ("sql_multi_table", "Multi-Warehouse Inventory Tracker", "Join customers, orders, order items, and products for unified stock tracking."),
        ("fastapi_basics", "REST API Backend Microservice", "Build a production-ready FastAPI endpoint that queries the database."),
    ]
    for cid, ch_title, ch_obj in vakh_challenges:
        ch_id = f"vch_{cid}"
        nodes_to_add.append(KnowledgeNode(
            id=ch_id,
            title=ch_title,
            description=ch_obj,
            node_type="CHALLENGE",
            domain="vakh",
            difficulty="intermediate",
            estimated_minutes=60,
            metadata_json={"vakh_form": "project_challenge_form"}
        ))
        edges_to_add.append(KnowledgeEdge(
            source_node_id=cid,
            target_node_id=ch_id,
            relationship_type="VERIFIED_BY",
            weight=1.5,
            required=False
        ))

    db.add_all(nodes_to_add)
    db.add_all(edges_to_add)
    db.commit()


def compute_node_state(
    cid: str,
    p_known: float,
    target: float,
    views: dict[str, Any],
    active_misconceptions: dict[str, list[str]],
    detour_concepts: set[str],
    recommended_cid: Optional[str],
    prereqs: list[str]
) -> dict[str, Any]:
    """Computes deterministic navigation state and tags for a knowledge node."""
    c = get_content()
    has_misconception = bool(active_misconceptions.get(cid))
    is_mastered = p_known >= (target * 0.95) and not has_misconception
    is_detour = cid in detour_concepts

    # Check prerequisites
    unmet_prereqs = [p for p in prereqs if views.get(p, {}).get("p", 0.0) < 0.70]
    misconception_prereqs = [p for p in prereqs if active_misconceptions.get(p)]

    # Determine State
    if has_misconception:
        state = "MISCONCEPTION"
        nav_tag = "DETOUR" if is_detour else "MISCONCEPTION"
    elif is_detour:
        state = "DETOUR"
        nav_tag = "DETOUR"
    elif is_mastered:
        state = "MASTERED"
        nav_tag = "COMPLETED"
    elif cid == recommended_cid:
        state = "RECOMMENDED"
        nav_tag = "RECOMMENDED NEXT"
    elif misconception_prereqs:
        state = "BLOCKED"
        nav_tag = f"BLOCKED UNTIL {c.concepts[misconception_prereqs[0]].name.upper()} FIXED"
    elif unmet_prereqs:
        state = "BLOCKED"
        nav_tag = f"BLOCKED UNTIL {c.concepts[unmet_prereqs[0]].name.upper()}"
    elif p_known > (c.concepts[cid].p_init if cid in c.concepts else 0.25):
        state = "IN_PROGRESS"
        nav_tag = "IN PROGRESS"
    elif all(views.get(p, {}).get("p", 0.0) >= 0.70 for p in prereqs):
        state = "AVAILABLE"
        nav_tag = "AVAILABLE"
    else:
        state = "LOCKED"
        nav_tag = "LOCKED"

    # Check Spaced Review
    if views.get(cid, {}).get("due_for_review"):
        state = "NEEDS_REVIEW"
        nav_tag = "NEEDS REVIEW"

    return {
        "state": state,
        "nav_tag": nav_tag,
        "is_mastered": is_mastered,
        "has_misconception": has_misconception,
        "is_detour": is_detour,
        "unmet_prereqs": unmet_prereqs,
        "misconception_prereqs": misconception_prereqs
    }


def get_learning_subgraph(
    db: Session,
    learner: Learner,
    goal_id: Optional[str] = None
) -> dict[str, Any]:
    """Retrieves the goal-specific knowledge graph enriched with real learner state and navigation tags."""
    sync_graph_to_db(db)
    content = get_content()
    gid = goal_id or learner.role_id or "backend_developer"
    role = content.role(gid)
    req = role["requirements"]
    views = mastery.concept_views(db, learner)

    # Active Misconceptions
    raw_mis = misconception.describe(db, learner.id)
    active_mis: dict[str, list[str]] = {}
    for m in raw_mis:
        if m["status"] in ("candidate", "confirmed", "correcting", "pending_verify"):
            active_mis.setdefault(m["concept_id"], []).append(m["misconception_id"])

    # Detect detours (where learner struggled repeatedly or has prerequisite struggle)
    detour_concepts: set[str] = set()
    for cid in req:
        v = views[cid]
        if v.get("attempts_since_unresolved", 0) >= 2 or cid in active_mis:
            # Add prerequisites as detours
            for p in content.concepts[cid].prereqs:
                if views[p]["p"] < req.get(p, {}).get("target", 0.8):
                    detour_concepts.add(p)

    # Topological sorting of required nodes
    closure_needed: set[str] = set(req.keys())
    for cid in list(closure_needed):
        closure_needed |= content.ancestors(cid)

    # Find Recommended Next node
    recommended_cid: Optional[str] = None
    # 1st priority: active detour
    for d in detour_concepts:
        if views[d]["p"] < req.get(d, {}).get("target", 0.8):
            recommended_cid = d
            break
    # 2nd priority: active misconception
    if not recommended_cid:
        for cid in content.topo_order(closure_needed):
            if cid in active_mis:
                recommended_cid = cid
                break
    # 3rd priority: first ready unmet concept
    if not recommended_cid:
        for cid in content.topo_order(closure_needed):
            if views[cid]["p"] < req.get(cid, {}).get("target", 0.8) * 0.95:
                # check if prerequisites satisfied
                prereqs = content.concepts[cid].prereqs
                if all(views[p]["p"] >= 0.5 and p not in active_mis for p in prereqs):
                    recommended_cid = cid
                    break

    nodes: list[dict[str, Any]] = []
    for cid in content.order:
        if cid not in closure_needed:
            continue
        c = content.concepts[cid]
        v = views[cid]
        target = req.get(cid, {}).get("target", 0.8)
        weight = req.get(cid, {}).get("weight", 1.0)
        gap = max(0.0, target - v["p"])

        computed = compute_node_state(
            cid=cid,
            p_known=v["p"],
            target=target,
            views=views,
            active_misconceptions=active_mis,
            detour_concepts=detour_concepts,
            recommended_cid=recommended_cid,
            prereqs=c.prereqs
        )

        # Evidence count
        n_ev = v.get("n_evidence", 0)

        # Grounded explanation
        if computed["has_misconception"]:
            mis_names = [content.misconceptions[m]["name"] for m in active_mis[cid] if m in content.misconceptions]
            why_text = f"You are here because recent answers flagged a misunderstanding: {', '.join(mis_names)}. Resolving this will unblock dependent concepts."
        elif computed["is_detour"]:
            why_text = "You are on an adaptive detour. Strengthening this foundation will allow you to master more advanced dependencies."
        elif computed["state"] == "BLOCKED":
            blockers = [content.concepts[p].name for p in computed["unmet_prereqs"] + computed["misconception_prereqs"]]
            why_text = f"Blocked until prerequisites are solid: {', '.join(blockers)}."
        elif computed["state"] == "RECOMMENDED":
            why_text = f"Recommended next: Closing this {int(gap*100)}% gap has the highest value density for your goal as a {role['title']}."
        elif computed["is_mastered"]:
            why_text = f"Mastered! You reached {int(v['p']*100)}% (target was {int(target*100)}%)."
        else:
            why_text = f"Current mastery is {int(v['p']*100)}% with a target of {int(target*100)}%."

        nodes.append({
            "id": cid,
            "title": c.name,
            "title_hi": c.name_hi,
            "domain": c.domain,
            "difficulty": "beginner" if not c.prereqs else ("intermediate" if len(c.prereqs) < 3 else "advanced"),
            "node_type": "CONCEPT",
            "p_known": round(v["p"], 3),
            "target": target,
            "weight": weight,
            "gap": round(gap, 3),
            "level": v["level"],
            "state": computed["state"],
            "nav_tag": computed["nav_tag"],
            "is_current": cid == recommended_cid,
            "prerequisites": c.prereqs,
            "dependents": [d for d in content.dependents(cid) if d in closure_needed],
            "n_evidence": n_ev,
            "misconceptions": active_mis.get(cid, []),
            "has_vakh_challenge": True,
            "why": why_text
        })

    # Edges
    edges: list[dict[str, Any]] = []
    for cid in closure_needed:
        for p in content.concepts[cid].prereqs:
            if p in closure_needed:
                p_mastered = views[p]["p"] >= (req.get(p, {}).get("target", 0.8) * 0.95)
                edges.append({
                    "from": p,
                    "to": cid,
                    "type": "PREREQUISITE",
                    "label": "Prerequisite",
                    "satisfied": p_mastered
                })

    return {
        "goal": {
            "id": role["id"],
            "title": role["title"],
            "title_hi": role.get("title_hi", role["title"]),
            "blurb": role["blurb"]
        },
        "current_node": recommended_cid,
        "recommended_next": recommended_cid,
        "nodes": nodes,
        "edges": edges,
        "detour_count": len(detour_concepts),
        "active_misconceptions": sum(len(m) for m in active_mis.values()),
        "generated_at": mastery.learner_now(learner).isoformat()
    }
