import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { apiV01, type InterviewStart, type ResumeSummary } from '../api_ext/V01'
import { Callout } from '../components/ui'
import InterviewReport from '../components/video/InterviewReport'
import InterviewRoom, { type RoomResult } from '../components/video/InterviewRoom'
import RecordingsPanel from '../components/video/RecordingsPanel'
import ResumeCard from '../components/video/ResumeCard'
import SetupGate from '../components/video/SetupGate'
import { useApp } from '../store'

type Stage = 'home' | 'setup' | 'room' | 'report'

export default function VideoInterview() {
  const { me, toast } = useApp()
  const nav = useNavigate()
  const fromInterview = (useLocation().state as { fromInterview?: boolean; useResume?: boolean } | null) ?? null
  const [stage, setStage] = useState<Stage>(fromInterview?.fromInterview ? 'setup' : 'home')
  const [resume, setResume] = useState<ResumeSummary | null>(null)
  const [useResume, setUseResume] = useState(fromInterview?.useResume ?? true)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [interview, setInterview] = useState<InterviewStart | null>(null)
  const [result, setResult] = useState<RoomResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [recKey, setRecKey] = useState(0)

  useEffect(() => { if (!fromInterview?.fromInterview) setUseResume(resume !== null) }, [resume])

  async function begin(s: MediaStream) {
    setBusy(true)
    try {
      const iv = await apiV01.start(useResume && !!resume)
      setStream(s); setInterview(iv); setStage('room')
    } catch (e: any) { s.getTracks().forEach(t => t.stop()); toast(e.message, 'err'); setStage('home') } finally { setBusy(false) }
  }

  function done(r: RoomResult) { setResult(r); setStream(null); setRecKey(k => k + 1); setStage('report') }

  if (stage === 'setup') return <div className="max-w-5xl mx-auto space-y-4"><div><div className="eyebrow">Video interview</div><h1 className="h-page">Get ready</h1></div>
    {busy ? <p className="text-sm text-muted">Starting your interview…</p> : <SetupGate isMinor={!!me?.is_minor} onStart={begin} />}
    <p className="text-sm text-muted">{useResume ? 'The questions will come from your resume.' : 'The questions will be general interview questions (no resume used).'}</p>
    <button type="button" className="btn btn-ghost btn-sm" onClick={() => (fromInterview?.fromInterview ? nav('/interview') : setStage('home'))}>← Back</button></div>

  if (stage === 'room' && interview && stream) return <div className="max-w-5xl mx-auto"><InterviewRoom interview={interview} stream={stream} onDone={done} /></div>

  if (stage === 'report' && result) return <InterviewReport r={result.report} speech={result.speechByTurn} recKey={recKey} showRecordings onAgain={() => { setResult(null); setInterview(null); setStage('home') }} />

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div>
        <div className="eyebrow">Video interview</div>
        <h1 className="h-page">Practise like a real video interview</h1>
        <p className="text-sm text-muted mt-1">The camera and microphone are required, as in a real video call. The interviewer asks questions based on your own resume and your answers, and you get feedback that quotes your own words. This is practice coaching: it does not change your skill estimates.</p>
      </div>
      <Callout tone="navy" title="Your video stays with you">
        The interview is recorded with sound to <b>this device only</b> and kept until you delete it. SAARTHI never receives the video or audio. Only your answers (as text) go to the server so the interviewer can respond. No camera or voice score is given.
      </Callout>
      <ResumeCard onChange={setResume} />
      {resume && <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={useResume} onChange={e => setUseResume(e.target.checked)} /> Ask me questions from my resume</label>}
      <div className="flex flex-wrap gap-2 items-center">
        <button type="button" className="btn btn-saffron py-3 px-6" onClick={() => setStage('setup')}>Set up camera and microphone →</button>
        <Link to="/interview" className="text-sm underline text-muted">No camera? Use the typed or voice interview</Link>
      </div>
      <RecordingsPanel refreshKey={recKey} />
    </div>
  )
}
