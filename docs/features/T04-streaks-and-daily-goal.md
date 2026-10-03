# T04 — Study streak and daily goal

| | |
|---|---|
| Source | TESSA — study streak, streak freeze, daily target, 7-day habit bar |
| SAARTHI today | **Missing.** The dashboard shows mission, skill graph, roadmap, calibration, cases. Nothing about habit or consistency. |
| Priority / size | P1 / S (1 day) |
| Depends on | nothing. Optional later: C05 (a gentle "streak at risk" notification) |
| External accounts | none. **No new table** — everything is computed from existing evidence. |

## 1. What the learner gets

A small card on the dashboard: current streak, best streak, a 7-day bar (which days they really practised), today's goal progress
("2 of 3 activities today"), and how many streak freezes they hold. A **study day** is a day on which they did something SAARTHI
can see: answered a check, ran graded SQL, did a teach-back/interview answer, or had a mentor session recorded. There is no
"I studied" button — you cannot fake a streak. Learners (especially under 18) can hide streaks in Settings.

## 2. How it works in TESSA (the source idea)

| What | File and place (relative to TESSA root) |
|---|---|
| Profile fields `current_streak`, `longest_streak`, `last_active_date`, `activity_history`, `daily_goal_minutes` (=45), `streak_freeze_count` | `backend/app/schemas.py` `LearnerProfile` (l.78–121) |
| Check-in: first session, same day, +1 on consecutive day, **freeze saves a single missed day**, otherwise reset to 1 | `backend/app/api/profile.py` `check_in()` (l.367–439) |
| Daily goal setter (5–480 min) | `profile.py` `set_streak_target()` (l.446–456) |
| Claim a freeze (max 2) | `profile.py` `add_streak_freeze()` (l.459–473) |
| UI: flame hero, best/total/freezes pills, 7-day bar, status sentence | `public/index.html` `renderProfile()` streak block (l.4260–4330), `logStudyCheckIn()` (l.4177–4197), `setDailyStreakTarget()` (l.4199–4213) |

Tech there: plain Python date arithmetic, JSON profile in a process-local store, vanilla JS rendering.

### Do not copy
- **The check-in is self-reported and client-dated**: `today = req.date or date.today().isoformat()` (`profile.py` l.373). Anyone can
  send any date or minutes and mint a streak. SAARTHI derives streaks from stored evidence on the server.
- Freezes handed out for free by a button (l.459–473). Earn them instead (see 4.1).
- `minutes` as the goal unit. SAARTHI has no reliable study-time measurement; claiming minutes would be an invented number.
- Guilt copy ("streak lost!"). Keep messages neutral and kind.

## 3. What SAARTHI already has

- `EvidenceEvent(created_at, source_type)` — the truth about what the learner did (`backend/app/models.py`).
- `mastery.learner_now(learner)` — "now" including the dev **advance-time** offset, so the demo tool moves streaks too.
- `Learner.settings` (JSON) for the daily goal and the hide toggle.
- `Ring`, `Bar`, `SectionTitle` in `frontend/src/components/ui.tsx`; Dashboard layout in `pages/Dashboard.tsx` (right column of cards).

## 4. How to adapt it

### 4.1 Definitions (put these in the module docstring and in tests)
- **Activity** = one `EvidenceEvent` with `source_type ∈ {question, work_product, explain_back, mentor}` (the same set as
  `MASTERY_SOURCES`). `feedback` and `self_report` do **not** count. Events with `grader == "simulated"` (the demo helpers) do not
  count either, otherwise `Load a demo starting history` would hand out a streak.
- **Study day** = a calendar day in the learner's local time with ≥ 1 activity. Use a fixed IST offset
  (`timezone(timedelta(hours=5, minutes=30))`) to convert `created_at` (naive UTC) to a local date. Do **not** use `zoneinfo` named
  zones — on Windows they need the extra `tzdata` package and the build machines would break.
- **Daily goal** = number of activities per day (1–10, default 3). Stored in `Learner.settings["daily_goal"]`.
- **Streak** = consecutive study days ending today or yesterday. If today has no activity yet the streak is still alive until the
  day ends.
- **Freezes**: earn one for every 7 consecutive study days, hold at most 2; a freeze is consumed automatically when **exactly one**
  day is missed. A gap of two or more days resets the streak to 0.

### 4.2 Engine `backend/app/engines/streak.py`
Write a **pure function** first — it is trivial to test:

```
summarize(active_days: set[date], today: date, daily_goal: int, activities_today: int) -> {
  current, longest, freezes, freeze_used_on: list[date], today_active: bool,
  goal_met_today: bool, week: [{date, active, count}], total_active_days }
```
Then a thin DB wrapper `for_learner(db, learner)` that loads event dates (one query, `created_at` for the learner, filtered by source
and `grader != "simulated"`), converts to local dates, calls `summarize`. The function replays history day by day from the first
active day so the freeze rule is deterministic (no stored state to corrupt).

### 4.3 Routes — new `backend/app/routes/streak.py`
| Method + path | Body | Returns |
|---|---|---|
| `GET /api/streak` | — | the `summarize` dict plus `show: bool` |
| `PATCH /api/streak/settings` | `{daily_goal?: int 1..10, show?: bool}` | updated settings |

Add `streak` to the `/api/dashboard` response (small payload) so the dashboard does not need an extra call.

### 4.4 Frontend
`components/StreakCard.tsx` (flame/number, best, freezes, 7 dots, a `Bar` for today's goal, a gear for the goal). Add it to
`Dashboard.tsx` in the right-hand column. Respect `show === false` (render nothing). Add strings to `DICT`.
Message examples (EN): "3-day streak", "One more activity keeps it going today", "A freeze kept your streak alive yesterday".

## 5. Files to create / touch
`engines/streak.py` (new), `routes/streak.py` (new, register in `main.py`), `routes/core.py` (`dashboard()` add `streak`; settings are already part of the export), `frontend/src/components/StreakCard.tsx` (new), `pages/Dashboard.tsx`, `pages/Settings.tsx` (goal + hide toggle),
`frontend/src/api_ext/T04.ts`, `backend/tests/test_streak.py` (new).

## 6. Tests (minimum)
1. `summarize` table-driven: no events; one day; 5 consecutive days; missed one day with a freeze; missed one day without; missed
   two days; 7-day run earns a freeze; max 2 freezes; longest vs current.
2. IST boundary: an event at 20:00 UTC (01:30 IST next day) is counted on the **IST** date.
3. `feedback`, `self_report` and `grader="simulated"` events never count.
4. Through the API: answer one MCQ ⇒ `today_active` true; **advance-time** by 1 day ⇒ streak still alive; by 3 days ⇒ reset.
5. Settings validation: goal 0 or 11 ⇒ 422; another learner's settings untouched.
6. Isolation: learner B's events never affect learner A's streak.

## 7. Done when
- [ ] Dashboard card shows current/best streak, 7-day bar, goal progress, freezes; goal editable; can be hidden.
- [ ] It cannot be gamed from the client (no endpoint accepts a date or minutes).
- [ ] The demo "advance time" tool visibly moves the streak; the demo "seed history" does not grant one.
- [ ] Tests above pass.

## 8. Risks and traps
- Query cost: one indexed query on `evidence_events.learner_id`; don't load whole rows (`select(EvidenceEvent.created_at, EvidenceEvent.source_type, EvidenceEvent.grader)`).
- Streaks create pressure. For under-18 learners default `show` to **true** but never send push/email nudges about it (C05 rule).
- Do not store the streak. A stored counter drifts when evidence is deleted or the dev clock moves; recomputation cannot.
