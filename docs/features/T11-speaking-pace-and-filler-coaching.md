# T11 — Speaking pace, pauses and filler-word coaching (voice answers)

| | |
|---|---|
| Source | TESSA — voice & communication metrics in the interview report, live mic level meter |
| SAARTHI today | **Missing.** Spoken answers are transcribed (ElevenLabs Speech-to-Text via `MicButton`, or the voice agent) and graded for *content*. Nothing tells the learner how they *sound*: too fast, long silences, lots of "basically/matlab". |
| Priority / size | P2 / M (2 days) |
| Depends on | nothing. Strongest value together with T08 (behavioural interview). |
| External accounts | none (ElevenLabs STT is already configured). **Verify first** what the STT response contains — see 4.1. |

## 1. What the learner gets

After they *speak* an answer (mic button in Teach-it-back or the interview), a small, kind coaching line appears next to the transcript:
"112 words per minute · 2 pauses longer than a second · you used 'basically' ×3". The interview report adds a short "How you sounded"
section across all spoken answers with one practical tip. It is **coaching, not grading**: no score, it never changes a level, it is
never shared with mentors, and typed answers get no speech metrics (there is no audio to measure).

## 2. How it works in TESSA (the source idea)

| What | File and place (relative to TESSA root) |
|---|---|
| Per-turn word count, filler list, pace = words / (audio seconds/60), average answer length, a feedback sentence | `backend/app/interview/communication.py` `analyze_communication()` (l.12–81), `FILLER_WORDS` (l.9) |
| Browser speech-to-text (Web Speech API, `lang='en-US'`, continuous + interim results) | `public/index.html` `startSpeechRecognitionBtn` handler (l.6046–6122) |
| Live microphone level meter (`AudioContext` + `AnalyserNode`, `requestAnimationFrame`) | `public/index.html` `initPlacementAudio()` (l.5603–5668), `stopPlacementAudio()` (l.5668) |
| Per-turn elapsed time sent as `audio_duration_seconds` | `public/index.html` `submitTurnAnswer()` (l.5819–5829) → `backend/app/api/interview.py` `respond_turn()` (l.139–152) |
| Metric model | `backend/app/interview/session.py` `VoiceMetrics` (l.22–31) |

Tech there: regex word counting in Python; browser Web Speech + Web Audio APIs (Chrome-centric).

### Do not copy (this module has real bugs and invented numbers)
- **Multi-word fillers never match**: the code splits the answer into single words and tests `w in FILLER_WORDS`, so `"you know"`,
  `"so yeah"`, `"i mean"` (l.9) can never be counted (l.33–37).
- `"like"`, `"actually"`, `"basically"` are counted as fillers even when they are normal words ("I like SQL").
- **The "duration" is wall-clock time since the question appeared** (`submitTurnAnswer`, l.5820), i.e. thinking + typing + speaking. WPM
  computed from it is wrong; when no duration is sent it assumes 2.5 words/second (`communication.py` l.41) — circular.
- `pause_count = filler*0.7` and `repetition_count = filler*0.4` (l.76–77) are fabricated, not measured.
- `clarity_score` (base 85 minus penalties) and blending it into "Communication" in the overall interview score. SAARTHI shows measured
  numbers only; no clarity score.

## 3. What SAARTHI already has

- `components/audio.tsx` `MicButton`: records with `MediaRecorder`, posts the blob to `/api/voice/stt`, returns text.
- `routes/voice.py` `stt()` (l.83–91) and `voice/elevenlabs.py` `speech_to_text()` (l.68–79): today it returns only
  `text, language_code, duration, language_probability`.
- `TranscriptTurn.meta` (JSON) — already stores `{"audio_seconds", "channel"}` for each learner turn (`explainback._answer_core`).
- `explainback.interview_report()`; `ExplainBack.tsx`, `Interview.tsx`; the "audio is never stored" rule (only text transcripts).

## 4. How to adapt it

### 4.1 First, verify what the STT API returns (30 minutes — do not skip)
The ElevenLabs Speech-to-Text response is expected to include a `words` array with per-word `start`/`end` times and a `type`
(`word` / `spacing` / `audio_event`). **Confirm this against the live API** — extend `scripts/check_env.py`'s STT round trip to print
the response keys, and record the result in this file. Also test whether the transcript keeps disfluencies such as "um/uh" (many STT
systems drop them). Decision rule: if `words` timestamps are missing, ship only the filler/marker counts from text and **skip WPM and
pauses** — do not estimate them.

### 4.2 Speech metrics — pure function `backend/app/engines/speech.py`
```
analyze(words: list[{text, start, end, type}], language: str) -> {
  "words": 118, "speaking_seconds": 63.2, "wpm": 112,
  "pauses": {"count_over_1s": 2, "longest_s": 2.4},
  "markers": {"basically": 3, "matlab": 2}, "markers_per_100_words": 4.2,
  "tips": ["code", ...] }          # codes, not prose; the UI turns them into text
```
Definitions (put them in the docstring and in tests):
- `speaking_seconds` = last word `end` − first word `start` (leading/trailing silence excluded). `wpm = words / (speaking_seconds/60)`; return `None` if < 8 words or < 5 s.
- A **pause** = gap between consecutive words > 1.0 s (inside the utterance only).
- **Markers** (not "fillers"): a list per language matched on the **token sequence**, so multi-word markers work: English `um, uh, er, "you know", "i mean", basically, actually`;
  Hinglish/Hindi `matlab, toh, "kya hai", "aisa hai ki", yaani, na`. Do **not** include `like` or other words that are usually ordinary.
  Keep the lists in `content/speech_markers.json` so a native speaker can edit them (C08 reviewers).
- Tips (codes): `PACE_FAST` (> 170 wpm), `PACE_SLOW` (< 90 wpm), `LONG_PAUSES`, `MANY_MARKERS` (> 6 per 100 words), `GOOD` — thresholds in one constants block.
  Wording is non-judgemental: "Many listeners find 110–160 words per minute comfortable." Never "bad".

### 4.3 Plumbing
- `voice/elevenlabs.speech_to_text()` also returns `words` (normalised list) when present.
- `routes/voice.py` `stt()` returns `{text, language_code, duration, speech: analyze(...) | null}` — **server-side** calculation.
- The explain-back / interview answer endpoints accept an optional `speech` object (`EBAnswer`, `InterviewAnswer` in `routes/learn.py`)
  and store it in `TranscriptTurn.meta["speech"]`. The values are display-only: validate ranges (`wpm 20–400`, counts ≥ 0) and **never**
  use them for scoring, evidence, mentor reports or `/api/cohort`.
- `interview_report()` adds `"speech": {"answers_with_audio": n, "median_wpm": …, "top_markers": […], "tips": […]}` when ≥ 1 spoken answer; absent otherwise.
- Voice-agent (ElevenLabs conversation) sessions: out of scope for v1 — only the `MicButton` recordings have audio+timestamps in our hands.

### 4.4 Frontend
- `components/SpeechChips.tsx`: renders the metrics next to the transcribed text; hidden when `speech` is null. Show a one-line
  explanation on hover/tap and a link "How is this measured?" (words ÷ speaking time, pauses > 1 s).
- `MicButton`: add a live input-level bar while recording (port the *idea* of TESSA's analyser meter — `AudioContext`,
  `createAnalyser`, `getByteFrequencyData`, one `requestAnimationFrame` loop; clean up tracks and the context on stop). It also
  prevents the common "I couldn't hear anything" failure.
- Report section in `Interview.tsx` ("How you sounded"); hidden for typed-only interviews. EN/Hindi/Hinglish strings.

## 5. Files to create / touch
`engines/speech.py` (new), `content/speech_markers.json` (new), `voice/elevenlabs.py`, `routes/voice.py`, `routes/learn.py` (request models),
`engines/explainback.py` (store `meta["speech"]`, report summary), `scripts/check_env.py` (print STT keys), `frontend/src/components/audio.tsx`,
`SpeechChips.tsx` (new), `pages/Interview.tsx`, `components/ExplainBack.tsx`, `frontend/src/api_ext/T11.ts`, tests `test_speech.py`.

## 6. Tests (minimum)
1. Exact numbers from a hand-written word list: 120 words over 60 s ⇒ `wpm == 120`; leading 5 s of silence is excluded.
2. Pauses: gaps of 0.9 s are not counted; 1.2 s is; `longest_s` correct.
3. Multi-word markers: "you know" ×2 counted as 2; "I like SQL" ⇒ 0 markers; Hinglish "matlab" counted for `language="hinglish"`.
4. Too few words / too short ⇒ `wpm is None` (no estimate); typed answer (no words array) ⇒ `speech: null`.
5. Client-supplied `speech` with `wpm=9000` ⇒ 422; metrics never appear in `EvidenceEvent`, case reports or `/api/cohort` (grep-style test on the report builders).
6. STT response without `words` ⇒ route still returns text, `speech: null`.

## 7. Done when
- [ ] Spoken answers show pace/pauses/markers with plain explanations; typed answers show nothing.
- [ ] The report's "How you sounded" appears only when audio existed; no score anywhere.
- [ ] Metrics are not used for grading or shared; audio is still never stored.
- [ ] Marker lists reviewed by a Hindi/Hinglish speaker.

## 8. Risks and traps
- Mic quality, accents and background noise change STT timing; keep the tone gentle and the thresholds wide.
- Don't coach accent or fluency — it would contradict the grader's rule "ignore accent, grammar, fluency".
- Hinglish code-switching: `language_code` may come back as `hi` for mixed speech; match markers from **both** lists when the language is `hindi`/`hinglish`.
- Browser `getUserMedia` needs HTTPS or `localhost`; the meter must fail soft (the recorder still works without it).
