"""C03: Learner prep notes before a mentor session and summary after it.

Deterministic generation grounded in the learner's case data (misconceptions, prerequisites,
and target role). Curated multilingual templates (English, Hinglish, Hindi).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import adapters
from ..content import get_content
from ..models import ConceptState, EvidenceEvent, Learner, MentorCase
from ..models_ext.C03 import CaseNote
from . import mastery

TEMPLATES: dict[str, dict[str, Any]] = {
    "english": {
        "bring_technical": [
            "The exact query you ran",
            "What you expected to see",
            "What you actually got",
        ],
        "bring_career": [
            "Your target role and preparation timeline",
            "Key topics or concepts you feel uncertain about",
            "Questions about real-world team workflows or interviews",
        ],
        "misconception": "Why does `{query}` give a different result?",
        "prerequisite": "Can we check if I really understand {name}? I think it is holding me back.",
        "concept": "What is the best mental model for understanding {name}?",
        "career_1": "How do technical interviewers evaluate junior developers on backend fundamentals?",
        "career_2": "Which practical projects or skills make a portfolio stand out most?",
        "career_3": "What daily habits help bridge the gap between learning and production code?",
        "goal": "What would you focus on next if you were in my position?",
        "icebreaker_tech": "Hi {mentor}, I'm {learner} — I've been working through {concept} and hit a roadblock with my queries.",
        "icebreaker_career": "Hi {mentor}, I'm {learner} — I'm preparing for backend roles and would love your guidance on my next steps.",
    },
    "hinglish": {
        "bring_technical": [
            "Aapne jo exact query run ki thi",
            "Aap kya output expect kar rahe the",
            "Actually kya result mila",
        ],
        "bring_career": [
            "Aapka target role aur preparation timeline",
            "Topics ya concepts jinme sabse zyada doubt hai",
            "Real-world workflows aur interviews se jude sawaal",
        ],
        "misconception": "Yeh query `{query}` alag result kyu deti hai?",
        "prerequisite": "Kya hum check kar sakte hain ki mujhe {name} theek se samajh aaya ya nahi? Lagta hai yeh mujhe hold back kar raha hai.",
        "concept": "{name} ko samajhne ke liye sabse accha mental model kya hai?",
        "career_1": "Interviewers junior backend developers ko fundamentals par kaise judge karte hain?",
        "career_2": "Backend resume par kaunse projects ya skills sabse zyada stand out karte hain?",
        "career_3": "Learning se real production coding tak pahunchne ke liye daily kya routine follow karein?",
        "goal": "Agar aap meri jagah hote toh agla focus kis cheez par karte?",
        "icebreaker_tech": "Hi {mentor}, main {learner} hoon — main {concept} par practice kar raha/rahi hoon aur mujhe kuch queries mein confusion aa raha hai.",
        "icebreaker_career": "Hi {mentor}, main {learner} hoon — main backend developer roles ke liye prepare kar raha/rahi hoon aur guidance chahiye thi.",
    },
    "hindi": {
        "bring_technical": [
            "सटीक क्वेरी जो आपने चलाई थी",
            "आप क्या परिणाम देखने की उम्मीद कर रहे थे",
            "वास्तव में क्या परिणाम मिला",
        ],
        "bring_career": [
            "आपकी लक्षित भूमिका और तैयारी की समय-सीमा",
            "वे विषय या अवधारणाएँ जिनमें आपको सबसे अधिक संदेह है",
            "साक्षात्कार और उद्योग के अनुभवों से संबंधित प्रश्न",
        ],
        "misconception": "यह क्वेरी `{query}` अलग परिणाम क्यों देती है?",
        "prerequisite": "क्या हम जाँच सकते हैं कि क्या मैं {name} को सही से समझता हूँ? मुझे लगता है कि यह मुझे रोक रहा है।",
        "concept": "{name} को समझने के लिए सबसे अच्छा तरीका क्या है?",
        "career_1": "साक्षात्कारकर्ता जूनियर बैकएंड डेवलपर्स के बुनियादी ज्ञान का मूल्यांकन कैसे करते हैं?",
        "career_2": "बैकएंड डेवलपर के पोर्टफोलियो में कौन से प्रोजेक्ट सबसे अधिक प्रभाव डालते हैं?",
        "career_3": "सीखने से लेकर वास्तविक सॉफ्टवेयर विकास तक पहुँचने के लिए कौन सी आदतें उपयोगी हैं?",
        "goal": "यदि आप मेरी स्थिति में होते तो आगे किस चीज़ पर ध्यान केंद्रित करते?",
        "icebreaker_tech": "नमस्ते {mentor}, मैं {learner} हूँ — मैं {concept} का अभ्यास कर रहा हूँ और मुझे अपनी क्वेरी में कुछ कठिनाई आ रही है।",
        "icebreaker_career": "नमस्ते {mentor}, मैं {learner} हूँ — मैं बैकएंड भूमिकाओं की तैयारी कर रहा हूँ और मार्गदर्शन चाहता हूँ।",
    },
}


def _build_prep_payload(db: Session, learner: Learner, case: MentorCase, lang: str) -> dict[str, Any]:
    c = get_content()
    tmpl = TEMPLATES.get(lang) or TEMPLATES["english"]
    mentor = adapters.mentors().get(db, case.mentor_id) if case.mentor_id else None
    mentor_first = mentor.name.split()[0] if mentor and mentor.name else "Mentor"
    learner_first = learner.name.split()[0] if learner.name else "Learner"

    concept_id = case.concept_id
    concept_name = c.concepts[concept_id].name if concept_id and concept_id in c.concepts else None

    # 1. What to bring
    if case.category == "career" or not concept_id:
        bring = list(tmpl["bring_career"])
    else:
        bring = list(tmpl["bring_technical"])

    # 2. Questions (3 to 5 grounded items)
    questions: list[dict[str, Any]] = []

    if case.category == "career" or not concept_id:
        questions.append({"text": tmpl["career_1"], "from": "career"})
        questions.append({"text": tmpl["career_2"], "from": "career"})
        questions.append({"text": tmpl["career_3"], "from": "career"})
        questions.append({"text": tmpl["goal"], "from": "goal"})
    else:
        # Technical questions from misconceptions in report
        rep_mis = (case.report or {}).get("misconceptions", [])
        for m_info in rep_mis:
            m_name = m_info.get("name")
            matched_m = next((m for m in c.misconceptions.values() if m.get("name") == m_name or m.get("id") == m_name), None)
            if matched_m and matched_m.get("counter_example"):
                ce_query = matched_m["counter_example"].get("query", "")
                q_text = tmpl["misconception"].format(query=ce_query)
                questions.append({
                    "text": q_text,
                    "from": "misconception",
                    "hidden_answer": matched_m["counter_example"].get("explanation", ""),
                })
            if len(questions) >= 2:
                break

        # Prerequisite questions from report
        rep_prereqs = (case.report or {}).get("prerequisite_state", [])
        for p_info in rep_prereqs:
            p_name = p_info.get("concept")
            if p_name:
                q_text = tmpl["prerequisite"].format(name=p_name)
                questions.append({"text": q_text, "from": "prerequisite"})
            if len(questions) >= 3:
                break

        # Concept grounding question if needed
        if concept_name and len(questions) < 3:
            questions.append({
                "text": tmpl["concept"].format(name=concept_name),
                "from": "concept",
            })

        # Goal question
        questions.append({"text": tmpl["goal"], "from": "goal"})

    # Ensure 3–5 items
    questions = questions[:5]

    # 3. Icebreaker
    if case.category == "career" or not concept_id:
        icebreaker = tmpl["icebreaker_career"].format(mentor=mentor_first, learner=learner_first)
    else:
        icebreaker = tmpl["icebreaker_tech"].format(
            mentor=mentor_first, learner=learner_first, concept=concept_name or "this topic"
        )

    return {
        "bring": bring,
        "questions": questions,
        "icebreaker": icebreaker,
        "mentor_sees": case.report or {},
        "language": lang,
    }


def learner_prep(db: Session, learner: Learner, case: MentorCase, lang: Optional[str] = None) -> dict[str, Any]:
    """Generates and caches prep notes for a scheduled/accepted mentor session."""
    target_lang = (lang or learner.language_pref or "english").lower()
    if target_lang not in ("english", "hinglish", "hindi"):
        target_lang = "english"

    note = db.scalars(
        select(CaseNote).where(CaseNote.case_id == case.id, CaseNote.kind == "learner_prep")
    ).first()

    if note and isinstance(note.body, dict) and "versions" in note.body:
        cached = note.body["versions"].get(target_lang)
        if cached:
            return cached

    # Generate for all three languages so language toggle is instant
    versions = {
        l: _build_prep_payload(db, learner, case, l)
        for l in ("english", "hinglish", "hindi")
    }

    if note:
        note.body = {"versions": versions}
    else:
        note = CaseNote(
            case_id=case.id,
            learner_id=learner.id,
            kind="learner_prep",
            body={"versions": versions},
        )
        db.add(note)
    db.flush()

    return versions[target_lang]


def session_summary(db: Session, learner: Learner, case: MentorCase) -> dict[str, Any]:
    """Builds and caches post-session summary with verbatim mentor notes and dated follow-up."""
    c = get_content()
    mentor = adapters.mentors().get(db, case.mentor_id) if case.mentor_id else None
    mentor_name = mentor.name if mentor else "Mentor"

    outcome = case.outcome or {}
    notes = outcome.get("notes", "")
    next_step = outcome.get("next_step", "")
    mentor_said = {"notes": notes, "next_step": next_step, "by": mentor_name}

    concept_id = case.concept_id
    concept_name = c.concepts[concept_id].name if concept_id and concept_id in c.concepts else (case.category.capitalize() if case.category else "Your Goal")
    p_before = case.p_at_open
    p_after = None
    ev_list: list[dict[str, Any]] = []

    if concept_id and concept_id in c.concepts:
        cs = db.scalars(
            select(ConceptState).where(ConceptState.learner_id == learner.id, ConceptState.concept_id == concept_id)
        ).first()
        p_after = round(cs.p_known, 3) if cs else (round(p_before, 3) if p_before is not None else None)
        events = list(db.scalars(
            select(EvidenceEvent)
            .where(EvidenceEvent.learner_id == learner.id, EvidenceEvent.concept_id == concept_id)
            .order_by(EvidenceEvent.created_at.desc())
            .limit(6)
        ))
        ev_list = [
            {"source": e.source_type, "score": e.score, "at": e.created_at.isoformat(timespec="minutes")}
            for e in reversed(events)
        ]

    saarthi_saw = {
        "concept": concept_name,
        "concept_id": concept_id,
        "p_before": round(p_before, 3) if p_before is not None else None,
        "p_after": p_after,
        "evidence": ev_list,
    }

    due_at = (case.followup or {}).get("due_at")
    if not due_at:
        due_at = (mastery.learner_now(learner) + timedelta(days=3)).date().isoformat()
    task = f"3-question check on {concept_name}" if concept_id else "Check-in on next steps"
    followup = {"due": due_at, "task": task}

    summary = {
        "mentor_said": mentor_said,
        "saarthi_saw": saarthi_saw,
        "followup": followup,
    }

    # Store or refresh in case_notes
    note = db.scalars(
        select(CaseNote).where(CaseNote.case_id == case.id, CaseNote.kind == "session_summary")
    ).first()
    if note:
        note.body = summary
    else:
        note = CaseNote(case_id=case.id, learner_id=learner.id, kind="session_summary", body=summary)
        db.add(note)
    db.flush()

    return summary
