"""T07: Grounded typed assistant chat engine.

Answers questions strictly from the learner's own data (roadmap, reason codes, evidence,
misconceptions, reviews) and curated notes. Never grades or moves mastery.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..llm import gateway, tasks
from ..models import Learner, LearningSession, TranscriptTurn
from . import escalation, mastery, misconception, planner, strategy, stuck

SAFEGUARDING_MSG = (
    "I'm really glad you reached out. If you are feeling overwhelmed, hopeless, or unsafe right now, "
    "please contact a trusted adult or call Tele-MANAS at 14416 (free, 24/7 across India). "
    "You do not have to carry this alone."
)

INJECTION_PATTERN = re.compile(
    r"\b(ignore (all )?(prior|previous|system )?rules|mark .* as mastered|give me (admin|full) access|pretend to be|bypass restrictions)\b",
    re.I,
)


def _get_or_create_session(db: Session, learner: Learner, session_id: Optional[str]) -> LearningSession:
    if session_id:
        sess = db.get(LearningSession, session_id)
        if sess and sess.learner_id == learner.id and sess.mode == "chat":
            return sess
    sess = LearningSession(learner_id=learner.id, mode="chat", channel="text", status="active")
    db.add(sess)
    db.flush()
    return sess


def get_chat_suggestions(db: Session, learner: Learner) -> list[str]:
    """Generates 4 personalized starter prompts based on learner's current plan and role."""
    c = get_content()
    live = planner.build(db, learner)
    role = c.role(learner.role_id or "backend_developer")
    suggestions: list[str] = ["What should I work on next today?"]

    if live["items"]:
        first_cid = live["items"][0]["concept_id"]
        if first_cid in c.concepts:
            suggestions.append(f"Why is {c.concepts[first_cid].name} scheduled first?")

    suggestions.append("Why isn't Docker in my plan?")
    suggestions.append(f"How am I progressing toward {role['title']}?")
    return suggestions[:4]


def reply_to_message(
    db: Session,
    learner: Learner,
    text: str,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    """Processes a typed message grounded entirely in learner data and curated content."""
    clean_text = text.strip()
    c = get_content()
    session = _get_or_create_session(db, learner, session_id)

    # 1. Hard Rule: Wellbeing words skip model entirely
    if escalation.classify_category(clean_text) == "wellbeing":
        db.add(TranscriptTurn(session_id=session.id, role="learner", text=clean_text))
        db.add(TranscriptTurn(
            session_id=session.id,
            role="mentor_ai",
            text=SAFEGUARDING_MSG,
            meta={"helpline": "14416", "category": "wellbeing"},
        ))
        db.flush()
        return {
            "session_id": session.id,
            "reply": SAFEGUARDING_MSG,
            "actions": [
                {"type": "helpline", "label": "Call Tele-MANAS (14416)"},
                {"type": "open_case", "label": "Talk to a Safeguarding Lead", "category": "wellbeing"},
            ],
            "facts_used": ["Tele-MANAS helpline: 14416 (free, 24x7)"],
            "source": "deterministic",
        }

    # 2. Hard Rule: Prompt injection check
    if INJECTION_PATTERN.search(clean_text):
        reply = (
            "I can only answer questions based on your roadmap, learning evidence, and curated notes. "
            "Mastery in SAARTHI is only earned through verified practice evidence and cannot be manually modified."
        )
        db.add(TranscriptTurn(session_id=session.id, role="learner", text=clean_text))
        db.add(TranscriptTurn(session_id=session.id, role="mentor_ai", text=reply))
        db.flush()
        return {
            "session_id": session.id,
            "reply": reply,
            "actions": [{"type": "roadmap", "label": "View Roadmap"}],
            "facts_used": ["SAARTHI non-negotiable rule: mastery only advances with evidence"],
            "source": "deterministic",
        }

    # 3. Intent Routing
    history_turns = list(db.scalars(
        select(TranscriptTurn)
        .where(TranscriptTurn.session_id == session.id)
        .order_by(TranscriptTurn.created_at.desc())
        .limit(8)
    ))
    history_payload = [{"role": t.role, "text": t.text[:200]} for t in reversed(history_turns)]

    try:
        route = tasks.route_chat(clean_text, history=history_payload, language=learner.language_pref)
    except gateway.LLMUnavailable:
        # Fallback offline keyword routing
        t_low = clean_text.lower()
        cid = tasks.concept_from_keywords(t_low)
        if "why not" in t_low:
            route = {"intent": "why_not", "concept_id": cid or "docker_basics"}
        elif any(w in t_low for w in ("what next", "what should i do", "today", "mission")):
            route = {"intent": "next_step"}
        elif "why" in t_low:
            route = {"intent": "why_item", "concept_id": cid}
        elif any(w in t_low for w in ("progress", "readiness", "stats")):
            route = {"intent": "progress"}
        elif any(w in t_low for w in ("explain", "what is", "teach")):
            route = {"intent": "explain", "concept_id": cid or "sql_select"}
        else:
            route = {"intent": "out_of_scope"}

    intent = route.get("intent", "out_of_scope")
    raw_cid = route.get("concept_id")

    # Validate concept_id against curated content
    concept_id: Optional[str] = raw_cid if raw_cid in c.concepts else None
    if raw_cid and not concept_id:
        if intent in ("why_not", "explain", "why_item"):
            intent = "out_of_scope"

    # 4. Deterministic Fact Assembly per Intent
    facts_used: list[str] = []
    actions: list[dict[str, Any]] = []
    reply: str = ""

    if intent == "why_not":
        cid = concept_id or "docker_basics"
        try:
            wn = planner.why_not(db, learner, cid)
            reply = wn["text"]
            facts_used.append(f"Planner code: {wn['code']}")
            facts_used.append(wn["text"])
            actions.append({"type": "roadmap", "label": "View Roadmap"})
        except KeyError:
            reply = f"I don't have curriculum information for that topic."
            facts_used.append("Unknown topic for why_not")

    elif intent == "next_step":
        missions = planner.today_mission(db, learner)
        if missions:
            m = missions[0]
            reply = (
                f"Your next step is {m['title']} (estimated {m.get('minutes', 15)} mins). "
                f"Reason: {m.get('reason', 'Scheduled in your prioritized plan')}."
            )
            facts_used.append(f"Mission: {m['title']}")
            facts_used.append(f"Reason: {m.get('reason')}")
            actions.append({"type": "concept", "label": f"Start {m['title']}", "concept_id": m.get("concept_id")})
        else:
            reply = "You have completed all planned tasks for today! Check your roadmap for upcoming topics."
            facts_used.append("No active missions today")
            actions.append({"type": "roadmap", "label": "View Roadmap"})

    elif intent == "why_item":
        live = planner.build(db, learner)
        target_cid = concept_id or (live["items"][0]["concept_id"] if live["items"] else None)
        item = next((it for it in live["items"] if it["concept_id"] == target_cid), None)
        if item and target_cid in c.concepts:
            wt = planner.why_text(item, lang=learner.language_pref)
            reply = f"{c.concepts[target_cid].name} is at step {item['order']} in week {item['week']}. {wt}"
            facts_used.append(f"Step {item['order']}, week {item['week']}")
            facts_used.append(wt)
            actions.append({"type": "concept", "label": f"Practice {c.concepts[target_cid].name}", "concept_id": target_cid})
        else:
            reply = "That topic is not currently an active milestone in your personalized roadmap."
            facts_used.append("Concept not in current roadmap items")
            actions.append({"type": "roadmap", "label": "View Roadmap"})

    elif intent == "progress":
        role = c.role(learner.role_id or "backend_developer")
        views = mastery.concept_views(db, learner)
        overall = int(mastery.overall_mastery(views, role["requirements"]) * 100)
        mis = misconception.describe(db, learner.id)
        due = sum(1 for v in views.values() if v.get("due_for_review"))
        reply = (
            f"You are at {overall}% readiness for the {role['title']} role. "
            f"You have {len(mis)} active misconception(s) and {due} review(s) due."
        )
        facts_used.append(f"Overall readiness: {overall}%")
        facts_used.append(f"Active misconceptions: {len(mis)}")
        facts_used.append(f"Due reviews: {due}")
        actions.append({"type": "genome", "label": "View Learner Genome"})

    elif intent == "explain":
        cid = concept_id or "sql_select"
        ex = strategy.explain(db, learner, cid)
        cname = c.concepts[cid].name
        reply = f"Here is a summary of {cname}: {ex['text'][:550]}"
        facts_used.append(f"Curated explanation of {cname}")
        actions.append({"type": "concept", "label": f"Learn {cname}", "concept_id": cid})

    elif intent == "stuck":
        diag = stuck.diagnose(db, learner, text=clean_text, concept_id=concept_id)
        reply = f"Diagnosis: {diag['explanation']} Next step: {diag['next_step']}"
        facts_used.append(f"Diagnosed cause: {diag['cause']}")
        facts_used.append(diag["explanation"])
        if diag.get("concept_id"):
            actions.append({"type": "concept", "label": "Go to concept", "concept_id": diag["concept_id"]})

    elif intent == "mentor":
        reply = (
            "You can open a case with a Chhatrachhaya mentor anytime from the Mentors page. "
            "They will receive your full diagnostic history, misconception cycles, and code attempts."
        )
        facts_used.append("Chhatrachhaya mentor support")
        actions.append({"type": "mentors", "label": "Open a Mentor Case"})

    elif intent == "smalltalk":
        name_first = learner.name.split()[0] if learner.name else "there"
        reply = (
            f"Hi {name_first}! I'm SAARTHI, your adaptive AI mentor. "
            "Ask me why a topic is in your plan, what to learn next, how you are progressing, or explain any backend concept."
        )
        facts_used.append("Greeting")
        actions.append({"type": "roadmap", "label": "View Roadmap"})

    else:  # out_of_scope
        reply = (
            "I'm specifically focused on your backend learning journey, your personalized roadmap, and curated concepts. "
            "For general queries outside your curriculum, try asking about your plan or requesting a mentor session."
        )
        facts_used.append("Out of scope")
        actions.append({"type": "roadmap", "label": "View Roadmap"})

    # 5. Persist transcript
    db.add(TranscriptTurn(session_id=session.id, role="learner", text=clean_text))
    db.add(TranscriptTurn(
        session_id=session.id,
        role="mentor_ai",
        text=reply,
        meta={"intent": intent, "concept_id": concept_id, "facts": facts_used, "actions": actions},
    ))
    db.flush()

    return {
        "session_id": session.id,
        "reply": reply,
        "actions": actions,
        "facts_used": facts_used,
        "source": "deterministic",
    }
