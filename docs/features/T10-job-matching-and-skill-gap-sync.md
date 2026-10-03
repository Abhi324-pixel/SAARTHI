# T10 — Live job listings, evidence-based match, "add this gap to my plan"

> ⏸ **PARKED — not planned for now.** Do not start this feature unless Abhinav asks for it. See [TEAM-SPLIT.md](TEAM-SPLIT.md).

| | |
|---|---|
| Source | TESSA — live job matching (Adzuna + search fallback) and one-click skill-gap sync into the roadmap |
| SAARTHI today | **Missing.** The roadmap targets a *role*, never a real listing. Interview weaknesses already flow into the roadmap automatically (through evidence), so the "sync" half exists in spirit; there are no job listings. |
| Priority / size | P3 / L (3 days) — only if the team wants a placement angle after the finale |
| Depends on | T01 (`aliases` for matching text to concepts). Optional T09 (not used for the match; see rules). |
| External accounts | **Adzuna developer account** (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`). Check Adzuna's terms (attribution, caching, free-tier limits, India coverage) **before** you build. |

## 1. What the learner gets

A "Jobs" card (under the roadmap or Interview page) listing a few current openings for their target role and city. For each: what the
listing asks for, mapped onto SAARTHI's concepts, and an honest statement such as **"You have verified 5 of the 8 skills this listing
asks for that SAARTHI teaches · 2 in progress · 1 not checked yet · also asked: Kubernetes, Java (not in SAARTHI's curriculum)"**. A
button "Add the missing skills to my plan" raises those concepts in the roadmap. No made-up "78 % match".

## 2. How it works in TESSA (the source idea)

| What | File and place (relative to TESSA root) |
|---|---|
| Fetch jobs from the Adzuna REST API (`/v1/api/jobs/{country}/search/1?what=&where=`), normalise fields | `backend/app/interview/job_matcher.py` `fetch_live_jobs()` (l.22–58) |
| Fallback: a Tavily web search presented as jobs; then **hard-coded mock jobs** | `job_matcher.py` (l.60–83 Tavily; l.85–117 mock listings) |
| "Match %": expected skills per role, compare with candidate skills + resume skills, clamp to 45–95 % | `job_matcher.py` `calculate_job_match()` (l.120–179; role map l.136–143; clamp l.166–167) |
| HTTP | `backend/app/api/interview.py` `match_jobs()` (l.293–323) |
| Interview weaknesses → profile → re-plan | `backend/app/interview/skill_gap.py` `extract_skill_gaps()` (l.13–39), `apply_gaps_to_tessa_profile()` (l.42–76); UI `applyInterviewSkillGaps()` (`public/index.html` l.6178) and `fetchLiveJobMatches()` (l.6204) |
| Test | `backend/tests/test_interview.py` `test_job_matcher` (l.92) |

Tech there: `urllib.request` to Adzuna, Tavily client, plain Python set matching.

### Do not copy
- **The match percentage.** Floor 45 %, cap 95 % (`l.166–167`) means every job looks "partly suitable" — invented. Also it counts the
  candidate's *claimed* skills. SAARTHI uses **verified evidence only** and shows counts, not a percentage.
- **Fake listings.** The Tavily fallback labels results `company: "Verified Employer"` (l.73) and the final fallback returns made-up
  companies ("TechSolutions Innovations", "CloudScale Systems", `example.com` URLs, l.85–117) as if real. SAARTHI shows the mock
  provider only behind a visible **Demo data / Example listing — not a real job** badge, or hides the feature.
- `apply_gaps_to_tessa_profile` **adds weaknesses to `claimed_skills`** (l.56–58) — i.e. it records "gaps" as skills the learner *claims to have*
  — and appends "(Focus areas: …)" to the goal text (l.61–64). Both corrupt the profile. SAARTHI adds *requirements*, not claims.
- Camera data in matching — TESSA's own docstring forbids it (l.1–7); keep that rule.

## 3. What SAARTHI already has

- The adapter pattern (`adapters/base.py`, `impl.py`, `__init__.py`, `config.py`) with contract tests — a jobs source is a textbook adapter.
- `mastery.concept_views()` → `level` (`not_assessed/unknown/developing/proficient/mastered`) and `p` per concept: the *verified* side of the match.
- `planner.build()` takes requirements from `content.role(...)["requirements"]` (`engines/planner.py` l.34–45): the hook for "extra requirements".
- T01's `aliases` (phrase → concept id) for turning listing text into concepts.

## 4. How to adapt it

### 4.1 Adapter `JobsProvider`
- Port in `adapters/base.py`: `JobRecord(id, title, company, location, url, description, posted, source, is_mock)` and
  `JobsProvider.search(query: str, location: str, limit: int) -> list[JobRecord]`.
- `MockJobs` (`impl.py`): 6 fixtures, ids `mock_job_…`, `is_mock=True`, title prefixed "Example:" and `url=""` (no fake links).
- `AdzunaJobs` (`impl.py`): `httpx` GET, 8 s timeout, map fields (`redirect_url`→`url`, `company.display_name`, `location.display_name`,
  `created`); on HTTP/JSON error raise `JobsUnavailable` (the route turns it into 503, **never** into fake data).
- Factory `adapters.jobs()`; switch `SAARTHI_JOBS=mock|adzuna` in `config.py` and `backend/.env.example`; `adzuna` without both
  keys ⇒ refuse to start (same rule as other adapters). Add the row to `docs/SWAPPING_MOCK_TO_REAL.md`.
- Cache by `(query, location)` for several hours in `backend/data/jobs_cache/` to protect the quota. Show Adzuna's required attribution.
- Contract tests (`tests/test_adapter_contracts.py` style) run the same assertions on both providers (fields present, `limit` respected, ids unique).

### 4.2 Listing → concepts (engine `engines/jobs.py`)
`requirements_from_listing(text) -> {covered: [concept_id], other: [str]}`:
1. Deterministic pass: match T01 `aliases`/concept names in the listing text (word-boundary, case-insensitive).
2. Optional LLM pass (`extract_job_skills` task): returns raw skill phrases only; each phrase goes through the **same** alias matcher;
   unmatched phrases land in `other` (shown, never invented as concepts). Treat the listing as untrusted text.
Be upfront in the UI: the listing text from the API is a short excerpt, so the list may be incomplete.

### 4.3 The match (no percentage)
```
match(db, learner, listing) -> {
  "covered_total": 8,               # SAARTHI concepts the listing asks for
  "verified": [..], "in_progress": [..], "not_checked": [..],     # from concept_views levels
  "other_skills": ["Kubernetes", "Java"],
  "summary": "5 of 8 verified · 2 in progress · 1 not checked yet"
}
```
`verified` = level ∈ {proficient, mastered}; `in_progress` = developing; `not_checked` = unknown/not_assessed. If `covered_total < 3`
say "this listing is mostly outside SAARTHI's topics" and show no summary. Sort listings by `verified/covered_total`, ties by recency.

### 4.4 "Add to my plan" = extra requirements, not claims
`POST /api/jobs/{job_id}/add-gaps` writes `Learner.settings["extra_requirements"] = {concept_id: {"target": 0.75, "weight": 0.8, "why": "job:<title>"}}`
for the `not_checked + in_progress` concepts. In `planner.build()` merge: `req = {**role["requirements"], **extra}` (role entries win), and
emit a reason code `JOB_GAP` (`why_text` EN + Hinglish: "A listing you saved asks for this"). The learner can remove them in Settings.
Cap at 6 extra concepts. No edit to the goal text, no claims.

### 4.5 Routes — new `backend/app/routes/jobs.py`
| Method + path | Notes |
|---|---|
| `GET /api/jobs?location=&limit=10` | role comes from the learner; 403 for under-18; 503 `unavailable` if provider fails; each item has `match` |
| `POST /api/jobs/{job_id}/add-gaps` | job must have been returned to this learner recently (server-side cache) — don't trust a client-sent listing |
| `DELETE /api/me/extra-requirements` | removes the additions |

Only the role title and city are sent to Adzuna; **no learner data**.

### 4.6 Frontend
`components/JobsCard.tsx` on `Interview.tsx` (or a new "Jobs" tab). Mock listings carry `DemoBadge` ("Example listing — not a real job").
Show `summary`, the three groups, `other_skills`, link out (`rel="noopener noreferrer"`), and the add-to-plan button with a confirm.
Add attribution text. EN/Hindi/Hinglish strings.

## 5. Files to create / touch
`adapters/base.py`, `adapters/impl.py`, `adapters/__init__.py`, `config.py`, `.env.example`, `docs/SWAPPING_MOCK_TO_REAL.md`,
`engines/jobs.py` (new), `engines/planner.py` (extra requirements + reason code + `why_text`), `routes/jobs.py` (new),
`frontend/src/components/JobsCard.tsx` (new), `frontend/src/api_ext/T10.ts`, tests `test_jobs.py` + additions to `test_adapter_contracts.py`.

## 6. Tests (minimum)
1. Contract tests across `MockJobs` and `AdzunaJobs` (HTTP mocked with `httpx.MockTransport`).
2. `adzuna` mode without keys refuses to start; provider failure ⇒ 503, **never** fake jobs.
3. Matching: listing mentioning "SQL joins, REST API, Docker, Kubernetes" ⇒ covered = join/rest/docker concepts, `other = ["Kubernetes"]`; levels map to groups exactly.
4. Self-reported skills (T01/T09 claims) do **not** count as verified (create a `self_report` event, assert it stays `not_checked`).
5. `add-gaps` adds ≤ 6 extra requirements, raises them in the roadmap with a `JOB_GAP` reason, and does not change goal text or claims.
6. Under-18 ⇒ 403; unknown `job_id` ⇒ 404; no learner PII in the outgoing Adzuna request (assert the URL/params).
7. Mock listings are flagged `is_mock` in the API response and the UI shows the badge.

## 7. Done when
- [ ] With `SAARTHI_JOBS=mock` the whole flow works and is labelled demo; with Adzuna keys it shows real listings with attribution.
- [ ] Match text is count-based and uses verified evidence only; outside-curriculum skills are shown, not invented.
- [ ] Adding gaps changes the roadmap with a visible reason; removing restores it.
- [ ] Minors cannot use it.

## 8. Risks and traps
- Adzuna free-tier limits and terms (display, attribution, storage) — read them first; a demo that hits the limit looks broken. Cache.
- Listing text is short and noisy; never present the match as a hiring prediction.
- Dedupe near-identical listings (same title+company) so the list isn't ten copies.
- Don't promise jobs. Put "SAARTHI does not apply for you and has no relationship with these employers" near the list.
