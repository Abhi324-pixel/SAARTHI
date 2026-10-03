# T05 — Roadmap phases, deadlines and personal checkpoints

| | |
|---|---|
| Source | TESSA — milestones with target dates, custom milestone checkpoints |
| SAARTHI today | **Missing.** The roadmap is a flat ordered list grouped by week (`pages/Roadmap.tsx`). There are no phases, no dates, and no way to say "I need SQL done by my exam on 20 Dec". |
| Priority / size | P2 / M (2–3 days) |
| Depends on | nothing. Related: T04 (dates), T06 (progress chart can mark deadlines) |
| External accounts | none |

## 1. What the learner gets

1. **Phases**: the roadmap is grouped into a few named phases (e.g. "Python basics → SQL → Backend") with a target date for each,
   derived from their weekly hours.
2. **Own deadlines**: they can set "I need this phase done by <date>". SAARTHI then says plainly whether the plan gets there:
   "At 6 h/week SQL finishes around 21 Nov — 10 days after your deadline. To make it: 8 h/week (see what-if), or move the date."
   No guilt, no automatic cutting of content.
3. **Personal checkpoints**: small dated goals ("finish all JOIN tasks by Sunday"). A checkpoint **linked to a concept completes by
   itself when the evidence says the concept reached its target**; free-text checkpoints ("apply for 3 internships") can be ticked by hand.
4. **"Check me on this phase"** instead of "mark phase complete": a short mixed check across the phase's concepts that produces real evidence.

## 2. How it works in TESSA (the source idea)

| What | File and place (relative to TESSA root) |
|---|---|
| Phases ("milestones") are buckets of ~N hours; each ends with a **project** (25 % of the bucket's hours) and a **checkpoint assessment** (1 h); target date = start + weeks | `backend/app/engines/planner.py` `_bucket()` (l.451–571; dates at l.553), `_milestone_title()` (l.582–) |
| Milestone data model (`start_week`, `end_week`, `target_date`) | `backend/app/schemas.py` `Milestone` (l.191–200) |
| Set a deadline for a phase | `backend/app/api/profile.py` `set_milestone_target()` (l.220–266) |
| Personal checkpoints: add / toggle / delete | `profile.py` (l.269–313); fields `custom_milestones`, `milestone_deadlines` in `LearnerProfile` (schemas.py l.113–115) |
| "Complete a whole phase" button | `profile.py` `complete_entire_milestone()` (l.316–358) |
| UI | `public/index.html` `renderProgress()` phase ledger (l.4051–4061), `updateMilestoneDeadline()` (l.4081–4100), `addCustomMilestone()` / `toggleCustomMilestone()` / `deleteCustomMilestone()` (l.4118–4173) |

Tech there: NetworkX topological order, plain dates, JSON profile in a process-local store.

### Do not copy
- **`complete_entire_milestone`** marks every item "done" and credits mastery with no evidence (`profile.py` l.328–336). SAARTHI must
  never mark learning done without evidence (playbook rule 1). Use "Check me on this phase".
- `start_date = dt.date.today()` on every rebuild (`planner.py` l.468) — all target dates slide forward each time the plan is
  recalculated, so a learner can never be "late". SAARTHI stores a fixed **plan start date**.
- Free "projects" injected as 25 % of hours with no content behind them. Only add a project/assessment step when SAARTHI has real
  content for it (it does: SQL tasks and explain-back rubrics).

## 3. What SAARTHI already has

- `planner.build()` returns ordered `items` each with `week`, `minutes`, `domain` and a `summary` (`engines/planner.py` l.32–151).
  `Roadmap.tsx` groups by week. `content/roles.json` has `domain_priority` (`["sql","python","backend","tools"]`).
- `planner.what_if()` (l.298–302) already answers "what if I changed my hours" — reuse it to offer the fix.
- `diagnostic.next_probe(count, concept_id)` — build the phase check from it.
- `mastery.concept_views()` for "target reached" (`p ≥ DONE_RATIO × target`, `planner.DONE_RATIO = 0.95`).

## 4. How to adapt it

### 4.1 Phases are derived, never stored
Write a pure function `phases(items) -> list[Phase]` in `backend/app/engines/phases.py`: walk the ordered non-review items and open a
new phase whenever `domain` changes (runs of the same domain = one phase). A phase has `{key, title, concept_ids, start_week,
end_week, minutes}`; `key = f"{domain}"` (+ `-2` if a domain appears twice). Titles: a small dictionary per domain, EN/Hinglish
(e.g. `sql → "SQL"`, `backend → "APIs & backend"`). Put the dictionary in `store.tsx`'s `DICT` style or a JSON file so C08 can translate it.
Add `phases` to the `GET /api/roadmap` response (`routes/core.py` `roadmap()`); do not change item order or planner maths.

### 4.2 Plan start date and target dates
- `Learner.settings["plan_start"]` = ISO date, set the first time a roadmap is generated (onboarding) using `mastery.learner_now`.
  Never reset it on rebuild (see "do not copy").
- Phase `target_date = plan_start + 7·end_week` days.
- Learner deadline: `Learner.settings["deadlines"] = {"<phase key>": "2026-12-20"}`.

### 4.3 Deadline check (deterministic, explained)
`deadline_status(phase, deadline, weekly_hours, today)`:
`weeks_left = (deadline − today)/7`; `minutes_needed = Σ minutes of items in this phase and every earlier phase not yet at target`;
`hours_needed_per_week = minutes_needed / 60 / weeks_left`. Return `{on_track: bool, projected_finish: date, gap_days, needed_hours_per_week}`.
Reason code `DEADLINE_RISK` with those numbers; the UI offers three honest options: raise hours (opens the existing what-if slider
pre-filled with `needed_hours_per_week`), move the date, or see what would be dropped (`summary.dropped`). Never auto-drop items.
If `weeks_left ≤ 0` say "this date has passed".

### 4.4 Personal checkpoints — new table `learner_checkpoints` (`models_ext/T05.py`)
`id, learner_id (FK CASCADE), title (≤120), due_date (date, nullable), concept_id (nullable, validated), done_at (nullable), created_at`.
- If `concept_id` is set the checkpoint's `done` is **computed** from `concept_views` (target reached) and the manual toggle endpoint
  returns 409 ("this one completes when your check shows you've got it").
- Include in `GET /api/me/export` and the delete cascade.

### 4.5 "Check me on this phase"
`POST /api/phases/{key}/check` → picks up to 5 unseen MCQs across the phase's concepts that are *not yet at target*
(use `diagnostic.next_probe` per concept, weakest first) and returns them for `QuizRunner`; answers go through the normal
`/api/probe/answer` so evidence, misconceptions and roadmap refresh all work unchanged.

### 4.6 Routes — new `backend/app/routes/phases.py`
| Method + path | Notes |
|---|---|
| `PUT /api/phases/{key}/deadline` | `{date}`; must be in the future and ≤ 2 years; stores in settings; returns `deadline_status` |
| `DELETE /api/phases/{key}/deadline` | removes it |
| `POST /api/phases/{key}/check` | see 4.5 |
| `GET /api/checkpoints` / `POST` / `PATCH /{id}` / `DELETE /{id}` | CRUD, all scoped to the learner; `PATCH` can toggle only free-text checkpoints |

### 4.7 Frontend
`Roadmap.tsx`: wrap the week groups in phase headers (title, week range, target date chip, deadline picker, status line, **Check me**
button). New `components/Checkpoints.tsx` (list + add form with optional concept dropdown) on the Roadmap page aside. Add strings to `DICT`.

## 5. Files to create / touch
`engines/phases.py` (new), `engines/planner.py` (no maths change; optional `plan_start` helper), `routes/phases.py` (new),
`routes/core.py` (`roadmap()` adds `phases`; checkpoints + deadlines are registered with `privacy.register_export` from `models_ext/T05.py`; `onboard()` sets `plan_start`),
`models_ext/T05.py` (new), `frontend/src/pages/Roadmap.tsx`, `frontend/src/components/Checkpoints.tsx` (new),
`frontend/src/api_ext/T05.ts`, `backend/tests/test_phases.py` (new).

## 6. Tests (minimum)
1. `phases()` on a hand-built item list: runs of equal domain merge; weeks are contiguous; deterministic.
2. Rebuilding the roadmap does **not** change `plan_start` or any phase target date (unless hours change the week numbers).
3. `deadline_status`: on-track, late by N days, impossible (weeks_left ≤ 0), needed hours computed exactly (table test).
4. Concept-linked checkpoint: cannot be toggled; becomes done after evidence takes the concept to target; free-text one can be toggled.
5. Another learner cannot read/edit my checkpoints (404). Deadline in the past → 422.
6. `POST /phases/{key}/check` returns only unseen items for concepts below target; after answering, evidence exists (not a "complete" flag).
7. No endpoint changes `ConceptState` without going through `apply_evidence` (assert via a spy or by checking `EvidenceEvent` rows).

## 7. Done when
- [ ] Roadmap shows phases with target dates; learner can set/clear a deadline and sees an honest on-track/late statement with the exact hours needed.
- [ ] Personal checkpoints work; concept-linked ones complete only from evidence.
- [ ] No way to mark learning "complete" without evidence.
- [ ] Hindi/Hinglish strings for the new labels; works at 360 px.

## 8. Risks and traps
- Changing hours changes week numbers, so phase target dates shift — that is correct, but show "(moved because you changed your hours)".
- Time zone: compute "today" with `mastery.learner_now` and the IST offset used in T04 so both features agree.
- Don't build a Gantt chart. A list with dates is enough and works on phones.
