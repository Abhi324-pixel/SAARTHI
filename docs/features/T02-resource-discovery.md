# T02 — Learning-resource discovery ("more ways to learn this")

> ⏸ **PARKED — not planned for now.** Do not start this feature unless Abhinav asks for it. See [TEAM-SPLIT.md](TEAM-SPLIT.md).

| | |
|---|---|
| Source | TESSA — live resource discovery, hybrid ranking, alternatives |
| SAARTHI today | **Missing.** SAARTHI teaches from its own curated notes (`content/notes.json`) and practice; it shows no external courses/videos/docs. |
| Priority / size | P3. **Phase A** (curated list) S–M, 1–2 days. **Phase B** (live search) L, 3–4 days. Build A first; B only if time allows. |
| Depends on | T03 (format preferences make the ranking personal; not required) |
| External accounts | Phase A none. Phase B: Tavily API key (new), reuse Gemini. |

## 1. What the learner gets

Under every concept (Learn page, side panel) a short list: "More ways to learn this" — e.g. one video, one reading, one interactive
exercise — ranked for *this* learner (level, preferred format, time, language) with a plain reason ("short, hands-on, you prefer
practice"). The learner can **hide** a resource ("not for me") and **save** one. Opening or finishing a resource is **not** evidence
and never changes a level; only SAARTHI's own checks do.

## 2. How it works in TESSA (the source idea)

| What | File and place (relative to TESSA root) |
|---|---|
| Per-skill web search, concurrent, bounded; cache by goal+skills+budget; retry with back-off | `backend/app/engines/discovery.py` `find()` (l.284–344), `_search_skill()` (l.196–237), `_search_all()` (l.240–258), `_key()` (l.165) |
| LLM only **selects and labels** pages from the search results; a URL is accepted only if it was returned by the search | `discovery.py` `SYSTEM` (l.123–141), `_collect()` (l.381–410), `_to_course()` (l.443–491; check at l.454), `_normalise_url()` (l.170) |
| Round-robin merge of sources so no skill is crowded out | `discovery.py` `_sources_for()` (l.261–281) |
| One recovery pass if coverage is thin | `discovery.py` `_retry_batch()` (l.347–354), constant `COVERAGE_STRENGTH` (l.62) |
| Ranking: BM25 + dense/TF-IDF fused with reciprocal-rank fusion; weighted score with *named terms that each emit a reason code* | `backend/app/engines/retrieval.py` `Retriever.search()` (l.72–91), `rank()` (l.95–215), `_level_fit()` (l.236–249), `_preference_fit()` (l.254–279) |
| "If not this, suggest another" (faster / hands-on / reference / deep-dive alternatives) and swapping with a DAG check | `backend/app/engines/suitability.py` `find_alternatives`, `backend/app/api/path.py` `get_alternatives()` (l.248–266), `swap_resource()` (l.289–407) |
| Frontend | `public/index.html` `loadAlternatives()` (l.3634), `swapCourse()` (l.3660) |
| Tests | `backend/tests/test_discovery.py` (`test_discovery_rejects_url_not_returned_by_tavily`, `test_discovery_uses_search_evidence_and_cache`) |

Stack there: Tavily Search API, Gemini (structured output), `rank_bm25`, scikit-learn TF-IDF / optional sentence-transformers, NetworkX.

### Do not copy
- `suitability.py`: the `match_score`, `hallucination_risk: "0.0% (Deterministic Reason-Code Constrained)"` (l.78),
  `zero_view_bias`, and the "archetype" with an invented hands-on ratio such as "75% Practical Coding · 25% Theory" guessed from
  words in the title (l.112–127). These are invented numbers (playbook rule 2).
- `_to_course()` defaulting an unknown duration to `8.0` hours (l.472–474). Show "duration not stated" instead.
- Completing a resource crediting mastery (`profiler.py` `COMPLETION_CREDIT`). Finishing a video proves nothing.
- BM25/TF-IDF/embeddings: with 3–8 candidates per concept they add dependencies (`rank_bm25`, scikit-learn, torch) and no value.

## 3. What SAARTHI already has

- `Content.concepts` (28) with `domain`, `minutes`; `Learner.language_pref`; `Learn.tsx` side column (`<aside>` at the end of the file).
- `gateway.generate_json` (Phase B labelling), `config.py` pattern for a new optional key.
- Adapter pattern for external sources (`adapters/`): a resource finder with a "curated" and a "search" implementation is exactly that.

## 4. How to adapt it

### 4.1 Phase A — curated resources (build this first; no external service)
**Content file** `backend/app/content/resources.json` (loaded in `content.py` like the others, validated at start-up):

```
{ "version": "...pending-review", "resources": [
  { "id": "res_sqlbolt_joins", "concept_ids": ["sql_inner_join","sql_outer_join"],
    "title": "...", "provider": "...", "url": "https://...", "format": "interactive",   // video|text|interactive|project
    "level": "beginner", "minutes": 30, "minutes_stated": true, "cost": "free",
    "language": "english", "note": "one honest sentence", "reviewed_by": "name", "reviewed_on": "2026-10-xx" } ] }
```
`validate()` must check: concept ids exist; `https` URL; `format/level/cost` in the allowed sets; `reviewed_by` present (else the
item is hidden in prod); no duplicate ids/URLs. Add a `scripts/check_links.py` that HEADs each URL and prints dead ones.
Someone human must pick and review the links — AI-suggested links are drafts until a person opens each one.

**Engine** `backend/app/engines/resources.py`:
```
rank(db, learner, concept_id, limit=4) -> list[dict]   # each with score components + reason codes
```
Deterministic score, every term named and returned (copy the *idea* of `retrieval.py rank()`):
`level_fit` (resource level vs learner's `p` for that concept; peak slightly above current — port `_level_fit` l.236–249),
`format_fit` (learner preference, from T03 or none), `time_fit` (minutes vs `weekly_hours`), `language_fit` (matches `language_pref`).
Reason codes: `LEVEL_FIT`, `FORMAT_FIT`, `TIME_FIT`, `LANGUAGE_FIT`. Prose comes from codes (same approach as `planner.why_text`).
Hidden resources (see table below) are excluded.

**Table** (new, `models_ext/T02.py`): `resource_interactions(id, learner_id, resource_id, concept_id, action, created_at)`;
`action ∈ {opened, saved, done, hidden}` — all are **behaviour records, not evidence**; they never call `apply_evidence`.
Add to export/delete (playbook rule 6).

**Routes** `backend/app/routes/resources.py`

| Method + path | Notes |
|---|---|
| `GET /api/concepts/{concept_id}/resources` | returns ranked list + `source: "curated"` per item |
| `POST /api/resources/{resource_id}/action` | body `{action}`; validates action, resource exists, scoped to learner |

**Frontend**: `components/ResourceList.tsx` used in `Learn.tsx` aside. Show format icon, minutes (or "length not stated"), cost, the
reason chips, and a visible line "Outside links are not part of SAARTHI's checks. Finishing one does not change your level."

### 4.2 Phase B — live search (optional)
- New port `ResourceFinder` in `adapters/base.py` with `CuratedFinder` (Phase A) and `SearchFinder` (Tavily). Switch
  `SAARTHI_RESOURCES=curated|search` in `config.py`/`.env.example` (`TAVILY_API_KEY`). `search` without a key refuses to start.
- `SearchFinder.find(concept)` ports `discovery.py`: one search per concept (`"{concept name} tutorial"` + learner language), then
  Gemini **selects/labels** from the returned snippets with the schema from `discovery.py` `SUBMIT_SCHEMA` (l.68–121).
  **Hard rule:** drop any resource whose normalised URL was not in the search results (`_normalise_url`, `_to_course` l.454). Also
  drop roundups ("best 10 resources") as TESSA's prompt does. Treat snippets as untrusted text in the prompt (TESSA does: l.125).
- Cache results per concept for 7 days in `backend/data/resource_cache/` (gateway-style file cache). A search failure returns the
  curated list only; never invent.
- Label these items `source: "search"` and show a chip "Found by search — not reviewed". They are never shown to minors? Decide in review;
  default: **curated only for under-18**.
- Contract tests run against both finders (same fields, same URL-grounding rule).

### 4.3 "Other options for this concept"
Instead of TESSA's alternatives with invented trade-off labels, derive labels from real fields: `shorter` (fewer minutes),
`hands_on` (`format in {interactive, project}`), `reading` (`format == text`), `video`. No ratios, no percentages.

## 5. Files to create / touch
`content/resources.json` (new), `content.py` (load+validate), `engines/resources.py` (new), `routes/resources.py` (new),
`models_ext/T02.py` (new), `privacy.register_export` from `models_ext/T02.py` (interactions), `scripts/check_links.py` (new),
`frontend/src/components/ResourceList.tsx` (new), `pages/Learn.tsx`, `frontend/src/api_ext/T02.ts`, tests `tests/test_resources.py`.
Phase B adds: `adapters/base.py`, `adapters/impl.py`, `adapters/__init__.py`, `config.py`, `.env.example`, `docs/SWAPPING_MOCK_TO_REAL.md`.

## 6. Tests
1. Content validation fails on unknown concept id, non-https URL, missing `reviewed_by`.
2. Ranking is deterministic and every returned item carries its components; a learner at p=0.1 gets beginner items first, p=0.8 gets advanced.
3. Hidden resource never returned again; another learner's hide does not affect me.
4. `action` endpoint cannot be used to change mastery (assert no `EvidenceEvent` is created).
5. Phase B: URL not in search results is dropped; cache hit makes no search call; no key ⇒ refuses to start when switch is `search`; search error ⇒ curated list.
6. Export/delete include interactions.

## 7. Done when
- [ ] Learn page shows ranked, reviewed resources with reasons; hide/save work and persist.
- [ ] No resource action changes any level; the UI says so.
- [ ] Every shown link was reviewed by a named human (curated) or is clearly labelled as unreviewed search output.
- [ ] Dead-link script exists and was run before the demo.

## 8. Risks and traps
- Link rot and paywalls: re-run `check_links.py` before any demo; keep `cost` honest.
- Copyright: store titles and URLs only, not page text.
- Search results can be spammy or unsafe for minors — see the under-18 default in 4.2.
- Do not let this grow into "recommend courses to complete the roadmap". The roadmap is built from concepts, not courses.
