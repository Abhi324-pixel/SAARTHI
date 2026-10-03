import { useEffect, useRef, useState } from 'react'
import { apiV01, type ResumeSummary } from '../../api_ext/V01'
import { SectionTitle } from '../ui'

/** Upload a resume (PDF or .txt). Only a short summary is kept; the file itself is read and discarded. */
export default function ResumeCard({ onChange }: { onChange?: (s: ResumeSummary | null) => void }) {
  const [summary, setSummary] = useState<ResumeSummary | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => { apiV01.resume().then(r => { setSummary(r.summary); onChange?.(r.summary) }).catch(() => {}) }, [])

  async function upload(f: File | undefined) {
    if (!f) return
    setBusy(true); setErr(null)
    try { const r = await apiV01.uploadResume(f); setSummary(r.summary); onChange?.(r.summary) }
    catch (e: any) { setErr(e.message) }
    finally { setBusy(false); if (input.current) input.current.value = '' }
  }
  async function remove() {
    setBusy(true)
    try { await apiV01.deleteResume(); setSummary(null); onChange?.(null) } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="card p-5 space-y-3">
      <SectionTitle eyebrow="Your resume" title={summary ? 'Questions will come from your resume' : 'Add your resume (optional)'} />
      {!summary && <p className="text-sm text-muted">Upload a PDF or text resume and the interviewer asks about <i>your</i> projects and skills. The file is read once and thrown away; SAARTHI keeps only a short summary, and you can delete it any time.</p>}
      {summary && (
        <div className="text-sm space-y-2">
          {summary.skills.length > 0 && <div><b className="text-navy">Skills found:</b> <span className="flex flex-wrap gap-1.5 mt-1">{summary.skills.map(s => <span key={s} className="chip bg-teal-soft">{s}</span>)}</span></div>}
          {summary.projects.length > 0 && <div><b className="text-navy">Projects:</b> {summary.projects.map(p => p.name).join(' · ')}</div>}
          <p className="text-xs text-muted">Only what is written in your file is used. Nothing is guessed.</p>
        </div>
      )}
      <div className="flex gap-2 flex-wrap">
        <input ref={input} type="file" accept=".pdf,.txt,application/pdf,text/plain" className="hidden" onChange={e => upload(e.target.files?.[0])} aria-label="Upload resume" />
        <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => input.current?.click()}>{busy ? 'Reading…' : summary ? 'Replace resume' : 'Upload resume (PDF or .txt)'}</button>
        {summary && <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={remove}>Delete my resume summary</button>}
      </div>
      {err && <p className="text-xs text-lvl-unknown font-semibold" role="alert">{err}</p>}
    </div>
  )
}
