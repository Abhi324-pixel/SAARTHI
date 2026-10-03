import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api'
import { apiV01, type InterviewAnswerResult, type InterviewReport, type InterviewStart } from '../../api_ext/V01'
import type { SpeechMetrics } from '../../api_ext/T11'
import { useFaceCheck } from '../../hooks/useFaceCheck'
import { useMicLevel } from '../../hooks/useMicLevel'
import { useRecorder } from '../../hooks/useRecorder'
import { LIMITS } from '../../lib/measure'
import { useApp } from '../../store'
import { MicButton, SpeakButton } from '../audio'
import { Bar, Callout, ConfidencePicker } from '../ui'
import { SpeechChips } from '../SpeechChips'
import { openCameraAndMic } from './SetupGate'

export interface RoomResult { report: InterviewReport; recordingIds: string[]; speechByTurn: (SpeechMetrics | null)[] }

/** The interview itself. The camera must stay on: if it stops, the interview pauses until it is back. */
export default function InterviewRoom({ interview, stream: initialStream, onDone }: { interview: InterviewStart; stream: MediaStream; onDone: (r: RoomResult) => void }) {
  const { toast, lang } = useApp()
  const [stream, setStream] = useState<MediaStream>(initialStream)
  const [question, setQuestion] = useState(interview.question ?? '')
  const [answered, setAnswered] = useState(interview.answered)
  const [text, setText] = useState('')
  const [conf, setConf] = useState<number | null>(null)
  const [speech, setSpeech] = useState<SpeechMetrics | null>(null)
  const [busy, setBusy] = useState(false)
  const [last, setLast] = useState<InterviewAnswerResult | null>(null)
  const [cameraLost, setCameraLost] = useState(false)
  const [autoRead, setAutoRead] = useState(true)
  const [noFaceSec, setNoFaceSec] = useState(0)
  const video = useRef<HTMLVideoElement>(null)
  const speechByTurn = useRef<(SpeechMetrics | null)[]>([])
  const recordingIds = useRef<string[]>([])
  const parts = useRef(0)
  const lastStream = useRef<MediaStream | null>(null)
  const liveTrack = useRef<MediaStreamTrack | undefined>(initialStream.getVideoTracks()[0])   // the camera that counts right now
  const finished = useRef(false)
  const audio = useRef<HTMLAudioElement | null>(null)

  const { state: face, stats: faceStats } = useFaceCheck(video, !cameraLost)
  const { db, level, stats: micStats } = useMicLevel(cameraLost ? null : stream)
  const rec = useRecorder()

  // show the camera and start recording it to this device
  useEffect(() => { if (video.current) { video.current.srcObject = stream; video.current.play().catch(() => {}) } }, [stream])
  useEffect(() => {
    let cancelled = false
    if (lastStream.current !== stream) { lastStream.current = stream; parts.current += 1 }
    rec.start(stream, `Interview ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}${parts.current > 1 ? ` (part ${parts.current})` : ''}`, interview.id)
      .then(id => { if (id && !cancelled) recordingIds.current.push(id) })
    return () => { cancelled = true }
  }, [stream])

  // the camera is mandatory: notice when it stops, and when the learner has left the picture
  useEffect(() => {
    const t = stream.getVideoTracks()[0]
    if (!t) { setCameraLost(true); return }
    const lost = () => { if (t === liveTrack.current) setCameraLost(true) }     // a late signal from an old, replaced camera is ignored
    t.addEventListener('ended', lost)
    const poll = window.setInterval(() => { if (t === liveTrack.current && (t.readyState !== 'live' || !t.enabled)) setCameraLost(true) }, 1000)
    return () => { t.removeEventListener('ended', lost); window.clearInterval(poll) }
  }, [stream])
  useEffect(() => {
    const t = window.setInterval(() => setNoFaceSec(s => (face.engine === 'ready' && face.faces === 0 ? s + 1 : 0)), 1000)
    return () => window.clearInterval(t)
  }, [face.engine, face.faces])
  useEffect(() => { if (cameraLost) rec.stop() }, [cameraLost])

  // always release the camera and microphone when leaving
  // (React may run an effect's cleanup and setup back to back while developing, so only release if we really left)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      window.setTimeout(() => { if (!mounted.current) { audio.current?.pause(); rec.stop().finally(() => stream.getTracks().forEach(t => t.stop())) } }, 0)
    }
  }, [stream])

  const speak = useCallback(async (q: string) => {
    try {
      const blob = await api.tts(q.replace(/\s+/g, ' ').slice(0, 900), lang)
      audio.current?.pause()
      const a = new Audio(URL.createObjectURL(blob))
      audio.current = a
      await a.play()
    } catch { /* autoplay blocked or voice unavailable: the Listen button still works */ }
  }, [lang])
  useEffect(() => { if (autoRead && question && !cameraLost) speak(question) }, [question])

  async function reopenCamera() {
    try {
      const s = await openCameraAndMic()
      liveTrack.current = s.getVideoTracks()[0]
      stream.getTracks().forEach(t => t.stop())     // release the old, dead stream (and its microphone) first
      setStream(s); setCameraLost(false)
    } catch (e: any) { toast(e.message, 'err') }
  }

  async function submit() {
    if (!text.trim() || busy) return
    setBusy(true)
    try {
      const r = await apiV01.answer(interview.id, text.trim())
      speechByTurn.current.push(speech)
      setLast(r); setAnswered(r.answered); setText(''); setSpeech(null); setConf(null)
      if (r.done) await finish()
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }

  async function finish() {
    if (finished.current) return
    finished.current = true
    const saved = await rec.stop()
    const fs = faceStats.current, ms = micStats.current
    const pct = (a: number, b: number) => (b > 0 ? (a / b) * 100 : undefined)
    const metrics: Record<string, unknown> = {
      face_in_frame_pct: pct(fs.oneFaceInFrame, fs.frames), facing_camera_pct: pct(fs.facing, fs.frames),
      voice_level_ok_pct: pct(ms.goodMs, ms.speakingMs), speaking_seconds: ms.speakingMs / 1000, recording_saved: !!saved && rec.state !== 'error',
    }
    try {
      const report = await apiV01.finish(interview.id, metrics)
      stream.getTracks().forEach(t => t.stop())
      onDone({ report, recordingIds: recordingIds.current, speechByTurn: speechByTurn.current })
    } catch (e: any) { finished.current = false; toast(e.message, 'err') }
  }

  function nextQuestion() { if (last?.next_question) { setQuestion(last.next_question); setLast(null) } }

  const fb = last?.feedback
  const meterPct = Math.max(0, Math.min(100, ((db + 70) / 70) * 100))

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px] items-start">
      <div className="space-y-4 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <div><div className="eyebrow">Video interview · question {Math.min(answered + 1, interview.total)} of {interview.total}</div><h1 className="h-page">Your interview</h1></div>
          <label className="text-xs flex items-center gap-1.5 text-muted"><input type="checkbox" checked={autoRead} onChange={e => setAutoRead(e.target.checked)} /> Read questions aloud</label>
        </div>
        <Bar value={answered / interview.total} h={6} />

        <div className="card p-4 space-y-3">
          <div className="rounded-2xl rounded-tl-sm bg-teal-soft px-4 py-3 text-sm leading-relaxed">
            <b className="block text-[11px] text-teal uppercase tracking-wide">Interviewer</b>{last ? 'Thank you. Here is some feedback, then the next question.' : question}
          </div>
          {!last && <SpeakButton text={question} label="Hear the question" />}

          {fb && last && (
            <div className="space-y-2 text-sm" aria-live="polite">
              {fb.status === 'unavailable' && <Callout tone="saffron" title="Feedback unavailable right now">The feedback service did not answer, so I will not guess. Your answer was saved and the interview continues.</Callout>}
              {fb.status === 'too_short' && <Callout tone="saffron" title="That answer was short">Try two or three full sentences next time.</Callout>}
              {fb.strengths.length > 0 && <div><b className="text-navy">What you did well</b><ul className="mt-1 space-y-1.5">{fb.strengths.map((s, i) => <li key={i}>✓ {s.point} <span className="text-muted italic">— “{s.quote}”</span></li>)}</ul></div>}
              {fb.gaps.length > 0 && <div><b className="text-navy">To improve</b><ul className="mt-1 list-disc ml-5 space-y-0.5">{fb.gaps.map((g, i) => <li key={i}>{g}</li>)}</ul></div>}
              {speechByTurn.current[speechByTurn.current.length - 1] && <SpeechChips speech={speechByTurn.current[speechByTurn.current.length - 1]} />}
              {!last.done && <button type="button" className="btn btn-saffron" onClick={nextQuestion}>Next question →</button>}
            </div>
          )}
        </div>

        {!last && (
          <div className="card p-4 space-y-2.5 relative">
            {cameraLost && (
              <div className="absolute inset-0 z-10 rounded-2xl bg-white/95 flex flex-col items-center justify-center text-center p-6 gap-3" role="alertdialog" aria-label="Camera stopped">
                <div className="text-3xl">📷</div>
                <b className="text-navy">Your camera stopped</b>
                <p className="text-sm text-muted">This interview needs the camera on. The interview is paused. Turn the camera back on to continue; your next part will be saved as a new recording.</p>
                <button type="button" className="btn btn-saffron" onClick={reopenCamera}>Turn the camera back on</button>
              </div>)}
            <textarea className="input min-h-[120px]" value={text} onChange={e => setText(e.target.value)} disabled={busy || cameraLost}
              placeholder="Speak with the microphone button, or type your answer…" aria-label="Your answer" />
            {speech && <SpeechChips speech={speech} />}
            <div className="flex flex-wrap items-end justify-between gap-3">
              <ConfidencePicker value={conf} onChange={setConf} />
              <div className="flex gap-2">
                <MicButton onText={t => setText(p => (p ? p + ' ' : '') + t)} onSpeech={s => setSpeech(s)} disabled={busy || cameraLost} />
                <button type="button" className="btn btn-saffron" disabled={busy || cameraLost || !text.trim()} onClick={submit}>{busy ? 'Reading your answer…' : 'Submit answer'}</button>
              </div>
            </div>
          </div>)}
      </div>

      <aside className="card p-3 space-y-2.5 lg:sticky lg:top-4" aria-label="Your camera and recording">
        <div className="relative aspect-[4/3] rounded-xl overflow-hidden bg-navy/90">
          <video ref={video} muted playsInline autoPlay aria-label="Your camera, only you can see this" className="h-full w-full object-cover [transform:scaleX(-1)]" />
          <span className={`absolute left-2 top-2 chip text-white text-[10px] ${rec.state === 'recording' ? 'bg-red-600/90' : 'bg-black/60'}`}>{rec.state === 'recording' ? '● REC · saved on this device' : rec.state === 'error' ? 'Not recording' : 'Starting…'}</span>
        </div>
        <ul className="text-xs space-y-1" aria-live="polite">
          <li className={face.faces === 1 && face.inFrame ? 'text-lvl-proficient font-semibold' : 'text-lvl-unknown font-semibold'}>{face.engine !== 'ready' ? 'Face check loading…' : face.faces === 1 && face.inFrame ? '✓ Face in view' : face.faces > 1 ? '! More than one face in view' : '! Face not fully in view'}</li>
          <li className={face.facing ? 'text-lvl-proficient font-semibold' : 'text-muted'}>{face.facing ? '✓ Facing the camera' : face.faces === 1 ? 'Face the camera' : ''}</li>
          <li className={face.light === 'ok' ? 'text-lvl-proficient font-semibold' : 'text-muted'}>{face.light === 'ok' ? '✓ Lighting fine' : face.light === 'dark' ? 'Too dark' : face.light === 'backlit' ? 'Light is behind you' : face.light === 'bright' ? 'Too bright' : ''}</li>
        </ul>
        {noFaceSec >= 6 && <p className="text-xs text-lvl-unknown font-semibold" role="status">I cannot see you. Please sit back in front of the camera.</p>}
        <div>
          <div className="flex justify-between text-[11px] text-muted mb-1"><span>Voice level</span><span>{level === 'silent' ? 'silent' : level === 'quiet' ? 'too quiet' : level === 'loud' ? 'too loud' : 'good'}</span></div>
          <div className="relative h-2.5 rounded-full bg-line overflow-hidden" role="meter" aria-label="Voice level" aria-valuemin={-70} aria-valuemax={0} aria-valuenow={Math.round(db)}>
            <div className="absolute inset-y-0 bg-teal-soft" style={{ left: `${((LIMITS.goodMinDb + 70) / 70) * 100}%`, width: `${((LIMITS.goodMaxDb - LIMITS.goodMinDb) / 70) * 100}%` }} />
            <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${meterPct}%`, background: level === 'good' ? '#10b981' : level === 'loud' ? '#ef4444' : '#e07a1f' }} />
          </div>
        </div>
        {rec.error && <p className="text-xs text-lvl-unknown font-semibold" role="alert">{rec.error}</p>}
        <p className="text-[11px] text-muted leading-snug">Recorded with sound to this device only. SAARTHI does not receive it. Find it later under "My interview recordings".</p>
        {answered > 0 && !last?.done && <button type="button" className="btn btn-ghost btn-sm w-full" onClick={finish}>End the interview and see my report</button>}
      </aside>
    </div>
  )
}
