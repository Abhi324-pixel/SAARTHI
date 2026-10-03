"""Explain-back assessment ("Don't answer me — teach it back to me") and interview mode.

Grading is a checklist-and-quote process with deterministic post-processing:
  * the model must quote the learner's own words for every item it marks covered
  * quotes are VERIFIED against the transcript; unverifiable credit is removed
  * the score is the weighted share of verified checklist items — the model never outputs a score
  * a clearly-stated misconception caps the score and goes to a READ-BACK before it becomes a flag
  * if the model is unavailable we FAIL CLOSED: no score, no evidence, a plain message
"""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..content import get_content
from ..llm import gateway, tasks
from ..models import Learner, LearningSession, TranscriptTurn
from . import mastery, misconception

MIN_WORDS = 6
MAX_TURNS = 3
MISCONCEPTION_SCORE_CAP = 0.6


# ---------------------------------------------------------------------------------------------------
# verification helpers
# ---------------------------------------------------------------------------------------------------

def _norm_tokens(s: str) -> list[str]:
    return re.findall(r"[\w']+", s.lower(), flags=re.UNICODE)


def quote_is_grounded(quote: str, transcript: str, min_ratio: float = 0.8) -> bool:
    """A quote counts if (almost) all its words occur in the learner's transcript."""
    qt = _norm_tokens(quote)
    if not qt:
        return False
    tt = set(_norm_tokens(transcript))
    hit = sum(1 for w in qt if w in tt)
    return hit / len(qt) >= min_ratio


def score_from_coverage(covered_ids: set[str], rubric: dict) -> float:
    total = sum(i["weight"] for i in rubric["checklist"])
    got = sum(i["weight"] for i in rubric["checklist"] if i["id"] in covered_ids)
    return round(got / total, 3) if total else 0.0


def evaluate_turn(concept_id: str, transcript: str, language: str, already_covered: set[str]) -> dict[str, Any]:
    """Run the model, verify its quotes, return verified coverage. Raises gateway.LLMUnavailable."""
    c = get_content()
    rub = c.rubrics[concept_id]
    words = _norm_tokens(transcript)
    if len(words) < MIN_WORDS:
        return {"insufficient": True, "covered": {}, "misconceptions": [], "grader_confidence": 0.0,
                "followup": None, "ungrounded": 0, "model": None}
    raw = tasks.score_explain_back(concept_id, transcript, language, sorted(already_covered))
    valid_ids = {i["id"] for i in rub["checklist"]}
    covered: dict[str, str] = {}
    ungrounded = 0
    for it in raw.get("checklist", []):
        if it.get("id") in valid_ids and it.get("covered") and it["id"] not in already_covered:
            if quote_is_grounded(it.get("evidence", ""), transcript):
                covered[it["id"]] = it["evidence"]
            else:
                ungrounded += 1
    mis: list[dict[str, str]] = []
    for it in raw.get("misconceptions", []):
        mid = it.get("id")
        if mid in rub.get("misconception_ids", []) and quote_is_grounded(it.get("evidence", ""), transcript, 0.8):
            mis.append({"id": mid, "evidence": it["evidence"]})
    conf = float(raw.get("grader_confidence", 0.5) or 0.0)
    conf = max(0.0, min(1.0, conf))
    if len(words) < 12:
        conf *= 0.7
    n_items = max(len(raw.get("checklist", [])), 1)
    conf *= (1 - 0.4 * (ungrounded / n_items))
    return {"insufficient": False, "covered": covered, "misconceptions": mis, "grader_confidence": round(conf, 3),
            "followup": raw.get("followup_question"), "ungrounded": ungrounded, "model": raw.get("_model", settings.model)}


# ---------------------------------------------------------------------------------------------------
# single-concept explain-back sessions
# ---------------------------------------------------------------------------------------------------

def _prompt_for(concept_id: str, language: str, seen: Optional[list[str]] = None) -> str:
    rub = get_content().rubrics[concept_id]
    is_hi = language in ("hindi", "hinglish")
    if is_hi and rub.get("prompts_hi"):
        options = rub["prompts_hi"]
    elif rub.get("prompts"):
        options = rub["prompts"]
    elif is_hi and rub.get("prompt_hi"):
        options = [rub["prompt_hi"]]
    else:
        options = [rub["prompt"]]

    if seen:
        unseen = [p for p in options if not any(p in s or s in p for s in seen)]
        if unseen:
            return unseen[0]
        return options[len(seen) % len(options)]
    return options[0]


def start(db: Session, learner: Learner, concept_id: str, channel: str = "text") -> dict[str, Any]:
    c = get_content()
    if not c.has_rubric(concept_id):
        raise KeyError(f"no explain-back rubric for {concept_id}")
    sess = LearningSession(learner_id=learner.id, mode="explain_back", concept_id=concept_id, channel=channel,
                           state={"covered": {}, "turns": 0, "misconceptions": {}, "conf": [], "finalized": False,
                                  "stated_confidence": None})
    db.add(sess)
    db.flush()
    prompt = _prompt_for(concept_id, learner.language_pref)
    db.add(TranscriptTurn(session_id=sess.id, role="mentor_ai", text=prompt))
    return {"session_id": sess.id, "concept_id": concept_id, "concept_name": c.concepts[concept_id].name,
            "prompt": prompt, "checklist_size": len(c.rubrics[concept_id]["checklist"]), "max_turns": MAX_TURNS}


def answer(db: Session, learner: Learner, session_id: str, text: str, *, stated_confidence: Optional[int] = None,
           audio_seconds: Optional[float] = None, channel: Optional[str] = None,
           speech: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    sess = db.get(LearningSession, session_id)
    if sess is None or sess.learner_id != learner.id or sess.mode != "explain_back":
        raise KeyError(session_id)
    return _answer_core(db, learner, sess, text, stated_confidence, audio_seconds, channel, speech=speech)


def _answer_core(db: Session, learner: Learner, sess: LearningSession, text: str, stated_confidence: Optional[int],
                 audio_seconds: Optional[float], channel: Optional[str], max_turns: int = MAX_TURNS,
                 speech: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    c = get_content()
    cid = sess.concept_id
    rub = c.rubrics[cid]
    st = dict(sess.state)
    if st.get("finalized"):
        return {"done": True, "finalized": True, "message": "This explanation is already scored.", **_summary(sess, rub)}
    meta: dict[str, Any] = {"audio_seconds": audio_seconds, "channel": channel or sess.channel}
    if speech:
        meta["speech"] = speech
    db.add(TranscriptTurn(session_id=sess.id, role="learner", text=text, meta=meta))
    try:
        ev = evaluate_turn(cid, text, learner.language_pref, set(st["covered"]))
    except gateway.LLMUnavailable as exc:
        return {"done": False, "unavailable": True,
                "message": "The grading model is not reachable right now, so I can't score this. "
                           "Nothing was recorded. Try again in a moment, or practise with the SQL tasks instead.",
                "detail": str(exc)[:160], **_summary(sess, rub)}
    if ev["insufficient"]:
        reply = ("Thoda aur batayein — kam se kam ek-do poore vaakya." if learner.language_pref != "english"
                 else "Could you say a bit more? A couple of full sentences will let me understand your thinking.")
        return {"done": False, "insufficient": True, "message": reply, **_summary(sess, rub)}

    st["turns"] = int(st.get("turns", 0)) + 1
    st["covered"] = {**st["covered"], **ev["covered"]}
    st["conf"] = [*st.get("conf", []), ev["grader_confidence"]]
    if stated_confidence:
        st["stated_confidence"] = stated_confidence
    readback = None
    for m in ev["misconceptions"]:
        if m["id"] in st["misconceptions"]:
            continue
        statement = m["evidence"].strip().strip('"')
        sig = misconception.register_signal(db, learner, m["id"], "explain_back", statement=statement)
        st["misconceptions"][m["id"]] = {"instance_id": sig["instance_id"], "quote": statement}
        if sig["needs_readback"]:
            readback = {"instance_id": sig["instance_id"], "misconception_id": m["id"],
                        "statement": statement, "name": c.misconceptions[m["id"]]["name"]}
    sess.state = st
    all_done = set(st["covered"]) >= {i["id"] for i in rub["checklist"]}
    done = all_done or st["turns"] >= max_turns
    missing = [i for i in rub["checklist"] if i["id"] not in st["covered"]]
    followup = None
    if not done:
        followup = ev["followup"] or (rub.get("followups") or [None])[0]
        if missing and not ev["followup"]:
            followup = f"Can you also explain: {missing[0]['text'].lower()}?"
        db.add(TranscriptTurn(session_id=sess.id, role="mentor_ai", text=followup or ""))
    result: dict[str, Any] = {
        "done": done, "turn": st["turns"], "followup": followup, "readback": readback,
        "grader_confidence": ev["grader_confidence"], "model": ev["model"], **_summary(sess, rub),
    }
    if done:
        result["final"] = finalize(db, learner, sess)
    return result


def _summary(sess: LearningSession, rub: dict) -> dict[str, Any]:
    cov = sess.state.get("covered", {})
    return {
        "session_id": sess.id, "concept_id": sess.concept_id,
        "checklist": [{"id": i["id"], "text": i["text"], "covered": i["id"] in cov, "evidence": cov.get(i["id"])}
                      for i in rub["checklist"]],
        "coverage": score_from_coverage(set(cov), rub),
    }


def finalize(db: Session, learner: Learner, sess: LearningSession) -> dict[str, Any]:
    c = get_content()
    rub = c.rubrics[sess.concept_id]
    st = dict(sess.state)
    if st.get("finalized"):
        return st.get("final", {})
    covered = set(st["covered"])
    score = score_from_coverage(covered, rub)
    mis_ids = list(st["misconceptions"])
    if mis_ids:
        score = min(score, MISCONCEPTION_SCORE_CAP)
    confs = st.get("conf") or [0.0]
    gconf = round(sum(confs) / len(confs), 3)
    res = mastery.apply_evidence(
        db, learner, sess.concept_id, "explain_back", score=score, item_id=sess.id,
        stated_confidence=st.get("stated_confidence"), grader=f"llm:{settings.model}:{gateway.PROMPT_VERSION}",
        grader_confidence=gconf,
        detail={"covered": sorted(covered), "misconceptions": mis_ids, "turns": st.get("turns")},
    )
    advanced = misconception.on_success(db, learner, sess.concept_id, "explain_back") if (score >= 0.7 and not mis_ids) else []
    st["finalized"] = True
    final = {
        "score": score, "grader_confidence": gconf, "mastery": res, "misconception_progress": advanced,
        "missed": [{"id": i["id"], "text": i["text"]} for i in rub["checklist"] if i["id"] not in covered],
        "covered": [{"id": i["id"], "text": i["text"], "evidence": st["covered"].get(i["id"])}
                    for i in rub["checklist"] if i["id"] in covered],
        "model_answer": rub["reference"],
        "note": ("Your score is capped because the explanation contained a misconception - see the read-back."
                 if mis_ids else None),
        "low_confidence": res["low_grader_confidence"],
    }
    st["final"] = final
    sess.state = st
    sess.status = "done"
    return final


# ---------------------------------------------------------------------------------------------------
# interview mode (coverage-driven, reuses the same scoring)
# ---------------------------------------------------------------------------------------------------

def _interview_candidates(db: Session, learner: Learner, role_id: str) -> list[str]:
    c = get_content()
    topics = [t for t in c.role(role_id)["interview_topics"] if c.has_rubric(t)]
    views = mastery.concept_views(db, learner)
    # least-evidenced and weakest first: coverage/uncertainty decides, not turn count
    return sorted(topics, key=lambda t: (views[t]["confidence"], views[t]["p"]))


def interview_start(db: Session, learner: Learner, n_topics: int = 4, channel: str = "text",
                    round: str = "technical", pack_id: Optional[str] = None) -> dict[str, Any]:
    c = get_content()
    role = c.role(learner.role_id or "backend_developer")

    if pack_id:
        pack = c.get_pack(pack_id)
        if not pack:
            raise KeyError(f"unknown interview pack: {pack_id}")
        if round == "behavioural" and "behavioural" in pack.get("rounds", {}):
            queue = list(pack["rounds"]["behavioural"]["concept_ids"])[:n_topics]
        else:
            queue = list(pack.get("concept_ids", []))[:n_topics]
    else:
        if round == "behavioural":
            beh_topics = ["comm_self_intro", "comm_star_story", "comm_project_walkthrough"]
            queue = [t for t in beh_topics if c.has_rubric(t)][:n_topics]
            if "comm_self_intro" in queue and queue[0] != "comm_self_intro":
                queue.remove("comm_self_intro")
                queue.insert(0, "comm_self_intro")
        elif round == "full":
            tech = [t for t in _interview_candidates(db, learner, role["id"]) if not t.startswith("comm_")]
            full_order = ["comm_self_intro", "comm_star_story"] + tech[:2] + ["comm_project_walkthrough"]
            queue = [t for t in full_order if c.has_rubric(t)][:n_topics]
        else:
            tech = [t for t in _interview_candidates(db, learner, role["id"]) if not t.startswith("comm_")]
            queue = tech[:n_topics]

    if not queue:
        raise KeyError("no interview topics")

    past_prompts = list(
        db.scalars(
            select(TranscriptTurn.text)
            .join(LearningSession, TranscriptTurn.session_id == LearningSession.id)
            .where(LearningSession.learner_id == learner.id, TranscriptTurn.role == "mentor_ai")
        )
    )

    q = _interview_question(queue[0], learner.language_pref, first=True, role_title=role["title"],
                            round_name=round, seen=past_prompts)
    sess = LearningSession(learner_id=learner.id, mode="interview", concept_id=queue[0], channel=channel,
                           state={"queue": queue, "idx": 0, "results": {}, "covered": {}, "turns": 0, "misconceptions": {},
                                  "conf": [], "finalized": False, "role_title": role["title"], "round": round,
                                  "pack_id": pack_id, "seen_prompts": past_prompts + [q]})
    db.add(sess)
    db.flush()
    db.add(TranscriptTurn(session_id=sess.id, role="mentor_ai", text=q))
    return {"session_id": sess.id, "role_title": role["title"], "round": round, "pack_id": pack_id,
            "topics": [c.concepts[t].name for t in queue], "question": q, "concept_id": queue[0],
            "index": 0, "total": len(queue)}


def _interview_question(concept_id: str, language: str, first: bool, role_title: str,
                        round_name: str = "technical", seen: Optional[list[str]] = None) -> str:
    base = _prompt_for(concept_id, language, seen=seen)
    if first:
        round_desc = "behavioural" if round_name == "behavioural" else "full mock" if round_name == "full" else "technical"
        return f"Welcome to your {role_title} mock interview ({round_desc} round). Let's begin. {base}"
    return f"Next question. {base}"


def interview_answer(db: Session, learner: Learner, session_id: str, text: str, *,
                     stated_confidence: Optional[int] = None,
                     audio_seconds: Optional[float] = None,
                     channel: Optional[str] = None,
                     speech: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    sess = db.get(LearningSession, session_id)
    if sess is None or sess.learner_id != learner.id or sess.mode != "interview":
        raise KeyError(session_id)
    st = dict(sess.state)
    c = get_content()
    cid = st["queue"][st["idx"]]
    sess.concept_id = cid
    # run the same per-concept pipeline on a sub-state
    sub = LearningSession(learner_id=learner.id, mode="explain_back", concept_id=cid, channel=sess.channel,
                          state={"covered": st["covered"], "turns": st["turns"], "misconceptions": st["misconceptions"],
                                 "conf": st["conf"], "finalized": False, "stated_confidence": stated_confidence})
    sub.id = sess.id  # share transcript
    out = _answer_core(db, learner, sub, text, stated_confidence, audio_seconds, channel, speech=speech, max_turns=2)
    if out.get("unavailable") or out.get("insufficient"):
        return {**out, "interview": True, "index": st["idx"], "total": len(st["queue"])}
    sess_state_after = dict(sub.state)
    st["covered"], st["turns"], st["misconceptions"], st["conf"] = (sess_state_after["covered"], sess_state_after["turns"],
                                                                      sess_state_after["misconceptions"], sess_state_after["conf"])
    resp: dict[str, Any] = {"interview": True, "index": st["idx"], "total": len(st["queue"]), "readback": out.get("readback"),
                            "checklist": out["checklist"], "concept_id": cid}
    if out["done"]:
        final = out["final"]
        kind = "behavioural" if cid.startswith("comm_") else "technical"
        st["results"][cid] = {"score": final["score"], "covered": final["covered"], "missed": final["missed"],
                              "p_before": final["mastery"]["p_before"], "p_after": final["mastery"]["p_after"],
                              "level_after": final["mastery"]["level_after"], "model_answer": final["model_answer"],
                              "misconceptions": list(st["misconceptions"]), "name": c.concepts[cid].name,
                              "kind": kind}
        st["idx"] += 1
        st["covered"], st["turns"], st["misconceptions"], st["conf"] = {}, 0, {}, []
        if st["idx"] >= len(st["queue"]):
            st["finalized"] = True
            sess.status = "done"
            sess.state = st
            resp.update({"done": True, "report": interview_report(db, learner, sess)})
            return resp
        nxt = st["queue"][st["idx"]]
        seen = st.get("seen_prompts", [])
        q = _interview_question(nxt, learner.language_pref, first=False, role_title=st["role_title"],
                                round_name=st.get("round", "technical"), seen=seen)
        st.setdefault("seen_prompts", []).append(q)
        db.add(TranscriptTurn(session_id=sess.id, role="mentor_ai", text=q))
        resp.update({"done": False, "next_question": q, "next_concept_id": nxt, "index": st["idx"],
                     "previous": st["results"][cid]})
    else:
        resp.update({"done": False, "followup": out.get("followup")})
    sess.state = st
    return resp


def interview_report(db: Session, learner: Learner, sess: LearningSession) -> dict[str, Any]:
    st = sess.state
    res = st["results"]
    n_items = sum(len(r["covered"]) + len(r["missed"]) for r in res.values())
    n_cov = sum(len(r["covered"]) for r in res.values())
    strong = [r["name"] for r in res.values() if r["score"] >= 0.75]
    weak = [r["name"] for r in res.values() if r["score"] < 0.5]
    
    topics_out = []
    for cid, r in res.items():
        kind = r.get("kind", "behavioural" if cid.startswith("comm_") else "technical")
        topics_out.append({"concept_id": cid, "kind": kind, **r})

    next_steps = [f"Revisit {w} in your roadmap" for w in weak[:3]]
    if any(cid == "comm_star_story" and res[cid]["score"] < 0.5 for cid in res):
        if "Revisit STAR stories in your roadmap" not in next_steps:
            next_steps.insert(0, "Revisit STAR stories in your roadmap")

    rep: dict[str, Any] = {
        "role_title": st["role_title"],
        "round": st.get("round", "technical"),
        "pack_id": st.get("pack_id"),
        "topics": topics_out,
        "checklist_items_covered": n_cov, "checklist_items_total": n_items,
        "strengths": strong, "needs_work": weak,
        "next_steps": next_steps,
        "note": "Scores come from verified quotes against a per-concept checklist - not from a generic interview rating.",
    }

    beh_topics = [t for t in topics_out if t.get("kind") == "behavioural"]
    if beh_topics:
        rep["behavioural_summary"] = {
            "topics_assessed": len(beh_topics),
            "items_covered": sum(len(t["covered"]) for t in beh_topics),
            "items_total": sum(len(t["covered"]) + len(t["missed"]) for t in beh_topics),
        }

    # Speech summary across spoken turns (T11)
    turns = list(db.scalars(select(TranscriptTurn).where(TranscriptTurn.session_id == sess.id, TranscriptTurn.role == "learner")))
    speech_turns = [t.meta.get("speech") for t in turns if t.meta and t.meta.get("speech")]
    if speech_turns:
        import statistics
        from collections import Counter
        wpms = [s["wpm"] for s in speech_turns if s.get("wpm") is not None]
        median_wpm = round(float(statistics.median(wpms)), 1) if wpms else None
        marker_counts: Counter[str] = Counter()
        for s in speech_turns:
            marker_counts.update(s.get("markers", {}))
        top_markers = [{"marker": m, "count": c} for m, c in marker_counts.most_common(5)]
        tips = list(dict.fromkeys(tip for s in speech_turns for tip in s.get("tips", [])))
        rep["speech"] = {
            "answers_with_audio": len(speech_turns),
            "median_wpm": median_wpm,
            "top_markers": top_markers,
            "tips": tips,
        }

    return rep
