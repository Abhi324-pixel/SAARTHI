# V01: Video interview with resume (built 3 Oct 2026)

Entry: `/interview` (Step 1 optional resume, Step 2 choose Typed, Voice with the agent, or Video). The video interview itself is `/video-interview`. Idea taken from TESSA's Placement Hub interview (resume upload, model-written questions, live camera and microphone), rebuilt with SAARTHI's rules. TESSA stays untouched.

## What it does
1. **Resume** (optional): PDF or `.txt`, max 2 MB. Read in memory and thrown away. The model proposes a summary; code keeps only skills and projects that appear word for word in the file. E-mail and phone are never kept. Stored in `resume_summaries` (export and delete cascade registered).
2. **Setup check** (camera is required for this mode): camera on, face model ready, exactly one face, whole face in frame at a good distance, head angle (turn, nod, tilt), lighting (dark, washed out, backlit), microphone heard. All must pass for 1.5 seconds, plus a tick-box that the interview is recorded to this device.
3. **Interview**: five questions, written by the model from the resume and the previous answer (curated fallback questions if the model is down). After each answer: strengths, each shown only with a quote found word for word in the learner's answer, plus up to three suggestions. Too-short answers get no model call.
4. **Camera stays mandatory**: if the camera stops, the interview pauses behind an overlay until it is back; the recording continues as a new part.
5. **Recording**: video and sound are recorded with `MediaRecorder` and saved in this browser's IndexedDB (chunk by chunk), kept until the learner deletes them under "My interview recordings" (play, download, delete). Never uploaded. `navigator.storage.persist()` is requested so the browser does not evict them.
6. **Report**: per-answer feedback and a "measured in your browser" box: share of time the face was fully in view, facing the camera, in the good volume range, and seconds of speech. Sent to the server as four numbers only (clamped 0-100, unknown keys dropped).

## One resume, three ways to be interviewed
- **Typed**: with the resume ticked, a text interview (`TextResumeInterview`, no camera) using the same backend; without it, the original rounds and packs.
- **Voice with the agent**: `use_resume` is sent to `/api/voice/connect`. The interview tools (`get_next_action`, `record_response` in `agent_tools.py`) then take questions and feedback from the resume interview engine, and any problem falls back to the curated interview. The agent is given only the short summary (skills, project names).
- **Video**: as above.

## Rules it keeps
- Coaching only: no evidence events, no mastery change (test `test_interview_runs_to_the_end_and_never_touches_mastery`).
- No invented numbers: angle, light and volume are measured from the camera and microphone. The limits that turn them into advice (`frontend/src/lib/measure.ts` `LIMITS`) are rules of thumb and are labelled as such. Nothing is scored. TESSA's constant "94% eye contact" was deliberately not copied.
- Fails closed: model down means "feedback unavailable" and curated questions, never made-up feedback. Face model fails to load means the setup cannot pass; the page links to the typed interview.
- Server receives only text answers, the grounded feedback, and the four numbers.

## Where things are
Backend: `models_ext/V01.py`, `engines/resume.py`, `engines/video_interview.py`, `routes/video_interview.py`, tests `tests/test_video_interview.py`. Dependency: `pypdf`.
Frontend: `pages/VideoInterview.tsx`, `components/video/{SetupGate,InterviewRoom,ResumeCard,RecordingsPanel}.tsx`, `hooks/{useFaceCheck,useMicLevel,useRecorder}.ts`, `lib/{measure,recordings}.ts`, `api_ext/V01.ts`.
Face model (bundled, runs offline in the browser): `frontend/public/mediapipe/` (MediaPipe Face Landmarker, from Google's official model storage; engine files from the `@mediapipe/tasks-vision` npm package).
The "Developer only: skip the checks" button exists only in the dev server (`import.meta.env.DEV`), never in a production build.

## Not verified
Real faces: the angle, framing and distance checks were verified with simulated rotations and a simulated picture, never with a real face. Test on a real laptop camera. Also not tested: Safari and Firefox recording, very long interviews and full storage, and phone layouts. The under-18 safeguarding lead should confirm that a required, locally recorded camera is acceptable for minors.
