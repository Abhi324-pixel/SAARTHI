import { useState, type ReactNode } from 'react'

export const LEVEL: Record<string, { label: string; color: string; bg: string; border: string }> = {
  not_assessed: { label: 'Not assessed', color: '#AEBBC5', bg: 'rgba(25, 39, 51, 0.60)', border: 'rgba(210, 225, 235, 0.16)' },
  unknown: { label: 'Needs work', color: '#FF5364', bg: 'rgba(255, 83, 100, 0.14)', border: 'rgba(255, 83, 100, 0.35)' },
  developing: { label: 'Developing', color: '#FFB52E', bg: 'rgba(255, 181, 46, 0.14)', border: 'rgba(255, 181, 46, 0.35)' },
  proficient: { label: 'Proficient', color: '#4D9DFF', bg: 'rgba(77, 157, 255, 0.14)', border: 'rgba(77, 157, 255, 0.35)' },
  mastered: { label: 'Mastered', color: '#35D07F', bg: 'rgba(53, 208, 127, 0.14)', border: 'rgba(53, 208, 127, 0.35)' },
}
export const LEVEL_FILL: Record<string, string> = {
  not_assessed: '#788895', unknown: '#FF5364', developing: '#FFB52E', proficient: '#4D9DFF', mastered: '#35D07F',
}

export function LevelChip({ level }: { level: string }) {
  const l = LEVEL[level] ?? LEVEL.not_assessed
  return (
    <span 
      className="chip backdrop-blur-sm" 
      style={{ color: l.color, background: l.bg, borderColor: l.border }}
    >
      <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: l.color }} />
      {l.label}
    </span>
  )
}

const FLAG: Record<string, { label: string; color: string; bg: string; border: string; tip: string }> = {
  misconception: { label: 'Misconception', color: '#C084FC', bg: 'rgba(168, 85, 247, 0.15)', border: 'rgba(168, 85, 247, 0.35)', tip: 'A likely incorrect mental model was detected here.' },
  blocked: { label: 'Blocked', color: '#FFB52E', bg: 'rgba(255, 181, 46, 0.15)', border: 'rgba(255, 181, 46, 0.35)', tip: 'A prerequisite is still weak.' },
  due_for_review: { label: 'Review due', color: '#4D9DFF', bg: 'rgba(77, 157, 255, 0.15)', border: 'rgba(77, 157, 255, 0.35)', tip: 'This was learned a while ago and may be fading.' },
  disputed: { label: 'Disputed', color: '#AEBBC5', bg: 'rgba(25, 39, 51, 0.60)', border: 'rgba(210, 225, 235, 0.16)', tip: 'You said this estimate is wrong; a re-check will settle it.' },
  low_confidence: { label: 'Low confidence', color: '#AEBBC5', bg: 'rgba(25, 39, 51, 0.60)', border: 'rgba(210, 225, 235, 0.16)', tip: 'Not enough evidence yet.' },
  overconfident: { label: 'Overconfident', color: '#FF5364', bg: 'rgba(255, 83, 100, 0.15)', border: 'rgba(255, 83, 100, 0.35)', tip: 'You were sure but wrong more than once.' },
}
export function FlagChip({ flag }: { flag: string }) {
  const f = FLAG[flag] ?? { label: flag, color: '#AEBBC5', bg: 'rgba(25, 39, 51, 0.60)', border: 'rgba(210, 225, 235, 0.16)', tip: '' }
  return <span className="chip backdrop-blur-sm" title={f.tip} style={{ color: f.color, background: f.bg, borderColor: f.border }}>{f.label}</span>
}

export function DemoBadge({ label = 'Demo data', title = 'This part uses mock data for now. It is swapped for real data through one setting.' }: { label?: string; title?: string }) {
  return (
    <span 
      className="chip backdrop-blur-sm" 
      title={title} 
      style={{ background: 'rgba(255, 138, 36, 0.12)', color: '#FF8A24', border: '1px dashed rgba(255, 138, 36, 0.50)' }}
    >
      ◌ {label}
    </span>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-slate-300 text-sm desc-glow" role="status">
      <span className="inline-block h-4 w-4 rounded-full border-2 border-slate-600 border-t-[#FF8A24] animate-spin" />
      {label ?? 'Loading…'}
    </div>
  )
}

export function Ring({ value, size = 96, stroke = 10, label, sub }: { value: number; size?: number; stroke?: number; label?: string; sub?: string }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r, v = Math.max(0, Math.min(1, value))
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={`${Math.round(v * 100)} percent`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(210, 225, 235, 0.10)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#FF8A24" strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - v)} style={{ transition: 'stroke-dashoffset .8s ease', filter: 'drop-shadow(0 0 8px rgba(255, 138, 36, 0.40))' }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="font-extrabold text-white heading-glow" style={{ fontSize: size * 0.26 }}>{label ?? `${Math.round(v * 100)}%`}</div>
        {sub && <div className="text-[10px] text-slate-300 font-semibold -mt-0.5 desc-glow">{sub}</div>}
      </div>
    </div>
  )
}

export function Bar({ value, color = '#FF8A24', h = 8 }: { value: number; color?: string; h?: number }) {
  return (
    <div className="w-full rounded-full bg-[rgba(210,225,235,0.10)] overflow-hidden" style={{ height: h }}>
      <div className="h-full rounded-full" style={{ width: `${Math.max(2, Math.min(100, value * 100))}%`, background: color, transition: 'width .6s ease', boxShadow: '0 0 8px rgba(255, 138, 36, 0.35)' }} />
    </div>
  )
}

export function ConfidencePicker({ value, onChange, label = 'How sure are you?' }: { value: number | null; onChange: (n: number) => void; label?: string }) {
  const names = ['Guessing', 'Unsure', 'Maybe', 'Fairly sure', 'Certain']
  return (
    <div>
      <div className="text-xs font-bold text-slate-300 mb-1.5 desc-glow">{label}</div>
      <div className="flex gap-1.5 flex-wrap" role="radiogroup" aria-label={label}>
        {names.map((n, i) => (
          <button 
            key={n} 
            type="button" 
            role="radio" 
            aria-checked={value === i + 1} 
            onClick={() => onChange(i + 1)}
            className={`btn btn-sm ${value === i + 1 ? 'btn-primary' : 'btn-ghost'}`}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  )
}

export function Callout({ tone = 'saffron', title, children, icon }: { tone?: 'saffron' | 'teal' | 'violet' | 'red' | 'navy'; title?: string; children?: ReactNode; icon?: string }) {
  const c = {
    saffron: ['rgba(255, 138, 36, 0.12)', '#FF8A24', 'rgba(255, 138, 36, 0.35)'],
    teal: ['rgba(77, 157, 255, 0.12)', '#4D9DFF', 'rgba(77, 157, 255, 0.35)'],
    violet: ['rgba(168, 85, 247, 0.12)', '#C084FC', 'rgba(168, 85, 247, 0.35)'],
    red: ['rgba(255, 83, 100, 0.12)', '#FF5364', 'rgba(255, 83, 100, 0.35)'],
    navy: ['rgba(20, 32, 44, 0.35)', '#4D9DFF', 'rgba(210, 225, 235, 0.20)']
  }[tone]
  return (
    <div className="rounded-xl px-4 py-3 text-sm pop backdrop-blur-md shadow-md" style={{ background: c[0], borderLeft: `4px solid ${c[1]}`, borderTop: `1px solid ${c[2]}`, borderRight: `1px solid ${c[2]}`, borderBottom: `1px solid ${c[2]}` }}>
      {title && <div className="font-extrabold mb-1" style={{ color: c[1] }}>{icon ? icon + ' ' : ''}{title}</div>}
      <div className="text-slate-200 desc-glow leading-relaxed">{children}</div>
    </div>
  )
}

export function Collapsible({ title, children, defaultOpen = false }: { title: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <button className="text-sm font-bold text-[#4D9DFF] hover:underline flex items-center gap-1.5" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        <span className="text-xs">{open ? '▾' : '▸'}</span> {title}
      </button>
      {open && <div className="mt-2 pop">{children}</div>}
    </div>
  )
}

export function DataTable({ columns, rows, highlightNull = true }: { columns: string[]; rows: any[][]; highlightNull?: boolean }) {
  return (
    <div translate="no" className="overflow-auto rounded-xl border border-[rgba(210,225,235,0.16)] bg-[rgba(16,26,36,0.38)] backdrop-blur-md max-h-72">
      <table className="w-full text-sm">
        <thead className="bg-[rgba(20,32,44,0.55)] sticky top-0 border-b border-[rgba(210,225,235,0.16)]">
          <tr>
            {columns.map((c, i) => (
              <th key={i} className="text-left px-3 py-2 font-bold text-white font-mono text-xs whitespace-nowrap">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-[rgba(210,225,235,0.10)] hover:bg-[rgba(255,255,255,0.03)] transition-colors">
              {r.map((v, j) => (
                <td key={j} className="px-3 py-1.5 font-mono text-xs whitespace-nowrap text-slate-200">
                  {v === null ? <span className={highlightNull ? 'text-[#FF8A24] font-bold' : 'text-slate-400'}>NULL</span> : String(v)}
                </td>
              ))}
            </tr>
          ))}
          {!rows.length && <tr><td className="px-3 py-3 text-slate-400 text-xs" colSpan={Math.max(columns.length, 1)}>No rows returned.</td></tr>}
        </tbody>
      </table>
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="text-sm text-slate-400 text-center py-8 desc-glow">{children}</div>
}

export function SectionTitle({ eyebrow, title, subtitle, right }: { eyebrow?: string; title: ReactNode; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-3 flex-wrap mb-3.5">
      <div>
        {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
        <h2 className="text-lg lg:text-xl font-extrabold text-white heading-glow">{title}</h2>
        {subtitle && <p className="text-xs text-[var(--text-secondary)] mt-0.5 desc-glow">{subtitle}</p>}
      </div>
      {right}
    </div>
  )
}

