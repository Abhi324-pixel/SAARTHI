# C05 — In-app notifications and unread badges

> 🚧 **RED ZONE — Abhinav is building this feature. Do not start it.** If you were told to take it over (or Abhinav is busy and says so), he will name it on the `RED ZONES CLEARED FOR ME:` line of your prompt. You may read this spec; building waits for that line. See [TEAM-SPLIT.md](TEAM-SPLIT.md).

| | |
|---|---|
| Source | Chhatrachhaya — notification documents, bell with unread count, per-conversation unread counters |
| SAARTHI today | **Built 2026-10-02 (tested; bell and empty state checked in a browser, real multi-user flow not).** Before that: **Missing.** Nothing tells a learner (or a mentor) that something happened: a mentor accepted, a reply arrived, a follow-up is due, a guardian approved, a review is due. The only cue is the "roadmap just changed" banner. |
| Priority / size | P1–P2 / M (2 days) |
| Depends on | nothing for learner-side events (they work in mock mode and make a good demo). Mentor-side events need C02. C04 (polling) shares the same poll. |
| External accounts | none. (No e-mail/push in v1.) |

## 1. What the user gets

A **bell** in the header with an unread count; a list of short, translated items ("Ananya accepted your case", "New message from your mentor", "Your follow-up check is due",
"3 reviews are due", "Your guardian approved mentor sessions"), each opening the right page. A **badge on the Chhatrachhaya nav item** and on each case with the number of
unread messages. Mentors get the same bell ("New case matched to you", "Priya replied"). The safeguarding lead gets "New mentor application" and an urgent "New safeguarding report".

## 2. How it works in Chhatrachhaya (the source idea)

| What | File and place (repo root = <https://github.com/mrgraciz123/chhatrachhayaa>) |
|---|---|
| Notification = a document under `users/{uid}/notifications` with `type, icon, text, fromName, navigateTo, read:false, createdAt`; written by the *sender's* browser; failures never block the main action | `src/notifications.ts` (whole file, 40 lines) |
| Listener, `unreadNotifCount`, "mark all read" with a batch write, bell sheet | `src/App.tsx` l.286–297 (listener), l.307 (count), l.309–317 (`handleMarkAllRead`), notification sheet ~l.549 |
| Per-conversation unread counters: `increment(1)` for the other participant on send, reset to 0 when the chat is opened | `src/BaatcheetScreen.tsx` l.43–49, l.73–77, list badge l.208–213 |
| Where notifications are created | `src/MatchmakingScreen.tsx` l.139–145 (new "dost"), `src/BaatcheetScreen.tsx` l.80–86 (new message) |
| Welcome e-mail via EmailJS | `src/emailService.ts` — **contains hard-coded EmailJS service/template/public-key ids; do not copy anything from this file** |

Tech there: Firestore documents + `onSnapshot`; EmailJS REST call from the browser.

### Do not copy
- **Sender-written notifications** (any client can write to anyone's notification list). Notifications are created **by the server** as a side effect of a real event.
- Message text inside the notification (`text: "📩 Name: <first 60 chars>"`). Titles must not leak case content; mentors/learners may be on shared screens, and cases can involve minors.
- E-mail from the browser with embedded keys. Out of scope for v1.
- The emoji-per-type icon table as stored data — icons are a front-end concern.

## 3. What SAARTHI already has

- All the triggering events already exist as code paths: `escalation._match_and_accept` (matched/accepted), `escalation.send_message`, `escalation.record_outcome`, `escalation.followup_check`, `escalation.resume_after_consent`,
  consent `grant`, `mastery` due reviews (`concept_views()[…]["due_for_review"]`).
- `useApp().toast`, `bump()` and the header in `App.tsx` (`Shell`) for the bell; `DICT` in `store.tsx` for translated strings.
- `GET /api/cases` already returns suggestions; `Dashboard.tsx` shows case cards.

## 4. How to adapt it

### 4.1 Tables (new, `models_ext/C05.py`)
```
notifications(id, recipient_id, kind, params JSON, link, dedupe_key, created_at, updated_at, read_at)   # index (recipient_id, read_at)
case_reads(case_id, reader_id, last_read_at)                                                       # PK (case_id, reader_id)
```
`recipient_id` is the **auth user id** (a learner id *or* a mentor/admin id), so there is no FK to `learners`; `DELETE /api/me` and `GET /api/me/export` must handle these rows explicitly
(playbook rule 6). Store `kind` + `params` (e.g. `{"mentor": "Ananya", "concept": "LEFT JOIN"}`) — **not** an English sentence — so the client renders the text from its translation
dictionary (this is what makes Hindi/Hinglish possible, spec C08). `params` may contain only first names and concept/role names, never message text or ids a user shouldn't see.

### 4.2 Engine `backend/app/engines/notify.py`
```
notify(db, recipient_id, kind, params, link, dedupe_key=None)
```
- If `dedupe_key` is given and an **unread** notification with that key exists, update its `params/updated_at` instead of inserting (so ten messages = one "new messages in your case" item).
- Never raises into the caller's transaction for a cosmetic failure (wrap in `try/except` + log) — a failed notification must not fail "accept case".
- Call sites (one line each, in the engine that causes the event, **after** the state change):

| Event | Recipient | `kind` | dedupe key |
|---|---|---|---|
| case matched to mentor | mentor | `case_assigned` | `case:{id}:assigned` |
| mentor accepted / scheduled | learner | `case_accepted` | `case:{id}:accepted` |
| new message | the other party | `case_message` | `case:{id}:msg` |
| session outcome recorded | learner | `case_outcome` | `case:{id}:outcome` |
| follow-up due | learner | `followup_due` | `case:{id}:followup` |
| guardian approved consent | learner | `consent_granted` | `consent:{scope}` |
| reviews due (computed on `GET /api/notifications/summary`, at most once/day) | learner | `reviews_due` | `reviews:{date}` |
| mentor application submitted / safeguarding report filed | admins | `mentor_application` / `safeguarding_report` | `app:{id}` / `report:{id}` |
**Do not** notify about streaks for under-18 learners, and never send "you're falling behind" nudges.

### 4.3 Unread counts
`unread_messages(case) = count(CaseMessage where sender != me-side and screened and created_at > case_reads.last_read_at)`. `POST /api/cases/{id}/read` upserts `case_reads`
(called when the chat is open and visible — C04's hook does it). Notifications of kind `case_message` for that case are marked read at the same time.

### 4.4 Routes — new `backend/app/routes/notifications.py` (usable by learners **and** mentors: depends on `current_account` from C01 once it exists; until then `current_learner`)
| Method + path | Notes |
|---|---|
| `GET /api/notifications/summary` | `{unread, cases: {case_id: unread_messages}}` — tiny; this is the poll |
| `GET /api/notifications?limit=30&before=` | newest first; also lazily deletes read items older than 60 days |
| `POST /api/notifications/read` | `{ids: [...]}` or `{all: true}` — only my rows |
| `POST /api/cases/{id}/read` | as above |

### 4.5 Frontend
`components/NotificationBell.tsx` (bell + badge + dropdown list, "mark all read", keyboard accessible), `hooks/useNotifications.ts` (poll `summary` every 30 s while visible and on window focus; share the timer with C04's hook —
one interval for the whole app, stored in `store.tsx`), nav badge in `App.tsx`, per-case unread chips in `Mentors.tsx`. Render titles from `DICT` keys `notif.<kind>` with `{param}` substitution (EN/Hindi/Hinglish). Optional: `document.title = "(2) SAARTHI"` while unread > 0.

## 5. Files to create / touch
`models_ext/C05.py` (new), `engines/notify.py` (new), `routes/notifications.py` (new), one-line calls in `engines/escalation.py`, consent adapter paths (`adapters/impl.py`, `routes/mentor.py`),
`privacy.py` hooks (`register_export`, `register_delete`) from `models_ext/C05.py`, `frontend/src/components/NotificationBell.tsx`, `hooks/useNotifications.ts`, `store.tsx`, `App.tsx`, `pages/Mentors.tsx`, `frontend/src/api_ext/C05.ts`, tests `test_notifications.py`.

## 6. Tests (minimum)
1. Accepting a case creates exactly one `case_accepted` for the learner; ten learner messages create one deduped `case_message` for the mentor with an updated timestamp.
2. A user can only list/mark their own notifications; marking another user's ids is a no-op (not an error that leaks existence).
3. `case_reads` upsert: unread count drops to 0 after read, rises again with a new message from the other side; own messages never count as unread.
4. `params` of every `kind` contain no message text (assert on a message containing a phone number) and no ids beyond what the recipient may see.
5. A failing `notify` (simulate DB error) does not fail the parent action.
6. `DELETE /api/me` removes the learner's notifications and `case_reads`; export includes them.
7. Reviews-due notification created at most once per day; never created for a learner with nothing due.

## 7. Done when
- [ ] Bell + badge work for learners (and mentors after C02); items link to the right screen; unread counts per case.
- [ ] All text is rendered from translation keys in three languages; no sentences stored in the database.
- [ ] Notifications are created only by the server, never leak message content, and are deleted/exported with the user's data.

## 8. Risks and traps
- Notification storms: always use `dedupe_key`; cap list length; purge old read items lazily.
- Shared devices/minors: keep titles generic ("New message in your mentor case"); no previews.
- Don't build e-mail/WhatsApp/push now. If it comes later: explicit opt-in, no case details in the message, never to a minor's address without the consent flow (D01).
