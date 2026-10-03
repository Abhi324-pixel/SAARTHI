import { useState } from 'react'
import { DataTable } from './ui'

// the same shop data used by the SQL tasks (customers and orders only)
const CUSTOMERS = [
  { id: 1, name: 'Aarav Sharma' }, { id: 2, name: 'Priya Verma' }, { id: 3, name: 'Rohan Gupta' }, { id: 4, name: 'Sneha Iyer' },
  { id: 5, name: 'Imran Khan' }, { id: 6, name: 'Kavya Nair' }, { id: 7, name: 'Deepak Yadav' }, { id: 8, name: 'Meera Joshi' },
]
const ORDERS = [
  { id: 101, c: 1, s: 'delivered' }, { id: 102, c: 1, s: 'delivered' }, { id: 103, c: 2, s: 'delivered' }, { id: 104, c: 2, s: 'cancelled' },
  { id: 105, c: 3, s: 'delivered' }, { id: 106, c: 3, s: null }, { id: 107, c: 4, s: 'delivered' }, { id: 108, c: 4, s: 'pending' },
  { id: 109, c: 5, s: 'delivered' }, { id: 110, c: 5, s: 'delivered' }, { id: 111, c: 6, s: 'delivered' }, { id: 112, c: 1, s: 'pending' },
]
type Mode = 'inner' | 'left' | 'left_where' | 'left_on'

const MODES: { id: Mode; label: string; sql: string; note: string }[] = [
  { id: 'inner', label: 'INNER JOIN', sql: 'FROM customers c\nJOIN orders o ON o.customer_id = c.id', note: 'Only customers that have a matching order. Deepak and Meera disappear.' },
  { id: 'left', label: 'LEFT JOIN', sql: 'FROM customers c\nLEFT JOIN orders o ON o.customer_id = c.id', note: 'Every customer stays. No match → the order columns are NULL (orange).' },
  { id: 'left_where', label: 'LEFT JOIN + WHERE', sql: "FROM customers c\nLEFT JOIN orders o ON o.customer_id = c.id\nWHERE o.status = 'delivered'", note: "The WHERE test on orders removes the NULL rows → it behaves like an INNER JOIN again." },
  { id: 'left_on', label: 'LEFT JOIN + ON filter', sql: "FROM customers c\nLEFT JOIN orders o ON o.customer_id = c.id\n                 AND o.status = 'delivered'", note: 'Filter in ON: customers without a delivered order still appear, with NULL.' },
]

function compute(mode: Mode) {
  const rows: { name: string; oid: number | null; status: string | null; matched: boolean }[] = []
  for (const c of CUSTOMERS) {
    let os = ORDERS.filter(o => o.c === c.id)
    if (mode === 'left_where') os = os.filter(o => o.s === 'delivered')
    if (mode === 'left_on') os = os.filter(o => o.s === 'delivered')
    if (os.length) os.forEach(o => rows.push({ name: c.name, oid: o.id, status: o.s, matched: true }))
    else if (mode === 'left' || mode === 'left_on') rows.push({ name: c.name, oid: null, status: null, matched: false })
  }
  return rows
}

export default function JoinDiagram({ initial = 'left' }: { initial?: Mode }) {
  const [mode, setMode] = useState<Mode>(initial)
  const m = MODES.find(x => x.id === mode)!
  const rows = compute(mode)
  const keepsAll = mode === 'left' || mode === 'left_on'
  const matchedCust = new Set(ORDERS.map(o => o.c))
  return (
    <div className="card p-4">
      <div className="flex flex-wrap gap-1.5 mb-3" role="tablist" aria-label="Join type">
        {MODES.map(x => (
          <button key={x.id} role="tab" aria-selected={mode === x.id} onClick={() => setMode(x.id)} className={`btn btn-sm ${mode === x.id ? 'btn-primary' : 'btn-ghost'}`}>{x.label}</button>
        ))}
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <svg viewBox="0 0 330 250" className="w-full" role="img" aria-label={`Diagram of ${m.label}: customers on the left, orders on the right`}>
            <text x="0" y="12" fontSize="10" fontWeight="800" fill="#16324f">customers</text>
            <text x="250" y="12" fontSize="10" fontWeight="800" fill="#16324f">orders</text>
            {CUSTOMERS.map((c, i) => {
              const y = 20 + i * 27
              const lost = !keepsAll && !matchedCust.has(c.id)
              return (
                <g key={c.id} opacity={lost ? 0.35 : 1}>
                  <rect x="0" y={y} width="110" height="21" rx="6" fill={matchedCust.has(c.id) ? '#e8eef5' : '#fdf3e9'} stroke={matchedCust.has(c.id) ? '#c9d3df' : '#e07a1f'} />
                  <text x="7" y={y + 14} fontSize="10" fontWeight="600" fill="#1e2530">{c.id} · {c.name}</text>
                </g>
              )
            })}
            {ORDERS.map((o, i) => {
              const y = 20 + i * 18
              const cy = 20 + (o.c - 1) * 27 + 10.5
              const filtered = (mode === 'left_where' || mode === 'left_on') && o.s !== 'delivered'
              return (
                <g key={o.id} opacity={filtered ? 0.25 : 1}>
                  <path d={`M110,${cy} C170,${cy} 190,${y + 8} 250,${y + 8}`} fill="none" stroke="#1f7a7a" strokeWidth="1.3" />
                  <rect x="250" y={y} width="78" height="16" rx="5" fill="#e3f2f1" stroke="#1f7a7a" />
                  <text x="256" y={y + 11.5} fontSize="9" fontWeight="600" fill="#1e2530">{o.id} · {o.s ?? 'NULL'}</text>
                </g>
              )
            })}
          </svg>
        </div>
        <div>
          <pre className="text-[11.5px] bg-navy text-white rounded-xl p-3 mb-2 overflow-auto leading-relaxed">{'SELECT c.name, o.id\n' + m.sql}</pre>
          <div className="text-sm font-semibold text-navy mb-2">{m.note}</div>
          <DataTable columns={['name', 'order_id', 'status']} rows={rows.map(r => [r.name, r.oid, r.status])} />
          <div className="text-xs text-muted mt-1.5">{rows.length} rows · {rows.filter(r => !r.matched).length} unmatched customer(s) kept</div>
        </div>
      </div>
    </div>
  )
}
