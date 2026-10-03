# C02 — Mentor console (the mentor's side of a case)

> 🚧 **RED ZONE — Abhinav is building this feature. Do not start it.** If you were told to take it over (or Abhinav is busy and says so), he will name it on the `RED ZONES CLEARED FOR ME:` line of your prompt. You may read this spec; building waits for that line. See [TEAM-SPLIT.md](TEAM-SPLIT.md).

| | |
|---|---|
| Source | Chhatrachhaya — Margdarshak role, shared messaging, availability, sessions (README) |
| SAARTHI today | **Built 2026-10-02 (tested with mock sign-in; not yet tried with real accounts or in a browser).** Before that: **Missing — real mentors hit a dead end.** With `SAARTHI_MENTORS=db` a case is created and matched (`status="matched"`, `engines/escalation.py` `_match_and_accept`, l.229–247), but **nothing lets the mentor see it, accept it, reply, hold the session or record an outcome**. All mentor actions in the demo are mock (`MockMentorResponder`, `POST /api/cases/{id}/simulate-session`). The safeguarding lead also cannot read the reports learners file (`SafeguardingReport` rows are write-only). |
| Priority / size | P1 for any real pilot / L (4–5 days) |
| Depends on | **C01** (mentor accounts + `current_account`). D01 (consent), C05 (notify mentor of a new case) and C04 (live chat) make it usable but are separate. |
| External accounts | none |

## 1. What a mentor gets

After signing in they land on a **Mentor console**: *New* (matched to me, waiting to accept), *Active*, *Follow-up due*, *Closed*; my capacity
and availability. Opening a case shows the **case report** SAARTHI prepared (concept, evidence timeline, misconceptions, strategies already tried,
weak prerequisites, a suggested intervention, optional shared transcript excerpts) — so they never start from zero. They can **accept** (picking a slot
from their availability) or **decline** (with a reason; the case is re-matched to someone else), **message** the learner (inside SAARTHI only, contact
details blocked), mark the **session held**, and **record the outcome** (notes, next step, and one rating: "How well did the learner show they
understand this concept in the session?"). That outcome becomes `mentor` evidence for the Learner Twin; success is later judged by the learner's *own*
later evidence, not by the mentor's star rating. A small **safeguarding view** lets the lead read reports, suspend a mentor and close a report with notes.

## 2. How it works in Chhatrachhaya (the source idea)

Chhatrachhaya has **no mentor-specific console**: elders and students use the same screens. The reusable ideas are:

| What | File and place (repo root = <https://github.com/mrgraciz123/chhatrachhayaa>) |
|---|---|
| One conversation list + chat for both roles, `participants` array, per-user unread counters | `src/BaatcheetScreen.tsx` (conversation listener l.14–27, message listener l.30–52, send l.58–90) |
| Mentor availability model `{days, slots, duration}` shown on the profile | `README.md` "Data Models → User"; `src/ProfileScreen.tsx` availability block (l.100–108) |
| Connecting a student with an elder creates the conversation and a first message | `src/MatchmakingScreen.tsx` `handleConnect()` (l.94–160) |
| Session booking / "Baatcheet" sessions list, AI prep notes, summary | **README only** — not implemented in `src/` (see C03) |

So the console is a **new design** on SAARTHI's existing case lifecycle, borrowing: shared chat component, availability slots, and role-aware lists.

### Do not copy
- Letting the client write the role/profile directly to the database (`setDoc(users/{uid})` from the browser). All mentor actions are server-checked.
- Firestore rules where "any authenticated user can read any user document" (`README.md` Firestore rules). SAARTHI mentors see only the case report fields.
- Free-form direct messaging between any elder and any student. SAARTHI chats exist **only inside a case**, are logged and screened.

## 3. What SAARTHI already has (reuse it all)

- The lifecycle and rules in `engines/escalation.py`: `open_case`, `match_mentor` (explainable score), `_match_and_accept`, `case_view`, `send_message`
  (+ `screen_message` contact-detail blocking l.46–52), `record_outcome` (turns the outcome into `mentor` evidence, l.295–306), `followup_check` (l.309–320), `resume_after_consent`.
- `models`: `Mentor`, `MentorCase` (`status`, `report`, `match_reasons`, `scheduled_for`, `outcome`, `followup`, `p_at_open`), `CaseMessage`, `SafeguardingReport`.
- Learner-side screens `pages/Mentors.tsx` (cases, chat, report aside, report-a-concern modal).
- Statuses already in use: `open, matched, accepted, scheduled, held, followup, closed, escalated, awaiting_consent`.
- `current_account` / `Mentor` rows from C01.

## 4. How to adapt it

### 4.1 State machine (write it down; tests lock it)
```
open ──match──▶ matched ──accept──▶ accepted ──schedule──▶ scheduled ──held──▶ held ──outcome──▶ followup ──check──▶ closed
   ▲               │decline/timeout                                              
   └───────────────┘ (re-match, excluding that mentor)       awaiting_consent ──(guardian approves)──▶ matched
wellbeing ──▶ escalated (no mentor ever; safeguarding lead only)
```
- Real mode currently sets `matched` and stops. Accept moves it to `accepted` (`scheduled_for` = a slot chosen from the mentor's availability or proposed text).
- **Decline** stores the mentor id in the case's excluded list and calls the matcher again (`match_mentor(..., exclude=[...])`); if nobody is left the case stays `open` ("queued") exactly like today.
- **Timeout**: a `matched` case not accepted within 24 h is re-matched. No scheduler needed in v1: perform this *lazily* when a case list or case is read
  (`escalation.expire_stale(db)`), and write an audit row.
- The mentor can **never** move a case to `closed` directly; only `followup_check` (learner evidence) closes it.

### 4.2 Tables (new, `models_ext/C02.py`)
`audit_log(id, at, actor_id, actor_role, action, subject_type, subject_id, detail JSON)` — shared with C01; **every** state change, decision, message block and
report decision writes a row (safeguarding needs a trail). `case_exclusions(case_id, mentor_id, reason, at)` (or store inside an audit row and query it — pick one and test it).
Do **not** add columns to `MentorCase` (see playbook §5a).

### 4.3 Backend — new `backend/app/routes/mentor_console.py`, prefix `/api/mentor-console`, all behind `current_mentor`
| Method + path | Notes |
|---|---|
| `GET /me` | profile, capacity (`active_case_cap` vs active), pledge version status (force re-accept if outdated), availability |
| `PUT /me/availability` | validated slots; updates `Mentor.availability` |
| `GET /cases?status=` | only cases where `MentorCase.mentor_id == me`; list view without messages |
| `GET /cases/{id}` | `escalation.case_view` **mentor projection**: `report`, `messages`, `scheduled_for`, `outcome`, `followup`; never e-mail, never learner id; learner shown as first name + age band (already in `report.learner`); transcript excerpts only if `report.shared.transcript` |
| `POST /cases/{id}/accept` `{slot}` · `/decline` `{reason}` | state machine above; capacity re-checked at accept time |
| `POST /cases/{id}/messages` | uses `screen_message` (blocked messages are stored with `screened=False` and the mentor is told why) |
| `POST /cases/{id}/held` | `accepted/scheduled → held` |
| `POST /cases/{id}/outcome` `{notes(≤1500), next_step(≤300), demonstrated(0..1)}` | calls `escalation.record_outcome`; return `hooks.after_evidence` is for the *learner's* roadmap — the mentor response omits it |
| `POST /cases/{id}/flag` `{detail}` | creates a `SafeguardingReport` about a learner concern (disclosure, risk); also the escalation path for a mentor who suspects wellbeing risk |
Safeguarding lead — extend `routes/admin.py` (C01): `GET /api/admin/reports?status=open`, `POST /api/admin/reports/{id}/resolve` `{note}`,
`POST /api/admin/mentors/{id}/suspend` (suspended mentors drop out of `match_mentor` and their open cases are re-matched).

### 4.4 The rating
`record_outcome(db, learner, case, notes, rating, next_step)` stores `mentor_rating` and feeds `apply_evidence("mentor", score=rating)`. The source's BKT weight is
modest (`SOURCE_PARAMS["mentor"]`: learn 0.5, guess 0.2, slip 0.15). Word the field exactly as in section 1 ("how well did the learner demonstrate the concept?") with 5
labelled steps mapped to `{0.1, 0.3, 0.5, 0.7, 0.9}`. It must **not** read as "how good was the session".

### 4.5 Mock vs real
- The console is available only when `mentors_mode == "db"` (404 otherwise). For demos without real people: create two Supabase test users (one learner, one mentor via the C01 flow and an admin approval) or add a **dev-only** `POST /api/dev/mentor-login` that signs a mock mentor token when `SAARTHI_ENV != prod` and `mentors_mode == "db"`.
- `NoResponder` stays as is (humans reply). `simulate-session` stays mock-only.

### 4.6 Frontend
`pages/MentorConsole.tsx` (tabs New/Active/Follow-up/Closed; availability editor; capacity chip), `pages/MentorCaseView.tsx` (extract the report aside from `Mentors.tsx` into a shared
`components/CaseReport.tsx` used by both sides; message thread; accept/decline dialogs; held; outcome form with the 5-step "demonstrated" scale; "I'm worried about this learner" button),
`Admin.tsx` tab for reports/suspension. Mentor navigation is separate from learner navigation (a mentor who is also a learner gets a role switch in the header). Add EN/Hindi/Hinglish strings.

## 5. Files to create / touch
`engines/escalation.py` (exclusions, `expire_stale`, mentor projection; keep existing function signatures), `deps.py` (`current_mentor`), `models_ext/C02.py`,
`routes/mentor_console.py` (new), `routes/admin.py` (extend), `main.py`, `frontend/src/pages/MentorConsole.tsx`, `MentorCaseView.tsx`, `components/CaseReport.tsx` (extracted from `Mentors.tsx`),
`App.tsx`, `store.tsx` (mentor role), `frontend/src/api_ext/C02.ts`, `docs/SWAPPING_MOCK_TO_REAL.md` (replace "Known difference" paragraph), tests `test_mentor_console.py` (+ adapter-contract additions).

## 6. Tests (minimum)
1. A mentor sees **only** cases assigned to them; another mentor's case id ⇒ 404; a learner token ⇒ 403 on every mentor route.
2. State machine table test: every allowed and disallowed transition (e.g. mentor cannot `close`; cannot `accept` when at capacity; cannot touch an `escalated` wellbeing case).
3. Decline re-matches to a different mentor and never back to the decliner; no one left ⇒ stays `open`.
4. Lazy timeout: a 25-hour-old `matched` case is re-matched on the next read and an audit row is written.
5. Contact details in a mentor message are blocked and recorded (`screened=False`, reason); the learner never sees the blocked text.
6. `outcome` creates exactly one `mentor` `EvidenceEvent` with the mapped score; the learner's roadmap refresh runs; the mentor cannot set mastery any other way.
7. Mentor projection of a case contains no learner id/e-mail and no transcript unless shared.
8. Admin: suspended mentor excluded from matching; open cases re-matched; resolving a report requires a note; non-admin ⇒ 403.
9. Wellbeing cases (`tier="safeguarding"`) never appear in any mentor's list.

## 7. Done when
- [ ] With real accounts: learner opens a case → mentor sees it, accepts, chats, holds the session, records the outcome → learner's twin and roadmap update → follow-up check closes it.
- [ ] Decline/timeout re-matching works; nothing gets stuck in `matched`.
- [ ] Every action is audited; the safeguarding lead can read and resolve reports and suspend a mentor.
- [ ] Mentors cannot see more than the case report and cannot change mastery directly.

## 8. Risks and traps
- Highest-risk feature in the product: it connects adults with possibly-minor learners. Review `screen_message` against evasion ("w h a t s a p p", "nine eight…"), and consider a second screening pass by a human for under-18 cases.
- Don't build video/voice rooms in v1; text inside SAARTHI is the safe, auditable channel.
- `case_view` is used by both sides today; create a separate mentor projection function instead of adding `if role` branches.
- Time zones for slots: store slots as plain strings like today (`"Mon 18:00"`, IST) and say "IST" in the UI.
