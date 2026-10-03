import { useEffect, useState } from 'react'
import { api } from '../api'
import { useApp } from '../store'
import { Callout, Collapsible, ConfidencePicker, DataTable, FlagChip, LevelChip } from './ui'

interface Task { id: string; concept_id: string; prompt: string; hints: string[]; difficulty: number }

export default function SqlWorkbench({ task, onResult }: { task?: Task | null; onResult?: (r: any) => void }) {
  const { toast, setRoadmapNote, bump, openStuck } = useApp()
  const [query, setQuery] = useState('SELECT *\nFROM customers')
  const [run, setRun] = useState<any>(null)
  const [res, setRes] = useState<any>(null)
  const [busy, setBusy] = useState<'' | 'run' | 'check'>('')
  const [conf, setConf] = useState<number | null>(null)
  const [schema, setSchema] = useState<any[] | null>(null)
  const [hintsShown, setHintsShown] = useState(0)

  useEffect(() => { setRes(null); setRun(null); setHintsShown(0); setConf(null) }, [task?.id])
  useEffect(() => { api.sqlSchema().then(s => setSchema(s.tables)).catch(() => {}) }, [])

  async function runIt() {
    setBusy('run'); setRes(null)
    try { setRun(await api.sqlRun(query)) } catch (e: any) { toast(e.message, 'err') } finally { setBusy('') }
  }
  async function check() {
    if (!task) return
    setBusy('check'); setRun(null)
    try {
      const r = await api.sqlSubmit({ task_id: task.id, query, stated_confidence: conf })
      setRes(r); onResult?.(r)
      if (r.after?.roadmap?.changed) setRoadmapNote(r.after.roadmap.change_reason)
      bump()
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy('') }
  }

  const shown = res ?? null
  const table = res?.ran ? { cols: res.columns, rows: res.rows } : run?.ok ? { cols: run.columns, rows: run.rows } : null
  const err = res && !res.ran ? res.error : run && !run.ok ? run.error : null

  return (
    <div className="space-y-3">
      {task && (
        <div className="card p-4">
          <div className="eyebrow">Task</div>
          <div className="font-bold text-navy mt-0.5">{task.prompt}</div>
          <div className="mt-2 flex items-center gap-2 flex-wrap">
            {task.hints.slice(0, hintsShown).map((h, i) => <span key={i} className="chip" style={{ background: '#e3f2f1', color: '#0f5d5d' }}>💡 {h}</span>)}
            {hintsShown < task.hints.length && <button className="btn btn-ghost btn-sm" onClick={() => setHintsShown(h => h + 1)}>Show a hint</button>}
          </div>
        </div>
      )}
      <div className="card p-3">
        <textarea className="mono input min-h-[130px] text-[13px] leading-relaxed" spellCheck={false} value={query}
          onChange={e => setQuery(e.target.value)} aria-label="SQL query editor"
          onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); task ? check() : runIt() } }} />
        <div className="flex flex-wrap items-end justify-between gap-3 mt-2">
          {task ? <ConfidencePicker value={conf} onChange={setConf} label="How sure are you about this query?" /> : <span />}
          <div className="flex gap-2">
            <button className="btn btn-ghost" onClick={runIt} disabled={busy !== ''}>{busy === 'run' ? 'Running…' : '▶ Run'}</button>
            {task && <button className="btn btn-saffron" onClick={check} disabled={busy !== ''}>{busy === 'check' ? 'Checking…' : '✓ Check my answer'}</button>}
          </div>
        </div>
        <div className="text-[11px] text-muted mt-1">Ctrl+Enter {task ? 'checks' : 'runs'} · runs on a safe, read-only practice database · SELECT only</div>
      </div>

      {err && <Callout tone="red" title="Your query could not run">{err}</Callout>}
      {table && <DataTable columns={table.cols} rows={table.rows} />}

      {shown && shown.ran && shown.correct && (
        <Callout tone="teal" title="Correct — your result matches the expected output" icon="✓">
          {shown.mastery && <span className="inline-flex items-center gap-2 flex-wrap">Your estimate for this concept moved from {Math.round(shown.mastery.p_before * 100)}% to <b>{Math.round(shown.mastery.p_after * 100)}%</b> <LevelChip level={shown.mastery.level_after} /></span>}
          {(shown.misconception_progress ?? []).map((m: any, i: number) => (
            <div key={i} className="mt-1 font-semibold">Misconception fix: now <b>{m.status.replace('_', ' ')}</b>{m.status === 'pending_verify' ? ' — a delayed re-check will confirm it is gone.' : m.status === 'resolved' ? ' 🎉' : ''}</div>
          ))}
          {shown.calibration && <div className="mt-1 text-teal font-semibold">{shown.calibration}</div>}
        </Callout>
      )}
      {shown && shown.ran && !shown.correct && !shown.misconception && (
        <Callout tone="saffron" title="Not quite — here is what to check">
          <ul className="list-disc pl-5">{shown.hints.map((h: string, i: number) => <li key={i}>{h}</li>)}</ul>
          {shown.calibration && <div className="mt-1 font-semibold">{shown.calibration}</div>}
          <button className="btn btn-ghost btn-sm mt-2" onClick={() => openStuck({ text: 'My query does not give the expected result.', query, task_id: task?.id, concept_id: task?.concept_id })}>Why am I stuck?</button>
        </Callout>
      )}
      {shown?.misconception && (
        <div className="card p-4 pop" style={{ borderColor: '#d9b8e6', background: '#fbf6fd' }}>
          <div className="flex items-center gap-2 flex-wrap">
            <FlagChip flag="misconception" />
            <span className="font-extrabold text-violet">{shown.misconception.name}</span>
            {shown.misconception.instance && <span className="chip" style={{ background: '#fff', color: '#7b1fa2', border: '1px solid #d9b8e6' }}>{shown.misconception.instance.status}</span>}
          </div>
          <p className="text-sm mt-1.5">{shown.misconception.description}</p>
          {shown.hints?.filter(Boolean).length > 0 && <p className="text-sm mt-1 font-semibold">What happened in your query: {shown.hints.filter(Boolean).join(' ')}</p>}
          {shown.misconception.counter_example?.query && (
            <div className="mt-2">
              <div className="text-xs font-bold text-muted mb-1">A query that shows the difference:</div>
              <pre className="text-[12px] bg-navy text-white rounded-lg p-2.5 overflow-auto whitespace-pre-wrap">{shown.misconception.counter_example.query}</pre>
              <div className="text-sm mt-1">{shown.misconception.counter_example.explanation}</div>
              <button className="btn btn-ghost btn-sm mt-2" onClick={() => { setQuery(shown.misconception.counter_example.query); setRes(null); setRun(null) }}>Load it in the editor</button>
            </div>
          )}
          <div className="text-sm mt-2 font-semibold text-violet">Fix: {shown.misconception.fix_hint}</div>
          {shown.calibration && <div className="text-sm mt-1.5 font-semibold text-saffron">{shown.calibration}</div>}
        </div>
      )}

      {schema && (
        <Collapsible title="Practice database (tables and columns)">
          <div className="grid sm:grid-cols-2 gap-3">
            {schema.map(t => (
              <div key={t.table} className="card p-3">
                <div className="font-mono font-bold text-sm text-navy">{t.table} <span className="text-muted font-sans font-medium text-xs">· {t.count} rows</span></div>
                <div className="text-xs font-mono mt-1 text-muted leading-relaxed">{t.columns.map((c: any) => c.name + (c.pk ? ' 🔑' : '')).join(', ')}</div>
                <button className="btn btn-ghost btn-sm mt-2" onClick={() => setQuery(`SELECT *\nFROM ${t.table}`)}>Preview</button>
              </div>
            ))}
          </div>
        </Collapsible>
      )}
    </div>
  )
}
