# T08 — HR / behavioural interview round and role packs

| | |
|---|---|
| Source | TESSA — Placement Hub: technical / HR & behavioural / full mock interview, company packs, adaptive interviewer |
| SAARTHI today | **Partial.** A *technical* mock interview exists: 4 concept topics picked from the learner's weakest evidence, probe once, scored against per-concept checklists with verified quotes (`engines/explainback.py` `interview_*`, `pages/Interview.tsx`, voice mode in `agent_tools.py`). There is **no HR/behavioural round** (self-introduction, "tell me about a time…", STAR) and **no packs**. |
| Priority / size | P2 / L (3–5 days; most of it is careful content writing and review) |
| Depends on | nothing hard. T09 (resume) adds "walk me through your project". C01–C02 optional (career mentor hand-off). |
| External accounts | none |

## 1. What the learner gets

A round selector on the Interview page: **Technical**, **HR & behavioural**, or **Full** (both). The behavioural round starts like a real
one — a warm greeting and "tell me about yourself" — then asks 3–4 situational questions ("a time you disagreed with a teammate", "a deadline
you almost missed", "a project you're proud of"). Each answer is checked against a **STAR checklist** (Situation, Task, *your own* Action,
Result, what you learned), item by item, with the learner's own words quoted as proof. No fake percentile, no "STAR score": they see which
parts they covered and which they skipped, with a model answer. Weak behavioural areas become roadmap items and, if they persist, a
suggestion to open a **Margdarshak** (career mentor) case.

## 2. How it works in TESSA (the source idea)

| What | File and place (relative to TESSA root) |
|---|---|
| Interview types, levels, durations; per-role topic blueprints; **company packs** (Amazon, Google, TCS NQT, Infosys, PM, Data) | `backend/app/interview/blueprint.py` `ROLE_BLUEPRINTS` (l.29–64), `COMPANY_PACKS` (l.66–97), `get_blueprint()` (l.100–133) |
| Turn 1 = corporate welcome + "introduce yourself", **no hard questions yet**; later turns probe or move on based on the last answer, one question at a time, no feedback during the interview | `backend/app/interview/interviewer.py` `generate_initial_question()` (l.16–51), `generate_next_adaptive_question()` (l.54–110) |
| Session state, turns with audio duration | `backend/app/interview/session.py` (`InterviewSession`, `InterviewTurn`, in-memory dict l.79–119) |
| HTTP: start / respond / end / report / history / apply gaps | `backend/app/api/interview.py` `start_interview()` (l.97–136), `respond_turn()` (l.139–182), `end_interview()` (l.199–219), `get_history()` (l.242–273), `apply_gaps()` (l.276–290) |
| Evaluation by an LLM over the whole transcript → category scores, per-question review, ideal answer; heuristic fallback if the model fails | `backend/app/interview/evaluator.py` `evaluate_interview_session()` (l.18–200), `_evaluate_transcript_heuristically()` (l.203–323) |
| UI: role/type/level/duration selectors, company-pack chips, start button that satisfies the browser's autoplay rule, timer, transcript log, report | `public/index.html` `startMockInterview()` (l.5728–5775), `launchWatchAndBegin()` (l.5777–5809), `submitTurnAnswer()` (l.5811–5856), `concludeMockInterview()` (l.5858–5887), `renderPerformanceReport()` (l.5901–), tests in `backend/tests/test_interview.py` (`test_interview_session_flow`, `test_company_placement_pack_interview`) |

Tech there: FastAPI, Gemini text generation with JSON parsing by `find("{")…rfind("}")`, Web Speech API in the browser, in-memory sessions.

### Do not copy (important — this file contains several invented numbers)
- `percentile_rank` (`evaluator.py` l.135: `overall*1.06+3`, capped 99; model default `82.5` in `session.py` l.45) and
  `star_method_score` (l.136: `overall*0.9 + clarity*0.1`; default `78.0`). These are made up. SAARTHI shows **no** percentile and no STAR score.
- Silent defaults when the model omits a score (`data.get("technical_knowledge", 65)` … l.124–129) and the keyword-counting
  heuristic that turns word counts into 25–94 "scores" (l.203–323). SAARTHI fails closed: no model ⇒ no score, nothing recorded.
- The `clarity_score` from `communication.py` mixed into "Communication" (see T11).
- **Company packs of unverified claims** ("Amazon Leadership Principles", "Googleyness", "TCS NQT topics") with no source. See 4.3.
- Camera/posture coaching (`visual_coaching.py`, `camera-event` endpoint) — excluded, see `99-NOT-BUILDING.md`.
- Evaluating the whole transcript in one model call. SAARTHI scores **per question against a checklist with verified quotes** (more reliable, auditable).

## 3. What SAARTHI already has

- The whole technical-interview engine: `explainback.interview_start/answer/report` (l.233–319), per-turn scoring `evaluate_turn()` with
  quote verification (`quote_is_grounded`), misconception read-back, fail-closed grading, `MISCONCEPTION_SCORE_CAP`.
- `content/rubrics.json`: `{prompt, prompt_hi, checklist:[{id,text,weight}], reference, followups, misconception_ids}` per concept;
  `roles.json` `interview_topics` per role.
- Voice interview mode in `agent_tools.t_get_next_action` already calls `interview_start` — so a better queue improves voice too.
- `escalation`: category `career` routes to a **Margdarshak**; `_CAREER_WORDS` already includes "interview".
- `Interview.tsx` UI (chat log, confidence picker, mic, report with covered/missed + model answer).

## 4. How to adapt it

### 4.1 Where do behavioural answers count? → new concepts in a `communication` domain
Evidence must belong to a concept so it can flow through `apply_evidence`, misconceptions, the roadmap and the Learner Twin. Add 3 concepts:

| id | name | what it covers |
|---|---|---|
| `comm_self_intro` | Introduce yourself | 60-second structure: who you are, what you studied/built, why this role |
| `comm_star_story` | Behavioural answers (STAR) | Situation, Task, own Action, Result, Reflection |
| `comm_project_walkthrough` | Explain your project | problem, your role, key decision, a hard bug, result |

Required edits (all are traps if forgotten):
1. `content/concepts.json`: add the 3 concepts with `domain: "communication"`, `prereqs: []`, small `minutes` (20–30), `p_init` ≈ 0.3.
2. `content/notes.json` **and** at least one MCQ each in `items.json` — `Content.validate()` fails start-up otherwise
   (`concept …: missing notes` / `no questions`). Example MCQ: "Which answer contains a measurable Result?".
3. `content/rubrics.json`: rubrics for all three (STAR checklist weights suggested: situation 1, task 1, **own action 3**, **result 3**,
   reflection 1; "own action" text: "Says what *they* did (uses 'I', not only 'we')"). Optionally 1–2 misconceptions
   (`star_all_we`, `star_no_result`) in `misconceptions.json`.
4. `content/roles.json`: add the three to `requirements` (weights 0.4–0.6, targets 0.7) and `"communication"` at the end of
   `domain_priority`; add them to a new `behavioural_topics` list (see 4.2).
5. `frontend/src/components/SkillGraph.tsx`: add `communication` to `DOMAIN_ORDER` (line ~30 sorts by it) and a colour.
6. Re-run `scripts/export_review_sheet.py` so the new text appears in `docs/CONTENT_REVIEW.md`. Mark `version` `pending-review`.
7. Tests that count concepts/items (`tests/test_content.py`, planner/API tests) will need their expectations updated deliberately.
All of this text is **AI-drafted and must be reviewed by a person who has actually interviewed candidates** (ask a Margdarshak).

### 4.2 Rounds, prompts and packs (content + engine)
- `content/rubrics.json`: allow `"prompts": ["…", "…", "…"]` (list) in addition to `prompt`; `_prompt_for()` picks the first one the
  learner has not seen (store seen ids in `LearningSession.state`), so retakes are not identical. Also `prompts_hi`.
- `content/interview_packs.json` (new, validated at start-up):
  ```
  {"packs": [ {"id": "services_fresher", "title": "IT-services fresher", "rounds": {
        "technical": {"concept_ids": [...from role.interview_topics...], "n": 4},
        "behavioural": {"concept_ids": ["comm_self_intro","comm_star_story","comm_project_walkthrough"], "n": 3}},
      "note": "...", "source": "who wrote/reviewed it", "reviewed_by": "name" } ] }
  ```
- `explainback.interview_start(db, learner, n_topics, channel, round="technical", pack_id=None)`: queue = technical (existing logic),
  behavioural (`comm_*`, **self-introduction first** — this is TESSA's "turn 1 warm-up"), or technical-then-behavioural for `full`.
  `state["round"]` and per-topic `kind` are stored; `interview_report()` adds `kind` per topic and a separate "behavioural" summary.
  Keep `MAX_TURNS`/probing rules unchanged. The opening line already says "Welcome to your … mock interview".
- **Named-company packs rule:** do not ship "Amazon/Google/TCS" packs unless a human adds a source URL (company's own careers/hiring
  page) and `reviewed_by`. Until then ship **generic** packs (services fresher, product-startup junior backend, internship). The company
  name alone is not content.

### 4.3 Report and next steps
`interview_report()`: for behavioural topics list covered/missed STAR items with quotes (already generic), and `next_steps` such as
"Revisit STAR stories in your roadmap". If a `comm_*` concept stays below `developing` after 3 attempts, `escalation.check_triggers`
(l.59–81) should suggest `category="career"` (→ **Margdarshak**) with reason "interview behaviour". Extend `_tags_for` so tags include `interview`.

### 4.4 Routes
Extend `InterviewStart` in `routes/learn.py` (l.188–190): `round: Literal["technical","behavioural","full"] = "technical"`,
`pack_id: Optional[str] = None`. Add `GET /api/interview/packs` (list id/title/note/reviewed flag) and
`GET /api/interview/history` (list of finished `LearningSession(mode="interview")` with date, round, covered/total — no scores invented).
Put the new endpoints in a new `routes/interview_ext.py`; do not grow `learn.py`.

### 4.5 Frontend
`Interview.tsx`: round + pack selector on the start card; behavioural topics show a "STAR" mini-legend; the report groups technical vs
behavioural. Keep the existing "no hints during the interview" rule. Add EN/Hindi/Hinglish strings.

## 5. Files to create / touch
`content/concepts.json`, `notes.json`, `items.json`, `rubrics.json`, `misconceptions.json`, `roles.json`, `interview_packs.json` (new),
`content.py` (load + validate packs), `engines/explainback.py` (round/pack, prompt rotation), `engines/escalation.py` (trigger/tags),
`routes/learn.py` (request model only), `routes/interview_ext.py` (new), `frontend/src/pages/Interview.tsx`,
`components/SkillGraph.tsx`, `frontend/src/api_ext/T08.ts`, tests: `test_content.py`, new `test_interview_rounds.py`.

## 6. Tests (minimum)
1. Content validation: packs reference existing concept ids; every `comm_*` concept has notes, an MCQ and a rubric.
2. `round="behavioural"` queue starts with `comm_self_intro`; `full` has technical then behavioural; `n_topics` respected.
3. STAR scoring through the fake grader: an answer with situation + own action + result covers those items **with grounded quotes**;
   an answer with only "we" does not credit "own action".
4. Fail-closed: LLM down ⇒ `unavailable`, no `EvidenceEvent`.
5. The report contains no `percentile`/`score_out_of_100` keys (assert absence).
6. Persistent weak `comm_star_story` after 3 attempts ⇒ a `career` escalation suggestion routed to `margdarshak`.
7. Prompt rotation: second attempt gets a different prompt.

## 7. Done when
- [ ] Round selector works for text and voice; self-introduction comes first in the behavioural round.
- [ ] STAR items are scored with verified quotes; no invented scores anywhere.
- [ ] New concepts appear in the roadmap/skill graph with a `communication` domain and are marked pending review.
- [ ] Generic packs only, or named packs with a source and reviewer.

## 8. Risks and traps
- Rubric quality decides everything; a bad STAR checklist teaches bad habits. Get it reviewed.
- Adding concepts changes every roadmap and the "overall" figure — do this carefully, in one push that keeps the tests green, and after the demo.
- Behavioural answers are personal (family, health). Transcripts are stored; remind the learner at the start and make sure they can
  delete them (`DELETE /api/me` cascades sessions; confirm `TranscriptTurn` is covered).
- Don't evaluate accent or fluency (the existing grader prompt already ignores them — keep that line).
