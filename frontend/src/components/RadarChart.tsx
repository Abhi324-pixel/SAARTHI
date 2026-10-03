/**
 * RadarChart — SVG polygon radar (4+ axes) or horizontal bar fallback (<3 axes).
 * Ported from the TESSA radarSvg idea; SAARTHI has 4–5 domains.
 * No external library.
 */

import type { RadarDomain } from '../api_ext/T06'

const DOMAIN_COLORS: Record<string, string> = {
  sql: '#e07a1f',
  python: '#1f7a7a',
  backend: '#16324f',
  tools: '#7b1fa2',
  communication: '#1f6f45',
}
const DEFAULT_COLOR = '#e07a1f'

interface RadarChartProps {
  domains: RadarDomain[]
}

function polarToXY(angle: number, radius: number, cx: number, cy: number) {
  return {
    x: cx + radius * Math.sin(angle),
    y: cy - radius * Math.cos(angle),
  }
}

export default function RadarChart({ domains }: RadarChartProps) {
  if (!domains.length) {
    return <div className="text-sm text-muted text-center py-4">No domain data yet.</div>
  }

  // Fallback to bars if fewer than 3 axes
  if (domains.length < 3) {
    return (
      <div className="space-y-2" id="t06-radar-bars">
        {domains.map((d) => (
          <div key={d.domain}>
            <div className="flex justify-between text-xs font-semibold mb-0.5">
              <span style={{ color: DOMAIN_COLORS[d.domain] ?? DEFAULT_COLOR }}>{d.domain}</span>
              <span className="text-muted">{Math.round(d.current * 100)}%</span>
            </div>
            <div className="w-full bg-[#e8edf3] rounded-full overflow-hidden" style={{ height: 7 }}>
              <div className="h-full rounded-full"
                style={{ width: `${Math.max(2, d.current * 100)}%`, background: DOMAIN_COLORS[d.domain] ?? DEFAULT_COLOR, transition: 'width .6s ease' }} />
            </div>
          </div>
        ))}
      </div>
    )
  }

  // Polygon radar
  const n = domains.length
  const size = 180
  const cx = size / 2
  const cy = size / 2
  const maxR = size / 2 - 20

  // Grid rings (25%, 50%, 75%, 100%)
  const rings = [0.25, 0.5, 0.75, 1.0]

  function domainPoints(vals: number[]) {
    return vals.map((v, i) => {
      const angle = (2 * Math.PI * i) / n
      const r = v * maxR
      return polarToXY(angle, r, cx, cy)
    })
  }

  const targetPts = domainPoints(domains.map(() => 1.0))
  const currentPts = domainPoints(domains.map((d) => d.current))

  function polyPath(pts: { x: number; y: number }[]) {
    return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') + ' Z'
  }

  return (
    <div id="t06-radar-chart">
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full" style={{ maxHeight: 200 }}
        role="img" aria-label="Skill radar chart" aria-describedby="t06-radar-table">
        {/* Grid rings */}
        {rings.map((r) => {
          const pts = Array.from({ length: n }, (_, i) => {
            const angle = (2 * Math.PI * i) / n
            return polarToXY(angle, r * maxR, cx, cy)
          })
          return <path key={r} d={polyPath(pts)} fill="none" stroke="#e8edf3" strokeWidth={1} />
        })}

        {/* Axis lines */}
        {domains.map((_, i) => {
          const angle = (2 * Math.PI * i) / n
          const outer = polarToXY(angle, maxR, cx, cy)
          return <line key={i} x1={cx} y1={cy} x2={outer.x} y2={outer.y} stroke="#dde2e9" strokeWidth={1} />
        })}

        {/* Target polygon */}
        <path d={polyPath(targetPts)} fill="#e8edf3" stroke="#dde2e9" strokeWidth={1} fillOpacity={0.3} />

        {/* Current polygon */}
        <path d={polyPath(currentPts)} fill="#e07a1f" stroke="#e07a1f" strokeWidth={2} fillOpacity={0.2} />

        {/* Axis labels */}
        {domains.map((d, i) => {
          const angle = (2 * Math.PI * i) / n
          const pt = polarToXY(angle, maxR + 12, cx, cy)
          return (
            <text key={d.domain} x={pt.x} y={pt.y + 3}
              textAnchor="middle" fontSize={9} fill={DOMAIN_COLORS[d.domain] ?? DEFAULT_COLOR}
              fontWeight="bold">
              {d.domain}
            </text>
          )
        })}

        {/* Current value dots */}
        {currentPts.map((pt, i) => (
          <circle key={i} cx={pt.x} cy={pt.y} r={3} fill={DOMAIN_COLORS[domains[i].domain] ?? DEFAULT_COLOR} />
        ))}
      </svg>

      {/* Accessible table */}
      <table className="sr-only" id="t06-radar-table">
        <caption>Skill radar data by domain</caption>
        <thead><tr><th>Domain</th><th>Current %</th><th>Target %</th></tr></thead>
        <tbody>
          {domains.map((d) => (
            <tr key={d.domain}>
              <td>{d.domain}</td>
              <td>{Math.round(d.current * 100)}</td>
              <td>{Math.round(d.target * 100)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Legend */}
      <div className="flex gap-3 text-xs text-muted mt-2 justify-center">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-1.5 rounded" style={{ background: '#e8edf3', border: '1px solid #dde2e9' }} /> Target
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-1.5 rounded" style={{ background: '#e07a1f', opacity: 0.6 }} /> You now
        </span>
      </div>
    </div>
  )
}
