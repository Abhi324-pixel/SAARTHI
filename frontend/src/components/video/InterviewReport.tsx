import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiV01, type FocusTopic, type InterviewReport as Report } from '../../api_ext/V01'
import type { SpeechMetrics } from '../../api_ext/T11'
import { useApp } from '../../store'
import { SectionTitle } from '../ui'
import { SpeechChips } from '../SpeechChips'
import RecordingsPanel from './RecordingsPanel'

const Tile = ({ big, label }: { big: string | number; label: string }) => (
  <div className="rounded-xl bg-paper border border-line px-4 py-3 min-w-[110px]"><div className="text-2xl font-extrabold text-navy leading-none">{big}</div><div className="text-[11px] text-muted mt-1 max-w-[150px]">{label}</div></div>
)

/** The report for a resume-based interview, shared by the typed and the video interview. Everything on it is either quoted from the
 *  learner's own answers, counted, or measured in their browser. Nothing is graded and nothing here changes their skill estimates. */
export default function InterviewReport({ r, speech = [], recKey = 0, showRecordings = false, onAgain, againLabel = 'Another interview' }: {
  r: Report; speech?: (SpeechMetrics | null)[]; recKey?: number; showRecordings?: boolean; onAgain: () => void; againLabel?: string
}) {
  const { toast, bump, setRoadmapNote } = useApp()
  const [topics, setTopics] = useState<FocusTopic[]>(r.focus_topics ?? [])
  const [adding, setAdding] = useState(false)
  const m = r.client_metrics
  const measured = m && (m.face_in_frame_pct !== undefined || m.facing_camera_pct !== undefined || m.voice_level_ok_pct !== undefined || m.speaking_seconds !== undefined)
  const stat = (label: string, v?: number, unit = '%') => v === undefined ? null : <Tile big={`${Math.round(v)}${unit}`} label={label} />
  const addable = topics.filter(t => t.state === 'addable')

  async function addToPlan() {
    setAdding(true)
    try {
      const res = await apiV01.addFocus(r.id)
      setTopics(res.focus_topics)
      if (res.roadmap_change) setRoadmapNote(res.roadmap_change)
      toast('Added to your plan. Open the Roadmap to see it moved up.')
      bump()
    } catch (e: any) { toast(e.message, 'err') } finally { setAdding(false) }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <SectionTitle eyebrow="Interview report" title={`${r.role_title}: how it went`} />
        <button type="button" className="btn btn-ghost btn-sm no-print" onClick={() => window.print()}>🖨 Save as PDF / Print</button>
      </div>
      <p className="text-xs text-muted">{r.created_at ? `Interview on ${new Date(r.created_at).toLocaleString()}. ` : ''}{r.note}</p>

      <div className="card p-4 space-y-3">
        <div className="eyebrow">Overview (counted from your answers)</div>
        <div className="flex flex-wrap gap-3">
          <Tile big={r.summary.answers} label="questions answered" />
          <Tile big={r.summary.grounded_strengths} label="strengths, each backed by a quote from you" />
          <Tile big={r.summary.suggestions} label="suggestions to improve" />
          {r.summary.too_short > 0 && <Tile big={r.summary.too_short} label="answers too short to assess" />}
        </div>
        {r.written_summary && <p className="text-sm leading-relaxed border-l-4 border-saffron pl-3">{r.written_summary}</p>}
        {!r.written_summary && <p className="text-xs text-muted">A written summary was not available for this interview. The facts above and the answers below are complete.</p>}
      </div>

      {measured && m && (
        <div className="card p-4 space-y-2">
          <div className="eyebrow">Measured in your browser during the interview</div>
          <div className="flex flex-wrap gap-3">
            {stat('of the time your face was fully in view', m.face_in_frame_pct)}
            {stat('of the time you faced the camera', m.facing_camera_pct)}
            {stat('of your speaking time was in the good volume range', m.voice_level_ok_pct)}
            {stat('of speaking time heard', m.speaking_seconds, 's')}
          </div>
          <p className="text-[11px] text-muted">These come from your own camera and microphone to help you practise. They are not a score and are not part of your skill estimates.</p>
          {m.recording_saved === false && <p className="text-xs text-lvl-unknown font-semibold">The recording could not be saved on this device.</p>}
        </div>)}

      {topics.length > 0 && (
        <div className="card p-4 space-y-3 no-break">
          <div className="eyebrow">Next steps</div>
          <p className="text-sm text-muted">Your answers showed a gap in these topics. Practising them is how your estimate improves; the interview itself does not change it.</p>
          <ul className="space-y-2">
            {topics.map(t => (
              <li key={t.concept_id} className="flex items-center justify-between gap-2 flex-wrap text-sm">
                <div><b className="text-navy">{t.name}</b> <span className="text-muted">· came up in {t.times} answer{t.times > 1 ? 's' : ''}</span></div>
                <div className="flex items-center gap-2 no-print">
                  {t.state === 'in_plan' && <span className="chip bg-teal-soft">In your plan</span>}
                  {t.state === 'at_target' && <span className="chip bg-paper">Already at your target</span>}
                  <Link to={`/learn/${t.concept_id}`} className="btn btn-ghost btn-sm">Practise this</Link>
                </div>
              </li>))}
          </ul>
          {addable.length > 0 && <button type="button" className="btn btn-saffron btn-sm no-print" disabled={adding} onClick={addToPlan}>{adding ? 'Updating your plan…' : `Move ${addable.length === 1 ? 'this topic' : 'these topics'} up my plan`}</button>}
        </div>)}

      {r.turns.map((t, i) => (
        <div key={i} className="card p-4 space-y-2 text-sm no-break">
          <div className="text-xs text-muted font-bold">Question {i + 1}</div>
          <div className="font-semibold text-navy">{t.question}</div>
          <div className="rounded-xl bg-paper p-3 whitespace-pre-wrap" translate="no">{t.answer}</div>
          {speech[i] && <SpeechChips speech={speech[i]} />}
          {t.feedback.status === 'unavailable' && <p className="text-xs text-muted">Feedback was unavailable for this answer.</p>}
          {t.feedback.status === 'too_short' && <p className="text-xs text-muted">This answer was too short to give feedback on.</p>}
          {t.feedback.strengths.length > 0 && <div><b className="text-navy">Did well:</b><ul className="mt-1 space-y-1">{t.feedback.strengths.map((s, k) => <li key={k}>✓ {s.point} <span className="italic text-muted" translate="no">— “{s.quote}”</span></li>)}</ul></div>}
          {t.feedback.gaps.length > 0 && <div><b className="text-navy">To improve:</b><ul className="mt-1 list-disc ml-5">{t.feedback.gaps.map((g, k) => <li key={k}>{g}</li>)}</ul></div>}
        </div>))}
      {showRecordings && <div className="no-print"><RecordingsPanel refreshKey={recKey} /></div>}
      <div className="flex gap-2 no-print"><button type="button" className="btn btn-saffron" onClick={onAgain}>{againLabel}</button><Link to="/interview" className="btn btn-ghost">Back to Interview</Link></div>
    </div>
  )
}
