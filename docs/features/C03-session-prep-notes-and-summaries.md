# C03 — Learner prep notes before a mentor session and a summary after it

| | |
|---|---|
| Source | Chhatrachhaya — "AI-generated prep notes before each session, 5 questions to ask your Margdarshak, ice-breakers, session summary after completion" |
| **Important** | These are described in Chhatrachhaya's `README.md` ("📅 Baatcheet (1-on-1 Sessions)") but are **not implemented** in its code: `src/BaatcheetScreen.tsx` is plain messaging (no sessions, no prep, no summaries); `grep -i prep src/` finds only the unrelated quiz helper `prepareQuiz`. So there is **no code to adapt** — design from the README's intent and SAARTHI's own data. |
| SAARTHI today | **Partial.** The *mentor* side is covered: the case report is a complete briefing (`escalation.build_report`). The *learner* gets only "matched with X · first slot Y". After the session the learner sees the mentor's notes/next step in a callout and a follow-up percentage; no preparation help, no plain-language summary, no scheduled follow-up. |
| Priority / size | P1 (cheap, and demoable today in mock mode) / M (2 days) |
| Depends on | nothing. Works with the mock `simulate-session` button now and with real outcomes after C02. |
| External accounts | none |

## 1. What the learner gets

**Before the session** (case `accepted`/`scheduled`): a "Get ready" card —
1. *What to bring*: the exact query/question you were stuck on and what you expected vs what you got.
2. *Three to five questions to ask* — built from their own case ("Why does moving the filter from WHERE to ON change my result?"),
3. *An ice-breaker* in their language ("Hi, I'm Priya — my LEFT JOIN keeps dropping customers"),
4. *What your mentor already knows* — the same report the mentor sees, so there are no surprises (privacy transparency).
A button **"Send these questions to my mentor"** posts them as the first message (screened like any message).

**After the session** (case `followup`): a plain-language summary — what the mentor said (their words, verbatim), your next step, what SAARTHI
saw change in your estimate (before → after, with the evidence behind it), and a dated **follow-up check** ("Friday: a 3-question check on
LEFT JOIN"). Doing the check is what closes the case (the existing `followup_check`).

## 2. How it works in Chhatrachhaya

Only as README text (see the box above):

| What | Where |
|---|---|
| Promise: prep notes, 5 questions, Hinglish ice-breakers, summary after completion | `README.md`, section "📅 Baatcheet (1-on-1 Sessions)" |
| Planned components `SessionsList.jsx`, `SessionCard.jsx`, `PrepNotes.jsx` | `README.md` "Project Structure" — **files do not exist** in `src/` |
| What actually exists: conversations list + chat only | `src/BaatcheetScreen.tsx` (whole file, 222 lines) |
| AI "session summary after room ends" (voice rooms) | README only; voice rooms are excluded from SAARTHI (see `99-NOT-BUILDING.md`) |

### Do not copy
- Generic AI advice ("be curious, ask good questions"). Notes must be built from **this learner's case data**, or they add nothing.
- Anything the model made up about the mentor. Mentor details come only from the `Mentor` record.

## 3. What SAARTHI already has

- `escalation.build_report()` (l.88–131): concept, evidence timeline, misconceptions with the learner's own statements, strategies tried, weak prerequisites, suggested intervention.
- Curated misconception data (`content/misconceptions.json`: `name`, `description`, `counter_example{query, explanation}`) and notes (`content/notes.json`).
- `escalation.record_outcome()` → `case.outcome = {notes, next_step, mentor_rating}`, status `followup`; `followup_check()` → `case.followup = {p_at_open, p_now, gain, improved}`, status `closed`.
- `tasks.rewrite_explanation`-style LLM paraphrase with curated fallback; `LANG_NAMES` for Hindi/Hinglish.
- `MentorCase.report/outcome/followup` JSON columns (no schema change needed for a due date inside `followup`).

## 4. How to adapt it

### 4.1 Engine `backend/app/engines/casenotes.py` (deterministic first, model only for wording)
```
learner_prep(db, learner, case) -> {
   "bring": ["The exact query you ran", "What you expected to see", "What you actually got"],
   "questions": [ {"text": "...", "from": "misconception|prerequisite|concept"} ],   # 3–5
   "icebreaker": "…", "mentor_sees": <the case report, same object the mentor gets>, "language": "hinglish" }
session_summary(db, learner, case) -> {
   "mentor_said": {"notes": "<verbatim>", "next_step": "<verbatim>", "by": "<mentor name>"},
   "saarthi_saw": {"concept": "...", "p_before": 0.31, "p_after": 0.46, "evidence": [...]},
   "followup": {"due": "2026-10-21", "task": "3-question check on LEFT JOIN"} }
```
How the questions are built (no model needed for the *content*):
- each active/previous misconception of the case → "Why does `<counter-example fix>` give a different result?" using `counter_example.explanation` as the hidden answer the learner will hear;
- each weak prerequisite → "Can we check I really understand `<prereq name>`? I think it is holding me back";
- one open question tied to the **learner's goal** ("What would you do next if you were me?").
Language: use small template dictionaries (EN + Hinglish + Hindi) for the sentences; an optional `rewrite_prep` LLM task may *re-voice* them (same pattern as `rewrite_explanation`:
"use only these facts"), and falls back to the templates when the model is unavailable.

### 4.2 Storage — new table `case_notes` (`models_ext/C03.py`)
`id, case_id (FK mentor_cases CASCADE), kind ('learner_prep'|'session_summary'), body JSON, created_at`. Generate on first read and cache; **regenerate** `session_summary`
after the outcome is recorded. The follow-up due date goes into `case.followup["due_at"]` (no column change): `due_at = learner_now + 3 days` set inside `record_outcome`.

### 4.3 Follow-up becomes a real task
- `planner.today_mission()` (`engines/planner.py` l.305–): add a mission type `followup` for cases in `followup` with `due_at ≤ learner_now` ("Show it worked: quick check on LEFT JOIN"); its action calls the usual probe endpoints.
- When the learner completes the check, call `escalation.followup_check` (today it is a manual button) — i.e. in `hooks.after_evidence`, if the evidence concept equals a case in `followup` and `due_at` has passed.
- Keep the manual button for the demo (the "advance time" dev tool plus this makes the whole loop demoable in one sitting).

### 4.4 Routes — new `backend/app/routes/case_notes.py`
| Method + path | Notes |
|---|---|
| `GET /api/cases/{id}/prep` | own case only; allowed when status ∈ `accepted, scheduled, matched`; 409 otherwise |
| `POST /api/cases/{id}/prep/share` `{question_indexes: [..]}` | sends the chosen questions as one learner message through `escalation.send_message` (so contact-detail screening still applies) |
| `GET /api/cases/{id}/summary` | allowed when status ∈ `followup, closed`; includes the dated follow-up task |

### 4.5 Frontend
`components/CasePrep.tsx` and `components/CaseSummary.tsx`, used in `pages/Mentors.tsx` `CaseDetail` (above the chat when status is accepted/scheduled; above the report when followup/closed).
Reuse `Callout`, `Collapsible`. Add a "Follow-up" chip in the dashboard "Mentor cases" card. EN/Hindi/Hinglish strings. Mock mentors: the card carries the existing "demo mentor" `DemoBadge`.

## 5. Files to create / touch
`engines/casenotes.py` (new), `llm/tasks.py` (optional `rewrite_prep`), `models_ext/C03.py` (new), `routes/case_notes.py` (new), `engines/escalation.py` (`due_at` in `record_outcome`),
`engines/planner.py` (`today_mission` followup), `engines/hooks.py` (auto follow-up), `frontend/src/components/CasePrep.tsx`, `CaseSummary.tsx`, `pages/Mentors.tsx`, `pages/Dashboard.tsx`,
`frontend/src/api_ext/C03.ts`, tests `test_casenotes.py`.

## 6. Tests (minimum)
1. Prep for a case with a `left_join_where_filter` misconception includes a question built from that misconception's counter-example; for a career case it has career-appropriate questions and no SQL.
2. Prep contains nothing that is not in the case report/curated content (assert every question's `from` source exists); generated twice ⇒ identical (deterministic).
3. LLM unavailable ⇒ template text, same structure. Hindi/Hinglish templates exist for every question kind (test iterates the kinds).
4. Another learner's case ⇒ 404. Wrong status ⇒ 409. `share` of a question containing a phone number is blocked by `screen_message`.
5. After `record_outcome`: summary shows the mentor's notes **verbatim**, before/after p, and a follow-up date 3 learner-days ahead; `advance-time` ⇒ the mission list contains the follow-up.
6. Completing the follow-up check closes the case with `followup.gain`; generating notes never creates an `EvidenceEvent` or changes mastery.

## 7. Done when
- [ ] Learner sees a personalised "Get ready" card before a session and can send their questions to the mentor.
- [ ] After the session they get a verbatim mentor note, a SAARTHI evidence summary and a dated follow-up task that closes the case when done.
- [ ] Works end-to-end in mock mode (demo) and with real outcomes after C02.
- [ ] Nothing in the notes is invented; Hinglish and Hindi are available.

## 8. Risks and traps
- Don't paraphrase the mentor's notes with a model — show them verbatim; label SAARTHI's own lines clearly ("SAARTHI saw…").
- Under-18: the summary is visible to the learner only; do not add "share with guardian" without D01-style consent.
- The 3-day due date uses `learner_now` so the dev clock works; don't use wall-clock time.
