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
    <div className="space-y-4">
      {task && (
        <div className="card p-5">
          <div className="eyebrow">Task Prompt</div>
          <div className="font-bold text-white text-base mt-1 heading-glow">{task.prompt}</div>
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            {task.hints.slice(0, hintsShown).map((h, i) => (
              <span key={i} className="chip" style={{ background: 'rgba(77, 157, 255, 0.15)', color: '#4D9DFF', border: '1px solid rgba(77, 157, 255, 0.35)' }}>
                💡 {h}
              </span>
            ))}
            {hintsShown < task.hints.length && (
              <button className="btn btn-ghost btn-sm" onClick={() => setHintsShown(h => h + 1)}>
                Show a hint ({task.hints.length - hintsShown} remaining)
              </button>
            )}
          </div>
        </div>
      )}

      <div className="card p-4 lg:p-5 space-y-3">
        <textarea 
          className="mono input min-h-[140px] text-[13.5px] leading-relaxed bg-[rgba(10,20,30,0.45)] border border-[rgba(210,225,235,0.18)] focus:border-[#FF8A24]" 
          spellCheck={false} 
          value={query}
          onChange={e => setQuery(e.target.value)} 
          aria-label="SQL query editor"
          onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); task ? check() : runIt() } }} 
        />
        <div className="flex flex-wrap items-end justify-between gap-3 pt-1">
          {task ? <ConfidencePicker value={conf} onChange={setConf} label="How sure are you about this query?" /> : <span />}
          <div className="flex gap-2.5">
            <button className="btn btn-ghost" onClick={runIt} disabled={busy !== ''}>
              {busy === 'run' ? 'Running…' : '▶ Run query'}
            </button>
            {task && (
              <button className="btn btn-primary" onClick={check} disabled={busy !== ''}>
                {busy === 'check' ? 'Checking…' : '✓ Check my answer'}
              </button>
            )}
          </div>
        </div>
        <div className="text-[11px] text-slate-400 desc-glow">
          Ctrl+Enter {task ? 'checks' : 'runs'} · runs on a safe, read-only practice database · SELECT only
        </div>
      </div>

      {err && <Callout tone="red" title="Your query could not run">{err}</Callout>}
      {table && <DataTable columns={table.cols} rows={table.rows} />}

      {shown && shown.ran && shown.correct && (
        <Callout tone="teal" title="Correct — your result matches the expected output" icon="✓">
          {shown.mastery && (
            <span className="inline-flex items-center gap-2 flex-wrap">
              Your estimate for this concept moved from {Math.round(shown.mastery.p_before * 100)}% to <b>{Math.round(shown.mastery.p_after * 100)}%</b> <LevelChip level={shown.mastery.level_after} />
            </span>
          )}
          {(shown.misconception_progress ?? []).map((m: any, i: number) => (
            <div key={i} className="mt-1 font-semibold">
              Misconception fix: now <b className="text-white">{m.status.replace('_', ' ')}</b>
              {m.status === 'pending_verify' ? ' — a delayed re-check will confirm it is gone.' : m.status === 'resolved' ? ' 🎉' : ''}
            </div>
          ))}
          {shown.calibration && <div className="mt-1 text-[#4D9DFF] font-semibold">{shown.calibration}</div>}
        </Callout>
      )}

      {shown && shown.ran && !shown.correct && !shown.misconception && (
        <Callout tone="saffron" title="Not quite — here is what to check">
          <ul className="list-disc pl-5 space-y-1">{shown.hints.map((h: string, i: number) => <li key={i}>{h}</li>)}</ul>
          {shown.calibration && <div className="mt-1 font-semibold">{shown.calibration}</div>}
          <div className="mt-2.5">
            <button className="btn btn-ghost btn-sm" onClick={() => openStuck({ text: 'My query does not give the expected result.', query, task_id: task?.id, concept_id: task?.concept_id })}>
              Why am I stuck?
            </button>
          </div>
        </Callout>
      )}

      {shown?.misconception && (
        <div className="card p-5 pop border-[rgba(168,85,247,0.35)] bg-[rgba(168,85,247,0.08)]">
          <div className="flex items-center gap-2 flex-wrap">
            <FlagChip flag="misconception" />
            <span className="font-extrabold text-[#C084FC] heading-glow">{shown.misconception.name}</span>
            {shown.misconception.instance && (
              <span className="chip" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#C084FC', border: '1px solid rgba(168, 85, 247, 0.35)' }}>
                {shown.misconception.instance.status}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-200 desc-glow mt-2 leading-relaxed">{shown.misconception.description}</p>
          {shown.hints?.filter(Boolean).length > 0 && <p className="text-sm text-slate-300 font-semibold mt-1">What happened in your query: {shown.hints.filter(Boolean).join(' ')}</p>}
          {shown.misconception.counter_example?.query && (
            <div className="mt-3">
              <div className="text-xs font-bold text-slate-300 desc-glow mb-1">A query that reveals the difference:</div>
              <pre className="text-[12px] bg-[rgba(10,20,30,0.50)] border border-[rgba(210,225,235,0.16)] text-white rounded-xl p-3 overflow-auto whitespace-pre-wrap font-mono">{shown.misconception.counter_example.query}</pre>
              <div className="text-sm text-slate-300 desc-glow mt-1.5">{shown.misconception.counter_example.explanation}</div>
              <button className="btn btn-ghost btn-sm mt-2" onClick={() => { setQuery(shown.misconception.counter_example.query); setRes(null); setRun(null) }}>
                Load it into the editor
              </button>
            </div>
          )}
          <div className="text-sm mt-3 font-semibold text-[#C084FC]">Fix: {shown.misconception.fix_hint}</div>
          {shown.calibration && <div className="text-sm mt-1.5 font-semibold text-[#FF8A24]">{shown.calibration}</div>}
        </div>
      )}

      {schema && (
        <Collapsible title="Practice database schema (tables & columns)">
          <div className="grid sm:grid-cols-2 gap-3.5 mt-2">
            {schema.map(t => (
              <div key={t.table} className="glass-row p-3.5">
                <div className="font-mono font-bold text-sm text-white flex items-center justify-between">
                  <span>{t.table}</span>
                  <span className="text-slate-400 font-sans font-medium text-xs">· {t.count} rows</span>
                </div>
                <div className="text-xs font-mono mt-1.5 text-slate-300 leading-relaxed">
                  {t.columns.map((c: any) => c.name + (c.pk ? ' 🔑' : '')).join(', ')}
                </div>
                <button className="btn btn-ghost btn-sm mt-2.5" onClick={() => setQuery(`SELECT *\nFROM ${t.table}`)}>
                  Preview table
                </button>
              </div>
            ))}
          </div>
        </Collapsible>
      )}
    </div>
  )
}
