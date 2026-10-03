"""Backend of the ElevenLabs agent's client tools (and reusable by any text front-end).

The voice agent never grades or decides: it calls these tools, which run the same engines as the text UI.
Every result carries a compact `say` (what to tell the learner) and a `ui` block (what the screen should show).
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from . import adapters
from .content import get_content
from .engines import escalation, explainback, hooks, mastery, misconception, planner, strategy
from .engines import resume as resume_engine, video_interview
from .models import Learner, LearningSession, TranscriptTurn

PANELS = {"join_diagram", "sql_task", "roadmap", "dashboard", "concept"}
MODES = {"diagnosis", "teach", "explain_back", "interview", "review", "free"}


def start_voice_session(db: Session, lr: Learner, mode: str, concept_id: Optional[str], use_resume: bool = False) -> LearningSession:
    mode = mode if mode in MODES else "free"
    sess = LearningSession(learner_id=lr.id, mode="voice", concept_id=concept_id, channel="voice",
                           state={"mode": mode, "concept_id": concept_id, "eb_session_id": None, "interview_session_id": None,
                                  "taught": [], "use_resume": bool(use_resume and mode == "interview"), "vi_session_id": None})
    db.add(sess)
    db.flush()
    return sess


def dynamic_variables(db: Session, lr: Learner, mode: str, concept_id: Optional[str], use_resume: bool = False) -> dict[str, str]:
    c = get_content()
    views = mastery.concept_views(db, lr)
    cid = concept_id or _pick_concept(db, lr, {"mode": mode, "concept_id": None}, views)
    v = views[cid]
    mis = misconception.describe(db, lr.id)
    bits = [f"{c.concepts[cid].name}: {v['level'].replace('_', ' ')} ({int(v['p']*100)}%)"]
    if mis:
        bits.append(f"active misconception: {mis[0]['name']}")
    if v["flags"]:
        bits.append("flags: " + ", ".join(v["flags"]))
    if use_resume and mode == "interview":
        rs = resume_engine.load(db, lr)
        if rs:    # only what the learner chose to share, and only the short summary (never the file)
            bits.append("resume skills: " + ", ".join(rs.get("skills", [])[:10]) + "; projects: " + ", ".join(p["name"] for p in rs.get("projects", [])[:3]))
    return {
        "learner_name": lr.name.split()[0] if lr.name else "there", "language_pref": lr.language_pref,
        "goal": c.role(lr.role_id or "backend_developer")["title"], "current_concept": cid,
        "current_concept_name": c.concepts[cid].name, "session_mode": mode if mode in MODES else "free",
        "learner_summary": "; ".join(bits),
    }


def _pick_concept(db: Session, lr: Learner, state: dict, views: Optional[dict] = None) -> str:
    c = get_content()
    views = views or mastery.concept_views(db, lr)
    if state.get("concept_id") and state["concept_id"] in c.concepts:
        cid = state["concept_id"]
    else:
        mis = misconception.describe(db, lr.id)
        if mis:
            cid = mis[0]["concept_id"]
        else:
            rm = planner.current(db, lr)
            cid = next((i["concept_id"] for i in rm["items"] if i["status"] != "done" and c.has_rubric(i["concept_id"])), None)
            if cid is None:
                cid = next(iter(c.role(lr.role_id or "backend_developer")["interview_topics"]))
    if not c.has_rubric(cid):
        # fall back to the nearest concept that has an explain-back rubric (itself's ancestors first, then dependents)
        cand = [a for a in c.topo_order(c.ancestors(cid)) if c.has_rubric(a)][::-1] + [d for d in c.dependents(cid) if c.has_rubric(d)]
        cid = cand[0] if cand else next(iter(c.rubrics))
    return cid


def _log(db: Session, voice_session: LearningSession, role: str, text: str) -> None:
    db.add(TranscriptTurn(session_id=voice_session.id, role=role, text=text[:1500]))


def _state(vs: LearningSession) -> dict:
    return dict(vs.state)


def _save(vs: LearningSession, st: dict) -> None:
    vs.state = st


def dispatch(db: Session, lr: Learner, tool: str, args: dict[str, Any], voice_session_id: Optional[str]) -> dict[str, Any]:
    vs = db.get(LearningSession, voice_session_id) if voice_session_id else None
    if vs is None or vs.learner_id != lr.id or vs.mode != "voice":
        vs = start_voice_session(db, lr, "free", None)
    fn = TOOLS.get(tool)
    if fn is None:
        return {"error": f"unknown tool '{tool}'", "say": "I can't do that."}
    return fn(db, lr, vs, args or {})


# ---------------------------------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------------------------------

def t_get_learner_context(db: Session, lr: Learner, vs: LearningSession, args: dict) -> dict[str, Any]:
    c = get_content()
    st = _state(vs)
    views = mastery.concept_views(db, lr)
    role = c.role(lr.role_id or "backend_developer")
    cid = _pick_concept(db, lr, st, views)
    v = views[cid]
    mis = misconception.describe(db, lr.id)
    mission = planner.today_mission(db, lr)
    return {
        "name": lr.name, "language": lr.language_pref, "goal": role["title"],
        "progress_percent": int(mastery.overall_mastery(views, role["requirements"]) * 100),
        "session_mode": st.get("mode"),
        "current_concept": {"id": cid, "name": c.concepts[cid].name, "level": v["level"], "percent": int(v["p"] * 100), "flags": v["flags"]},
        "active_misconception": ({"name": mis[0]["name"], "status": mis[0]["status"]} if mis else None),
        "todays_mission": [m["title"] for m in mission],
        "ui": {"panel": "concept", "concept_id": cid},
    }


def t_get_next_action(db: Session, lr: Learner, vs: LearningSession, args: dict) -> dict[str, Any]:
    c = get_content()
    st = _state(vs)
    mode = st.get("mode", "free")
    if mode == "interview":
        if st.get("use_resume") and not st.get("vi_session_id") and not st.get("interview_session_id"):
            try:     # questions written from the learner's resume; any problem falls back to the curated interview below
                iv = video_interview.start(db, lr, None, True)
                st["vi_session_id"] = iv["id"]
                _save(vs, st)
                _log(db, vs, "mentor_ai", iv["question"])
                return {"action": "interview_question", "say": iv["question"], "topics": [],
                        "instruction": "Ask this question as the interviewer. Do not give hints or feedback during the interview."}
            except video_interview.InterviewError:
                st["use_resume"] = False
                _save(vs, st)
        if st.get("vi_session_id"):
            return {"action": "continue_interview", "say": "Please continue with your answer.", "instruction": "Wait for the learner's answer, then call record_response."}
        if not st.get("interview_session_id"):
            out = explainback.interview_start(db, lr, n_topics=4, channel="voice")
            st["interview_session_id"] = out["session_id"]
            _save(vs, st)
            _log(db, vs, "mentor_ai", out["question"])
            return {"action": "interview_question", "say": out["question"], "topics": out["topics"],
                    "instruction": "Ask this question as the interviewer. Do not give hints or feedback during the interview.",
                    "ui": {"panel": "concept", "concept_id": out["concept_id"]}}
        return {"action": "continue_interview", "say": "Please continue with your answer.", "instruction": "Wait for the learner's answer, then call record_response."}
    cid = _pick_concept(db, lr, st)
    st["concept_id"] = cid
    views = mastery.concept_views(db, lr)
    v = views[cid]
    if mode == "teach" and cid not in st.get("taught", []) and v["p"] < 0.6:
        ex = strategy.explain(db, lr, cid)
        st["taught"] = [*st.get("taught", []), cid]
        _save(vs, st)
        _log(db, vs, "mentor_ai", ex["text"][:400])
        return {"action": "teach", "concept": c.concepts[cid].name, "say": ex["text"][:700], "strategy": ex["strategy_label"],
                "why": ex["why_strategy"], "instruction": "Explain this briefly in your own words, then invite the learner to teach it back.",
                "ui": {"panel": ex.get("visual") or "concept", "concept_id": cid}}
    eb_id = st.get("eb_session_id")
    sess = db.get(LearningSession, eb_id) if eb_id else None
    if sess is None or sess.status != "active" or sess.concept_id != cid:
        out = explainback.start(db, lr, cid, channel="voice")
        st["eb_session_id"] = out["session_id"]
        prompt = out["prompt"]
    else:
        prompt = "Please continue your explanation."
    _save(vs, st)
    _log(db, vs, "mentor_ai", prompt)
    mis = [m for m in misconception.describe(db, lr.id) if m["concept_id"] == cid]
    return {"action": "explain_back", "concept": c.concepts[cid].name, "say": "Don't answer me - teach it back to me. " + prompt,
            "why": ("A misconception is active here: " + mis[0]["name"]) if mis else f"You are at {int(v['p']*100)}% on this concept.",
            "instruction": "Say the signature line, ask the prompt, then listen without interrupting. After they finish call record_response.",
            "ui": {"panel": "concept", "concept_id": cid}}


def t_explain_topic(db: Session, lr: Learner, vs: LearningSession, args: dict) -> dict[str, Any]:
    c = get_content()
    cid = args.get("concept_id") or _state(vs).get("concept_id") or _pick_concept(db, lr, _state(vs))
    if cid not in c.concepts:
        return {"error": "unknown concept", "say": "I don't have notes on that."}
    ex = strategy.explain(db, lr, cid)
    _log(db, vs, "mentor_ai", ex["text"][:400])
    return {"concept": ex["concept_name"], "strategy": ex["strategy_label"], "text": ex["text"][:800], "key_points": ex["key_points"][:3],
            "ui": {"panel": ex.get("visual") or "concept", "concept_id": cid}}


def _format_final(final: dict, after: dict, concept_name: str) -> str:
    cov, missed = final["covered"], final["missed"]
    total = len(cov) + len(missed)
    line = f"You covered {len(cov)} of {total} key points on {concept_name}."
    if missed:
        line += " Still missing: " + "; ".join(m["text"].lower() for m in missed[:2]) + "."
    if final.get("note"):
        line += " " + final["note"]
    rm = after["roadmap"]
    if rm["changed"]:
        line += " I've updated your roadmap: " + rm["change_reason"]
    return line


def t_record_response(db: Session, lr: Learner, vs: LearningSession, args: dict) -> dict[str, Any]:
    c = get_content()
    text = (args.get("text") or "").strip()
    if not text:
        return {"say": "I didn't catch that. Could you say it again?", "done": False}
    st = _state(vs)
    sc = args.get("stated_confidence")
    sc = int(sc) if isinstance(sc, (int, float)) and 1 <= int(sc) <= 5 else None
    _log(db, vs, "learner", text)
    if st.get("mode") == "interview" and st.get("vi_session_id"):
        try:
            r = video_interview.answer(db, lr, st["vi_session_id"], text)
        except video_interview.InterviewError as e:
            return {"say": e.message, "done": False}
        if r["done"]:
            rep = video_interview.finish(db, lr, st["vi_session_id"], None)
            wins = sum(len(t["feedback"].get("strengths", [])) for t in rep["turns"])
            gap = next((g for t in rep["turns"] for g in t["feedback"].get("gaps", [])), None)
            say = f"That's the end of the interview. I noted {wins} things you did well, each backed by your own words."
            if gap:
                say += f" One thing to work on: {gap}"
            say += " Your full written feedback is in the Video interview report list. This was practice, so it does not change your skill estimates."
            _log(db, vs, "mentor_ai", say)
            return {"say": say, "done": True}
        _log(db, vs, "mentor_ai", r["next_question"])
        return {"say": r["next_question"], "done": False}
    if st.get("mode") == "interview" and st.get("interview_session_id"):
        out = explainback.interview_answer(db, lr, st["interview_session_id"], text, stated_confidence=sc)
        if out.get("unavailable") or out.get("insufficient"):
            return {"say": out["message"], "done": False}
        ui = {"checklist": out.get("checklist"), "panel": "concept", "concept_id": out.get("concept_id")}
        if out.get("readback"):
            rb = out["readback"]
            return {"say": f"Just to be sure I understood: you said \"{rb['statement']}\". Is that right?", "done": False,
                    "readback": {"statement_id": rb["instance_id"], "statement": rb["statement"]}, "ui": ui}
        if out.get("done"):
            after = hooks.after_evidence(db, lr, out.get("concept_id"), "your interview")
            rep = out.get("report", {})
            return {"say": f"That's the end of the interview. You covered {rep.get('checklist_items_covered')} of "
                           f"{rep.get('checklist_items_total')} key points. Strong: {', '.join(rep.get('strengths', [])) or 'none yet'}. "
                           f"To work on: {', '.join(rep.get('needs_work', [])) or 'nothing major'}.",
                    "done": True, "ui": {**ui, "panel": "roadmap"}, "roadmap_change": after["roadmap"]}
        nxt = out.get("next_question") or out.get("followup") or "Please go on."
        _log(db, vs, "mentor_ai", nxt)
        return {"say": nxt, "done": False, "ui": ui}
    # explain-back
    cid = args.get("concept_id") or st.get("concept_id") or _pick_concept(db, lr, st)
    if cid not in c.concepts or not c.has_rubric(cid):
        cid = _pick_concept(db, lr, st)
    eb_id = st.get("eb_session_id")
    sess = db.get(LearningSession, eb_id) if eb_id else None
    if sess is None or sess.status != "active" or sess.concept_id != cid:
        out0 = explainback.start(db, lr, cid, channel="voice")
        st["eb_session_id"] = out0["session_id"]
        st["concept_id"] = cid
        _save(vs, st)
        eb_id = out0["session_id"]
    out = explainback.answer(db, lr, eb_id, text, stated_confidence=sc, channel="voice")
    ui = {"checklist": out.get("checklist"), "coverage": out.get("coverage"), "panel": "concept", "concept_id": cid}
    if out.get("unavailable") or out.get("insufficient"):
        return {"say": out["message"], "done": False, "ui": ui}
    if out.get("readback"):
        rb = out["readback"]
        return {"say": f"Just to be sure I understood: you said \"{rb['statement']}\". Is that right?", "done": False,
                "readback": {"statement_id": rb["instance_id"], "statement": rb["statement"]}, "ui": ui}
    if out["done"]:
        after = hooks.after_evidence(db, lr, cid, "your spoken explanation")
        say = _format_final(out["final"], after, c.concepts[cid].name)
        _log(db, vs, "mentor_ai", say)
        return {"say": say, "done": True, "score_percent": int(out["final"]["score"] * 100),
                "roadmap_change": after["roadmap"], "ui": {**ui, "panel": "roadmap"},
                "escalation_suggestions": after["escalation_suggestions"]}
    nxt = out.get("followup") or "Can you add an example?"
    _log(db, vs, "mentor_ai", nxt)
    return {"say": nxt, "done": False, "ui": ui}


def t_confirm_statement(db: Session, lr: Learner, vs: LearningSession, args: dict) -> dict[str, Any]:
    sid = args.get("statement_id")
    confirmed = bool(args.get("confirmed"))
    try:
        out = misconception.confirm_statement(db, lr, sid, confirmed)
    except KeyError:
        return {"say": "I can't find that statement.", "error": "unknown statement"}
    c = get_content()
    if out.get("status") == "confirmed":
        m = c.misconceptions[out["misconception_id"]]
        after = hooks.after_evidence(db, lr, m["concept_id"], "a confirmed misconception")
        return {"say": f"Thanks for confirming. A common mix-up here: {m['description']} {m['counter_example']['explanation']}",
                "status": "confirmed", "ui": {"panel": "join_diagram" if "join" in m["concept_id"] else "concept", "concept_id": m["concept_id"]},
                "roadmap_change": after["roadmap"]}
    return {"say": "Okay, thanks for clarifying - I won't count that.", "status": out.get("status"), "ui": {}}


def t_show_visual(db: Session, lr: Learner, vs: LearningSession, args: dict) -> dict[str, Any]:
    panel = args.get("panel")
    if panel not in PANELS:
        return {"error": "unknown panel", "say": "I can't show that."}
    return {"ok": True, "say": "It's on your screen.", "ui": {"panel": panel, "concept_id": args.get("concept_id") or _state(vs).get("concept_id")}}


def t_request_mentor(db: Session, lr: Learner, vs: LearningSession, args: dict) -> dict[str, Any]:
    reason = (args.get("reason") or "Learner asked for a mentor.")[:400]
    cat = args.get("category") if args.get("category") in ("technical", "career", "wellbeing") else escalation.classify_category(reason)
    if escalation.classify_category(reason) == "wellbeing":
        cat = "wellbeing"
    cid = _state(vs).get("concept_id") if cat == "technical" else None
    out = escalation.open_case(db, lr, category=cat, concept_id=cid, trigger="voice_request", reason=reason)
    say = out.get("message") or ""
    if out.get("mentor"):
        say = f"I've opened a case and matched you with {out['mentor']['name']}. " + ("(This is a demo mentor.) " if out.get("mock_mentor") else "") + \
              f"They'll see a full report of what we've tried. Reasons: {', '.join(out.get('match_reasons', [])[:2])}."
    return {"say": say, "case": {k: out.get(k) for k in ("case_id", "status", "tier", "category")}, "ui": {"panel": "mentor"}}


TOOLS = {
    "get_learner_context": t_get_learner_context,
    "get_next_action": t_get_next_action,
    "explain_topic": t_explain_topic,
    "record_response": t_record_response,
    "confirm_statement": t_confirm_statement,
    "show_visual": t_show_visual,
    "request_mentor": t_request_mentor,
}
