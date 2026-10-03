# Universal prompt for starting work (everyone works on `main`)

**How to use**
1. Open the repo folder (`SAARTHI_AI`, your own clone) in Claude Code (or paste into any AI coding assistant).
2. Copy the whole prompt below, **fill the lines in "MY ASSIGNMENT"** with your name and group (`Group 1` or `Group 2`; see [TEAM-SPLIT.md](TEAM-SPLIT.md)), and paste it as your first message.
3. The assistant must show you its plan for today's slice of your first feature and wait for your OK before it writes code.

Abhinav: the only parts that differ between teammates are the `MY ...` lines and the two switch lines (`RED ZONES CLEARED FOR ME`, `PUSH CUTOFF`). The feature lists and today's slices are in [TEAM-SPLIT.md](TEAM-SPLIT.md).

---

````text
You are helping me build features for SAARTHI, an adaptive AI mentor for learners (FastAPI backend, React + Vite frontend,
SQLAlchemy with SQLite locally and Supabase Postgres later). The work is divided into specs in docs/features/. I am one of two
teammates; the project owner is Abhinav. Everyone works directly on the `main` branch, so main must stay working at every
push. What is on main at the push cutoff is shown on stage at tomorrow's hackathon demo (3 Oct 2026), so today's work is a small,
safe, visible slice of each feature (section 1b). Follow this prompt exactly. If anything here conflicts with what I say later, stop and ask me.

## MY ASSIGNMENT (filled in by me)
MY NAME: <your name>
MY GROUP: <Group 1 OR Group 2>
MY FEATURES, IN ORDER:
  <!-- If Group 1 (Conversations & Interview): -->
  Group 1: C03, T07, C04, T11, T08
  (Today's demo slices: C03 then T07 -> details: docs/features/TEAM-SPLIT.md#group-1--conversations-and-interview-work-in-this-order)

  <!-- If Group 2 (Progress & Planning): -->
  Group 2: T04, T06, T03, T05, T01, C06
  (Today's demo slices: T04, T06, then T03 -> details: docs/features/TEAM-SPLIT.md#group-2--progress-and-planning-work-in-this-order)
RED ZONES CLEARED FOR ME: none      (Abhinav changes this only if he hands a red-zone feature to me, e.g. "C05")
PUSH CUTOFF: 2026-10-02 20:00 IST   (after this time nobody pushes; Abhinav may change it, or write "now" to stop all pushes immediately)

## 1. Working on main safely (do this first, every session)
- We all commit to `main`. That is allowed ONLY if every push is small, tested and leaves the app working. Never push something
  that fails the tests, the typecheck or the build, and never push a half-finished screen that is reachable from the UI
  (finish it first, or leave it unmounted until it works).
- Check the time before every push with `date` (times are IST). If it is later than PUSH CUTOFF, or PUSH CUTOFF says "now": do not push. Commit locally
  only and tell me. Anything not pushed by the cutoff is not part of the demo.
- NEVER use: `git push --force` / `--force-with-lease`, `git reset --hard`, `git clean -fd`, `git checkout -- .`, `--no-verify`,
  `git commit --amend` on a commit that was already pushed, or `git rebase -i`. Never delete or rewrite history on origin.
  Never create or switch to other branches unless Abhinav tells me to.
- First commands every session, in order (show me the output of each):
    git status
    git branch --show-current        (must print: main)
    git fetch origin
    git pull --rebase origin main
  If `git status` shows uncommitted changes I did not expect, or the branch is not main, stop and tell me.
- Before EVERY push, in this order:
    1. git status                                        (only the files I mean to commit)
    2. git pull --rebase origin main                     (bring in the other people's work first)
    3. cd backend && python -m pytest -q                 (all green)
    4. cd ../frontend && npm run typecheck && npm run build   (both green)
    5. git push origin main
  If the push is rejected, repeat from step 2. If `git pull --rebase` reports a conflict, stop: show me the conflicting files; if a
  file belongs to the other teammate or to Abhinav (see docs/features/TEAM-SPLIT.md), ask before resolving. After resolving,
  run the tests again before pushing. Use `git rebase --abort` if I say I want to back out.
- Stage files by name (`git add path/to/file`), never `git add .` or `git add -A`. Before committing run `git status` and
  `git diff --cached --stat` and show me. `.env`, `.env.local`, data/*.db, node_modules, dist, __pycache__ must never be staged.
- Commit messages: `feat(<SPEC-ID>): short summary` (or `fix(...)`, `test(...)`, `docs(...)`), a blank line, a few lines of why.
  Small commits, one logical change each. Push at least at the end of every working session so others get your changes.

## 1b. Today's scope (the demo is tomorrow)
- docs/features/TEAM-SPLIT.md has a section "Today" with the slice to build for each feature and what to skip. Build ONLY that slice for my first
  feature, push it, and only then start the next one. Do not try to complete a whole spec today.
- Additive only: do not change how the existing demo path behaves (docs/DEMO.md: login, placement, dashboard, learn / teach-back, SQL practice,
  roadmap, mentor case). New things appear next to the old ones. Existing endpoints keep their response shape (adding fields is fine).
- Fail soft: if my new endpoint errors, my card/button must disappear or show a small message; it must never break the page around it.
- Before every push also do the quick smoke check, with SAARTHI_LLM_MODE=fake: start the app (run-dev.bat), sign in (mock), Settings > Demo tools >
  "Load a demo starting history", then Dashboard, one concept page (Learn) and Roadmap. My feature must be visible and the rest unchanged.
  Tell me exactly what I should click and look at; I will confirm it.
- I do not need real Gemini or ElevenLabs keys for this work; Abhinav tests the live parts. Do not ask me for keys unless a spec step truly needs them.

## 2. Read before coding (in this order, then summarise to me)
1. docs/features/00-PLAYBOOK.md   (rules, recipes, hot-spot files)
2. docs/features/INDEX.md and docs/features/TEAM-SPLIT.md   (who owns which files; hand-offs)
3. The spec for my first feature in docs/features/ (e.g. T03-...md) and any spec it depends on.
4. The SAARTHI files that spec names under "What SAARTHI already has".
The source projects TESSA and Chhatrachhaya are READ-ONLY idea references. Open them only to read the files the spec cites.
Never edit, commit into, or copy code/UI/content/keys from them. Re-implement the idea in SAARTHI's own structure.

## 2b. Red zones and parked features (check BEFORE planning any feature)
In docs/features/TEAM-SPLIT.md and INDEX.md some features are marked 🚧 RED ZONE (currently D01, C07, C01, C02, C05, C08): Abhinav is
building them himself, and each of those specs starts with a "RED ZONE" banner. Some are marked ⏸ PARKED (currently T09, T10, T02).
- Before you plan or write anything for a feature, open its spec and the TEAM-SPLIT table and check its marker.
- If the feature is a 🚧 red zone and it is NOT listed on my line "RED ZONES CLEARED FOR ME", do NOT start it. Stop, and tell me
  exactly this: "<ID> is a red zone owned by Abhinav. I will not start it unless he clears it for you. Do you want to continue
  with <next feature from MY FEATURES> instead?" Then wait.
- If the feature is ⏸ parked and Abhinav has not asked for it, treat it the same way.
- If I insist in chat that I may take a red zone, still warn me once and ask me to have Abhinav add it to my "RED ZONES CLEARED FOR ME"
  line (or confirm in writing), because the red-zone features share files and must land in a fixed order.
- Reading a red-zone spec to understand code that my feature touches is fine. Editing red-zone files beyond the small, named
  hand-off edits in TEAM-SPLIT.md is not.

## 3. Prerequisite check
Step 0 shared setup (playbook section 6) is on main: backend/app/models_ext/ (your tables go there, one file per spec), backend/app/privacy.py
(register your export/delete hooks there; do not edit routes/core.py for that), one router per line in backend/app/main.py, and
frontend/src/api_ext/ (your API calls; `req` is exported from frontend/src/api.ts). After pulling, check they exist.
If they do not, STOP and tell me; do not create your own version.

## 4. Local setup rules (protect shared data and secrets)
- Develop against local SQLite: leave DATABASE_URL EMPTY in backend/.env. Do NOT point your local app at the shared Supabase
  project (new tables/columns would appear there, and create_all does not alter existing tables).
- Keep SAARTHI_AUTH=mock, SAARTHI_MENTORS=mock, SAARTHI_CONSENT=mock, SAARTHI_COHORT=mock while developing. Tests pin these themselves.
- Never print, paste, log or commit API keys, passwords, tokens or the contents of .env files. If a real key is needed, ask me.
  .env.example files hold placeholders only.
- Never modify the TESSA folder or the Chhatrachhaya clone.

## 5. How to work on each feature
1. Tell me, in at most 12 lines, your plan for the feature: files to create/touch, tables, endpoints, tests, what you will NOT do.
   WAIT for my "go" before writing code.
2. Follow the spec's sections: rules, data, engine, routes, frontend, tests, done-when. Follow docs/features/00-PLAYBOOK.md section 4
   (the 8 non-negotiable rules): only question/work_product/explain_back/mentor evidence moves mastery; no invented numbers;
   the model proposes and code decides; fail closed; mock/real via adapters with contract tests; export + delete cover every new
   learner table; minors protected on the server; safety wording not weakened.
3. Add tests as you go (backend/tests/test_<feature>.py) — test the rules, not just the happy path.
4. Work in steps that each leave main working (follow the spec's "suggested order of work"). A new table, engine, route or test can
   be pushed as soon as it is green; a new screen or button is pushed only when it works end to end.
5. Run the full check from section 1 before every push, and show me the results. If something that was passing now fails,
   find out why; never delete or weaken a test to get green.
6. Edit only the files your feature needs. Respect the shared-file rules in TEAM-SPLIT.md (append, don't reorder; new routes in new
   files; new tables in models_ext/<spec>.py; new API calls in api_ext/<spec>.ts; i18n keys named <SPEC>.<screen>.<name>).
7. At the end of a feature: update only MY rows in docs/features/INDEX.md (owner, status) and, if you deviated from the spec,
   update the spec so it records what was really built. Push.
8. Do not start the next feature until I say so.
9. Priority: features are marked in docs/features/TEAM-SPLIT.md (red circle = Tier 1 build first, yellow circle = Tier 2, construction sign = red zone
   owned by Abhinav, pause sign = parked). Work Tier 1 in the listed order. Do NOT start a Tier 2 feature until my Tier 1 is done and I have told
   Abhinav, and never start a red-zone or parked feature (section 2b). When my Tier 1 is done, say so and wait.

## 6. Hand-off note (instead of a pull request)
When a feature (or a meaningful step of one) is pushed, write me a short note for Abhinav that I can paste into our chat: what changed
(files, tables, endpoints, screens); which playbook rules it touches and how each is honoured; new env vars; new tables (and any manual SQL);
how it was tested (commands and results); and "NOT verified live:" listing anything you could not check (real e-mail, Google, Adzuna,
real STT, real Gemini, Postgres...). Put the same content in the body of the last commit of the feature.

## 7. Communication and honesty
- Ask when the spec is ambiguous or when a change would touch the other teammate's files. Do not guess.
- Report outcomes plainly: if tests fail, show the output; if a step was skipped, say so; do not claim something works unless
  you ran it.
- Never expand scope beyond the spec I am working on (no drive-by refactors, no reformatting of existing files).
- If you notice a bug or risk outside my spec, tell me instead of fixing it silently.
- If you broke main (tests or build fail after a push, or the app does not start), tell me immediately and fix forward with a new
  commit or `git revert <your commit>` — never by rewriting history.

Now: do section 1 (check branch and sync), section 1b (today's scope), section 2 (read and summarise), section 2b (red-zone check of my first feature),
section 3 (prerequisite check), then give me the plan for my first feature and wait.
````

## Notes for Abhinav

- Give each teammate their filled `MY ...` block:
  - **Group 1 — Conversations and interview:** [Group 1 specs in TEAM-SPLIT.md](TEAM-SPLIT.md#group-1--conversations-and-interview-work-in-this-order)
    ```text
    MY NAME: <teammate name>
    MY GROUP: Group 1
    MY FEATURES, IN ORDER: C03, T07, C04, T11, T08
    RED ZONES CLEARED FOR ME: none
    PUSH CUTOFF: 2026-10-02 20:00 IST
    ```
    *(Today's demo slices: C03 prep/summary cards, then T07 grounded typed chat)*

  - **Group 2 — Progress and planning:** [Group 2 specs in TEAM-SPLIT.md](TEAM-SPLIT.md#group-2--progress-and-planning-work-in-this-order)
    ```text
    MY NAME: <teammate name>
    MY GROUP: Group 2
    MY FEATURES, IN ORDER: T04, T06, T03, T05, T01, C06
    RED ZONES CLEARED FOR ME: none
    PUSH CUTOFF: 2026-10-02 20:00 IST
    ```
    *(Today's demo slices: T04 streak card, T06 progress-over-time chart, then T03 feedback buttons)*

- `RED ZONES CLEARED FOR ME: none` is the default. If you are busy or unavailable and want a teammate to take a red-zone feature, change that line to the feature id (e.g. `C05`) in their copy. Without it, their assistant stops and warns them.
- `PUSH CUTOFF` defaults to **2026-10-02 20:00 IST**. Change the time in their copy if you want more or less evening for verification, or write `PUSH CUTOFF: now` to stop pushes at once. Their assistants check the clock with `date` before every push.
- **After the cutoff:** `git pull`, run the pre-flight in `docs/DEMO.md`, and present from a tag so a late stray push cannot change the demo: `git tag demo-final && git push origin demo-final`, then `git checkout demo-final` on the demo machine. `demo-baseline` is the fallback (the last commit before teammate work started today).
- With everyone on `main`, a broken push breaks everyone's checkout. Cheap protection: in GitHub (Settings → Branches) block force-push and deletion on `main`, without requiring pull requests.
- The prompt tells them to use local SQLite. Do not give them the Supabase `DATABASE_URL` until a feature is ready for a joint integration test.
