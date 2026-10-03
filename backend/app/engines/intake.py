"""T01 — Free-text goal and conversational intake engine.

Parses unstructured learner statements into structured constraints and self-reported skills,
snaps free-text skill claims to verified concept IDs using aliases and ambiguity rules,
and applies the confirmed intake profile to the learner twin.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..content import get_content
from ..llm import tasks
from ..models import Learner, LearningSession, TranscriptTurn
from . import mastery, planner

FILLER_WORDS = {
    "and", "the", "a", "an", "i", "know", "have", "some", "with", "in", "basics",
    "of", "experience", "concepts", "good", "knowledge", "skill", "skills",
    "aata", "hai", "mujhe", "thoda", "bahut", "basic", "already", "well",
    "done", "about", "to", "my", "me", "am", "learning", "understand",
}

LEVEL_WORDS_MAP = {
    "novice": 1,
    "elementary": 2,
    "basic": 2,
    "basics": 2,
    "thoda": 2,
    "beginner": 2,
    "some": 3,
    "intermediate": 3,
    "decent": 3,
    "practical": 3,
    "familiar": 3,
    "good": 3,
    "strong": 4,
    "advanced": 4,
    "proficient": 4,
    "bahut": 4,
    "expert": 5,
    "master": 5,
}


def rating_for(level_word: Optional[str]) -> int:
    """Map a level word to a 1..5 rating; default is 3."""
    if not level_word:
        return 3
    lw = level_word.strip().lower()
    return LEVEL_WORDS_MAP.get(lw, 3)


def snap_skills(phrases: list[dict[str, Any] | str]) -> list[dict[str, Any]]:
    """Port of TESSA's snap() / _match() onto SAARTHI concepts.

    Matches against Concept.name, name_hi, and Concept.aliases.
    Strips level words and filler words.
    Ambiguity rule: if a phrase matches >= 2 concepts, return none for that phrase.
    """
    content = get_content()
    snapped: list[dict[str, Any]] = []
    seen_concepts: set[str] = set()

    for item in phrases:
        if isinstance(item, dict):
            raw_phrase = item.get("phrase", "")
            level_word = item.get("level_word")
        else:
            raw_phrase = str(item)
            level_word = None

        if not raw_phrase or not raw_phrase.strip():
            continue

        raw_lower = raw_phrase.strip().lower()

        # Check if level word is embedded in phrase if not passed explicitly
        if not level_word:
            for lw in LEVEL_WORDS_MAP:
                if re.search(rf"\b{re.escape(lw)}\b", raw_lower):
                    level_word = lw
                    break

        tokens = re.findall(r"[a-z0-9_]+", raw_lower)
        meaningful = [t for t in tokens if t not in FILLER_WORDS]
        if not meaningful:
            # Phrase was entirely filler words
            continue

        cleaned_phrase = " ".join(meaningful)
        stem = re.sub(r"s$", "", cleaned_phrase) if len(cleaned_phrase) > 3 else cleaned_phrase

        # Phase 1: Exact matches (exact alias, exact concept id, or exact name)
        exact_matches: set[str] = set()
        for cid, concept in content.concepts.items():
            c_name = concept.name.lower()
            c_name_hi = concept.name_hi.lower()
            c_aliases = [a.lower() for a in getattr(concept, "aliases", [])]

            if cid.lower() in (cleaned_phrase, stem):
                exact_matches.add(cid)
            elif any(a in (cleaned_phrase, stem) for a in c_aliases):
                exact_matches.add(cid)
            elif any(n in (cleaned_phrase, stem) for n in (c_name, c_name_hi)):
                exact_matches.add(cid)

        if len(exact_matches) == 1:
            matched_cid = list(exact_matches)[0]
            if matched_cid not in seen_concepts:
                seen_concepts.add(matched_cid)
                rating = rating_for(level_word)
                snapped.append({
                    "concept_id": matched_cid,
                    "concept_name": content.concepts[matched_cid].name,
                    "rating": rating,
                    "phrase": raw_phrase,
                })
            continue

        if len(exact_matches) >= 2:
            # Ambiguous exact match -> return none
            continue

        # Phase 2: Containment / partial matches
        partial_matches: set[str] = set()
        for cid, concept in content.concepts.items():
            c_name = concept.name.lower()
            c_aliases = [a.lower() for a in getattr(concept, "aliases", [])]

            for query_term in (cleaned_phrase, stem):
                for a in c_aliases:
                    if (
                        re.search(rf"\b{re.escape(query_term)}\b", a)
                        or re.search(rf"\b{re.escape(a)}\b", query_term)
                    ):
                        partial_matches.add(cid)
                        break

                if (
                    re.search(rf"\b{re.escape(query_term)}\b", c_name)
                    or re.search(rf"\b{re.escape(c_name)}\b", query_term)
                ):
                    partial_matches.add(cid)

        # Ambiguity rule: if phrase matches >= 2 concepts, return none (do not guess)
        if len(partial_matches) == 1:
            matched_cid = list(partial_matches)[0]
            if matched_cid not in seen_concepts:
                seen_concepts.add(matched_cid)
                rating = rating_for(level_word)
                snapped.append({
                    "concept_id": matched_cid,
                    "concept_name": content.concepts[matched_cid].name,
                    "rating": rating,
                    "phrase": raw_phrase,
                })

    return snapped


def extract(
    db: Session,
    learner: Learner,
    message: str,
    history: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Call extract_intake task, validate roles, clamp constraints, and snap skills."""
    content = get_content()

    raw = tasks.extract_intake(
        message=message,
        history=history,
        language=learner.language_pref or "english",
    )

    role_id = raw.get("role_id")
    unavailable_role = None

    if role_id:
        if role_id not in content.roles:
            role_id = None
        else:
            role_def = content.roles[role_id]
            if not role_def.get("available", True):
                unavailable_role = role_def["title"]
                settings = dict(learner.settings or {})
                settings["wanted_goal"] = role_id
                learner.settings = settings
                db.flush()
                # Do not silently substitute; clear role_id
                role_id = None

    weekly_hours = raw.get("weekly_hours")
    if weekly_hours is not None:
        weekly_hours = max(1.0, min(60.0, float(weekly_hours)))

    horizon_weeks = raw.get("horizon_weeks")
    if horizon_weeks is not None:
        horizon_weeks = max(2, min(52, int(horizon_weeks)))

    language = raw.get("language")
    if language not in ("english", "hindi", "hinglish"):
        language = None

    snapped = snap_skills(raw.get("known_skills", []))

    # Determine readiness
    ready = bool(
        raw.get("goal_text")
        and not unavailable_role
        and (role_id or weekly_hours or snapped)
    )

    understood = {
        "goal_text": raw.get("goal_text") or message.strip(),
        "role_id": role_id,
        "role_title": content.roles[role_id]["title"] if role_id and role_id in content.roles else None,
        "weekly_hours": weekly_hours,
        "horizon_weeks": horizon_weeks,
        "language": language,
        "known_skills": snapped,
        "confidence": float(raw.get("confidence", 0.6)),
    }

    return {
        "understood": understood,
        "follow_up": raw.get("follow_up_question"),
        "ready": ready,
        "unavailable_role": unavailable_role,
    }


def apply(db: Session, learner: Learner, draft: dict[str, Any]) -> dict[str, Any]:
    """Apply the confirmed intake draft to the learner twin, record self-report evidence, and refresh roadmap."""
    content = get_content()
    understood = draft.get("understood", draft)

    role_id = understood.get("role_id")
    if role_id and role_id in content.roles and content.roles[role_id].get("available", True):
        learner.role_id = role_id

    if understood.get("weekly_hours") is not None:
        learner.weekly_hours = max(1.0, min(60.0, float(understood["weekly_hours"])))

    if understood.get("horizon_weeks") is not None:
        learner.horizon_weeks = max(2, min(52, int(understood["horizon_weeks"])))

    if understood.get("language") in ("english", "hindi", "hinglish"):
        learner.language_pref = understood["language"]

    # Record self-report evidence for claimed skills
    known_skills = understood.get("known_skills", [])
    for s in known_skills:
        cid = s.get("concept_id")
        if cid and cid in content.concepts:
            rating = s.get("rating", 3)
            mastery.apply_evidence(
                db,
                learner,
                concept_id=cid,
                source_type="self_report",
                score=rating / 5.0,
                grader="intake",
                detail={"phrase": s.get("phrase", ""), "rating": rating},
            )

    # Save intake session and transcript
    session = LearningSession(
        learner_id=learner.id,
        mode="intake",
        channel="text",
        status="completed",
        state={"draft": understood},
    )
    db.add(session)
    db.flush()

    turn = TranscriptTurn(
        session_id=session.id,
        role="learner",
        text=understood.get("goal_text", ""),
        meta={"understood": understood},
    )
    db.add(turn)

    learner.onboarded = True
    mastery.ensure_states(db, learner)
    rm = planner.refresh(db, learner, "your goals")

    # Clear pending draft from settings
    settings = dict(learner.settings or {})
    if "intake_draft" in settings:
        del settings["intake_draft"]
        learner.settings = settings

    db.flush()

    from ..routes.core import _me
    return {
        "me": _me(db, learner),
        "roadmap": {
            "version": rm["version"],
            "summary": rm["summary"],
        },
    }
