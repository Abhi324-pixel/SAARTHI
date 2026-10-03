import { useEffect, useState } from 'react'
import { apiT05, Checkpoint } from '../api_ext/T05'
import { api } from '../api'
import { SectionTitle, Spinner } from './ui'
import { useApp } from '../store'

interface CheckpointsProps {
  onConceptSelect?: (conceptId: string) => void
}

export default function Checkpoints({ }: CheckpointsProps = {}) {
  const { toast, t } = useApp()
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([])
  const [loading, setLoading] = useState(true)
  const [title, setTitle] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [conceptId, setConceptId] = useState('')
  const [concepts, setConcepts] = useState<any[]>([])
  const [busy, setBusy] = useState(false)

  async function load() {
    try {
      const res = await apiT05.getCheckpoints()
      setCheckpoints(res.checkpoints)
    } catch (e: any) {
      toast(e.message || 'Failed to load checkpoints', 'err')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    api.graph()
      .then(g => setConcepts(g.nodes || []))
      .catch(() => {})
  }, [])

  async function handleToggle(cp: Checkpoint) {
    if (cp.is_concept_linked) {
      toast('This checkpoint completes automatically when you reach your target mastery.', 'warn')
      return
    }
    try {
      const updated = await apiT05.toggleCheckpoint(cp.id)
      setCheckpoints(prev =>
        prev.map(c => (c.id === cp.id ? { ...c, done: updated.done, done_at: updated.done_at } : c))
      )
    } catch (e: any) {
      toast(e.message || 'Failed to update checkpoint', 'err')
    }
  }

  async function handleDelete(id: string) {
    try {
      await apiT05.deleteCheckpoint(id)
      setCheckpoints(prev => prev.filter(c => c.id !== id))
      toast('Checkpoint removed', 'ok')
    } catch (e: any) {
      toast(e.message || 'Failed to delete checkpoint', 'err')
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    setBusy(true)
    try {
      const created = await apiT05.createCheckpoint({
        title: title.trim(),
        due_date: dueDate || null,
        concept_id: conceptId || null,
      })
      const conceptObj = concepts.find(c => c.id === created.concept_id)
      setCheckpoints(prev => [{ ...created, concept_name: conceptObj?.name || created.concept_id }, ...prev])
      setTitle('')
      setDueDate('')
      setConceptId('')
      toast('Checkpoint added!', 'ok')
    } catch (e: any) {
      toast(e.message || 'Failed to add checkpoint', 'err')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card p-4 space-y-3">
      <SectionTitle eyebrow={t('T05.checkpoints')} title="Personal Checkpoints" />
      <p className="text-xs text-muted">
        Set your own milestone targets. Concept-linked checkpoints complete on their own when your verified mastery reaches target!
      </p>

      {loading ? (
        <div className="py-4 flex justify-center"><Spinner label="Loading checkpoints..." /></div>
      ) : (
        <div className="space-y-2">
          {checkpoints.length === 0 ? (
            <div className="text-xs text-muted py-2 italic text-center">No personal checkpoints yet. Add one below!</div>
          ) : (
            <ul className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {checkpoints.map(cp => (
                <li
                  key={cp.id}
                  className={`p-2.5 rounded-lg border text-sm flex items-start gap-2.5 transition-all ${
                    cp.done ? 'bg-emerald-50/60 border-emerald-200 dark:bg-emerald-950/20 dark:border-emerald-800' : 'bg-paper border-line'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={cp.done}
                    onChange={() => handleToggle(cp)}
                    disabled={cp.is_concept_linked}
                    className="mt-1 h-4 w-4 rounded text-teal accent-teal focus:ring-teal cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
                    title={cp.is_concept_linked ? 'Completes automatically via evidence' : 'Click to toggle'}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={`font-medium ${cp.done ? 'line-through text-muted' : 'text-navy'}`}>
                        {cp.title}
                      </span>
                      {cp.is_concept_linked && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 font-semibold" title="Linked to concept mastery">
                          🎯 {cp.concept_name || cp.concept_id}
                        </span>
                      )}
                    </div>
                    {cp.due_date && (
                      <div className="text-[11px] text-muted mt-0.5 flex items-center gap-1">
                        <span>📅 Due: {cp.due_date}</span>
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(cp.id)}
                    className="text-muted hover:text-red-600 text-xs px-1.5 py-0.5 rounded hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                    title="Delete checkpoint"
                    aria-label="Delete checkpoint"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <form onSubmit={handleCreate} className="space-y-2 pt-2 border-t border-line">
        <input
          type="text"
          className="input text-sm w-full"
          placeholder="New checkpoint (e.g. solve 3 joins)"
          value={title}
          maxLength={120}
          onChange={e => setTitle(e.target.value)}
          required
        />
        <div className="grid grid-cols-2 gap-2">
          <input
            type="date"
            className="input text-xs w-full"
            value={dueDate}
            onChange={e => setDueDate(e.target.value)}
            title="Optional due date"
          />
          <select
            className="input text-xs w-full"
            value={conceptId}
            onChange={e => setConceptId(e.target.value)}
          >
            <option value="">No linked concept</option>
            {concepts.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          disabled={busy || !title.trim()}
          className="btn btn-secondary text-xs w-full py-1.5"
        >
          {busy ? 'Adding…' : '+ Add checkpoint'}
        </button>
      </form>
    </div>
  )
}
