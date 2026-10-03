# ElevenLabs setup for SAARTHI — what YOU need to do

The code is built around one ElevenLabs **Agent** (live voice conversation) plus the
**Text-to-Speech** and **Speech-to-Text** APIs. You can do this while the app is being built.
The tool names below are fixed — the app already expects exactly these names.

Time needed: about 20 minutes.

## 0. Before you start
1. Claim the free Creator month: join the event Discord → `#coupon-codes` → *Start Redemption*
   (use the same email you registered with). This avoids running out of credits during the demo.
2. Create an API key: ElevenLabs dashboard → *Developers* → *API keys* → create a key.
   Give it access to **Text to Speech**, **Speech to Text** and **ElevenLabs Agents** (read/write).
   Put it in `D:\SAARTHI\backend\.env` as `ELEVENLABS_API_KEY=...` (never paste it in chat).

## 1. Create the agent
Dashboard → *Agents* → *Create agent* → *Blank agent* → name it **SAARTHI Mentor**.

### 1a. Agent tab
- **Language**: default `English`. Under *Additional languages* add `Hindi`.
- **First message** (default): `Namaste {{learner_name}}! I'm SAARTHI, your learning mentor. Ready to continue with {{current_concept_name}}?`
- For the **Hindi** preset, set the first message to:
  `Namaste {{learner_name}}! Main SAARTHI hoon, aapka learning mentor. Chaliye {{current_concept_name}} ke saath aage badhte hain?`
- **LLM**: pick a fast Gemini Flash model from the list (low latency matters more than depth here;
  all learning logic lives in the SAARTHI backend, not in this model).
- **System prompt**: paste the prompt in section 3 below.
- **Voice**: choose a multilingual voice that sounds good in both Hindi and English
  (preview it in both languages). Set the same language presets for Hindi.
- Turn **ON** the system tool **Language detection** (*Add tool* → *System tools*), so the agent follows
  the learner if they switch between English and Hindi.

### 1b. Dynamic variables
In the agent's *Dynamic variables* / test panel, add these (the app sends real values at runtime;
the defaults only matter for the dashboard test button):

| Variable | Default (for testing) |
|---|---|
| `learner_name` | Priya |
| `language_pref` | english |
| `goal` | Backend Developer |
| `current_concept` | sql_outer_join |
| `current_concept_name` | SQL outer joins |
| `session_mode` | explain_back |
| `learner_summary` | Developing in SQL joins; one active misconception. |

### 1c. Security tab
- Enable **Authentication** (recommended). The app then uses a signed URL from the backend,
  so your agent cannot be used by strangers. If you leave it public, put the agent id in
  `ELEVENLABS_AGENT_ID` and set `ELEVENLABS_AGENT_PUBLIC=true`.
- You do **not** need to enable any overrides — the app only uses dynamic variables.

## 2. Add the 7 client tools
*Tools* → *Add tool* → type **Client** (these run inside the learner's browser and call the SAARTHI
backend with the learner's login, so **no public URL or tunnel is needed**).
For each tool turn **"Wait for response" ON**. Names are case-sensitive.
In the dashboard every parameter has its own **Identifier**, **Data type**, **Required** switch and **Description** box (value type: *LLM Prompt*) —
paste the descriptions below into those boxes. Tools 1 and 2 have no parameters.

### 1. `get_learner_context` — no parameters
Description: `Get the learner's current goal, mastery summary, active misconception, today's mission and language. Call this at the start of the session and whenever you need facts about the learner.`

### 2. `get_next_action` — no parameters
Description: `Ask SAARTHI what to do next in this session (which concept to probe, teach, or practise, and why). Always call this before choosing what to talk about next.`

### 3. `explain_topic`
Description: `Get a short, accurate explanation of a concept from SAARTHI, using the teaching strategy it selected. Use it instead of explaining from your own knowledge.`

| Identifier | Type | Required | Parameter description (paste) |
|---|---|---|---|
| `concept_id` | string | no | `The id of the concept to explain, for example sql_outer_join or http_basics. Leave empty to explain the concept currently being discussed.` |
| `language` | string | no | `Language of the explanation: en for English or hi for Hindi. Leave empty to use the learner's language.` |

### 4. `record_response`
Description: `Send the learner's spoken answer or explanation to SAARTHI for scoring. SAARTHI returns what to say next (a follow-up question, a read-back to confirm, or feedback). Call it after EVERY substantive learner answer.`

| Identifier | Type | Required | Parameter description (paste) |
|---|---|---|---|
| `text` | string | **yes** | `What the learner said, as close to word-for-word as possible. Do not summarise, correct or translate it.` |
| `concept_id` | string | no | `The id of the concept the learner is talking about. Leave empty to use the current concept.` |
| `kind` | string | no | `Type of answer: explain_back when the learner is teaching a concept back, answer for a direct answer to a question, interview during a mock interview.` |
| `stated_confidence` | number | no | `How sure the learner said they are, from 1 (guessing) to 5 (certain). Only fill it in if the learner actually said so.` |

### 5. `confirm_statement`
Description: `Tell SAARTHI whether the learner confirmed a read-back statement (for example "You said LEFT JOIN returns only matching rows - is that right?").`

| Identifier | Type | Required | Parameter description (paste) |
|---|---|---|---|
| `statement_id` | string | **yes** | `The statement_id that record_response returned together with the read-back statement.` |
| `confirmed` | boolean | **yes** | `true if the learner agreed that the statement is what they meant, false if they said they misspoke or disagreed.` |

### 6. `show_visual`
Description: `Show a visual on the learner's screen (a diagram, a SQL editor task, or the roadmap).`

| Identifier | Type | Required | Parameter description (paste) |
|---|---|---|---|
| `panel` | string | **yes** | `Which visual to show: join_diagram (how joins work), sql_task (the SQL practice editor), roadmap (the learning plan) or dashboard (overall progress).` |
| `concept_id` | string | no | `The id of the concept the visual relates to. Leave empty for the current concept.` |

### 7. `request_mentor`
Description: `Ask for a human mentor. Use when the learner asks for a person, keeps failing the same concept, or says they feel distressed.`

| Identifier | Type | Required | Parameter description (paste) |
|---|---|---|---|
| `reason` | string | **yes** | `One short sentence saying why a human mentor is needed, in the learner's own words where possible.` |
| `category` | string | no | `technical for coding or SQL problems, career for career or interview guidance, wellbeing if the learner sounds distressed. Leave empty if unsure.` |

## 3. System prompt (paste into the agent's System prompt)

```
You are SAARTHI, a warm, concise voice mentor for {{learner_name}}, who wants to become a {{goal}}.
Language: speak {{language_pref}}. If the learner mixes Hindi and English (Hinglish), reply the same way.
Keep every turn short (1–3 sentences) — this is a spoken conversation.

CURRENT SESSION MODE: {{session_mode}}  |  CURRENT CONCEPT: {{current_concept_name}} ({{current_concept}})
WHAT WE KNOW: {{learner_summary}}

HARD RULES
1. You do NOT decide what the learner knows or grade them. SAARTHI's tools do that.
   Never say "you got it right/wrong" or give scores yourself — wait for tool results.
2. At the start call get_learner_context, then get_next_action, and follow it.
3. After EVERY substantive learner answer call record_response with their words (verbatim as possible).
   Then say what the tool's `say` field tells you to say, in your own words and in the learner's language
   (keep numbers, SQL and technical terms unchanged). If it returns a read-back statement, read it back and ask
   "kya yeh sahi hai? / is that right?", then call confirm_statement with the learner's yes/no.
   If a tool returns `done: true`, wrap up warmly in one or two sentences and stop asking questions.
4. To teach, call explain_topic and paraphrase its result briefly. Do not invent technical facts.
5. If a visual would help (JOIN diagram, SQL task), call show_visual and tell the learner to look.
6. Signature move: when the mode is explain_back, say "Don't answer me — teach it back to me" and let the
   learner explain in their own words. Do not interrupt or correct mid-explanation.
7. If the learner asks for a person, keeps failing, or sounds distressed, call request_mentor.
   If they mention self-harm, abuse, or serious distress: respond kindly, share the Tele-MANAS helpline 14416
   (India), call request_mentor with category "wellbeing", and do not continue the lesson.
8. Never guess emotions from the learner's voice. Never claim to be human.
9. If a tool fails, say so honestly and offer to continue by typing.
```

## 4. Hand over to the app
Copy the agent id (agent page → *Agent ID*) and add to `backend\.env`:

```
ELEVENLABS_API_KEY=...
ELEVENLABS_AGENT_ID=agent_...
ELEVENLABS_VOICE_ID=...        # voice for read-aloud (Text-to-Speech); use the same voice as the agent if you like
```

Then run `python backend/scripts/check_env.py` — it tests the Gemini key, the ElevenLabs key,
the agent id (signed URL), text-to-speech and speech-to-text, and tells you what is missing.

## 5. Demo-day checklist
- [ ] Creator coupon redeemed; credits visible in the dashboard
- [ ] Agent test call works in the dashboard in English **and** Hindi
- [ ] `check_env.py` shows everything green
- [ ] Browser microphone permission allowed on the demo laptop
- [ ] Backup: text mode works even if the network drops (the app falls back automatically)
- [ ] Demo video recorded (required by the Craftora ElevenLabs track) and uploaded to the portal
- [ ] Optional: ElevenLabs showcase submission (fork repo → add project file → pull request → form)

## 6. Troubleshooting
| Symptom | Likely cause | Fix |
|---|---|---|
| "Voice agent is not set up yet" in the app | `ELEVENLABS_AGENT_ID` or `ELEVENLABS_API_KEY` missing | Fill `backend/.env`, restart the API, run `check_env.py` |
| "could not get a signed URL (401/403)" | API key lacks Agents permission, or wrong agent id | Recreate the key with Agents (read) enabled; re-copy the Agent ID |
| Agent connects but never calls tools | Tools not added as **Client** tools, or names differ | Names must match exactly (section 2); "Wait for response" ON |
| Agent answers on its own without tools | System prompt not pasted | Paste section 3 in full; keep the HARD RULES |
| Agent speaks English only | Hindi not added under Additional languages / no Language detection tool | Section 1a |
| Mic does not start | Browser permission blocked | Allow the microphone for 127.0.0.1 in Chrome |
| Public agent works but signed URL fails | Authentication is OFF on the agent | Set `ELEVENLABS_AGENT_PUBLIC=true` (or turn authentication ON) |
| Read-aloud / mic buttons say "not set up" | `ELEVENLABS_VOICE_ID` missing or key lacks TTS/STT permission | Add the voice id; widen key permissions |

The tool contract (arguments and results) is defined in `backend/app/agent_tools.py`; the tests in `backend/tests/test_agent_and_voice.py` exercise every tool.
