import { useState, type ReactNode } from 'react'

export const LEVEL: Record<string, { label: string; color: string; bg: string }> = {
  not_assessed: { label: 'Not assessed', color: '#5b6675', bg: '#eceff3' },
  unknown: { label: 'Needs work', color: '#c62828', bg: '#fdeaea' },
  developing: { label: 'Developing', color: '#9a6b00', bg: '#fff3d1' },
  proficient: { label: 'Proficient', color: '#1f6f45', bg: '#e2f4ea' },
  mastered: { label: 'Mastered', color: '#124a17', bg: '#d3efd6' },
}
export const LEVEL_FILL: Record<string, string> = {
  not_assessed: '#b0bec5', unknown: '#c62828', developing: '#e0a100', proficient: '#2e8b57', mastered: '#1b5e20',
}

export function LevelChip({ level }: { level: string }) {
  const l = LEVEL[level] ?? LEVEL.not_assessed
  return <span className="chip" style={{ color: l.color, background: l.bg }}>{l.label}</span>
}

const FLAG: Record<string, { label: string; color: string; bg: string; tip: string }> = {
  misconception: { label: 'Misconception', color: '#7b1fa2', bg: '#f3e5f9', tip: 'A likely incorrect mental model was detected here.' },
  blocked: { label: 'Blocked', color: '#8a4b00', bg: '#ffe9cc', tip: 'A prerequisite is still weak.' },
  due_for_review: { label: 'Review due', color: '#0b5d6b', bg: '#d9f1f5', tip: 'This was learned a while ago and may be fading.' },
  disputed: { label: 'Disputed', color: '#5b6675', bg: '#eceff3', tip: 'You said this estimate is wrong; a re-check will settle it.' },
  low_confidence: { label: 'Low confidence', color: '#5b6675', bg: '#eceff3', tip: 'Not enough evidence yet.' },
  overconfident: { label: 'Overconfident', color: '#b3261e', bg: '#fdeaea', tip: 'You were sure but wrong more than once.' },
}
export function FlagChip({ flag }: { flag: string }) {
  const f = FLAG[flag] ?? { label: flag, color: '#5b6675', bg: '#eceff3', tip: '' }
  return <span className="chip" title={f.tip} style={{ color: f.color, background: f.bg }}>{f.label}</span>
}

export function DemoBadge({ label = 'Demo data', title = 'This part uses mock data for now. It is swapped for real data through one setting.' }: { label?: string; title?: string }) {
  return <span className="chip" title={title} style={{ background: '#fdf3e9', color: '#9a4f0a', border: '1px dashed #e07a1f' }}>◌ {label}</span>
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-muted text-sm" role="status">
      <span className="inline-block h-4 w-4 rounded-full border-2 border-line border-t-saffron animate-spin" />
      {label ?? 'Loading…'}
    </div>
  )
}

export function Ring({ value, size = 96, stroke = 10, label, sub }: { value: number; size?: number; stroke?: number; label?: string; sub?: string }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r, v = Math.max(0, Math.min(1, value))
  return (
    <div className="relative" style={{ width: size, height: size }} role="img" aria-label={`${Math.round(v * 100)} percent`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e8edf3" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e07a1f" strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - v)} style={{ transition: 'stroke-dashoffset .8s ease' }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="font-extrabold text-navy" style={{ fontSize: size * 0.26 }}>{label ?? `${Math.round(v * 100)}%`}</div>
        {sub && <div className="text-[10px] text-muted font-semibold -mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

export function Bar({ value, color = '#e07a1f', h = 8 }: { value: number; color?: string; h?: number }) {
  return (
    <div className="w-full rounded-full bg-[#e8edf3] overflow-hidden" style={{ height: h }}>
      <div className="h-full rounded-full" style={{ width: `${Math.max(2, Math.min(100, value * 100))}%`, background: color, transition: 'width .6s ease' }} />
    </div>
  )
}

export function ConfidencePicker({ value, onChange, label = 'How sure are you?' }: { value: number | null; onChange: (n: number) => void; label?: string }) {
  const names = ['Guessing', 'Unsure', 'Maybe', 'Fairly sure', 'Certain']
  return (
    <div>
      <div className="text-xs font-bold text-muted mb-1.5">{label}</div>
      <div className="flex gap-1.5 flex-wrap" role="radiogroup" aria-label={label}>
        {names.map((n, i) => (
          <button key={n} type="button" role="radio" aria-checked={value === i + 1} onClick={() => onChange(i + 1)}
            className={`btn btn-sm ${value === i + 1 ? 'btn-primary' : 'btn-ghost'}`}>{n}</button>
        ))}
      </div>
    </div>
  )
}

export function Callout({ tone = 'saffron', title, children, icon }: { tone?: 'saffron' | 'teal' | 'violet' | 'red' | 'navy'; title?: string; children?: ReactNode; icon?: string }) {
  const c = { saffron: ['#fdf3e9', '#e07a1f'], teal: ['#e3f2f1', '#1f7a7a'], violet: ['#f3e5f9', '#7b1fa2'], red: ['#fdeaea', '#c62828'], navy: ['#e8eef5', '#16324f'] }[tone]
  return (
    <div className="rounded-xl px-4 py-3 text-sm pop" style={{ background: c[0], borderLeft: `4px solid ${c[1]}` }}>
      {title && <div className="font-extrabold mb-0.5" style={{ color: c[1] }}>{icon ? icon + ' ' : ''}{title}</div>}
      <div className="text-ink/90 leading-relaxed">{children}</div>
    </div>
  )
}

export function Collapsible({ title, children, defaultOpen = false }: { title: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <button className="text-sm font-bold text-teal hover:underline" onClick={() => setOpen(o => !o)} aria-expanded={open}>{open ? '▾' : '▸'} {title}</button>
      {open && <div className="mt-2 pop">{children}</div>}
    </div>
  )
}

export function DataTable({ columns, rows, highlightNull = true }: { columns: string[]; rows: any[][]; highlightNull?: boolean }) {
  return (
    <div translate="no" className="overflow-auto rounded-xl border border-line max-h-72">
      <table className="w-full text-sm">
        <thead className="bg-paper sticky top-0"><tr>{columns.map((c, i) => <th key={i} className="text-left px-3 py-1.5 font-bold text-navy font-mono text-xs whitespace-nowrap">{c}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-line">
              {r.map((v, j) => (
                <td key={j} className="px-3 py-1.5 font-mono text-xs whitespace-nowrap">
                  {v === null ? <span className={highlightNull ? 'text-saffron font-bold' : 'text-muted'}>NULL</span> : String(v)}
                </td>
              ))}
            </tr>
          ))}
          {!rows.length && <tr><td className="px-3 py-3 text-muted text-xs" colSpan={Math.max(columns.length, 1)}>No rows returned.</td></tr>}
        </tbody>
      </table>
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="text-sm text-muted text-center py-8">{children}</div>
}

export function SectionTitle({ eyebrow, title, right }: { eyebrow?: string; title: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-3 flex-wrap mb-3">
      <div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h2 className="text-lg font-extrabold text-navy">{title}</h2></div>
      {right}
    </div>
  )
}
