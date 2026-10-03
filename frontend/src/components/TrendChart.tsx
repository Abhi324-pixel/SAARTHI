/**
 * TrendChart — hand-written SVG progress-over-time line chart.
 * No external chart library. Accessible: visually-hidden data table for screen readers.
 *
 * Props:
 *   series    – array of {at, overall, by_domain, n, simulated}
 *   markers   – array of {at, kind, label}
 *   projection – {overall, weeks}
 *   domains   – list of domain keys to offer as toggles (derived from series)
 */

import { useState, useMemo } from 'react'
import type { ProgressPoint, ProgressMarker } from '../api_ext/T06'

const W = 560
const H = 220
const PAD = { top: 16, right: 16, bottom: 32, left: 40 }
const INNER_W = W - PAD.left - PAD.right
const INNER_H = H - PAD.top - PAD.bottom

const DOMAIN_COLORS: Record<string, string> = {
  sql: '#e07a1f',
  python: '#1f7a7a',
  backend: '#16324f',
  tools: '#7b1fa2',
  communication: '#1f6f45',
}
const OVERALL_COLOR = '#e07a1f'
const SIM_DASH = '4 3'

function xOf(at: string, tMin: number, tMax: number): number {
  const t = new Date(at).getTime()
  const range = tMax - tMin || 1
  return PAD.left + ((t - tMin) / range) * INNER_W
}

function yOf(val: number): number {
  return PAD.top + INNER_H - val * INNER_H
}

function pathD(pts: { x: number; y: number }[]): string {
  if (!pts.length) return ''
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
}

// Y-axis labels
const Y_TICKS = [0, 25, 50, 75, 100]

interface TrendChartProps {
  series: ProgressPoint[]
  markers: ProgressMarker[]
  projection: { overall: number; weeks: number }
}

export default function TrendChart({ series, markers, projection }: TrendChartProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)

  // Derive available domains from the first point that has by_domain
  const allDomains = useMemo(() => {
    const sample = series.find((p) => p.by_domain)
    return sample ? Object.keys(sample.by_domain).sort() : []
  }, [series])

  const [activeDomains, setActiveDomains] = useState<Set<string>>(new Set())

  function toggleDomain(dom: string) {
    setActiveDomains((prev) => {
      const next = new Set(prev)
      if (next.has(dom)) next.delete(dom)
      else next.add(dom)
      return next
    })
  }

  if (!series.length) {
    return (
      <div className="text-sm text-muted text-center py-8" id="t06-trend-empty">
        No evidence yet — take the placement to start your progress chart.
      </div>
    )
  }
  if (series.length === 1) {
    return (
      <div className="text-sm text-muted text-center py-8" id="t06-trend-one-point">
        Only one point so far — come back after more practice to see a trend.
      </div>
    )
  }

  const times = series.map((p) => new Date(p.at).getTime())
  const tMin = Math.min(...times)
  const tMax = Math.max(...times)

  // Split series into real vs simulated segments for visual difference
  const overallPts = series.map((p) => ({ x: xOf(p.at, tMin, tMax), y: yOf(p.overall), sim: p.simulated }))

  // Projection endpoint
  const lastPt = overallPts[overallPts.length - 1]
  const projX = PAD.left + INNER_W  // right edge (future)
  const projY = yOf(projection.overall)

  // Marker x positions
  const markerKindIcon: Record<string, string> = {
    mentor: '🤝',
    misconception_resolved: '✓',
    plan_changed: '📝',
  }

  return (
    <div id="t06-trend-chart">
      {/* Domain toggles */}
      {allDomains.length > 0 && (
        <div className="flex gap-1.5 flex-wrap mb-3" role="group" aria-label="Toggle domains">
          {allDomains.map((dom) => {
            const active = activeDomains.has(dom)
            const color = DOMAIN_COLORS[dom] ?? '#888'
            return (
              <button
                key={dom}
                id={`t06-toggle-${dom}`}
                className={`chip text-xs font-semibold transition`}
                style={{
                  background: active ? color : '#e8edf3',
                  color: active ? '#fff' : '#5b6675',
                  border: `1px solid ${active ? color : '#dde2e9'}`,
                }}
                onClick={() => toggleDomain(dom)}
                aria-pressed={active}
              >
                {dom}
              </button>
            )
          })}
        </div>
      )}

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ maxHeight: 240 }}
        role="img"
        aria-label="Progress over time chart"
        aria-describedby="t06-trend-table-caption"
      >
        {/* Y-axis grid lines + labels */}
        {Y_TICKS.map((pct) => {
          const y = yOf(pct / 100)
          return (
            <g key={pct}>
              <line x1={PAD.left} x2={PAD.left + INNER_W} y1={y} y2={y}
                stroke="#e8edf3" strokeWidth={1} />
              <text x={PAD.left - 4} y={y + 3.5} textAnchor="end"
                fontSize={9} fill="#9ca3af">{pct}%</text>
            </g>
          )
        })}

        {/* Domain lines (when toggled) */}
        {allDomains.filter((d) => activeDomains.has(d)).map((dom) => {
          const color = DOMAIN_COLORS[dom] ?? '#888'
          const pts = series.map((p) => ({
            x: xOf(p.at, tMin, tMax),
            y: yOf((p.by_domain?.[dom] ?? 0)),
          }))
          return (
            <path key={dom} d={pathD(pts)} fill="none"
              stroke={color} strokeWidth={1.5} strokeOpacity={0.7}
              strokeDasharray="5 3" />
          )
        })}

        {/* Overall line — split at simulated boundaries for visual cue */}
        {overallPts.map((pt, i) => {
          if (i === 0) return null
          const prev = overallPts[i - 1]
          return (
            <line key={i}
              x1={prev.x} y1={prev.y} x2={pt.x} y2={pt.y}
              stroke={OVERALL_COLOR}
              strokeWidth={2}
              strokeDasharray={pt.sim || prev.sim ? SIM_DASH : undefined}
              strokeOpacity={pt.sim ? 0.5 : 1}
            />
          )
        })}

        {/* Projection dotted line */}
        {series.length > 0 && (
          <g>
            <line x1={lastPt.x} y1={lastPt.y} x2={projX} y2={projY}
              stroke={OVERALL_COLOR} strokeWidth={1.5} strokeDasharray="6 4" strokeOpacity={0.4} />
            <circle cx={projX} cy={projY} r={3} fill={OVERALL_COLOR} opacity={0.4} />
            <text x={projX - 2} y={projY - 7} textAnchor="end" fontSize={9} fill="#9ca3af">
              Projection ({projection.weeks}w)
            </text>
          </g>
        )}

        {/* Markers */}
        {markers.map((m, i) => {
          const mx = xOf(m.at, tMin, tMax)
          if (mx < PAD.left || mx > PAD.left + INNER_W) return null
          return (
            <g key={i}>
              <line x1={mx} y1={PAD.top} x2={mx} y2={PAD.top + INNER_H}
                stroke="#b0b8c4" strokeWidth={1} strokeDasharray="3 2" />
              <text x={mx} y={PAD.top - 2} textAnchor="middle" fontSize={9} fill="#9ca3af">
                {markerKindIcon[m.kind] ?? '·'}
              </text>
            </g>
          )
        })}

        {/* Hover dots */}
        {overallPts.map((pt, i) => (
          <circle key={i}
            cx={pt.x} cy={pt.y} r={hoveredIdx === i ? 5 : 3}
            fill={OVERALL_COLOR} stroke="#fff" strokeWidth={1}
            style={{ cursor: 'pointer' }}
            tabIndex={0}
            onMouseEnter={() => setHoveredIdx(i)}
            onMouseLeave={() => setHoveredIdx(null)}
            onFocus={() => setHoveredIdx(i)}
            onBlur={() => setHoveredIdx(null)}
            role="button"
            aria-label={`${series[i].at.slice(0, 10)}: ${Math.round(series[i].overall * 100)}%${series[i].simulated ? ' (simulated)' : ''}`}
          />
        ))}

        {/* Hover tooltip */}
        {hoveredIdx !== null && (() => {
          const pt = overallPts[hoveredIdx]
          const sp = series[hoveredIdx]
          const tx = Math.min(pt.x + 6, PAD.left + INNER_W - 60)
          const ty = Math.max(pt.y - 20, PAD.top + 12)
          return (
            <g>
              <rect x={tx - 2} y={ty - 10} width={88} height={22} rx={4} fill="#16324f" opacity={0.85} />
              <text x={tx + 2} y={ty + 2} fontSize={9} fill="#fff">
                {sp.at.slice(0, 10)} · {Math.round(sp.overall * 100)}%
                {sp.simulated ? ' ◌' : ''}
              </text>
            </g>
          )
        })()}

        {/* X-axis date labels */}
        <text x={PAD.left} y={H - 4} fontSize={9} fill="#9ca3af">
          {series[0]?.at.slice(0, 10)}
        </text>
        <text x={PAD.left + INNER_W} y={H - 4} fontSize={9} fill="#9ca3af" textAnchor="end">
          {series[series.length - 1]?.at.slice(0, 10)}
        </text>
      </svg>

      {/* Simulated notice */}
      {series.some((p) => p.simulated) && (
        <div className="text-xs text-muted mt-1">
          <span style={{ opacity: 0.5 }}>◌</span> Dashed segments are demo-seeded history (labelled <em>simulated</em> in the evidence log).
        </div>
      )}

      {/* Projection label */}
      <div className="text-xs text-muted mt-0.5">
        Dotted extension = Projection — assumes you reach every target on your roadmap.
      </div>

      {/* Visually-hidden accessible table */}
      <table className="sr-only" id="t06-trend-table-caption">
        <caption>Progress over time data</caption>
        <thead><tr><th>Date</th><th>Overall %</th><th>Evidence count</th><th>Simulated</th></tr></thead>
        <tbody>
          {series.map((p, i) => (
            <tr key={i}>
              <td>{p.at.slice(0, 10)}</td>
              <td>{Math.round(p.overall * 100)}</td>
              <td>{p.n}</td>
              <td>{p.simulated ? 'yes' : 'no'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Sparkline({ points, width = 110, height = 24 }: { points: { overall: number; at?: string }[]; width?: number; height?: number }) {
  if (!points || points.length === 0) return null
  if (points.length === 1) {
    return (
      <div className="text-[10px] text-muted flex items-center gap-1">
        <span className="inline-block w-2 h-2 rounded-full" style={{ background: OVERALL_COLOR }} />
        <span>{Math.round(points[0].overall * 100)}%</span>
      </div>
    )
  }
  const vals = points.map((p) => p.overall)
  const min = Math.min(...vals, 0)
  const max = Math.max(...vals, 1)
  const range = max - min || 1
  const pad = 3
  const innerW = width - pad * 2
  const innerH = height - pad * 2
  const coords = points.map((p, i) => {
    const x = pad + (i / (points.length - 1)) * innerW
    const y = pad + innerH - ((p.overall - min) / range) * innerH
    return { x, y }
  })
  const d = coords.map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ')
  const last = coords[coords.length - 1]

  return (
    <svg width={width} height={height} className="overflow-visible" role="img" aria-label="14-day progress sparkline">
      <path d={d} fill="none" stroke={OVERALL_COLOR} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last.x} cy={last.y} r={2.5} fill={OVERALL_COLOR} />
    </svg>
  )
}
