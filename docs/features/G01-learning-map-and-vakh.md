# G01: Learning map and Vakh challenges (built by Abhay, reviewed and hardened 3 Oct 2026)

## What it is
- **GPS map** (`Roadmap` page, first tab): every concept as a waypoint with a state computed from the learner's own evidence: target reached, in progress, recommended next, blocked until a prerequisite is ready, misconception, detour, review due. Data: `GET /api/map`, `/api/map/node/{id}`, `/api/map/history`, `POST /api/map/goal`. Engine: `engines/learning_navigation.py`, `knowledge_graph.py`. Tables: `models_ext/G01.py`.
- **Practical challenge** per concept, generated from the learner's level and misconception (`engines/challenge_generator.py`), shown on the Learn page and in the map.
- **Vakh**: the place where a learner builds and gets the work reviewed. A reviewed submission becomes `work_product` evidence through the normal pipeline (`mastery.apply_evidence`), then the roadmap re-plans.

## Words on the map
"Target reached" means the learner reached about 95% of that concept's target for the chosen goal. It is not the same as the dashboard's strict "Mastered" (95% estimate plus two kinds of evidence, one of them applied work). "Blocked until ready" uses about 70% on the prerequisite.

## Vakh is OFF until configured. Nothing about Vakh is assumed.
Set in `backend/.env`:
- `VAKH_BASE_URL`: the real https address of your Vakh site. Empty means the "Open on Vakh" buttons say Vakh is not connected.
- `VAKH_WEBHOOK_SECRET`: a long random string you also give to Vakh. Empty means the webhook answers 503.
- `VAKH_ENABLED=false` switches every Vakh endpoint off whatever else is set.

### What SAARTHI sends (our design, not yet confirmed with Vakh)
Launch link: `<VAKH_BASE_URL>/forms/<form id>?state=<signed token>`. The token is opaque and signed by SAARTHI (valid 30 days) and contains the learner and concept. **The internal learner id never appears in the link.** Whether Vakh can carry a `state` value through a form and send it back is **unknown and must be confirmed with the Vakh team**; the API says `prefill_verified: false`.

### What SAARTHI accepts (our design, not yet confirmed with Vakh)
`POST /api/vakh/webhook` with header `X-Vakh-Signature: sha256=<hex HMAC-SHA256 of the exact raw body using VAKH_WEBHOOK_SECRET>` and JSON:
`{"post_id": "...", "state": "<token from the link>", "status": "approved|reviewed|passed|rejected|failed|changes_requested", "score": 0.0-1.0, "review_notes": "...", "reviewer_type": "mentor|peer|auto", "submission_url": "..."}`
(`learner_id` + `concept_id` can replace `state`; the body is already protected by the signature.)

Rules (tests in `tests/test_vakh_security.py`):
- No valid signature, no effect. The shared secret itself is not accepted as a signature. Wrong key or edited body gives 401.
- Only a **final** review with a **numeric score** becomes evidence. Approved without a score gives 422 and nothing is recorded. A rejected review with no score is stored but earns no credit; with a low score it counts as that low score. Not-final statuses record nothing.
- Same `post_id` twice never double counts.
- Bad input is a clean 422/400/404/413 with no internal text.

## Still to confirm with Vakh
Real address, whether form pre-fill or a hidden field can carry `state`, whether Vakh can send a signed webhook (and its exact header and payload), and how a review score is expressed. Until then the learner builds the challenge themselves and nothing is sent to Vakh.
