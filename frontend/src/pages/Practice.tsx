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

  if (!tasks) return <div className="py-16 flex justify-center"><Spinner /></div>
  const task = tasks.find(t => t.id === sel) ?? null

  return (
    <div className="grid lg:grid-cols-[300px_1fr] gap-5">
      <aside className="card p-3 h-fit lg:sticky lg:top-20 max-h-[80vh] overflow-auto">
        <div className="eyebrow px-2 pt-1">SQL practice</div>
        <button onClick={() => { setSel(null); setParams({}) }} className={`w-full text-left rounded-lg px-3 py-2 text-sm font-bold mt-1 ${!sel ? 'bg-navy text-white' : 'hover:bg-paper text-navy'}`}>✎ Free playground</button>
        {groups.map(([cid, list]) => (
          <div key={cid} className="mt-3">
            <div className="px-2 flex items-center gap-2 text-xs font-extrabold text-muted uppercase tracking-wide">{nodes[cid]?.name ?? cid} {nodes[cid] && <LevelChip level={nodes[cid].level} />}</div>
            {list.map((t, i) => (
              <button key={t.id} onClick={() => { setSel(t.id); setParams({ task: t.id }) }} className={`w-full text-left rounded-lg px-3 py-2 text-sm mt-1 ${sel === t.id ? 'bg-saffron-soft ring-1 ring-saffron font-bold' : 'hover:bg-paper'}`}>
                <span className="text-muted mr-1.5">{i + 1}.</span>{t.prompt.length > 70 ? t.prompt.slice(0, 68) + '…' : t.prompt}
              </button>
            ))}
          </div>
        ))}
      </aside>
      <div className="min-w-0">
        <div className="mb-3"><h1 className="h-page">{task ? nodes[task.concept_id]?.name : 'SQL playground'}</h1>
          <p className="text-muted text-sm mt-1">{task ? 'Your query is run against a safe practice database and compared with the expected result. Wrong results are matched to specific misconceptions.' : 'Run any SELECT query on the shop database. Nothing here is graded.'}</p></div>
        <SqlWorkbench task={task} />
      </div>
    </div>
  )
}
