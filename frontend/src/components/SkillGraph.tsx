import { useMemo, useState } from 'react'
import { LEVEL_FILL } from './ui'

interface Node { id: string; name: string; domain: string; level: string; p: number; flags: string[]; in_role: boolean }
interface Edge { from: string; to: string }

const DOMAIN_ORDER = ['tools', 'python', 'sql', 'backend', 'communication']
const W = 168, H = 46, GX = 52, GY = 14

export default function SkillGraph({ nodes, edges, onSelect, highlight }: { nodes: Node[]; edges: Edge[]; onSelect?: (id: string) => void; highlight?: string | null }) {
  const [hover, setHover] = useState<string | null>(null)

  const { pos, width, height, depth } = useMemo(() => {
    const byId = new Map(nodes.map(n => [n.id, n]))
    const parents = new Map<string, string[]>()
    edges.forEach(e => parents.set(e.to, [...(parents.get(e.to) ?? []), e.from]))
    const depth = new Map<string, number>()
    const d = (id: string): number => {
      if (depth.has(id)) return depth.get(id)!
      const ps = parents.get(id) ?? []
      const v = ps.length ? Math.max(...ps.map(d)) + 1 : 0
      depth.set(id, v); return v
    }
    nodes.forEach(n => d(n.id))
    const cols = new Map<number, Node[]>()
    nodes.forEach(n => cols.set(depth.get(n.id)!, [...(cols.get(depth.get(n.id)!) ?? []), n]))
    const pos = new Map<string, { x: number; y: number }>()
    let maxRows = 0
    ;[...cols.keys()].sort((a, b) => a - b).forEach(c => {
      const list = cols.get(c)!.sort((a, b) => DOMAIN_ORDER.indexOf(a.domain) - DOMAIN_ORDER.indexOf(b.domain) || nodes.indexOf(a) - nodes.indexOf(b))
      maxRows = Math.max(maxRows, list.length)
      list.forEach((n, i) => pos.set(n.id, { x: c * (W + GX), y: i * (H + GY) }))
    })
    void byId
    return { pos, width: (Math.max(...depth.values()) + 1) * (W + GX) - GX, height: maxRows * (H + GY) - GY, depth }
  }, [nodes, edges])

  const related = useMemo(() => {
    const s = new Set<string>()
    const target = hover ?? highlight
    if (!target) return s
    s.add(target)
    edges.forEach(e => { if (e.from === target) s.add(e.to); if (e.to === target) s.add(e.from) })
    return s
  }, [hover, highlight, edges])

  return (
    <div>
      <div className="overflow-auto rounded-xl border border-line bg-white" style={{ maxHeight: 560 }}>
        <svg width={width + 24} height={height + 24} role="img" aria-label="Skill graph: concepts coloured by your current level, arrows point from prerequisite to dependent concept">
          <g transform="translate(12,12)">
            {edges.map((e, i) => {
              const a = pos.get(e.from), b = pos.get(e.to)
              if (!a || !b) return null
              const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2
              const mx = (x1 + x2) / 2
              const active = related.size === 0 || (related.has(e.from) && related.has(e.to))
              return <path key={i} d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} fill="none" stroke={active ? '#7a8aa0' : '#d5dce5'} strokeWidth={active && related.size ? 2 : 1.2} opacity={active ? 1 : 0.5} />
            })}
            {nodes.map(n => {
              const p = pos.get(n.id)!
              const fill = LEVEL_FILL[n.level] ?? '#b0bec5'
              const dim = related.size > 0 && !related.has(n.id)
              const light = n.level === 'not_assessed'
              const blocked = n.flags.includes('blocked')
              return (
                <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.35 : n.in_role ? 1 : 0.6} style={{ cursor: onSelect ? 'pointer' : 'default' }}
                  tabIndex={0} role="button" aria-label={`${n.name}: ${n.level.replace('_', ' ')}, ${Math.round(n.p * 100)} percent${n.flags.length ? ', ' + n.flags.join(', ') : ''}`}
                  onClick={() => onSelect?.(n.id)} onKeyDown={ev => { if (ev.key === 'Enter') onSelect?.(n.id) }}
                  onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(n.id)} onBlur={() => setHover(null)}>
                  <rect width={W} height={H} rx={11} fill={light ? '#fff' : fill} stroke={blocked ? '#e07a1f' : light ? '#b0bec5' : fill} strokeWidth={blocked ? 2.5 : 1.5} strokeDasharray={blocked ? '5 3' : undefined} />
                  <text x={10} y={19} fontSize={11.5} fontWeight={700} fill={light ? '#1e2530' : '#fff'}>{n.name.length > 24 ? n.name.slice(0, 23) + '…' : n.name}</text>
                  <text x={10} y={35} fontSize={10} fill={light ? '#5b6675' : 'rgba(255,255,255,.85)'}>{n.level === 'not_assessed' ? 'not assessed' : `${Math.round(n.p * 100)}% · ${n.level}`}</text>
                  {n.flags.includes('misconception') && <g><circle cx={W - 12} cy={12} r={8} fill="#7b1fa2" stroke="#fff" strokeWidth={1.5} /><text x={W - 12} y={16} fontSize={11} fontWeight={800} fill="#fff" textAnchor="middle">!</text></g>}
                  {n.flags.includes('due_for_review') && <circle cx={W - 12} cy={H - 11} r={5} fill="#0b8fa3" stroke="#fff" strokeWidth={1.5} />}
                </g>
              )
            })}
          </g>
        </svg>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-2.5 text-xs text-muted font-semibold">
        {Object.entries({ 'Not assessed': 'not_assessed', 'Needs work': 'unknown', Developing: 'developing', Proficient: 'proficient', Mastered: 'mastered' }).map(([l, k]) => (
          <span key={k} className="inline-flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded" style={{ background: k === 'not_assessed' ? '#fff' : LEVEL_FILL[k], border: '1.5px solid ' + LEVEL_FILL[k] }} />{l}</span>
        ))}
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded border-2 border-dashed border-saffron" />Blocked by a weak prerequisite</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-full bg-violet" />Misconception</span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#0b8fa3' }} />Review due</span>
      </div>
      <span className="sr-only">{depth.size} concepts</span>
    </div>
  )
}
