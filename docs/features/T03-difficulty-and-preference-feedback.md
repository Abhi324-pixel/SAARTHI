# T03 — "Too easy / too hard / not helpful" feedback that adapts the plan

| | |
|---|---|
| Source | TESSA — feedback adapter (preference nudges, difficulty signals) |
| SAARTHI today | **Missing.** The learner can say "this estimate looks wrong" (dispute) and "I'm stuck", and can try another teaching approach on the Learn page, but cannot say "too easy" / "too hard" / "this helped" and have the plan react. |
| Priority / size | P1 / S–M (1–2 days) — small, visible, and a good first feature |
| Depends on | nothing. Feeds T02 (format preference) and T05 (pace). |
| External accounts | none |

## 1. What the learner gets

On a concept explanation, a practice task or a quick check there are three small buttons: **Too easy**, **Too hard**, **This helped**.
What they do is visible and honest:

- **Too easy** → "Prove it": SAARTHI immediately offers a *harder-than-usual* question on that concept. If they answer it, that is real
  evidence and may raise the level. The click itself changes nothing about mastery.
- **Too hard** → SAARTHI switches to a gentler teaching approach (e.g. worked example), checks the weakest prerequisite under this
  concept with one question, and gives that concept a little more time in the roadmap. It says so ("I'll check the basics under this").
- **This helped** → remembered for choosing the next teaching approach when there is no better data.

Every effect is shown as a roadmap reason code `LEARNER_FEEDBACK` ("You told us this was too hard, so we added time"), so adaptation is
never silent.

## 2. How it works in TESSA (the source idea)

| What | File and place (relative to TESSA root) |
|---|---|
| Three separate updates with different half-lives: mastery, preferences, bandit arms | `backend/app/engines/adapter.py` docstring (l.1–14) |
| Apply one signal (`completed`, `too_easy`, `too_hard`, `not_interested`, `skipped`, `loved_it`) | `adapter.py` `apply()` (l.30–81) |
| Small weight nudges (`STEP = 0.04`, clamped 0.02–0.6) on the scoring weights | `adapter.py` `_adjust()` (l.84–88), `STEP` (l.27) |
| Beta-Bernoulli Thompson sampling over content formats | `adapter.py` `_bump_arm()` (l.91–98), `preferred_formats()` (l.101–109) |
| HTTP: record feedback, rebuild the path, return a message + diff | `backend/app/api/path.py` `feedback()` (l.150–177) |
| Signal enum | `backend/app/schemas.py` `Feedback.signal` (l.223–226) |
| UI: send feedback, show a "receipt" of what changed | `public/index.html` `sendFeedback()` (l.4650–4669), `addReceipt()` (l.3215), `diffRoute()` (l.3204) |

Tech there: plain Python, a dict of `[alpha, beta]` per format, no database (process-local).

### Do not copy
- `too_easy` / `too_hard` **edit `profile.quiz_results`** (`adapter.py` l.45–61), i.e. a click directly changes the estimated skill.
  That violates SAARTHI's central rule: *feedback never moves mastery* (playbook rule 1). Replace with "turn the claim into a test".
- `skipped` / `not_interested` on a course removes it from the path (l.63–74). SAARTHI's roadmap items are the role's required
  concepts; skipping one would break the prerequisite closure the planner guarantees. Offer "Why do I need this?" instead.
- A second bandit keyed on **clicks** (`loved_it`). SAARTHI already has a better one: `engines/strategy.py` rewards *later learning
  gain*, not satisfaction. Keep a single bandit.

## 3. What SAARTHI already has

- `EvidenceEvent.source_type` already allows `feedback` and `mastery.apply_evidence` records it without moving mastery
  (`MASTERY_SOURCES` in `engines/mastery.py`, l.23).
- `strategy.explain(db, learner, concept_id, strategy=..., misconception_id=...)` (`engines/strategy.py` l.123–147) and
  `strategy.choose()` (l.47–88) with its rule list.
- `diagnostic.next_probe(db, learner, count, concept_id=...)` (`engines/diagnostic.py` l.52–72) picks an unseen MCQ whose
  difficulty is closest to `0.25 + 0.5·p`.
- `mastery.concept_views()` returns `blocked_by` (weak prerequisites) per concept.
- `planner._minutes()` and `PRACTICE_FACTOR = 2.0` (`engines/planner.py` l.24–29) decide time per concept.
- `hooks.after_evidence()` rebuilds the roadmap and returns the "roadmap changed" payload the banner uses.

## 4. How to adapt it

### 4.1 Data (no schema change to existing tables)
- Record each click as `EvidenceEvent(source_type="feedback", score=None, correct=None, grader="learner_click",
  detail={"signal": "too_hard", "context": "explanation|task|quiz", "item_id": "...", "strategy": "..."})`. `changed_mastery` stays `False`.
- Per-learner knobs live in `Learner.settings` (JSON): `{"practice_factor": {"sql": 2.0, "python": 2.0, ...}, "format_pref": [...]}`.
  Defaults come from `PRACTICE_FACTOR`; allowed range `[1.5, 3.0]`; one signal moves it by `±0.1`; at most one change per
  concept per day (stops click-spam from rewriting the plan).

### 4.2 Engine `backend/app/engines/feedback.py`
```
apply(db, learner, concept_id, signal, context, item_id=None) -> {
   "message": str,                       # what SAARTHI did, in the learner's language
   "action": {"type": "probe"|"strategy"|"none", ...},   # what the UI should do next
   "after": hooks.after_evidence(...)    # only if something changed
}
```
Signals: `too_easy`, `too_hard`, `helpful`, `not_helpful`. Behaviour (copy these exactly; tests lock them):

| Signal | Effect | Does it touch mastery? |
|---|---|---|
| `too_easy` | return `action = {type: "probe", item: next_probe(..., concept_id, harder=True)}`; nudge `practice_factor` for the domain by −0.1 **only if the learner then answers it correctly** (do that in the probe-answer path, not on the click) | No (the later answer may, through `question` evidence) |
| `too_hard` | `strategy.explain(strategy=<next untried gentle strategy>)` ; probe the first of `views[cid]["blocked_by"]` (or the weakest prerequisite) ; `practice_factor` +0.1 for the domain | No |
| `helpful` | store; `strategy.choose()` uses it as a **tie-breaker in the rules phase only** (before `BANDIT_MIN_OUTCOMES`), never overriding the misconception rule | No |
| `not_helpful` | same as `too_hard` strategy switch, no probe | No |

`next_probe` needs a small extension: an optional `harder: bool` that shifts the target difficulty to `0.5 + 0.4·p` and prefers items
the learner has not seen (reuse `answered_item_ids`). If no unseen harder item exists, say so honestly ("no harder question left — try
the explain-back").

### 4.3 Planner change
In `planner.build()` replace the constant in `_minutes(...)` with `factor = learner.settings.get("practice_factor", {}).get(domain, PRACTICE_FACTOR)`.
When the factor differs from the default add a reason item `{"type": "LEARNER_FEEDBACK", "detail": {"factor": 2.3, "default": 2.0},
"contribution": 0.0}` and teach `why_text` (EN + Hinglish lines) and `change_text` about it. Keep the planner **deterministic**:
same inputs ⇒ same output (the existing planner tests rely on it).

### 4.4 Routes — `backend/app/routes/feedback.py`
| Method + path | Body | Notes |
|---|---|---|
| `POST /api/feedback` | `{concept_id, signal, context, item_id?}` | validates concept & signal; rate-limited per concept per hour (e.g. 6) → `429` with a kind message |

### 4.5 Frontend
- A small `components/FeedbackButtons.tsx` placed in `Learn.tsx` (explanation card header, after SQL task result, after quick check).
- On `action.type === "probe"` open the existing `QuizRunner` with that single item (see `components/QuizRunner.tsx`); on
  `strategy` replace the explanation with the returned one (same shape as `api.teach`).
- Show the returned `message` as a toast and, if `after.roadmap.changed`, `setRoadmapNote(...)` like the other pages do.
- Settings page: a read-only "What SAARTHI has adapted for you" list (the `practice_factor` values and *why*), with a **Reset** button
  (deletes the keys). Transparency is the point.

## 5. Files to create / touch
`engines/feedback.py` (new), `routes/feedback.py` (new), `engines/diagnostic.py` (`harder` option), `engines/planner.py`
(factor + reason code), `engines/strategy.py` (`choose` tie-breaker), `frontend/src/components/FeedbackButtons.tsx` (new),
`pages/Learn.tsx`, `pages/Settings.tsx`, `frontend/src/api_ext/T03.ts`, `backend/tests/test_feedback.py` (new).

## 6. Tests (minimum)
1. **Rule test:** after `too_easy` and `too_hard`, `concept_views()[cid]["p"]` and `n_evidence` are unchanged; an `EvidenceEvent` with
   `source_type="feedback"` and `changed_mastery=False` exists.
2. `too_easy` returns a harder, **unseen** item; answering it correctly *does* go through `apply_evidence` as `question`.
3. `too_hard` returns a different strategy than the last one and a prerequisite probe when `blocked_by` is non-empty.
4. Planner: two learners identical except `practice_factor` get different minutes and a `LEARNER_FEEDBACK` reason code; defaults unchanged.
5. Click-spam: the 7th click in an hour returns 429 and does not change the factor; factor stays within `[1.5, 3.0]`.
6. Another learner's `Learner.settings` is untouched; reset restores the defaults.
7. `helpful` does not override `contrasting_cases` when a misconception is active.

## 7. Done when
- [ ] The three buttons exist on explanation, task and quick-check, in English/Hindi/Hinglish.
- [ ] Each button has a visible consequence and a reason code in the roadmap; nothing changes silently.
- [ ] Mastery is provably unaffected by clicks (test 1).
- [ ] Settings shows what has been adapted and allows a reset.

## 8. Risks and traps
- A learner clicking "too easy" on everything: the "prove it" probe is the guard — they only move forward by answering.
- Do not log the click as `self_report`; `feedback` and `self_report` are different source types (`self_report` = claims about knowledge).
- The planner is used by `what_if`, `why_not` and the roadmap page; changing `_minutes` changes all of them — run `tests/test_planner.py`.
- Keep translations short; the buttons must fit at 360 px.
