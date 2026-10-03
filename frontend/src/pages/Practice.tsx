import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import SqlWorkbench from '../components/SqlWorkbench'
import { LevelChip, Spinner } from '../components/ui'
import { useApp } from '../store'

export default function Practice() {
  const { version } = useApp()
  const [params, setParams] = useSearchParams()
  const [tasks, setTasks] = useState<any[] | null>(null)
  const [nodes, setNodes] = useState<Record<string, any>>({})
  const [sel, setSel] = useState<string | null>(params.get('task'))

  useEffect(() => {
    api.sqlTasks().then(r => { setTasks(r.tasks); setSel(s => s ?? r.tasks[0]?.id ?? null) })
    api.graph().then(g => setNodes(Object.fromEntries(g.nodes.map((n: any) => [n.id, n]))))
  }, [version])

  const groups = useMemo(() => {
    const g: Record<string, any[]> = {}
    ;(tasks ?? []).forEach(t => { (g[t.concept_id] ||= []).push(t) })
    return Object.entries(g)
  }, [tasks])

  if (!tasks) return <div className="py-20 flex justify-center"><Spinner label="Loading SQL practice workbench…" /></div>
  const task = tasks.find(t => t.id === sel) ?? null

  return (
    <div className="grid lg:grid-cols-12 gap-5">
      <aside className="lg:col-span-4 card p-4 h-fit lg:sticky lg:top-20 max-h-[82vh] overflow-auto">
        <div className="eyebrow px-2 pt-1">SQL practice</div>
        <button 
          onClick={() => { setSel(null); setParams({}) }} 
          className={`w-full text-left rounded-xl px-3.5 py-2.5 text-sm font-bold mt-2 transition-all ${
            !sel 
              ? 'bg-[rgba(255,138,36,0.18)] text-white border border-[rgba(255,138,36,0.35)] shadow-[0_0_12px_rgba(255,138,36,0.2)]' 
              : 'hover:bg-[rgba(255,255,255,0.06)] text-slate-300'
          }`}
        >
          ✎ Free SQL playground
        </button>
        {groups.map(([cid, list]) => (
          <div key={cid} className="mt-4 pt-3 border-t border-[rgba(210,225,235,0.10)]">
            <div className="px-2 flex items-center justify-between text-xs font-extrabold text-slate-400 uppercase tracking-wider mb-1.5">
              <span className="truncate">{nodes[cid]?.name ?? cid}</span>
              {nodes[cid] && <LevelChip level={nodes[cid].level} />}
            </div>
            {list.map((t, i) => (
              <button 
                key={t.id} 
                onClick={() => { setSel(t.id); setParams({ task: t.id }) }} 
                className={`w-full text-left rounded-xl px-3.5 py-2 text-sm mt-1 transition-all ${
                  sel === t.id 
                    ? 'bg-[rgba(255,138,36,0.18)] text-white border border-[rgba(255,138,36,0.35)] shadow-[0_0_12px_rgba(255,138,36,0.2)] font-bold' 
                    : 'hover:bg-[rgba(255,255,255,0.05)] text-slate-300'
                }`}
              >
                <span className="text-[#FF8A24] font-mono mr-1.5">{i + 1}.</span>
                {t.prompt.length > 65 ? t.prompt.slice(0, 63) + '…' : t.prompt}
              </button>
            ))}
          </div>
        ))}
      </aside>
      <div className="lg:col-span-8 min-w-0 space-y-4">
        <div className="card p-5 lg:p-6">
          <h1 className="h-page">{task ? nodes[task.concept_id]?.name : 'SQL playground'}</h1>
          <p className="text-slate-300 desc-glow text-sm mt-1.5 leading-relaxed">
            {task 
              ? 'Your query is run against a safe practice database and compared with the expected result. Wrong results are matched to specific misconceptions.' 
              : 'Run any SELECT query on the shop database. Nothing here is graded.'}
          </p>
        </div>
        <SqlWorkbench task={task} />
      </div>
    </div>
  )
}
