# C04 — Live updates in the mentor case chat

| | |
|---|---|
| Source | Chhatrachhaya — real-time messaging (Firestore listeners) |
| SAARTHI today | **Partial.** Messages are stored in the database and `GET /api/cases/{id}` returns them, but the page loads them **once** (`Mentors.tsx` `CaseDetail`, `useEffect(() => { load() }, [id])`). In mock mode the reply arrives instantly in the POST response, so it looks live. With a real mentor, the learner must refresh the page to see a reply (and vice-versa). |
| Priority / size | P2 / S (1 day) |
| Depends on | nothing. Needed by C02 (mentor console) to feel usable; feeds C05 (unread). |
| External accounts | none |

## 1. What the user gets

New messages (and status changes such as "mentor accepted", "session held") appear within a few seconds on both sides without refreshing, with a
subtle "new message" cue; the page stops polling when the tab is hidden. No typing indicators in v1.

## 2. How it works in Chhatrachhaya (the source idea)

| What | File and place (repo root = <https://github.com/mrgraciz123/chhatrachhayaa>) |
|---|---|
| Conversation list subscribed with `onSnapshot` (`where participants array-contains uid`, `orderBy lastMessageAt desc`) | `src/BaatcheetScreen.tsx` l.14–27 |
| Messages of the open chat subscribed with `onSnapshot(orderBy createdAt asc)`; auto-scroll; clears the unread counter while viewing | `src/BaatcheetScreen.tsx` l.30–56 |
| Sending: add the message, bump `lastMessage/lastMessageAt`, `increment(1)` the *other* user's unread count, create a notification | `src/BaatcheetScreen.tsx` `handleSendMessage()` l.58–90 |
| Presence ("N online") with Realtime Database `onDisconnect` | `src/App.tsx` l.244–284 (not needed for SAARTHI) |
| **Typing indicators and voice messages** | listed in `README.md` but **not present** in `src/` (`grep -i typing` finds nothing) |

Tech there: Firebase Firestore real-time listeners (WebSocket under the hood), Firebase Realtime Database for presence.

### Do not copy
- Client-side database access. The browser reading `conversations/*/messages` directly relies on Firestore security rules. SAARTHI keeps
  authorization in the API (every query is scoped to the signed-in user); the browser only talks to Supabase for sign-in.
- Presence/online counters (privacy-hostile for minors and mentors).

## 3. What SAARTHI already has

- `CaseMessage(id, case_id, sender, text, screened, blocked_reason, created_at)`; `escalation.case_view()` already hides unscreened messages from the thread.
- `GET /api/cases/{id}` and `POST /api/cases/{id}/messages` in `routes/mentor.py`; `_case()` ownership check (404 for others).
- Frontend `api.caseDetail`, `api.sendMsg`; `Mentors.tsx` scrolls to the newest message.
- Playbook decision (docs/SWAPPING_MOCK_TO_REAL.md "Known difference"): *polling or Supabase Realtime is purely a frontend change* — this spec chooses polling and explains why.

## 4. How to adapt it

### 4.1 Decision: **short polling with a cursor**, not Supabase Realtime
Supabase Realtime streams table changes to the browser **directly**, which needs row-level-security policies on `case_messages`. SAARTHI deliberately keeps
RLS **on with no policies** so the publishable key cannot read any table (docs/SWAPPING_MOCK_TO_REAL.md step 7); adding policies would duplicate the access rules in a second
place (database SQL vs Python) and for mentors/learners/cases that join across tables is easy to get wrong. Polling is boring, safe, works on SQLite and Postgres, and is enough for
conversations measured in minutes. If load ever demands push, add **Server-Sent Events** from the API (still authorized in Python) — don't open the database to the browser.

### 4.2 Backend — add to `routes/mentor.py`? **No**: put new endpoints in `backend/app/routes/case_sync.py`
| Method + path | Returns |
|---|---|
| `GET /api/cases/{id}/state` | `{status, updated_at, last_message_at, message_count}` — a very cheap query; supports `ETag`/`If-None-Match` (return `304`) |
| `GET /api/cases/{id}/messages?since=<ISO-8601 with microseconds>` | only messages with `created_at > since` (and `screened == True`), ordered by `(created_at, id)`; max 100; `next_since` for the cursor |
The mentor console (C02) gets the same two endpoints under `/api/mentor-console/cases/{id}/…` sharing one implementation. Ids are random hex (not ordered), so the cursor is the
**timestamp**; the client de-duplicates by id (two messages can share a timestamp). Rate-limit at the framework or proxy level (≈ 60 requests/minute/user).

### 4.3 Frontend — one hook for both sides
`frontend/src/hooks/useCaseSync.ts`:
```
useCaseSync(caseId, { fetchState, fetchMessages, onMessages, onStatus }) 
```
- Poll `state` every **3 s** while the tab is visible and the case is *active*; every **15 s** otherwise; **stop** on `document.visibilityState === "hidden"`
  and resume (with an immediate poll) on `visibilitychange`. Exponential back-off (to 30 s) on errors; reset on success.
- Only fetch messages when `state.last_message_at`/`message_count` changed; merge by id; keep scroll position unless the user is at the bottom.
- Optimistic send: show the learner's own message immediately with a "sending" mark; replace on success; if blocked (`blocked: true`) show the existing toast and remove it.
- Use it in `Mentors.tsx` `CaseDetail` (replace the single `load()`), in the mentor case view (C02), and expose `unreadSince(lastSeen)` for C05.
- A visually hidden `aria-live="polite"` region announces "New message from <mentor first name>".

### 4.4 Out of scope (explicit)
Typing indicators, read receipts, online presence, voice messages, push notifications (C05 covers in-app unread + notifications).

## 5. Files to create / touch
`backend/app/routes/case_sync.py` (new, register in `main.py`), `frontend/src/hooks/useCaseSync.ts` (new), `frontend/src/pages/Mentors.tsx` (`CaseDetail`),
`frontend/src/api_ext/C04.ts`, mentor console views (C02), tests `test_case_sync.py`, a short note in `docs/SWAPPING_MOCK_TO_REAL.md` replacing the "Known difference" paragraph.

## 6. Tests (minimum)
1. `since` returns only newer messages, ordered, capped at 100; the cursor returned lets the next call continue with no gaps and no duplicates (two messages with the same timestamp).
2. Messages with `screened=False` never appear for either party.
3. Ownership: another learner or another mentor ⇒ 404; wrong role ⇒ 403.
4. `ETag`/`If-None-Match` ⇒ 304 when nothing changed; changes after a new message.
5. Status change (accept) changes `updated_at` and the state response.
6. Manual two-browser checklist (in the hand-off note): learner and mentor see each other's messages within ~5 s; hidden tab stops requests (check the network tab).

## 7. Done when
- [ ] Two real accounts can converse without refreshing; status changes show up on both sides.
- [ ] Polling pauses when hidden and backs off on errors; no request storms.
- [ ] Authorization is unchanged (all in the API).

## 8. Risks and traps
- Many open tabs multiply requests; keep the 3 s interval only for the *focused* chat page.
- Database cost on Supabase free tier: the `state` query must be indexed (`case_messages.case_id` is indexed) and tiny.
- Time: use `created_at` from the database (`models.now()`), never the client's clock, for the cursor.
