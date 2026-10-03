import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Bar, Callout, Spinner } from './ui'
import WebResources from './WebResources'

interface MapNode {
  id: string
  name: string
  domain: string
  difficulty: string
  state: 'MASTERED' | 'IN_PROGRESS' | 'AVAILABLE' | 'RECOMMENDED' | 'LOCKED' | 'BLOCKED' | 'NEEDS_REVIEW' | 'MISCONCEPTION' | 'DETOUR'
  p: number
  target: number
  confidence: number
  nav_tag: string | null
  misconceptions: string[]
  blocked_by: string[]
  why_reason: string
  vakh_challenge_id: string | null
  prerequisites: string[]
}

interface MapEdge {
  source: string
  target: string
  relationship: string
  required: boolean
}

interface MapResponse {
  goal: {
    id: string
    title: string
    required_competencies: string[]
  }
  version: number
  current_position: string | null
  recommended_next: string | null
  next_action: {
    concept_id: string
    action: string
    title: string
    reason: string
    vakh_challenge?: any
  } | null
  nodes: MapNode[]
  edges: MapEdge[]
  reason: string
  generated_at: string
}

const STATE_CONFIG: Record<string, { label: string; bg: string; border: string; text: string; icon: string }> = {
  MASTERED: { label: 'Target reached', bg: 'bg-[rgba(53,208,127,0.10)]', border: 'border-[rgba(53,208,127,0.55)]', text: 'text-[#6EE7A8]', icon: '✓' },
  RECOMMENDED: { label: 'Recommended Next', bg: 'bg-[rgba(255,181,46,0.12)]', border: 'border-[rgba(255,181,46,0.7)] shadow-md ring-2 ring-[rgba(255,181,46,0.35)]', text: 'text-[#FFD27A]', icon: '⚡' },
  DETOUR: { label: 'Active Detour', bg: 'bg-[rgba(168,127,255,0.12)]', border: 'border-[rgba(168,127,255,0.6)] shadow-md ring-2 ring-[rgba(168,127,255,0.3)]', text: 'text-[#C9B3FF]', icon: '↻' },
  MISCONCEPTION: { label: 'Needs Remediation', bg: 'bg-[rgba(255,83,100,0.12)]', border: 'border-[rgba(255,83,100,0.5)]', text: 'text-[#FF9AA5]', icon: '⚠' },
  AVAILABLE: { label: 'Available', bg: 'bg-[rgba(77,157,255,0.10)]', border: 'border-[rgba(77,157,255,0.45)]', text: 'text-[#8EC1FF]', icon: '○' },
  IN_PROGRESS: { label: 'In Progress', bg: 'bg-[rgba(110,120,255,0.12)]', border: 'border-[rgba(110,120,255,0.5)]', text: 'text-[#B4BAFF]', icon: '◐' },
  BLOCKED: { label: 'Blocked by Prerequisite', bg: 'bg-[rgba(210,225,235,0.06)]', border: 'border-[rgba(210,225,235,0.18)] opacity-80', text: 'text-[#9FB0BF]', icon: '🔒' },
  LOCKED: { label: 'Locked', bg: 'bg-[rgba(210,225,235,0.04)]', border: 'border-[rgba(210,225,235,0.12)] opacity-70', text: 'text-[#8798A8]', icon: '🔒' },
  NEEDS_REVIEW: { label: 'Review Due', bg: 'bg-[rgba(255,138,36,0.12)]', border: 'border-[rgba(255,138,36,0.5)]', text: 'text-[#FFB070]', icon: '🔁' },
}

const READY = 0.7   // a prerequisite counts as "ready to build on" at about 70% (the same rule the backend uses to unlock)

/** The backend sends `title`, `p_known`, `why`, `navigation_action`, `current_node` and `from`/`to` edges. This turns that into the
 *  shape the screen draws, and fills safe defaults so one missing field can never blank the whole map. */
function normalizeMap(raw: any): MapResponse {
  const src: any[] = Array.isArray(raw?.nodes) ? raw.nodes : []
  const byId = new Map<string, any>(src.map(n => [n.id, n]))
  const nodes: MapNode[] = src.map(n => {
    const prereqs: string[] = Array.isArray(n.prerequisites) ? n.prerequisites : []
    const weak = ['BLOCKED', 'LOCKED'].includes(n.state)
      ? prereqs.filter(pid => (byId.get(pid)?.p_known ?? 1) < READY).map(pid => byId.get(pid)?.title ?? pid)
      : []
    return {
      id: n.id, name: n.title ?? n.name ?? n.id, domain: n.domain ?? '', difficulty: String(n.difficulty ?? ''), state: n.state,
      p: Number(n.p_known ?? n.p ?? 0), target: Number(n.target ?? 0.7), confidence: Number(n.confidence ?? 0),
      nav_tag: n.nav_tag ?? null, misconceptions: Array.isArray(n.misconceptions) ? n.misconceptions : [],
      blocked_by: weak, why_reason: n.why ?? n.why_reason ?? '', vakh_challenge_id: n.has_vakh_challenge ? `vch_${n.id}` : (n.vakh_challenge_id ?? null),
      prerequisites: prereqs,
    }
  })
  const act = raw?.navigation_action
  return {
    goal: { id: raw?.goal?.id ?? '', title: raw?.goal?.title ?? raw?.goal?.name ?? 'Your goal', required_competencies: raw?.goal?.required_competencies ?? nodes.map(n => n.id) },
    version: raw?.version ?? 1,
    current_position: raw?.current_position ?? raw?.current_node ?? null,
    recommended_next: raw?.recommended_next ?? null,
    next_action: act ? { concept_id: raw?.recommended_next ?? '', action: act.type ?? '', title: act.title ?? '', reason: act.why ?? act.reason ?? '' } : (raw?.next_action ?? null),
    nodes,
    edges: (Array.isArray(raw?.edges) ? raw.edges : []).map((e: any) => ({ source: e.from ?? e.source, target: e.to ?? e.target, relationship: e.type ?? e.relationship ?? '', required: e.required ?? true })),
    reason: raw?.reason ?? '',
    generated_at: raw?.generated_at ?? '',
  }
}

export default function NavigationMap() {
  const [mapData, setMapData] = useState<MapResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedDetail, setSelectedDetail] = useState<any | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState<any[]>([])
  const [goalSwitching, setGoalSwitching] = useState(false)

  const loadMap = async () => {
    try {
      setLoading(true)
      const data = normalizeMap(await api.map())
      setMapData(data)
      if (data.recommended_next) {
        setSelectedNodeId(data.recommended_next)
      } else if (data.nodes.length > 0) {
        setSelectedNodeId(data.nodes[0].id)
      }
      setError(null)
    } catch (e: any) {
      setError(e.message || 'Failed to load navigation map')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadMap()
  }, [])

  useEffect(() => {
    if (!selectedNodeId) {
      setSelectedDetail(null)
      return
    }
    setDetailLoading(true)
    api.inspectNode(selectedNodeId)
      .then(res => setSelectedDetail(res))
      .catch(() => setSelectedDetail(null))
      .finally(() => setDetailLoading(false))
  }, [selectedNodeId])

  const handleGoalChange = async (newGoalId: string) => {
    if (!newGoalId || (mapData && mapData.goal.id === newGoalId)) return
    try {
      setGoalSwitching(true)
      const updatedMap = normalizeMap(await api.setMapGoal(newGoalId))
      setMapData(updatedMap)
      if (updatedMap.recommended_next) {
        setSelectedNodeId(updatedMap.recommended_next)
      }
    } catch (e: any) {
      alert(e.message || 'Failed to change goal')
    } finally {
      setGoalSwitching(false)
    }
  }

  const handleOpenHistory = async () => {
    setShowHistory(true)
    try {
      const res = await api.mapHistory()
      setHistory(res.history || [])
    } catch (e) {
      // ignore
    }
  }

  const handleLaunchVakh = async (conceptId: string) => {
    try {
      const res = await api.vakhLaunch(conceptId)
      if (res.launch_url) {
        window.open(res.launch_url, '_blank', 'noopener,noreferrer')
      } else {
        alert(res.message || 'Vakh is not connected yet.')
      }
    } catch (e: any) {
      alert(e.message || 'Unable to launch Vakh challenge')
    }
  }

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center space-y-3">
        <Spinner label="Recalculating learning coordinates..." />
        <p className="text-xs text-muted">Analyzing BKT mastery, graph dependencies, and active misconceptions</p>
      </div>
    )
  }

  if (error || !mapData) {
    return (
      <div className="card p-6 bg-red-50 border-red-200 text-red-800 space-y-3">
        <h3 className="font-bold text-base">Learning GPS Offline</h3>
        <p className="text-sm">{error || 'No route data available'}</p>
        <button className="btn btn-secondary btn-sm" onClick={loadMap}>Retry Navigation</button>
      </div>
    )
  }

  // Group nodes into topological lanes: Completed/Mastered, Current Focus, Upcoming/Blocked
  const masteredNodes = mapData.nodes.filter(n => n.state === 'MASTERED')
  const activeNodes = mapData.nodes.filter(n => ['RECOMMENDED', 'DETOUR', 'MISCONCEPTION', 'IN_PROGRESS'].includes(n.state))
  const upcomingNodes = mapData.nodes.filter(n => ['AVAILABLE', 'BLOCKED', 'LOCKED', 'NEEDS_REVIEW'].includes(n.state))

  const selectedNode = mapData.nodes.find(n => n.id === selectedNodeId)

  return (
    <div className="space-y-6">
      {/* GPS NAVIGATION STATUS BAR */}
      <div className="p-5 bg-navy text-white shadow-xl rounded-2xl relative overflow-hidden">
        <div className="absolute right-0 top-0 bottom-0 opacity-10 flex items-center pr-6 pointer-events-none text-9xl">
          🧭
        </div>
        
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 relative z-10">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-400 text-navy uppercase tracking-wider">
                GPS NAVIGATION ACTIVE
              </span>
              <span className="text-xs text-slate-300">Route Version {mapData.version}</span>
            </div>
            
            <div className="flex items-center gap-3 flex-wrap pt-1">
              <h2 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
                <span>🎯 Destination:</span>
                <span className="text-amber-300">{mapData.goal.title}</span>
              </h2>
              
              <div className="flex items-center gap-1 bg-[rgba(16,26,36,0.38)]/10 px-3 py-1 rounded-lg border border-white/20">
                <span className="text-xs text-slate-300 font-semibold">Change Goal:</span>
                <select
                  disabled={goalSwitching}
                  value={mapData.goal.id}
                  onChange={(e) => handleGoalChange(e.target.value)}
                  className="bg-navy text-white text-xs font-bold rounded px-2 py-1 border border-white/30 focus:outline-none focus:ring-1 focus:ring-amber-400"
                >
                  <option value="backend_developer">Backend Developer</option>
                  <option value="ml_engineer">Machine Learning Engineer (foundations track)</option>
                </select>
              </div>
            </div>

            <p className="text-xs text-slate-300 max-w-2xl pt-1">
              <span className="font-semibold text-amber-200">Latest Route Reason:</span> {mapData.reason}
            </p>
          </div>

          <div className="flex items-center gap-2 self-start lg:self-center">
            <button
              onClick={handleOpenHistory}
              className="px-3 py-2 rounded-lg bg-[rgba(16,26,36,0.38)]/10 hover:bg-[rgba(16,26,36,0.38)]/20 border border-white/20 text-xs font-bold text-white transition flex items-center gap-1.5"
            >
              <span>📜 What Changed? (v{mapData.version})</span>
            </button>
            <button
              onClick={loadMap}
              className="px-3 py-2 rounded-lg bg-amber-400 hover:bg-amber-300 text-navy text-xs font-black transition flex items-center gap-1.5 shadow"
            >
              <span>🔄 Recalculate</span>
            </button>
          </div>
        </div>

        {/* TURN BY TURN NAVIGATION BANNER */}
        <div className="mt-4 pt-4 border-t border-white/15 grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="bg-[rgba(16,26,36,0.38)]/5 rounded-xl p-3 border border-white/10">
            <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">YOU ARE HERE</div>
            <div className="font-bold text-sm text-white mt-0.5 flex items-center gap-1.5">
              <span className="text-amber-400">📍</span>
              <span>{mapData.current_position ? mapData.current_position.replace(/_/g, ' ') : 'Start of Route'}</span>
            </div>
          </div>

          <div className="bg-amber-400/20 rounded-xl p-3 border border-[rgba(255,181,46,0.4)]">
            <div className="text-[10px] uppercase font-black text-amber-300 tracking-wider">RECOMMENDED NEXT ACTION</div>
            <div className="font-extrabold text-sm text-amber-100 mt-0.5 flex items-center gap-1.5">
              <span>⚡</span>
              <span>{mapData.next_action?.title || mapData.recommended_next?.replace(/_/g, ' ') || 'Goal Achieved!'}</span>
            </div>
            {mapData.next_action?.reason && (
              <div className="text-[11px] text-amber-200/80 mt-1 line-clamp-1">{mapData.next_action.reason}</div>
            )}
          </div>

          <div className="bg-[rgba(16,26,36,0.38)]/5 rounded-xl p-3 border border-white/10">
            <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">ROUTE STATUS</div>
            <div className="font-bold text-sm text-white mt-0.5 flex items-center gap-2">
              <span className="text-emerald-400">✓ {masteredNodes.length} target reached</span>
              <span className="text-slate-400">·</span>
              <span className="text-amber-300">⚡ {activeNodes.length} In Route</span>
              <span className="text-slate-400">·</span>
              <span className="text-slate-400">🗺️ {upcomingNodes.length} upcoming</span>
            </div>
          </div>
        </div>
      </div>

      {/* INTERACTIVE NAVIGATION MAP & DETAILS SPLIT */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6">
        {/* MAP CANVAS / FLOW */}
        <div className="space-y-6">
          {/* Active Detours / Misconceptions Banner if any */}
          {mapData.nodes.some(n => n.state === 'DETOUR') && (
            <Callout tone="saffron" title="Active Adaptive Detour">
              A foundational prerequisite was identified as needing reinforcement before continuing on the main path. The learning GPS has rerouted you to ensure mastery.
            </Callout>
          )}

          {/* LANE 1: IMMEDIATE / FOCUS ROUTE (YOU ARE HERE & NEXT) */}
          <section className="card p-5 space-y-4 border-2 border-[rgba(255,181,46,0.4)] bg-gradient-to-b from-amber-50/40 to-white">
            <div className="flex items-center justify-between border-b border-line pb-2">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-amber-500 animate-ping" />
                <h3 className="font-extrabold text-navy text-base">Active Waypoints (Current Guidance)</h3>
              </div>
              <span className="text-xs text-muted font-medium">Click any waypoint to inspect</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {activeNodes.map(node => {
                const conf = STATE_CONFIG[node.state] || STATE_CONFIG.AVAILABLE
                const isSelected = selectedNodeId === node.id
                return (
                  <div
                    key={node.id}
                    onClick={() => setSelectedNodeId(node.id)}
                    className={`cursor-pointer rounded-xl p-4 border transition-all duration-150 ${conf.bg} ${conf.border} ${
                      isSelected ? 'ring-2 ring-navy scale-[1.02] shadow-lg' : 'hover:scale-[1.01] hover:shadow'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-xs font-black px-2 py-0.5 rounded-full bg-[rgba(16,26,36,0.38)] border shadow-sm">
                          {conf.icon} {conf.label}
                        </span>
                        {node.nav_tag && (
                          <span className="text-[10px] font-extrabold px-1.5 py-0.5 rounded bg-amber-400 text-navy uppercase">
                            {node.nav_tag}
                          </span>
                        )}
                      </div>
                      <span className="text-xs font-black text-navy">{Math.round(node.p * 100)}%</span>
                    </div>

                    <h4 className="font-black text-navy text-base mt-2">{node.name}</h4>
                    <p className="text-xs text-muted line-clamp-2 mt-1">{node.why_reason}</p>

                    <div className="mt-3">
                      <Bar value={node.p} h={6} />
                    </div>

                    <div className="mt-3 pt-2 border-t border-black/5 flex items-center justify-between text-xs">
                      <span className="text-muted capitalize">{node.domain}</span>
                      {node.vakh_challenge_id ? (
                        <span className="font-bold text-[#C9B3FF] flex items-center gap-1">
                          🏆 Vakh Challenge
                        </span>
                      ) : (
                        <span className="font-bold text-teal flex items-center gap-1">
                          📘 Learn
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          {/* LANE 2: UPCOMING WAYPOINTS & BLOCKED NODES */}
          {upcomingNodes.length > 0 && (
            <section className="card p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-2">
                <h3 className="font-extrabold text-navy text-base flex items-center gap-2">
                  <span>🗺️ Downstream Route ({upcomingNodes.length})</span>
                </h3>
                <span className="text-xs text-muted">Unlocks as prerequisites are satisfied</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {upcomingNodes.map(node => {
                  const conf = STATE_CONFIG[node.state] || STATE_CONFIG.AVAILABLE
                  const isSelected = selectedNodeId === node.id
                  return (
                    <div
                      key={node.id}
                      onClick={() => setSelectedNodeId(node.id)}
                      className={`cursor-pointer rounded-xl p-3 border transition-all ${conf.bg} ${conf.border} ${
                        isSelected ? 'ring-2 ring-navy shadow-md' : 'hover:border-navy/40'
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-muted">{conf.icon} {conf.label}</span>
                        <span className="font-bold text-navy">{Math.round(node.p * 100)}%</span>
                      </div>
                      <div className="font-bold text-sm text-navy mt-1 truncate">{node.name}</div>
                      {node.blocked_by.length > 0 && (
                        <div className="text-[11px] text-red-600 mt-1 truncate">
                          Requires: {node.blocked_by.join(', ').replace(/_/g, ' ')}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          {/* LANE 3: MASTERED / SATISFIED PREREQUISITES */}
          {masteredNodes.length > 0 && (
            <section className="card p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-2">
                <h3 className="font-extrabold text-navy text-base flex items-center gap-2">
                  <span>✅ Target-reached waypoints ({masteredNodes.length})</span>
                </h3>
                <span className="text-xs text-[#6EE7A8] font-bold">Transferable Knowledge Preserved</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {masteredNodes.map(node => {
                  const isSelected = selectedNodeId === node.id
                  return (
                    <div
                      key={node.id}
                      onClick={() => setSelectedNodeId(node.id)}
                      className={`cursor-pointer rounded-xl p-3 border border-emerald-300 bg-[rgba(53,208,127,0.10)]/50 transition-all ${
                        isSelected ? 'ring-2 ring-emerald-600 shadow-md' : 'hover:border-emerald-500'
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-[#6EE7A8]">✓ Target reached</span>
                        <span className="font-black text-[#6EE7A8]">{Math.round(node.p * 100)}%</span>
                      </div>
                      <div className="font-bold text-sm text-navy mt-1 truncate">{node.name}</div>
                    </div>
                  )
                })}
              </div>
            </section>
          )}
        </div>

        {/* SIDE DRAWER: SELECTED NODE INSPECTION & VAKH CHALLENGE */}
        <aside className="space-y-4">
          {selectedNode ? (
            <div className="card p-5 space-y-4 sticky top-20 shadow-md border-2 border-line">
              <div className="border-b border-line pb-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted">
                    {selectedNode.domain}
                  </span>
                  <span className={`text-xs font-extrabold px-2 py-0.5 rounded-full ${
                    STATE_CONFIG[selectedNode.state]?.bg || 'bg-[rgba(210,225,235,0.08)]'
                  } ${STATE_CONFIG[selectedNode.state]?.text || 'text-[#9FB0BF]'}`}>
                    {STATE_CONFIG[selectedNode.state]?.label || selectedNode.state}
                  </span>
                </div>
                <h3 className="text-xl font-black text-navy mt-1">{selectedNode.name}</h3>
                <div className="flex items-center gap-3 mt-2 text-xs text-muted">
                  <span>Difficulty: <b className="text-navy capitalize">{selectedNode.difficulty}</b></span>
                  <span>Confidence: <b className="text-navy">{Math.round(selectedNode.confidence * 100)}%</b></span>
                </div>
              </div>

              {/* BKT Mastery Display */}
              <div className="space-y-1.5 bg-paper p-3 rounded-xl border border-line">
                <div className="flex items-center justify-between text-xs font-bold">
                  <span className="text-navy">BKT Mastery Probability</span>
                  <span className="text-saffron font-black">{Math.round(selectedNode.p * 100)}% of {Math.round(selectedNode.target * 100)}% target</span>
                </div>
                <Bar value={selectedNode.p} h={8} />
                <p className="text-[11px] text-muted pt-1">
                  Estimated from your answers, practice and submitted work. It is not a grade.
                </p>
              </div>

              {/* WHY THIS NAVIGATION EXPLANATION */}
              <div className="space-y-1">
                <div className="text-xs font-black text-saffron uppercase tracking-wider flex items-center gap-1">
                  <span>🔍 WHY THIS WAYPOINT?</span>
                </div>
                <div className="text-xs text-navy leading-relaxed bg-amber-50/70 p-3 rounded-xl border border-[rgba(255,181,46,0.4)]">
                  {selectedNode.why_reason}
                </div>
              </div>

              {/* ACTIVE MISCONCEPTIONS IF ANY */}
              {selectedNode.misconceptions && selectedNode.misconceptions.length > 0 && (
                <div className="space-y-1">
                  <div className="text-xs font-black text-[#FF9AA5] uppercase tracking-wider flex items-center gap-1">
                    <span>⚠️ IDENTIFIED MISCONCEPTION</span>
                  </div>
                  <div className="text-xs text-[#FF9AA5] bg-[rgba(255,83,100,0.12)] p-3 rounded-xl border border-[rgba(255,83,100,0.4)] space-y-1">
                    {selectedNode.misconceptions.map(m => (
                      <div key={m} className="font-semibold">• {m.replace(/_/g, ' ')}</div>
                    ))}
                    <p className="text-[11px] text-[#FF9AA5] pt-1">
                      Remediation required before downstream multi-step topics can unlock.
                    </p>
                  </div>
                </div>
              )}

              {/* PREREQUISITES / BLOCKERS */}
              {selectedNode.blocked_by && selectedNode.blocked_by.length > 0 && (
                <div className="space-y-1">
                  <div className="text-xs font-black text-[#9FB0BF] uppercase tracking-wider">
                    BLOCKED UNTIL READY (about 70%):
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedNode.blocked_by.map(pr => (
                      <span key={pr} className="text-xs px-2 py-1 bg-red-50 text-red-700 rounded-lg border border-red-200 font-bold">
                        🔒 {pr.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* VAKH PRACTICAL CHALLENGE SECTION */}
              <WebResources conceptId={selectedNode.id} compact />

              {selectedDetail?.challenge && (
                <div className="card p-4 bg-purple-50/60 border-2 border-[rgba(168,127,255,0.4)] rounded-xl space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-black tracking-wider text-[#C9B3FF] flex items-center gap-1">
                      <span>🏆 VAKH PRACTICAL BUILD</span>
                    </span>
                    <span className="text-[10px] bg-purple-200 text-[#C9B3FF] font-bold px-1.5 py-0.5 rounded">
                      PRACTICAL BUILD
                    </span>
                  </div>
                  <h4 className="font-extrabold text-navy text-sm">
                    {selectedDetail.challenge.title}
                  </h4>
                  <p className="text-xs text-slate-200 line-clamp-3">
                    {selectedDetail.challenge.description}
                  </p>
                  <button
                    onClick={() => handleLaunchVakh(selectedNode.id)}
                    className="w-full py-2 px-3 rounded-xl bg-purple-700 hover:bg-purple-800 text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow transition"
                  >
                    <span>🚀 Launch Challenge on Vakh</span>
                  </button>
                  <p className="text-[10px] text-center text-[#C9B3FF]">
                    When you submit your build on Vakh and it is reviewed, the review counts as evidence of what you can do.
                  </p>
                </div>
              )}

              {/* ACTIONS: START LEARNING / PRACTICE */}
              <div className="space-y-2 pt-2 border-t border-line">
                <Link
                  to={`/learn/${selectedNode.id}`}
                  className="w-full py-2.5 px-4 rounded-xl bg-navy hover:bg-[#1b2b48] text-white text-xs font-bold text-center block shadow transition"
                >
                  📖 Open Learning & Practice Unit
                </Link>

                {selectedNode.domain === 'sql' && (
                  <Link
                    to={`/sql?concept=${selectedNode.id}`}
                    className="w-full py-2 px-4 rounded-xl bg-paper hover:bg-line text-navy text-xs font-bold text-center block border border-line transition"
                  >
                    💻 Launch SQL Sandbox
                  </Link>
                )}
              </div>
            </div>
          ) : (
            <div className="card p-6 text-center text-muted text-sm">
              Select any waypoint on the map to inspect its prerequisites, BKT mastery probability, and actionable Vakh challenges.
            </div>
          )}
        </aside>
      </div>

      {/* HISTORY MODAL / DRAWER */}
      {showHistory && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-[rgba(16,26,36,0.38)] rounded-2xl max-w-lg w-full max-h-[80vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="p-4 border-b border-line flex items-center justify-between">
              <div>
                <h3 className="font-black text-navy text-base">Route Version History</h3>
                <p className="text-xs text-muted">Why your learning map evolved across versions</p>
              </div>
              <button
                onClick={() => setShowHistory(false)}
                className="text-xs font-bold text-muted hover:text-navy px-2 py-1 rounded"
              >
                ✕ Close
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-3 flex-1">
              {history.length === 0 ? (
                <div className="text-center py-8 text-sm text-muted">Initial route version 1 generated.</div>
              ) : (
                history.map((h, i) => (
                  <div key={i} className="p-3 rounded-xl bg-paper border border-line space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-extrabold text-navy">Version {h.version}</span>
                      <span className="text-muted">{h.at || 'Earlier'}</span>
                    </div>
                    <div className="text-xs text-navy font-medium">{h.reason}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
