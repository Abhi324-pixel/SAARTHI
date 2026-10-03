# SAARTHI feature playbook — read this before any feature spec

This file is the shared part of every spec in this folder. Each spec (`T01…`, `C01…`, `D01…`) tells you *what* to build and *where to
find the source idea*. This playbook tells you *how work is done in this repo*. Reading both takes ~30 minutes and saves days.

Spec IDs: **T** = idea comes from TESSA, **C** = idea comes from Chhatrachhaya, **D** = a gap in SAARTHI's own demo/safety flow.
The list, priorities and dependencies are in [`INDEX.md`](INDEX.md).

---

## 1. What SAARTHI is (the 60-second version)

SAARTHI is an adaptive AI mentor for learners heading to a Backend Developer role (first release: SQL and its prerequisites).

- It keeps a **Learner Twin**: for each of 28 concepts, a probability the learner knows it (Bayesian Knowledge Tracing), plus the
  *evidence* behind it (every question, SQL query, spoken explanation, mentor session is an `EvidenceEvent` with a source type).
- It finds **misconceptions** (a specific wrong idea, e.g. "LEFT JOIN + WHERE filter keeps all rows"), not just wrong answers.
- It rebuilds a **roadmap** after every piece of evidence, with a reason code for every item ("Why this?", "Why not X?", what-if).
- When SAARTHI cannot move the learner forward, a human mentor (**Chhatrachhaya**) receives a case with a full report.
- Voice (ElevenLabs agent, text-to-speech, speech-to-text) works in English, Hindi and Hinglish.
- The language model **never decides mastery**. It only (a) quotes the learner's own words against a checklist, (b) paraphrases
  curated notes, (c) classifies "I'm stuck" messages into curated ids. Everything else is deterministic code.

Read these once, in this order: `README.md`, `docs/DEMO.md`, `docs/SWAPPING_MOCK_TO_REAL.md`, `backend/app/models.py`,
`backend/app/engines/mastery.py`, `backend/app/engines/hooks.py`.

## 2. Get it running

```bash
cd backend
python -m pip install -r requirements.txt
copy .env.example .env            # fill GEMINI_API_KEY etc. — ask Abhinav for the team keys; NEVER commit .env
python scripts/check_env.py       # green/red check of Gemini, ElevenLabs, database, Supabase
python -m pytest -q               # ~150 tests, all offline; must stay green
cd ../frontend && npm install && npm run typecheck && npm run build
```

Start both servers with `run-dev.bat` (repo root) → <http://127.0.0.1:5173>. For solo work without keys set
`SAARTHI_LLM_MODE=fake` (a red "TEST LLM" banner appears; grading is a keyword toy; **never use it in the demo**).
Keep `SAARTHI_AUTH=mock`, `SAARTHI_MENTORS=mock`, `SAARTHI_CONSENT=mock`, `SAARTHI_COHORT=mock` while developing; the
tests pin all of these themselves (`backend/tests/conftest.py`) and never read your `.env`.

## 3. Repo map

```
backend/app/
  main.py            app factory; routers are registered here
  config.py          every setting (pydantic-settings, reads backend/.env). Nothing else reads os.environ.
  db.py              one SQLAlchemy engine; SQLite locally, Supabase Postgres when DATABASE_URL is set
  models.py          ALL tables (learners, concept_states, evidence_events, misconception_instances, roadmap_versions,
                     learning_sessions, transcript_turns, mentors, mentor_cases, case_messages, consents, ...)
  deps.py            current_learner (auth dependency used by every route)
  content.py         loads + validates app/content/*.json (28 concepts, 23 misconceptions, 63 MCQs, 22 SQL tasks, 19 rubrics)
  engines/           the deterministic brain: mastery, diagnostic, misconception, planner, explainback (+interview),
                     strategy (bandit), escalation (mentor routing), stuck, cohort, hooks, sqlcheck
  routes/            HTTP layer only: core.py (me/dashboard/roadmap/genome/dev), learn.py (probe/sql/teach/explain-back/interview/
                     misconceptions/reviews/stuck), mentor.py (mentors/cases/consent/reports/cohort), voice.py
  adapters/          ports (base.py) + mock/real implementations (impl.py) + factory (__init__.py) for auth, mentors, consent, cohort, responder
  llm/gateway.py     the ONLY module that talks to Gemini. llm/tasks.py holds prompts, schemas and offline "fake" handlers.
  voice/elevenlabs.py  signed agent URL, text-to-speech, speech-to-text (server side; the API key never reaches the browser)
  agent_tools.py     the 7 tools the ElevenLabs voice agent can call
backend/tests/       pytest; conftest.py pins the environment
backend/scripts/     check_env.py, seed.py (mentors + cohort), export_review_sheet.py
frontend/src/
  App.tsx            routes + shell (nav, banners, voice drawer)      store.tsx   app context, i18n dictionary, toasts
  api.ts             typed-ish client for every endpoint              pages/      one file per screen
  components/        ui.tsx (Ring, Bar, Callout, chips…), audio.tsx (SpeakButton/MicButton), VoiceDrawer, ExplainBack, …
docs/                ELEVENLABS_SETUP, DEMO, SWAPPING_MOCK_TO_REAL, CONTENT_REVIEW, and this folder
```

## 4. Non-negotiable rules (a change that breaks one gets reverted)

1. **Only four source types may move mastery**: `question`, `work_product`, `explain_back`, `mentor`
   (`MASTERY_SOURCES` in `engines/mastery.py`). `feedback` and `self_report` are *recorded* but never move it. Stated confidence never
   raises mastery. Do not add a new source type without the team deciding it. Everything that moves mastery goes through
   `mastery.apply_evidence(...)` — never write to `ConceptState.p_known` yourself.
2. **No invented numbers.** No percentile, no "interview score", no "match %", no "Gyaan score", no confidence-padding. If a
   number is shown, it must be computed from stored evidence and you must be able to say how. (Several TESSA/Chhatrachhaya features
   fabricate numbers; each spec lists them under "Do not copy".)
3. **The model proposes, code decides.** Every id the LLM returns (concept, misconception, skill) is validated against curated
   content before use. Quotes it claims are verified as substrings of what the learner actually said.
4. **Fail closed.** If the LLM or a provider is unavailable, grading features say so and record nothing. They never guess.
   (`llm/gateway.py` raises `LLMUnavailable`.) Paraphrase-only features may fall back to the curated text.
5. **Mock vs real is an adapter, never an `if`.** New external dependency ⇒ a port in `adapters/base.py`, a mock + a real class in
   `adapters/impl.py`, a factory branch in `adapters/__init__.py`, a switch in `config.py` and `backend/.env.example`, a row in
   `docs/SWAPPING_MOCK_TO_REAL.md`, and **contract tests that run against both** (see `tests/test_adapter_contracts.py`).
   A "real" switch with missing configuration must refuse to start. Mock rows carry `is_mock=True` and a `mock_` id prefix and the UI
   shows a **Demo data** badge (`DemoBadge` in `components/ui.tsx`).
6. **Learner data rights.** Every new table with learner data has `learner_id` with `ondelete="CASCADE"`, is included in
   `GET /api/me/export` and removed by `DELETE /api/me` (both in `routes/core.py`). Audio is never stored; only text transcripts.
7. **Minors (under 18) are protected by default.** Any feature that exposes a learner to another person (mentors, jobs, sharing)
   checks `learner.age < 18` and the consent adapter. Never rely on the client for this.
8. **Safety wording is fixed.** The wellbeing path (Tele-MANAS 14416, safeguarding lead, never an ordinary mentor ticket) and the
   message screening for contact details (`escalation.screen_message`) must not be weakened.

## 5. Recipes

### 5a. Add a table
- Add the model (portable types only: `String/Integer/Float/JSON/DateTime/Boolean/Text`; **no** Postgres-only types).
- `db.init_db()` calls `Base.metadata.create_all`, which **creates missing tables but never alters existing ones**. So:
  - **New table → fine**, it appears on SQLite and on Supabase the next time the API starts.
  - **New column on an existing table → NOT applied on Supabase.** Avoid it: put new data in a new table, or in an existing JSON
    column (`Learner.settings`, `MentorCase.report/outcome/followup`, `LearningSession.state`). If a column is truly needed, write the
    `ALTER TABLE` in the hand-off note and the commit message and run it in the Supabase SQL editor.
- Keep ids as `new_id("prefix_")` strings (see `models.new_id`). Datetimes are naive UTC via `models.now()`.
- **Learner time**: use `mastery.learner_now(learner)` (it adds the demo `clock_offset_days`) for anything about "today", streaks,
  review dates and deadlines, otherwise the "advance time" demo tool will not affect your feature.

### 5b. Add an engine + route
- Logic goes in `backend/app/engines/<name>.py` as plain functions taking `(db: Session, learner: Learner, ...)`. No FastAPI imports there.
- HTTP goes in `backend/app/routes/<name>.py` using `router = APIRouter(prefix="/api")`, `Depends(current_learner)`, `Depends(get_db)`.
  Register in `main.py`. Validate input with pydantic (`Field(min_length=…, le=…)`) — copy the style of `routes/learn.py`.
- After anything that creates evidence call `hooks.after_evidence(db, learner, concept_id, "your explanation")` so the roadmap
  refreshes and the "roadmap just changed" banner can appear. Return its result under the key `after`.
- Every query is scoped to the signed-in learner (`.where(Model.learner_id == lr.id)`); object ids from the client are always
  re-checked for ownership (see `_case()` in `routes/mentor.py`).

### 5c. Add a curated content file
- Content lives in `backend/app/content/*.json`, is loaded in `content.py` and **validated at start-up** (`Content.validate`): a typo
  makes the API refuse to start, by design. Add your checks to `validate()` and a test in `tests/test_content.py`.
- Trap: `validate()` currently requires **every concept to have notes and at least one MCQ**. If you add a concept, add both (or
  deliberately relax the rule for a new domain and say so in the commit message).
- All curated content is "AI-drafted, pending expert review". Say so in the file's `version` string (contains `pending-review`) and
  add it to `docs/CONTENT_REVIEW.md` via `scripts/export_review_sheet.py`.

### 5d. Add an LLM task
- Write it in `llm/tasks.py`: a `system` prompt, a JSON `schema`, a `fake` handler for offline tests, and call
  `gateway.generate_json("task_name", system, prompt, SCHEMA, fake=fake, max_tokens=…)` or `generate_text`.
- Treat everything the learner/resume/web page wrote as **untrusted data**: say so in the system prompt and put it inside delimiters.
- Always catch `gateway.LLMUnavailable`. Grading → return `{"unavailable": True, ...}` and record nothing (copy `explainback.answer`).
- Responses are cached on disk only when `cache=True` (use it for deterministic content such as paraphrases, never for grading).

### 5e. Add a mock/real adapter
Follow rule 5 above. Copy the shape of `MentorDirectory` (`adapters/base.py`) → `MockMentorDirectory`/`DbMentorDirectory`
(`adapters/impl.py`) → `adapters.mentors()` (`adapters/__init__.py`) → `mentors_mode` (`config.py`).
Contract tests: `tests/test_adapter_contracts.py` runs the same assertions on both implementations.

### 5f. Add a frontend screen
1. Page in `frontend/src/pages/<Name>.tsx` (copy `Genome.tsx` for a read-only page, `Mentors.tsx` for a form-heavy one).
2. Route in `App.tsx` (wrap in `<Guard>`), nav entry in `Shell` if it is a main page.
3. API functions in `frontend/src/api_ext/<spec>.ts` (import `req` from `../api`; see "Hot-spot files" below).
4. Use the shared pieces: `Callout`, `SectionTitle`, `Ring`, `Bar`, `LevelChip`, `FlagChip`, `DemoBadge`, `Spinner` (`components/ui.tsx`);
   `useApp()` for `me`, `toast`, `bump()` (re-fetch after a change), `setRoadmapNote`, `openVoice`, `openStuck`.
5. Styling is Tailwind v4 with the project tokens (`navy`, `saffron`, `teal`, `paper`, `line`, `muted`) from `src/index.css`.
   **Do not copy TESSA's or Chhatrachhaya's CSS/UI** — they are only idea references.
6. Accessibility basics: labels on inputs, `aria-live` for streaming/updating text, keyboard operable, works at 360 px width.
7. User-visible text: add keys to the dictionary in `store.tsx` (`DICT`) when you add navigation or headline strings, so spec **C08**
   (Hindi interface) stays possible. Do not hard-code more English than you have to.

### 5g. Tests (a change without tests is not done)
- Backend: `backend/tests/test_<feature>.py`. Use the `client` fixture and `login()` helper at the top of `tests/test_api.py`
  (in-memory SQLite, fake LLM, mock adapters). Engines are tested directly with a `dbm.SessionLocal()` session.
- Test the **rules**, not just the happy path: "feedback does not move mastery", "another learner cannot read this", "minor is
  refused", "LLM down ⇒ nothing recorded".
- Frontend: `npm run typecheck` and `npm run build` must pass (there is no UI test runner yet; add a manual checklist to the hand-off note).
- Run `python -m pytest -q` (everything) before every push.

### 5h. Add a voice-agent tool (rare)
Add a function to `agent_tools.py` + `TOOLS` map, document it in `docs/ELEVENLABS_SETUP.md` (the user creates the tool in the
ElevenLabs dashboard, with a **description for every parameter**), and add a test in `tests/test_agent_and_voice.py`.

## 6. Hot-spot files (where merge conflicts happen) and how to avoid them

| File | Conflict risk | Rule |
|---|---|---|
| `backend/app/models.py` | high — everyone adds tables | put new tables in `backend/app/models_ext/<spec-id>.py` (see Step 0) |
| `backend/app/main.py` | medium — router list | one `include_router` line per router, each on its own line (Step 0) |
| `backend/app/routes/core.py`, `learn.py`, `mentor.py` | high | do **not** grow these; new endpoints go in a new `routes/<name>.py` |
| `frontend/src/api.ts` | high | new calls go in `frontend/src/api_ext/<spec-id>.ts` (Step 0) |
| `frontend/src/App.tsx` | medium | add your `<Route>` and import on their own lines, alphabetical by path |
| `frontend/src/store.tsx` | medium | only touch `DICT`; one key per line |
| `backend/.env.example`, `docs/SWAPPING_MOCK_TO_REAL.md` | low | append, don't reorder |

### Step 0 — shared setup (✅ done, on `main`)
What exists now, so features can be added in parallel without editing the same files:
1. **Tables:** `backend/app/models_ext/` — one file per spec (`T04.py`, `C03.py`, …), auto-imported by `db.init_db()`. Do not edit `models.py`.
2. **Export / delete:** `backend/app/privacy.py` — in your `models_ext/<spec>.py` call `privacy.register_export("key", fn)` (what `GET /api/me/export` should include, under `more`) and, only for rows not removed by FK cascade, `privacy.register_delete(fn)`. Do not edit the export/delete code in `routes/core.py`.
3. **Routes:** `backend/app/main.py` has one route-module import and one router per line — add your own two lines.
4. **Frontend API calls:** `frontend/src/api.ts` exports `req`; put your calls in `frontend/src/api_ext/<spec>.ts` (see its README). The folder is `api_ext`, not `api`, because a folder named like `api.ts` makes `'./api'` imports ambiguous.
Tests for this setup: `backend/tests/test_shared_setup.py`.

## 7. Working together

- **Everyone works on `main`.** That only works if every push is small, tested and leaves the app working: pull with `git pull --rebase origin main` before you start and before every push, run `pytest`, `npm run typecheck` and `npm run build`, then push.
  Never force-push or rewrite history. The step-by-step routine and a paste-in prompt are in [`TEAMMATE-PROMPT.md`](TEAMMATE-PROMPT.md); who owns what is in [`TEAM-SPLIT.md`](TEAM-SPLIT.md).
- **Push cutoff (demo is 3 Oct).** What is on `main` at the cutoff is what Abhinav verifies and presents. After the cutoff (the time on your prompt's `PUSH CUTOFF` line, IST) nobody pushes; commit locally and wait for Abhinav.
- **One owner per spec.** Put your name in the INDEX table. If a spec depends on another, build the dependency first or stub it.
- **Small steps.** Follow the spec's "suggested order of work": push a step as soon as it is green; push a new screen only when it works end to end.
- **Hand-off note (instead of a pull request)** — in the last commit of a feature and in a message to Abhinav: what changed; which rules in §4 it touches and how they are honoured; new env vars; new tables
  (and any manual SQL); how it was tested; what was **not** verified live (say it plainly).
- **Secrets.** Never paste keys into chat, issues or code. Real values live only in `backend/.env` and `frontend/.env.local`
  (both git-ignored). `.env.example` files hold placeholders only.
- **Content review.** If you add curated text (questions, rubrics, packs), mark it AI-drafted and list it in the hand-off note for human review.

## 8. About the two source projects

- **TESSA** (`D:\Hackathon projects\TESSA` on Abhinav's machine — ask for a copy): Python/FastAPI, vanilla-JS single page
  (`public/index.html`, 6,437 lines), process-local JSON store, Gemini + Tavily + Adzuna. Paths in specs are relative to its root.
- **Chhatrachhaya** (<https://github.com/mrgraciz123/chhatrachhayaa>, MIT): React + Firebase (Auth, Firestore, Realtime DB, Storage).
  Paths in specs are relative to the repo root. Note: README describes more than the code implements (prep notes, session booking,
  AI match scoring and the Gyaan score are **README only**); each spec says what the code really does.
- **Both are read-only.** Do not edit, commit into, or copy files from them. We re-implement ideas and algorithms in SAARTHI's own
  structure. No code, UI, CSS, content, keys or ids are copied.
- **Never copy** (global): hard-coded or client-side API keys (Chhatrachhaya's `emailService.ts` ships EmailJS ids; `AiChatbot.tsx`
  reads a Gemini/OpenAI key in the browser), invented scores (TESSA percentile/STAR/job-match clamp, Chhatrachhaya match % and
  Gyaan score), fake fallback data presented as real (TESSA's mock jobs), and "mark complete" buttons that change progress without
  evidence.

## 9. Glossary

- **Concept** — one skill node (e.g. `sql_outer_join`) in `content/concepts.json`, with prerequisites.
- **Evidence event** — one observation about one concept with a source type; append-only.
- **Level** — `not_assessed / unknown / developing / proficient / mastered`, derived from probability + evidence diversity.
- **Flags** — independent warnings on a concept: `misconception, blocked, due_for_review, disputed, low_confidence, overconfident`.
- **Misconception lifecycle** — `candidate → confirmed → correcting → pending_verify → resolved` (or `dismissed`).
- **Reason code** — machine-readable reason attached to a roadmap item (`GAP_COVERAGE`, `MISCONCEPTION_FIX`, `PREREQ_FOR`,
  `NEEDS_FIRST`, `TIME_FIT`); prose is generated from codes.
- **Skill Mentor / Margdarshak / Safeguarding lead** — the three human tiers of Chhatrachhaya (technical / career / wellbeing).
- **Case** — a mentor request with a report; **outcome** — what the mentor records; **follow-up** — SAARTHI's later check of whether it helped.
- **Mock / real** — the adapter switch for auth, mentors, consent, cohort (and any adapter you add).
