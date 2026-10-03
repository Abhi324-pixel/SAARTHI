import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useFaceCheck } from '../../hooks/useFaceCheck'
import { useMicLevel } from '../../hooks/useMicLevel'
import { LIMITS } from '../../lib/measure'
import { requestPersistence } from '../../lib/recordings'
import { Bar } from '../ui'

export async function openCameraAndMic(): Promise<MediaStream> {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error('This browser cannot open a camera and microphone here. Please use Chrome, Edge or Firefox on a laptop or desktop.')
  try {
    return await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
      audio: { echoCancellation: true, noiseSuppression: false, autoGainControl: false },   // no auto-gain, so the meter shows the real level
    })
  } catch (e: any) {
    if (e?.name === 'NotAllowedError') throw new Error('Camera and microphone permission was not given. Allow both in the browser address bar, then press the button again.')
    if (e?.name === 'NotFoundError') throw new Error('No camera or no microphone was found. Connect one and try again.')
    throw new Error('The camera or microphone could not be opened (is another app using it?). Close it and try again.')
  }
}

/** The camera is required for the video interview. Every check below is measured from the live camera and microphone. */
export default function SetupGate({ isMinor, onStart }: { isMinor: boolean; onStart: (stream: MediaStream) => void }) {
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [consent, setConsent] = useState(false)
  const [micHeard, setMicHeard] = useState(false)
  const [passMs, setPassMs] = useState(0)
  const video = useRef<HTMLVideoElement>(null)
  const handedOver = useRef(false)

  const { state: face } = useFaceCheck(video, !!stream)
  const { db, level } = useMicLevel(stream)

  useEffect(() => { if (video.current && stream) { video.current.srcObject = stream; video.current.play().catch(() => {}) } }, [stream])
  useEffect(() => { if (db >= LIMITS.speakingDb) setMicHeard(true) }, [db])
  // if the learner leaves this screen without starting, release the camera
  useEffect(() => () => { if (!handedOver.current) stream?.getTracks().forEach(t => t.stop()) }, [stream])

  async function allow() {
    setBusy(true); setErr(null)
    try { setStream(await openCameraAndMic()) } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }

  const cameraOn = !!stream?.getVideoTracks().some(t => t.readyState === 'live')
  const hasFace = face.faces >= 1
  const checks: { ok: boolean; label: string; hint: string }[] = [
    { ok: cameraOn, label: 'Camera is on', hint: 'Press "Allow camera and microphone".' },
    { ok: face.engine === 'ready', label: 'Face check is ready', hint: face.engine === 'error' ? 'The face check could not load. Reload the page; if it keeps failing, use the typed interview.' : 'Loading the face check…' },
    { ok: face.faces === 1, label: 'Exactly one face in view', hint: hasFace ? 'Only you should be in the picture.' : 'I cannot see your face. Look at the camera and make sure it is not covered.' },
    { ok: hasFace && face.inFrame && face.distance === 'ok', label: 'Face fully in frame, at a good distance',
      hint: !hasFace ? 'Waiting for your face.' : !face.inFrame ? 'Move so your whole face is inside the picture.' : face.distance === 'far' ? 'Move a little closer to the camera.' : 'Move a little back from the camera.' },
    { ok: face.facing, label: 'Camera angle: facing the camera',
      hint: face.yaw === null ? 'Waiting for your face.' : (face.yaw ?? 0) > LIMITS.yawDeg ? 'Turn your head to face the camera.' : (face.pitch ?? 0) > LIMITS.pitchDeg ? 'Raise or lower the screen so the camera is at eye level.' : 'Straighten your head (it is tilted sideways).' },
    { ok: face.light === 'ok', label: 'Lighting is fine',
      hint: face.light === 'dark' ? 'It is too dark. Face a window or a lamp.' : face.light === 'bright' ? 'The picture is washed out. Reduce the light on your face.' : face.light === 'backlit' ? 'The light is behind you. Turn so the light is in front of you.' : 'Checking the light…' },
    { ok: micHeard && level !== 'quiet', label: 'Microphone hears you', hint: micHeard ? 'Speak a little louder, or move closer to the microphone.' : 'Say a sentence out loud, like "Hello, this is a mic check".' },
  ]
  const allOk = checks.every(c => c.ok)
  useEffect(() => {
    const t = window.setInterval(() => setPassMs(p => (allOk ? p + 250 : 0)), 250)
    return () => window.clearInterval(t)
  }, [allOk])
  const ready = allOk && passMs >= 1500 && consent

  async function begin() {
    if (!stream) return
    await requestPersistence()
    handedOver.current = true
    onStart(stream)
  }

  const meterPct = Math.max(0, Math.min(100, ((db + 70) / 70) * 100))

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] items-start">
      <div className="card p-3 space-y-3">
        <div className="relative aspect-[4/3] rounded-xl overflow-hidden bg-navy/90 text-white flex items-center justify-center">
          {stream
            ? <video ref={video} muted playsInline autoPlay aria-label="Your camera, only you can see this" className="h-full w-full object-cover [transform:scaleX(-1)]" />
            : <div className="text-center px-6"><div className="text-3xl">🎥</div><div className="mt-2 font-semibold">The camera is required for this interview</div><div className="text-xs text-white/70 mt-1">Like a real video interview. Nothing is sent to SAARTHI.</div></div>}
          {stream && face.box && <div className="absolute border-2 rounded-lg pointer-events-none" style={{ left: `${(1 - (face.box.x + face.box.w)) * 100}%`, top: `${face.box.y * 100}%`, width: `${face.box.w * 100}%`, height: `${face.box.h * 100}%`, borderColor: face.facing ? '#34d399' : '#fbbf24' }} />}
        </div>
        {stream && (
          <div>
            <div className="flex items-center justify-between text-xs text-muted mb-1"><span>Microphone level</span><span>{db <= -99 ? 'no sound' : `${Math.round(db)} dBFS`} · {level === 'silent' ? 'silent' : level === 'quiet' ? 'too quiet' : level === 'loud' ? 'too loud' : 'good'}</span></div>
            <div className="relative h-3 rounded-full bg-line overflow-hidden" role="meter" aria-label="Microphone level" aria-valuemin={-70} aria-valuemax={0} aria-valuenow={Math.round(db)}>
              <div className="absolute inset-y-0 bg-teal-soft" style={{ left: `${((LIMITS.goodMinDb + 70) / 70) * 100}%`, width: `${((LIMITS.goodMaxDb - LIMITS.goodMinDb) / 70) * 100}%` }} />
              <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${meterPct}%`, background: level === 'good' ? '#10b981' : level === 'loud' ? '#ef4444' : '#e07a1f' }} />
            </div>
            <p className="text-[11px] text-muted mt-1">dBFS: 0 is the loudest possible. Speak so the bar stays in the green zone.</p>
          </div>
        )}
        {!stream && <button type="button" className="btn btn-saffron w-full py-3" disabled={busy} onClick={allow}>{busy ? 'Opening…' : 'Allow camera and microphone'}</button>}
        {err && <p className="text-sm text-lvl-unknown font-semibold" role="alert">{err} <Link to="/interview" className="underline">Use the typed or voice interview instead</Link></p>}
      </div>

      <div className="card p-5 space-y-3">
        <div className="eyebrow">Before we start</div>
        <h2 className="text-xl font-extrabold text-navy">Setup check</h2>
        <ul className="space-y-2" aria-live="polite">
          {checks.map(c => (
            <li key={c.label} className="flex gap-2.5 text-sm">
              <span className={`mt-0.5 font-extrabold ${c.ok ? 'text-lvl-proficient' : 'text-muted'}`} aria-hidden>{c.ok ? '✓' : '○'}</span>
              <div><div className={c.ok ? 'font-semibold' : ''}>{c.label}</div>{!c.ok && stream && <div className="text-xs text-muted">{c.hint}</div>}</div>
            </li>))}
        </ul>
        <Bar value={Math.min(1, checks.filter(c => c.ok).length / checks.length)} h={6} />
        <label className="flex gap-2 items-start text-sm pt-1">
          <input type="checkbox" className="mt-1" checked={consent} onChange={e => setConsent(e.target.checked)} />
          <span>I understand this interview is <b>recorded with video and sound</b>, saved <b>only on this device</b>, and kept until I delete it in "My interview recordings". SAARTHI does not receive the video or audio.{isMinor && <> Because I am under 18, a parent or guardian should know about it.</>}</span>
        </label>
        <button type="button" className="btn btn-saffron w-full py-3" disabled={!ready} onClick={begin}>
          {!stream ? 'Allow the camera first' : !allOk ? 'Fix the checks above' : passMs < 1500 ? 'Hold still…' : !consent ? 'Tick the box to continue' : 'Start the interview →'}
        </button>
        {import.meta.env.DEV && stream && <button type="button" className="btn btn-ghost btn-sm w-full" onClick={begin}>Developer only: skip the checks (does not exist in the production build)</button>}
        <p className="text-[11px] text-muted">The checks use a small face-detection model that runs inside your browser. The numbers (angle, light, volume) are measured from your own camera and microphone, and the limits are rules of thumb, not a score.</p>
      </div>
    </div>
  )
}
