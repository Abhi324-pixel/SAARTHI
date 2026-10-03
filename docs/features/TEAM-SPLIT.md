# Who builds what

Three people share the list. Abhinav takes a set of features marked **🚧 RED ZONE**; the two teammates split the rest into two groups. The plan is deliberately short: finish the 🔴 features first, then the 🟡 ones. Everything else is parked. **Everything pushed today is on stage tomorrow** — see "Today" below.
Names are filled in by Abhinav (blank cells below). Everyone works directly on `main`; see the rhythm at the bottom. Sizes are rough working days taken from the specs (midpoints), not promises.

| | **Abhinav — 🚧 red zones** | **Group 1 — Conversations and interview** | **Group 2 — Progress and planning** |
|---|---|---|---|
| Person | Abhinav | _______________ | _______________ |
| Features | D01, C07, C01, C02, C05, C08 | C03, T07, C04, T11, T08 | T04, T06, T03, T05, T01, C06 |
| Rough total | ≈ 19 days | ≈ 12 days | ≈ 10 days |
| Main areas | consent, sign-in, mentor accounts and console, notifications, translation | mentor-case notes, chat (typed and mentor), speech, interview | planner, roadmap, dashboard cards, intake, profile |

## 🚧 Red zones — read this before you pick anything up

**D01, C07, C01, C02, C05, C08 are red zones: Abhinav is building them, in that order.** They share files with each other (consent, sign-in, the mentor and notification code, every page's text), so they have to land as one coordinated set, one after another.

- **Do not start a red-zone feature.** Your assistant is instructed to stop and warn you if you try (see [TEAMMATE-PROMPT.md](TEAMMATE-PROMPT.md)).
- **If Abhinav is busy or unable**, he will tell you which red-zone feature to take over. He does this by filling the line `RED ZONES CLEARED FOR ME:` in your prompt. Until that line names the feature, treat it as taken.
- Red-zone specs are still readable — they describe code your features sit next to. Reading is fine; building is not.

## Priority — what to build first

| Marker | Meaning |
|---|---|
| 🔴 Tier 1 | Build first, in the order listed |
| 🟡 Tier 2 | Next. Start only when your Tier 1 is merged and you have told Abhinav |
| 🚧 Red zone | Abhinav's. Do not start (see above) |
| ⏸ Parked | Not planned for now: **T09, T10, T02**. Do not start them unless Abhinav asks |

| | Group 1 — Conversations and interview | Group 2 — Progress and planning |
|---|---|---|
| 🔴 Tier 1 | C03, T07 | T04, T06, T03 |
| 🟡 Tier 2 | C04, T11, T08 | T05, T01, C06 |

**Natural stopping points:** after Tier 1 the product already shows visible improvements — mentor-session prep and follow-up and a typed assistant (Group 1); a streak card, a progress chart and feedback buttons (Group 2). Tier 2 adds live case chat, speaking coaching and the behavioural interview (Group 1) and phases/deadlines, free-text intake and a profile page (Group 2).

## Group 1 — Conversations and interview (work in this order)

| Order | Tier | Spec | What | Size | Notes |
|---|---|---|---|---|---|
| 1 | 🔴 | [C03](C03-session-prep-notes-and-summaries.md) | Prep notes before a mentor session, summary + dated follow-up after | M | Works in mock mode, so it shows in the demo. Keep your UI in new components (`CasePrep.tsx`, `CaseSummary.tsx`) and mount them in `Mentors.tsx` with minimal lines |
| 2 | 🔴 | [T07](T07-typed-assistant-chat.md) | Typed assistant chat, grounded in the learner's own data | M | Confirm the "grounded only" scope with Abhinav first (spec §4.1) |
| 3 | 🟡 | [C04](C04-live-chat-updates.md) | Live updates in the case chat (polling hook) | S | Only matters with real mentors (mock mentors reply instantly), so not for the demo |
| 4 | 🟡 | [T11](T11-speaking-pace-and-filler-coaching.md) | Speaking pace, pauses and filler markers | M | Check what the speech-to-text response really contains first (spec §4.1) |
| 5 | 🟡 | [T08](T08-behavioural-interview-and-company-packs.md) | HR / behavioural interview round + generic packs | L | Content-heavy, needs a human reviewer. Touches a few lines of `escalation.py` (see hand-offs) |

## Group 2 — Progress and planning (work in this order)

| Order | Tier | Spec | What | Size | Notes |
|---|---|---|---|---|---|
| 1 | 🔴 | [T04](T04-streaks-and-daily-goal.md) | Streak and daily goal, derived from evidence | S | No new table; read-only, so the safest first push |
| 2 | 🔴 | [T06](T06-progress-over-time-chart.md) | Progress-over-time chart and radar | S–M | No new table; read-only |
| 3 | 🔴 | [T03](T03-difficulty-and-preference-feedback.md) | "Too easy / too hard / helped" that adapts the plan | S–M | Edits `planner._minutes` — leave the default behaviour unchanged for learners who never click |
| 4 | 🟡 | [T05](T05-milestones-deadlines-checkpoints.md) | Phases, deadlines, personal checkpoints | M | |
| 5 | 🟡 | [T01](T01-free-text-goal-intake.md) | Free-text goal / conversational intake | M | Adds concept `aliases` |
| 6 | 🟡 | [C06](C06-learner-profile-page.md) | Learner profile page | S | You own `Settings.tsx` and `Profile.tsx`; skip the birth-year note in the spec (Abhinav handles age) |

## Today — the demo is tomorrow (read this before you plan anything)

`docs/DEMO.md` is the 5-minute story Abhinav will present. Whatever is on `main` at the push cutoff goes on stage, so today's goal is **a small, visible, safe slice of your first features — not the whole spec**.

**Rules for today**
1. **Build the slice, not the spec.** Do the slice below for your first feature. Start the next one only after the first is pushed and green. Anything marked "skip today" stays for later.
2. **Additive only.** Do not change how the existing demo path behaves (login → placement → dashboard → learn / teach-back → SQL practice → roadmap → mentor case). New things appear *next to* the old ones; existing endpoints keep their response shape (you may add fields).
3. **Fail soft.** If your new endpoint errors, your card/button must disappear or show a small message — never break the page around it (catch the error; render nothing).
4. **Run the quick smoke check before every push**, with `SAARTHI_LLM_MODE=fake`: backend tests, `npm run typecheck`, `npm run build`, then in the browser: sign in (mock) → Settings → Demo tools → Load a demo starting history → Dashboard → open a concept (Learn) → Roadmap. Your feature visible and the rest still working.
5. **No new settings or keys needed for the demo.** Use local SQLite; no real Gemini/ElevenLabs required for your work (Abhinav tests the live parts).
6. **Cutoff:** the time on your prompt's `PUSH CUTOFF` line (default 20:00 IST today). After it, no pushes. Push earlier if you can; Abhinav needs the evening to verify and rehearse.

**Today's slices**

| Spec | Do today | Skip today |
|---|---|---|
| T04 | Dashboard card: current / best streak, 7-day bar, today's goal progress (computed from evidence on the server, no check-in button) | Hide toggle, Settings page entry |
| T06 | Genome page: progress-over-time line (overall + per domain) replayed from the evidence log, demo-seeded points marked "simulated"; radar | Markers, projection line, dashboard sparkline |
| T03 | Three buttons on the explanation card (too easy / too hard / helped) with the effects in the spec and a `LEARNER_FEEDBACK` reason on the roadmap | Settings "what was adapted" panel, rate limit (must come later) |
| C03 | "Get ready" card (template text, English + Hinglish, no model call) before a session and the "After your session" summary with the follow-up date, working with the mock `simulate-session` button | Model re-wording, follow-up as a daily task, auto-closing, "send my questions to the mentor" button |
| T07 | Chat drawer answering next-step / why / why-not / progress / explain from the learner's own data (keyword routing is fine; model routing optional) | Streaming, rate limit, mentor hand-off action |

**After the cutoff (Abhinav):** pulls `main`, runs the pre-flight in `docs/DEMO.md`, fixes or reverts anything that breaks the story, then tags the commit he will present (`git tag demo-final && git push origin demo-final`). A fallback tag `demo-baseline` marks the last commit before today's teammate work.

## Abhinav — 🚧 red zones (for information)

| Order | Spec | What |
|---|---|---|
| 1 | [D01](D01-guardian-consent-flow.md) | Real guardian consent |
| 2 | [C07](C07-google-sign-in.md) | Google sign-in with a mandatory age step |
| 3 | [C01](C01-mentor-signup-verification-pledge.md) | Mentor sign-up, verification record, pledge |
| 4 | [C02](C02-mentor-console.md) | Mentor console |
| 5 | [C05](C05-notifications-and-unread-badges.md) | Notifications and unread badges |
| 6 | [C08](C08-hindi-first-interface.md) | Hindi / Hinglish interface |

## Hand-offs and shared files (read before you start)

| Shared file / area | Who | Rule |
|---|---|---|
| `engines/planner.py` | Group 2 owns | Group 1's C03 adds a `followup` mission to `today_mission()` — small and additive; do it after Group 2's T03 has merged, or rebase carefully |
| `engines/escalation.py` | Abhinav | C03 needs a 1–2 line change in `record_outcome()` (a due date) and T08 a ~5-line change in `check_triggers()` / `_tags_for()`. Make only that change, say so in the commit message, and expect Abhinav's pushes to land first — pull with `git pull --rebase origin main` and re-check before pushing |
| `adapters/*`, `config.py`, `.env.example` | Abhinav | Teammates' active features add no adapters. If you think you need one, ask |
| `routes/core.py` (`dashboard`) | everyone | Only add lines, never reformat. For data export / account deletion do **not** edit `core.py`: register hooks in `privacy.py` from your `models_ext/<spec>.py` (Step 0) |
| `frontend/src/pages/Settings.tsx`, `Profile.tsx`, `Dashboard.tsx`, `Roadmap.tsx`, `Learn.tsx` | Group 2 (Dashboard: small additive edits from Group 1's C03 chip) | Put new UI in separate components and mount them with one line |
| `frontend/src/pages/Mentors.tsx` | Abhinav, with Group 1's C03/C04 mounting small pieces | New components in new files; minimal edits in `CaseDetail` |
| `frontend/src/pages/Interview.tsx`, `components/ExplainBack.tsx`, `engines/explainback.py` | Group 1 (T08, T11) | |
| `frontend/src/App.tsx`, `store.tsx` | everyone | Add routes, imports and keys on their own lines; i18n keys named `<spec id>.<screen>.<name>` (e.g. `T04.streak.title`) |
| `llm/tasks.py` | Groups 1 and 2 | Append new tasks at the end, one section per spec |
| `models_ext/<spec id>.py`, `routes/<name>.py`, `api_ext/<spec id>.ts` | one owner each | No conflicts — this is why Step 0 (shared setup) matters |
| `docs/features/INDEX.md` | everyone | Edit **only your own rows** (owner, status) in the last commit of a feature |

## Shared setup (Step 0) — already done
`models_ext/`, `privacy.py`, one router per line in `main.py`, and `frontend/src/api_ext/` are on `main` (see the playbook §6). Pull first, then use them; do not create your own versions.

## Rhythm
- Everyone commits directly to `main`, in small steps. Before every push: `git pull --rebase origin main`, run `pytest`, `npm run typecheck`, `npm run build`, then `git push origin main` (exact routine in [TEAMMATE-PROMPT.md](TEAMMATE-PROMPT.md)). Never force-push.
- Pull at the start of every session and push at the end of every session, so nobody works on stale code.
- **Push cutoff:** no pushes after the time on your prompt's `PUSH CUTOFF` line (default 2026-10-02 20:00 IST), or earlier if Abhinav writes `PUSH CUTOFF: now`. Commit locally and wait.
- Each finished feature ends with a hand-off note (what changed, how it was tested, what was **not** verified live) — in the last commit message and as a message to Abhinav.
