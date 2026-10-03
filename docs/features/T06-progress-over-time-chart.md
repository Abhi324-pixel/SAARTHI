# T06 — Progress-over-time chart and skill radar

| | |
|---|---|
| Source | TESSA — readiness ring, per-domain radar, route-completion and timeline on the Progress tab |
| SAARTHI today | **Partial.** Dashboard has a ring with the *current* overall figure and "after plan" projection (`pages/Dashboard.tsx`, `engines/mastery.overall_mastery`). There is **no history**: a learner cannot see that they went from 18 % to 41 % over three weeks. |
| Priority / size | P1 / S–M (1–2 days). The most convincing "it works" visual for a demo or a pilot. |
| Depends on | nothing. T05 deadlines can be drawn as markers later. |
| External accounts | none. **No new table** — the history is replayed from the evidence log. |

## 1. What the learner gets

A "Progress over time" card: a line of overall progress toward the role target across days/weeks, one line per domain (SQL, Python,
Backend, Tools) that can be toggled, small markers where something notable happened (a mentor session, a misconception fixed), a dotted
extension to "if you reach every target" (clearly labelled as a projection), and a radar of current vs target by domain. A small
sparkline on the dashboard ring. When a long break makes the line dip, the chart says why ("memory fades without review — 3 reviews are due").

## 2. How it works in TESSA (the source idea)

TESSA has no time series. It has a point-in-time view; that is what to take as the idea.

| What | File and place (relative to TESSA root) |
|---|---|
| Importance-weighted readiness = Σ w·min(m,target) / Σ w·target (clamped so overshooting one skill can't hide a missing one) | `backend/app/engines/gap.py` `readiness()` (l.21–28), `gap_items()` (l.31–49), `strengths()` (l.52–61) |
| Dashboard payload: readiness now vs projected, radar per domain (mean current vs mean target), progress in hours, milestones, last 20 timeline events | `backend/app/api/dashboard.py` `build()` (l.21–139; radar l.36–53) |
| Radar SVG (falls back to bars with < 3 axes), ring, progress cards, "what has happened" timeline | `public/index.html` `radarSvg()` (l.3990–4024), `radarBars()` (l.3972–3988), `renderProgress()` (l.4028–4070), `timelineDetail()` (l.4072) |

Tech there: NumPy vectors, hand-written SVG (no chart library).

### Do not copy
- The wording "skill readiness … reflects capability" as if it predicted a job outcome. Call it **progress toward the role target**.
- `percent` computed from *hours of courses completed* (`dashboard.py` l.120–126) — SAARTHI does not measure completion, it measures evidence.

## 3. What SAARTHI already has (and why no table is needed)

- `EvidenceEvent` rows carry `concept_id`, `created_at`, `source_type`, `changed_mastery`, `p_before`, `p_after` (the *effective* p of
  that concept right after the event, forgetting included) and `grader` (`"simulated"` for demo helpers). So the whole history can be **replayed**.
- `mastery.overall_mastery(views, role_requirements)` is the same formula as TESSA's `readiness` (`engines/mastery.py` l.261–268).
- `content.role(role_id)["requirements"]` gives `weight`/`target` per concept; `Concept.domain` and `Concept.p_init` exist.
- `Ring`, `Bar`, `SectionTitle` in `components/ui.tsx`; `SkillGraph.tsx` shows how this project draws SVG by hand.
- `planner` summary already has `readiness_after` (projection if every selected item reaches target).

## 4. How to adapt it

### 4.1 Engine `backend/app/engines/progress.py`
```
history(db, learner, since_days=None) -> {
  "series": [ {"at": iso, "overall": 0.41, "by_domain": {"sql": 0.33, "python": 0.62, ...}, "n": 17, "simulated": false} ],
  "markers": [ {"at": iso, "kind": "mentor"|"misconception_resolved"|"plan_changed", "label": "..."} ],
  "now": {"overall": 0.39, "by_domain": {...}},     # live value, includes forgetting
  "projection": {"overall": 0.82, "weeks": 9},      # planner summary readiness_after, total_weeks
  "due_reviews": 3 }
radar(db, learner) -> [ {"domain": "sql", "current": 0.41, "target": 0.85} ]
```
Algorithm (write as a pure function over a list of events so it is unit-testable):
1. `p = {cid: content.concepts[cid].p_init}` for every concept in the role's requirements.
2. Walk `EvidenceEvent` rows for the learner **ordered by `created_at`**; skip those with `changed_mastery == False`.
3. Set `p[event.concept_id] = event.p_after`; recompute `overall` and `by_domain` **incrementally** (keep running sums of
   `Σ w·min(p,t)` and `Σ w·t` per domain) — O(1) per event.
4. Emit one point per event; if more than ~200 points, keep the **last point per day**.
5. Mark a point `simulated: true` if the event's `grader == "simulated"` (the Settings demo tools) and draw those dashed with a label,
   so a demo history is never mistaken for real learning.
6. The final live value `now` comes from `mastery.concept_views()` (it applies forgetting), so a dip after a long break is real.
`markers`: `mentor` events (source_type `mentor`), resolved misconceptions (`MisconceptionInstance.resolved_at`), and roadmap
versions whose `change_reason` is not "No change" (`RoadmapVersion.created_at`) — cap at ~12 to keep the chart readable.

### 4.2 Route — add to a new `backend/app/routes/progress.py`
| Method + path | Notes |
|---|---|
| `GET /api/progress/history?days=90` | `days` 7–365, default 90; returns the dict above |
| `GET /api/progress/radar` | list of `{domain, current, target}` — mean of concept values weighted by role weight |
Add `sparkline: [last 14 daily points]` to the `/api/dashboard` payload so the dashboard needs no second call.

### 4.3 Frontend
- `components/TrendChart.tsx`: hand-written SVG (no new dependency). Props: `series`, `domains`, `markers`, `projection`. X = time,
  Y = 0–100 %. Domain toggles as chips. Hover/focus shows the date, value and the evidence count; also provide the same data as a
  visually-hidden table for screen readers (`<table class="sr-only">`).
- `components/RadarChart.tsx`: port the **idea** of `radarSvg` (3+ axes ⇒ polygon, otherwise bars). SAARTHI has 4 domains.
- Place the card on `Genome.tsx` (the Learner Twin page) and a 14-point sparkline inside the dashboard ring card.
- Honest empty states: "No evidence yet — take the placement" and "Only one point so far".
- Label the dotted projection: "Projection — assumes you reach every target on your roadmap".

## 5. Files to create / touch
`engines/progress.py` (new), `routes/progress.py` (new), `routes/core.py` (`dashboard()` adds `sparkline`),
`frontend/src/components/TrendChart.tsx`, `RadarChart.tsx` (new), `pages/Genome.tsx`, `pages/Dashboard.tsx`,
`frontend/src/api_ext/T06.ts`, `backend/tests/test_progress.py` (new).

## 6. Tests (minimum)
1. Pure replay: hand-made events ⇒ exact expected `overall` sequence; the last replay value equals `overall_mastery` computed from
   `concept_views` when no time has passed (tolerance 0.01).
2. After the dev **advance-time** tool jumps 30 days, `now.overall` < last series point and `due_reviews > 0`.
3. Events with `changed_mastery == False` (feedback, self_report, low-confidence grades) never create a point.
4. `grader == "simulated"` points are flagged; a learner with only simulated history gets `simulated: true` for all.
5. Downsampling: 1,000 events ⇒ ≤ 200 points, still ordered, last point preserved.
6. Isolation: learner B's events never appear in learner A's series. `days=0` or `days=1000` ⇒ 422.
7. Performance guard: 2,000 events replay in well under 100 ms (assert loosely).

## 7. Done when
- [ ] Genome page shows the trend card (overall + toggleable domains + markers + labelled projection) and the radar.
- [ ] Dashboard ring card has a sparkline.
- [ ] Demo-seeded history is visibly marked simulated.
- [ ] A long break shows a dip with an explanation, not a silent drop.
- [ ] Accessible: data table alternative, keyboard-focusable points, colours not the only cue.

## 8. Risks and traps
- `p_after` is rounded to 4 decimals and is the *effective* value at that moment; do not recompute BKT here — that would duplicate
  the maths in `mastery.py` and drift from it.
- Replaying needs `ORDER BY created_at`; the dev clock offset writes `created_at = learner_now(...)`, so events can be *in the future*
  relative to wall-clock. Order by stored `created_at` and don't filter "future" points out.
- Do not add a "predicted job readiness" or "percentile". Only measured progress and a clearly labelled projection.
- Keep the radar's domain list from the role requirements (`Concept.domain`), not hard-coded names, so a second role works later.
