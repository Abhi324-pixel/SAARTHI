import { useEffect, useState } from 'react'
import { apiR01, type WebResources as Data } from '../api_ext/R01'
import { SectionTitle } from './ui'

const ICON: Record<string, string> = { docs: '📘', article: '📰', video: '▶️' }
const KIND: Record<string, string> = { docs: 'Official docs', article: 'Article', video: 'Video' }

/** "Learn from real sources": pages found on the web for this concept. Only pages the search really returned are shown. */
export default function WebResources({ conceptId, compact = false }: { conceptId: string; compact?: boolean }) {
  const [data, setData] = useState<Data | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    setData(null); setFailed(false)
    apiR01.forConcept(conceptId).then(d => { if (live) setData(d) }).catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [conceptId])

  if (data?.status === 'disabled') return null          // web search is not set up on this server: show nothing rather than an empty box
  return (
    <section className={compact ? 'space-y-2' : 'card p-5 space-y-3'} aria-label="Learn from real sources">
      {compact ? <div className="text-xs font-black text-teal uppercase tracking-wider">🌐 Learn from real sources</div> : <SectionTitle eyebrow="Beyond SAARTHI" title="Learn from real sources" />}
      {!data && !failed && <p className="text-sm text-muted">Finding real resources for this topic…</p>}
      {failed && <p className="text-sm text-muted">Could not load web resources just now. The lesson above still works.</p>}
      {data?.status === 'unavailable' && <p className="text-sm text-muted">The web search is not reachable right now. Try again in a little while.</p>}
      {data?.status === 'ok' && data.items.length === 0 && <p className="text-sm text-muted">No web resources were found for this topic yet.</p>}
      {data?.status === 'ok' && data.items.length > 0 && (
        <ul className="space-y-2">
          {data.items.map(i => (
            <li key={i.url}>
              <a href={i.url} target="_blank" rel="noopener noreferrer" className="block rounded-xl border border-line bg-white p-3 hover:bg-paper">
                <div className="flex items-center gap-2 text-[11px] text-muted font-semibold"><span aria-hidden>{ICON[i.kind]}</span><span>{KIND[i.kind]}</span><span>·</span><span>{i.domain}</span></div>
                <div className="font-bold text-sm text-navy mt-0.5">{i.title}</div>
                {!compact && i.snippet && <div className="text-xs text-muted mt-0.5 line-clamp-2">{i.snippet}</div>}
              </a>
            </li>))}
        </ul>)}
      {data?.status === 'ok' && <p className="text-[11px] text-muted">{data.label}</p>}
    </section>
  )
}
