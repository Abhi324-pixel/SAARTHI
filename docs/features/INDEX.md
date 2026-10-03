# SAARTHI feature specs — index

**Start here.** Read [`00-PLAYBOOK.md`](00-PLAYBOOK.md) once (≈ 30 min), then [`TEAM-SPLIT.md`](TEAM-SPLIT.md) to see which features are yours and which are 🚧 red zones, then open your specs. Every spec uses the same sections:
what the user gets → **how it works in the source project (exact files and lines)** → what SAARTHI already has → how to adapt it → files to touch → tests → "done when" → risks.

- **T** = idea from **TESSA** (`D:\Hackathon projects\TESSA` — ask Abhinav for a copy; paths are relative to its root).
- **C** = idea from **Chhatrachhaya** (<https://github.com/mrgraciz123/chhatrachhayaa>; paths relative to the repo root).
- **D** = a gap in SAARTHI's own demo/safety flow (not from either source).
- Both source projects are **read-only**. We re-implement ideas; we copy no code, UI, content or keys.
- File/line references were checked against the local copies on 2026-10-02. Sizes are rough estimates (S ≤ 1 day, M 2–3 days, L 4–6 days), not commitments.

## The list

**Marker** (details in [TEAM-SPLIT.md](TEAM-SPLIT.md)): 🔴 build first · 🟡 next · 🚧 **red zone — Abhinav's, do not start** · ⏸ parked, not planned for now. Finish all 🔴 before starting a 🟡.

| ID | Tier | Feature | Source | SAARTHI today | Priority | Size | Depends on | Needs external account | Owner | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| [D01](D01-guardian-consent-flow.md) | 🚧 | Real guardian consent for under-18s **(+ a security fix)** | SAARTHI gap | Mock works; real mode is safe but has no way to reach a guardian (**Step 0 self-approval hole fixed 2026-10-02**) | **P0 safety** | M (rest of the spec) | C07 helper (recommended) | outgoing e-mail (SMTP), mock first | Abhinav | ✅ built 2026-10-02 (real mailbox untested) |
| [C07](C07-google-sign-in.md) | 🚧 | "Continue with Google" + mandatory age step | Chhatrachhaya | Missing (e-mail/password only); OAuth would default to age 20 | P1 | S–M | — | Google Cloud OAuth client (set in Supabase) | Abhinav | ✅ built 2026-10-02 (Google itself untested) |
| [C01](C01-mentor-signup-verification-pledge.md) | 🚧 | Mentor sign-up, human verification record, pledge | Chhatrachhaya | Missing (seeded mentors only) | P1 (pilot) | M–L | — | — | Abhinav | ✅ built 2026-10-02 (real accounts untested) |
| [C02](C02-mentor-console.md) | 🚧 | Mentor console + safeguarding view | Chhatrachhaya (idea) | Missing — real mentors hit a dead end | P1 (pilot) | L | C01 | — | Abhinav | ✅ built 2026-10-02 (real accounts untested) |
| [C05](C05-notifications-and-unread-badges.md) | 🚧 | In-app notifications + unread badges | Chhatrachhaya | Missing | P1–P2 | M | (C02 for mentor events) | — | Abhinav | ✅ built 2026-10-02 |
| [C04](C04-live-chat-updates.md) | 🟡 | Live updates in case chat (polling) | Chhatrachhaya | Partial (loads once) | P2 | S | (C02) | — | Abhay | ☑ |
| [C03](C03-session-prep-notes-and-summaries.md) | 🔴 | Learner prep notes + session summary + dated follow-up | Chhatrachhaya (README only) | Partial (mentor side only) | P1 (demoable now) | M | — | — | Abhay | ☑ |
| [C06](C06-learner-profile-page.md) | 🟡 | Profile page with real activity numbers + privacy panel | Chhatrachhaya | Partial (Settings only) | P2 | S | (C07 birth year) | — | Abhay | ☑ |
| [C08](C08-hindi-first-interface.md) | 🚧 | Fully Hindi / Hinglish interface | Chhatrachhaya (tone) | Partial (13 keys; ~300 strings hard-coded) | P2 | L | — (do last, or add keys as you go) | native Hindi reviewer | Abhinav | ☐ |
| [T03](T03-difficulty-and-preference-feedback.md) | 🔴 | "Too easy / too hard / helped" that adapts the plan | TESSA | Missing | P1 | S–M | — | — | Abhay | ☑ |
| [T04](T04-streaks-and-daily-goal.md) | 🔴 | Streak + daily goal (derived from evidence) | TESSA | Missing | P1 | S | — | — | Abhay | ☑ |
| [T06](T06-progress-over-time-chart.md) | 🔴 | Progress-over-time chart + skill radar | TESSA | Partial (current value only) | P1 | S–M | — | — | Abhay | ☑ |
| [T05](T05-milestones-deadlines-checkpoints.md) | 🟡 | Roadmap phases, deadlines, personal checkpoints | TESSA | Missing | P2 | M | — | — | Abhay | ☑ |
| [T01](T01-free-text-goal-intake.md) | 🟡 | Free-text goal / conversational intake | TESSA | Partial (form only) | P2 | M | — | — | Abhay | ☑ |
| [T07](T07-typed-assistant-chat.md) | 🔴 | Typed assistant chat (grounded) | TESSA | Partial (only inside a voice session) | P2 | M | — | — | Abhay | ☑ |
| [T11](T11-speaking-pace-and-filler-coaching.md) | 🟡 | Speaking pace / pauses / filler-marker coaching | TESSA | Missing | P2 | M | — (verify STT payload first) | — | Abhay | ☑ |
| [T08](T08-behavioural-interview-and-company-packs.md) | 🟡 | HR / behavioural round + role packs | TESSA | Partial (technical round only) | P2 | L | — (content review needed) | — | Abhay | ☑ |
| [T09](T09-resume-upload-and-parsing.md) | ⏸ | Resume upload, validation, parsing | TESSA | Missing | P3 | M | T01 | — (new dependency `pypdf`) | | ☐ |
| [T10](T10-job-matching-and-skill-gap-sync.md) | ⏸ | Live jobs + evidence-based match + "add gaps to plan" | TESSA | Missing | P3 | L | T01 | Adzuna developer account | | ☐ |
| [T02](T02-resource-discovery.md) | ⏸ | "More ways to learn this" (curated, optional live search) | TESSA | Missing | P3 | A: S–M · B: L | (T03) | Phase B: Tavily key | | ☐ |

Also read [`99-NOT-BUILDING.md`](99-NOT-BUILDING.md): 20 things in the sources that we deliberately do not build, and why.

## Suggested order of work

1. **Shared setup (Step 0, playbook §6)** — ✅ done and on `main`.
   **Today (demo is tomorrow):** build only the small slices listed under "Today" in [TEAM-SPLIT.md](TEAM-SPLIT.md), and stop pushing at the cutoff.
2. **🚧 Red zones — Abhinav, in this order:** D01 → C07 → C01 → C02 → C05 → C08. (The D01 self-approval hole is already fixed.) Teammates do not start these unless Abhinav hands one over.
3. **Group 1 — Conversations and interview:** 🔴 C03 → T07, then 🟡 C04 → T11 → T08.
4. **Group 2 — Progress and planning:** 🔴 T04 → T06 → T03, then 🟡 T05 → T01 → C06.
5. **⏸ Parked:** T09, T10, T02 — not planned for now.

## Who builds what

Abhinav takes the 🚧 red-zone features; the two teammates split the rest into two groups — see [TEAM-SPLIT.md](TEAM-SPLIT.md) for the order of work, shared files and hand-offs.
To start a session safely (everyone works on `main` with a fixed pull–test–push routine, and a warning if you pick up a red zone), use the universal prompt in [TEAMMATE-PROMPT.md](TEAMMATE-PROMPT.md).

## Rules that apply to every spec (full text in the playbook §4)

1. Only `question`, `work_product`, `explain_back`, `mentor` evidence moves mastery. Feedback and self-reports are recorded, never counted.
2. No invented numbers (no percentile, match %, scores without a formula you can show).
3. The model proposes, code decides; validate every id the model returns; quotes must be verifiable.
4. Fail closed: no model, no grade, nothing recorded.
5. Mock vs real = adapter + switch + contract tests; real misconfiguration refuses to start.
6. Learner data rights: export + delete cover every new table.
7. Minors are protected on the server; age is self-declared and unconfirmed means minor.
8. Safeguarding wording and screening are not weakened.

## Keeping this folder honest

- When you finish a spec: tick Status, put your name in Owner, link the commit, and **update the spec** if you deviated (the spec is the record of what was built and why).
- If a source file reference is wrong or has moved, fix it here — future readers rely on it.
- Say plainly in each hand-off note what was **not** verified live (Google sign-in, real e-mail, real Adzuna, real STT payload, etc.).
