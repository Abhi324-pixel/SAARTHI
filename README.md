# SAARTHI — an AI mentor that learns how to teach you

Adaptive learning for aspiring Backend Developers (first release: **SQL and its prerequisites**).
SAARTHI keeps an evidence-backed **Learner Twin**, finds the *exact idea* you have wrong (misconceptions, not just wrong answers),
rebuilds your **roadmap** from that evidence — with a reason for every change — and hands persistent problems to a human mentor
(**Chhatrachhaya**) with a full case report. Voice is powered by **ElevenLabs** (Agents + Text-to-Speech + Speech-to-Text), in
English, Hindi and Hinglish.

Product report: `updated_v3.pdf` · Voice setup: [`docs/ELEVENLABS_SETUP.md`](docs/ELEVENLABS_SETUP.md) · Demo script: [`docs/DEMO.md`](docs/DEMO.md) ·
Swapping mock → real: [`docs/SWAPPING_MOCK_TO_REAL.md`](docs/SWAPPING_MOCK_TO_REAL.md) · Content review sheet: [`docs/CONTENT_REVIEW.md`](docs/CONTENT_REVIEW.md)

---

## Run it (Windows)

Prerequisites: Python 3.12+, Node 20+.

```bash
# 1. backend dependencies (once)
cd backend
python -m pip install -r requirements.txt

# 2. configuration (once)
copy .env.example .env          # then fill in GEMINI_API_KEY and the ELEVENLABS_* values (see docs/ELEVENLABS_SETUP.md)
python scripts/check_env.py     # green/red check of every key — run it before the demo

# 3. frontend dependencies (once)
cd ..\frontend
npm install
```

Start both servers (two windows) with **`run-dev.bat`** in the repo root, then open <http://127.0.0.1:5173>.

Single-port mode (what you would deploy): `build-and-serve.bat` builds the frontend and serves everything from <http://127.0.0.1:8000>.

Offline development without keys: set `SAARTHI_LLM_MODE=fake` in `backend/.env`. A red **TEST LLM** banner appears and explain-back uses a keyword
grader. **Never use this in the demo.** Without keys everything that does not need a model (placement, SQL checking, misconception detection, roadmap,
mentors) still works; model-dependent grading *fails closed* (it says so and records nothing).

## What is real and what is mock

| Area | Now | How it is swapped | 
|---|---|---|
| Gemini (`gemini-3.5-flash-lite`) | **real** | — |
| ElevenLabs Agent / TTS / STT | **real** | — |
| Learner Twin, BKT mastery, evidence log, roadmap, planner, misconception engine, SQL checker | **real** | — |
| Database | local SQLite | set `DATABASE_URL` to Supabase Postgres (same models) |
| Sign-in (`SAARTHI_AUTH`) | **mock** dev login | `supabase` (verifies Supabase signing-key JWTs via JWKS; needs `SUPABASE_URL`) |
| Mentors & their verification (`SAARTHI_MENTORS`) | **mock** (6 seeded) | `db` after `python scripts/seed.py` |
| Mentor replies | **mock** canned replies | automatic: none when mentors are real (humans reply) |
| Guardian consent (`SAARTHI_CONSENT`) | **mock** "approve as guardian" button | `db` (guardian approves through an e-mailed single-use link; set `SAARTHI_MAIL=smtp` + SMTP settings for real delivery, see `docs/features/D01-guardian-consent-flow.md`) |
| Teacher cohort (`SAARTHI_COHORT`) | **mock** synthetic class of 24 | `db` (aggregates real learners) |

Every mock item is badged **Demo data** in the UI. The same contract tests run against the mock *and* the real version of each adapter
(`backend/tests/test_adapter_contracts.py`), and a "real" switch with missing configuration **refuses to start** instead of silently using mock data.

## Architecture

```
React (Vite) PWA ──/api──▶ FastAPI ──▶ engines (deterministic) ──▶ SQLite / Supabase Postgres
     │                        │             mastery (BKT) · diagnostic · misconception · planner
     │                        │             explain-back · strategy · escalation · stuck · cohort
     │                        ├──▶ LLM gateway ──▶ Gemini   (quotes evidence, paraphrases curated notes; never sets mastery)
     │                        └──▶ ElevenLabs REST (TTS, STT, signed agent URL)
     └── ElevenLabs Agent (voice) ── client tools ──▶ /api/voice/tools/* ──▶ the same engines
```

Design rules (see report §Reuse Map): the language model *proposes*, structured state and deterministic logic *decide*. The voice agent cannot grade
or change mastery — every learner answer goes through SAARTHI's tools. Only questions, executed SQL, explain-back and mentors move mastery; feedback
clicks and self-reports are recorded but never change it. Explain-back credit needs a quote that is verified against the learner's own words.
Nothing is shown that was not measured (no percentile, no "interview score").

### Folders
- `backend/app/content/` — curated learning content (concept graph, 23 misconceptions, 63 questions, 22 SQL tasks, 19 explain-back rubrics, notes). **AI-drafted, pending expert review.**
- `backend/app/engines/` — mastery, diagnostic, misconception, planner, explain-back/interview, strategy, escalation, stuck, cohort, hooks, SQL checker
- `backend/app/adapters/` — ports + mock/real implementations (auth, mentors, consent, cohort)
- `backend/app/llm/`, `backend/app/voice/` — Gemini gateway; ElevenLabs REST wrappers
- `backend/tests/` — ~150 tests (content integrity, SQL variants, BKT rules, planner, adapters, API flows, gateway fallback)
- `frontend/src/` — pages, skill graph, SQL workbench, explain-back, voice drawer with the "Under the hood" ElevenLabs panel

## Tests

```bash
cd backend && python -m pytest -q          # everything runs offline (fake LLM / mocked HTTP); real services are checked by scripts/check_env.py
cd frontend && npm run typecheck && npm run build
```

## Notes worth knowing
- The SQL practice database runs **on the server** (read-only SQLite authorizer: SELECT only, row cap, time limit) rather than in the browser, so evidence cannot be forged from the client.
- Demo helpers (advance time, simulate struggle, load a starting history) live in *Settings → Demo tools*, are labelled `simulated` in the evidence log, and disappear when `SAARTHI_ENV=prod`.
- Under-18 learners can use all learning features; mentor sessions need (mock) guardian approval. Real verification of mentors, police checks and legal review are **not** done — see the report's safeguarding section before any real pilot.
- Audio is never stored; only transcripts are.
