"""Learning Navigation System: "Google Maps for Learning".

Generates dynamic, learner-specific navigation maps directly from live BKT mastery states,
misconception signals, prerequisite closures, and adaptive detours.
"""

from __future__ import annotations

from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..models import Learner, RoadmapVersion
from ..models_ext.G01 import DetourLog
from . import knowledge_graph, mastery, misconception, planner


def generate_learning_map(
    db: Session,
    learner: Learner,
    goal_id: Optional[str] = None
) -> dict[str, Any]:
    """Generates the full self-generating learning map from the learner's current state."""
    content = get_content()
    gid = goal_id or learner.role_id or "backend_developer"
    role = content.role(gid)

    # 1. Fetch live knowledge subgraph with computed states
    subgraph = knowledge_graph.get_learning_subgraph(db, learner, gid)
    nodes = subgraph["nodes"]
    edges = subgraph["edges"]

    # 2. Get latest roadmap version
    rm = planner.current(db, learner)

    # 3. Locate the recommended next node
    recommended_node_id = subgraph["recommended_next"]
    recommended_node = next((n for n in nodes if n["id"] == recommended_node_id), None)

    # 4. Formulate the immediate navigation action
    if recommended_node:
        if recommended_node["state"] == "MISCONCEPTION":
            action_type = "remediation"
            action_title = f"Fix Misconception: {recommended_node['title']}"
            action_url = f"/learn/{recommended_node['id']}#teachback"
        elif recommended_node["state"] == "DETOUR":
            action_type = "detour"
            action_title = f"Adaptive Detour: Solidify {recommended_node['title']}"
            action_url = f"/learn/{recommended_node['id']}"
        elif content.tasks_by_concept.get(recommended_node["id"]):
            action_type = "practice"
            action_title = f"Practise SQL: {recommended_node['title']}"
            action_url = f"/learn/{recommended_node['id']}#practice"
        else:
            action_type = "learn"
            action_title = f"Master Concept: {recommended_node['title']}"
            action_url = f"/learn/{recommended_node['id']}"
    else:
        action_type = "goal_reached"
        action_title = "You have reached the target on every competency for this goal! 🎓"
        action_url = "/interview"

    # 5. Extract active detours
    active_detours = list(db.scalars(
        select(DetourLog).where(DetourLog.learner_id == learner.id, DetourLog.status == "active")
    ))
    detour_items = [
        {
            "id": d.id,
            "target_concept": d.target_concept_id,
            "target_title": content.concepts[d.target_concept_id].name if d.target_concept_id in content.concepts else d.target_concept_id,
            "detour_concept": d.detour_concept_id,
            "detour_title": content.concepts[d.detour_concept_id].name if d.detour_concept_id in content.concepts else d.detour_concept_id,
            "reason": d.reason,
            "created_at": d.created_at.isoformat()
        }
        for d in active_detours
    ]

    # 6. Aggregate counts
    state_counts = {
        "mastered": sum(1 for n in nodes if n["state"] == "MASTERED"),
        "in_progress": sum(1 for n in nodes if n["state"] == "IN_PROGRESS"),
        "available": sum(1 for n in nodes if n["state"] == "AVAILABLE"),
        "recommended": sum(1 for n in nodes if n["state"] == "RECOMMENDED"),
        "blocked": sum(1 for n in nodes if n["state"] == "BLOCKED"),
        "misconception": sum(1 for n in nodes if n["state"] == "MISCONCEPTION"),
        "detour": sum(1 for n in nodes if n["state"] == "DETOUR"),
        "locked": sum(1 for n in nodes if n["state"] == "LOCKED"),
    }

    # Overall progress percentage
    req = role["requirements"]
    views = mastery.concept_views(db, learner)
    overall_pct = mastery.overall_mastery(views, req)

    return {
        "goal": subgraph["goal"],
        "version": rm["version"],
        "overall_progress": overall_pct,
        "current_node": recommended_node_id,
        "recommended_next": recommended_node_id,
        "navigation_action": {
            "type": action_type,
            "title": action_title,
            "url": action_url,
            "why": recommended_node["why"] if recommended_node else "Goal completed."
        },
        "nodes": nodes,
        "edges": edges,
        "detours": detour_items,
        "stats": state_counts,
        "reason": rm.get("change_reason", "Adaptive route generated from current Learner Twin state."),
        "diff": rm.get("diff", {}),
        "generated_at": subgraph["generated_at"]
    }


def change_learner_goal(
    db: Session,
    learner: Learner,
    new_goal_id: str
) -> dict[str, Any]:
    """Switches the learner's destination, preserves all existing mastery, and regenerates the route."""
    content = get_content()
    if new_goal_id not in content.roles:
        raise KeyError(f"Unknown goal role: {new_goal_id}")

    old_goal_id = learner.role_id or "backend_developer"
    old_role = content.role(old_goal_id)
    new_role = content.role(new_goal_id)

    # 1. Update learner role in DB
    learner.role_id = new_goal_id
    db.commit()

    # 2. Count transferable competencies
    views = mastery.concept_views(db, learner)
    old_req = old_role["requirements"]
    new_req = new_role["requirements"]

    transferable_mastered = [
        cid for cid in new_req
        if cid in old_req and views[cid]["p"] >= (new_req[cid]["target"] * 0.95)
    ]
    new_unmet = [
        cid for cid in new_req
        if views[cid]["p"] < (new_req[cid]["target"] * 0.95)
    ]

    reason = (
        f"Goal changed from {old_role['title']} to {new_role['title']}. "
        f"{len(transferable_mastered)} skills at target level carried over; "
        f"{len(new_unmet)} competencies targeted for the new destination."
    )

    # 3. Refresh and rebuild the roadmap with the new goal
    new_rm = planner.refresh(db, learner, trigger=reason, force=True)

    # 4. Generate the new map
    return generate_learning_map(db, learner, new_goal_id)
