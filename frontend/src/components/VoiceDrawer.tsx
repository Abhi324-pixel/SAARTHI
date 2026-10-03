import { useConversation } from '@elevenlabs/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../store'
import JoinDiagram from './JoinDiagram'
import { Bar, Callout, Spinner } from './ui'

const TOOL_NAMES = ['get_learner_context', 'get_next_action', 'explain_topic', 'record_response', 'confirm_statement', 'show_visual', 'request_mentor']
const MODES = [
  { id: 'explain_back', label: 'Teach it back', hint: 'You explain, SAARTHI listens and scores with quotes.' },
  { id: 'diagnosis', label: 'Diagnose me', hint: 'A short voice check-up on the most useful concept.' },
  { id: 'teach', label: 'Teach me', hint: 'SAARTHI explains first, then asks you to teach it back.' },
  { id: 'interview', label: 'Mock interview', hint: 'A coverage-driven interview for your target role.' },
]

interface Ev { id: number; kind: 'tool' | 'user' | 'agent' | 'system'; name?: string; args?: any; result?: any; ms?: number; text?: string; at: string }

export default function VoiceDrawer({ open, onClose, initialMode = 'explain_back', initialConcept, initialUseResume = false }: {
  open: boolean; onClose: () => void; initialMode?: string; initialConcept?: string; initialUseResume?: boolean
}) {
  const { toast, bump, setRoadmapNote, me } = useApp()
  const [mode, setMode] = useState(initialMode)
  const [concept, setConcept] = useState<string>(initialConcept ?? '')
  const [concepts, setConcepts] = useState<any[]>([])
  const [vstatus, setVstatus] = useState<any | null>(null)
  const [connecting, setConnecting] = useState(false)
  const [setupError, setSetupError] = useState<string | null>(null)
  const [events, setEvents] = useState<Ev[]>([])
  const [panel, setPanel] = useState<{ panel: string; concept_id?: string } | null>(null)
  const [checklist, setChecklist] = useState<any[]>([])
  const [roadmapChange, setRoadmapChange] = useState<any | null>(null)
  const [typed, setTyped] = useState('')
  const [roadmap, setRoadmap] = useState<any | null>(null)
  const vsRef = useRef<string | undefined>(undefined)
  const idRef = useRef(1)
  const logRef = useRef<HTMLDivElement>(null)

  const conv = useConversation({
    onMessage: (p: any) => {
      const role = p.role ?? (p.source === 'user' ? 'user' : 'agent')
      addEvent({ kind: role === 'user' ? 'user' : 'agent', text: p.message })
    },
    onError: (e: any) => { toast(typeof e === 'string' ? e : e?.message ?? 'Voice connection problem', 'err'); addEvent({ kind: 'system', text: 'Error: ' + (typeof e === 'string' ? e : e?.message ?? 'unknown') }) },
    onConnect: () => addEvent({ kind: 'system', text: 'Connected to the ElevenLabs agent' }),
    onDisconnect: () => addEvent({ kind: 'system', text: 'Conversation ended' }),
  })
  const status = String((conv.status as any)?.status ?? conv.status ?? 'disconnected')
  const connected = status === 'connected'

  function addEvent(e: Omit<Ev, 'id' | 'at'>) {
    const id = idRef.current++
    setEvents(list => [...list, { ...e, id, at: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }])
    return id
  }
  function patchEvent(id: number, patch: Partial<Ev>) { setEvents(list => list.map(x => (x.id === id ? { ...x, ...patch } : x))) }

  useEffect(() => { logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' }) }, [events.length])
  useEffect(() => {
    if (!open) return
    setMode(initialMode); setConcept(initialConcept ?? '')
    api.voiceStatus().then(setVstatus).catch(() => setVstatus(null))
    api.graph().then(g => setConcepts(g.nodes.filter((n: any) => n.has_rubric))).catch(() => {})
    // eslint-disable-next-line
  }, [open])

  function applyUi(res: any) {
    if (res?.ui?.panel) setPanel({ panel: res.ui.panel, concept_id: res.ui.concept_id })
    if (res?.ui?.checklist) setChecklist(res.ui.checklist)
    if (res?.roadmap_change?.changed) {
      setRoadmapChange(res.roadmap_change); setRoadmapNote(res.roadmap_change.change_reason); bump()
      api.roadmap().then(setRoadmap).catch(() => {})
    }
    if (res?.done) { bump() }
  }

  const tools = useMemo(() => {
    const t: Record<string, (p: any) => Promise<string>> = {}
    TOOL_NAMES.forEach(name => {
      t[name] = async (params: any) => {
        const t0 = performance.now()
        const id = addEvent({ kind: 'tool', name, args: params })
        try {
          const res = await api.voiceTool(name, params ?? {}, vsRef.current)
          patchEvent(id, { result: res, ms: Math.round(performance.now() - t0) })
          applyUi(res)
          const { ui, ...forAgent } = res
          return JSON.stringify(forAgent)
        } catch (e: any) {
          patchEvent(id, { result: { error: e.message }, ms: Math.round(performance.now() - t0) })
          return JSON.stringify({ error: e.message, say: 'Something went wrong on my side. Let us continue by typing.' })
        }
      }
    })
    return t
    // eslint-disable-next-line
  }, [])

  async function start() {
    setConnecting(true); setSetupError(null); setEvents([]); setChecklist([]); setRoadmapChange(null)
    try {
      const c = await api.voiceConnect(mode, concept || undefined, mode === 'interview' && initialUseResume)
      vsRef.current = c.voice_session_id
      setPanel({ panel: 'concept', concept_id: c.dynamic_variables.current_concept })
      addEvent({ kind: 'system', text: `Session started · mode ${mode} · concept ${c.dynamic_variables.current_concept_name}` })
      conv.startSession({
        ...(c.mode === 'signed' ? { signedUrl: c.signed_url } : { agentId: c.agent_id }),
        dynamicVariables: c.dynamic_variables,
        clientTools: tools,
      } as any)
    } catch (e: any) {
      setSetupError(e.message)
    } finally { setConnecting(false) }
  }
  function stop() { try { conv.endSession() } catch { /* already closed */ } bump() }
  function close() { stop(); onClose() }
  function sendTyped() {
    if (!typed.trim() || !connected) return
    conv.sendUserMessage(typed.trim()); addEvent({ kind: 'user', text: typed.trim() }); setTyped('')
  }

  if (!open) return null
  const toolEvents = events.filter(e => e.kind === 'tool')
  const avg = toolEvents.filter(e => e.ms).length ? Math.round(toolEvents.reduce((a, e) => a + (e.ms ?? 0), 0) / toolEvents.filter(e => e.ms).length) : null
  const speaking = (conv as any).isSpeaking, listening = (conv as any).isListening
  const orbState = !connected ? 'idle' : speaking ? 'speaking' : 'listening'

  return (
    <div className="fixed inset-0 z-50 bg-[rgba(5,14,22,0.75)] backdrop-blur-md flex items-stretch md:items-center justify-center p-0 md:p-4" role="dialog" aria-modal="true" aria-label="Talk to SAARTHI">
      <div className="bg-[rgba(12,22,32,0.70)] backdrop-blur-2xl border border-[rgba(210,225,235,0.20)] w-full max-w-6xl md:rounded-3xl overflow-hidden flex flex-col max-h-full shadow-2xl text-white">
        <div className="bg-[rgba(10,20,30,0.50)] backdrop-blur-md text-white px-5 py-3.5 flex items-center justify-between gap-3 border-b border-[rgba(210,225,235,0.14)]">
          <div className="flex items-center gap-3">
            <div className="font-extrabold tracking-tight text-lg heading-glow">SAARTHI <span className="text-[#FF8A24]">voice mentor</span></div>
            <span className="chip" style={{ background: 'rgba(255,138,36,0.12)', color: '#FF8A24', border: '1px solid rgba(255,138,36,0.30)' }}>Powered by ElevenLabs</span>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={close}>Close ✕</button>
        </div>

        <div className="overflow-auto grid lg:grid-cols-[1fr_340px] gap-4 p-5">
          <div className="space-y-4 min-w-0">
            {!connected && (
              <div className="card p-5 space-y-4">
                <div className="eyebrow">Step 1 · choose what to do</div>
                <div className="grid sm:grid-cols-2 gap-2.5">
                  {MODES.map(m => (
                    <button 
                      key={m.id} 
                      onClick={() => setMode(m.id)} 
                      className={`text-left rounded-xl border p-3.5 transition-all ${
                        mode === m.id 
                          ? 'border-[#FF8A24] bg-[rgba(255,138,36,0.16)] shadow-[0_0_12px_rgba(255,138,36,0.2)]' 
                          : 'border-[rgba(210,225,235,0.14)] bg-[rgba(20,32,44,0.35)] hover:bg-[rgba(28,42,56,0.50)]'
                      }`}
                    >
                      <div className="font-bold text-white text-sm">{m.label}</div>
                      <div className="text-xs text-slate-300 desc-glow mt-0.5">{m.hint}</div>
                    </button>
                  ))}
                </div>
                {mode !== 'interview' && (
                  <label className="block text-sm font-semibold text-slate-200 desc-glow">Concept (optional — SAARTHI picks the most useful one if you don't)
                    <select className="input mt-1.5" value={concept} onChange={e => setConcept(e.target.value)}>
                      <option value="">Let SAARTHI choose</option>
                      {concepts.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </label>
                )}
                {vstatus && !vstatus.agent_ready && (
                  <Callout tone="saffron" title="Voice agent is not set up yet">
                    Create the ElevenLabs agent and add <code>ELEVENLABS_AGENT_ID</code> + <code>ELEVENLABS_API_KEY</code> to <code>backend/.env</code> (guide: <code>docs/ELEVENLABS_SETUP.md</code>). Meanwhile you can <Link className="underline font-bold text-[#FF8A24]" to={`/learn/${concept || 'sql_outer_join'}`} onClick={close}>teach it back in text</Link> — it uses the same engine.
                  </Callout>
                )}
                {setupError && <Callout tone="red" title="Could not start the voice session">{setupError}</Callout>}
                <button className="btn btn-primary w-full py-3 text-base" onClick={start} disabled={connecting || !!(vstatus && !vstatus.agent_ready)}>
                  {connecting ? 'Connecting…' : '🎙 Start talking'}
                </button>
                <div className="text-xs text-slate-400 desc-glow">Your browser will ask for microphone access. Prefer typing? Use the text teach-back on any concept page — same scoring.</div>
              </div>
            )}

            {connected && (
              <div className="card p-5 flex items-center gap-4">
                <div className={`h-16 w-16 rounded-full flex items-center justify-center text-2xl text-white shrink-0 ${orbState === 'speaking' ? 'bg-[#FF8A24] pulse-ring' : 'bg-[#4D9DFF]'}`} aria-hidden>
                  {orbState === 'speaking' ? '🗣' : '👂'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-extrabold text-white text-base heading-glow">{orbState === 'speaking' ? 'SAARTHI is speaking…' : listening || orbState === 'listening' ? "Listening — speak when you're ready" : 'Connected'}</div>
                  <div className="text-xs text-slate-300 desc-glow mt-0.5">Mode: {MODES.find(m => m.id === mode)?.label} · {me?.language}</div>
                </div>
                <div className="flex gap-2">
                  <button className="btn btn-ghost btn-sm" onClick={() => conv.setMuted(!(conv as any).isMuted)}>{(conv as any).isMuted ? '🔇 Unmute' : '🎤 Mute'}</button>
                  <button className="btn btn-primary btn-sm" onClick={stop}>End</button>
                </div>
              </div>
            )}

            {/* visual panel driven by the agent's show_visual / tool results */}
            {panel?.panel === 'join_diagram' && <JoinDiagram initial="left" />}
            {(panel?.panel === 'concept' || panel?.panel === 'sql_task') && checklist.length > 0 && (
              <div className="card p-4">
                <div className="eyebrow">Live checklist</div>
                <ul className="mt-1.5 space-y-1">{checklist.map((c: any) => (
                  <li key={c.id} className={`text-sm flex gap-2 ${c.covered ? 'flash rounded' : ''}`}><span className={c.covered ? 'text-[#35D07F] font-bold' : 'text-slate-400'}>{c.covered ? '✓' : '○'}</span><span>{c.text}{c.covered && c.evidence ? <i className="text-slate-400"> — “{c.evidence}”</i> : null}</span></li>))}
                </ul>
              </div>
            )}
            {roadmapChange && (
              <div className="card p-4 flash border-[#FF8A24]">
                <div className="eyebrow">Roadmap updated live</div>
                <div className="font-bold text-white mt-0.5">{roadmapChange.change_reason}</div>
                <div className="flex items-center gap-3 mt-2 text-xs font-semibold text-slate-300">
                  Readiness <b className="text-white">{Math.round(roadmapChange.readiness_now * 100)}%</b>
                  <Bar value={roadmapChange.readiness_now} color="#FF8A24" /> <span>after plan {Math.round(roadmapChange.readiness_after * 100)}%</span>
                </div>
                {roadmap && <ol className="mt-2 text-sm list-decimal pl-5">{roadmap.items.filter((i: any) => i.status !== 'done').slice(0, 4).map((i: any) => <li key={i.item_id}><b>{i.title}</b> <span className="text-slate-400">— {i.why?.split('. ')[0]}</span></li>)}</ol>}
              </div>
            )}

            <div className="card p-5">
              <div className="eyebrow mb-2">Conversation</div>
              <div ref={logRef} className="max-h-64 overflow-auto space-y-2.5 pr-1" aria-live="polite">
                {events.filter(e => e.kind !== 'tool').map(e => (
                  <div key={e.id} className={`text-sm rounded-2xl px-4 py-2.5 max-w-[90%] ${e.kind === 'user' ? 'bg-[rgba(255,138,36,0.22)] border border-[rgba(255,138,36,0.40)] text-white ml-auto' : e.kind === 'agent' ? 'bg-[rgba(20,32,44,0.50)] border border-[rgba(210,225,235,0.16)] text-slate-100' : 'bg-[rgba(10,20,30,0.40)] text-slate-400 text-xs italic'}`}>{e.text}</div>
                ))}
                {!events.length && <div className="text-sm text-slate-400 desc-glow">The conversation will appear here.</div>}
              </div>
              {connected && (
                <div className="flex gap-2 mt-3.5">
                  <input className="input" placeholder="Or type a message to SAARTHI…" value={typed} onChange={e => setTyped(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendTyped()} aria-label="Type a message" />
                  <button className="btn btn-primary" onClick={sendTyped}>Send</button>
                </div>
              )}
            </div>
          </div>

          {/* under the hood: makes the ElevenLabs usage obvious */}
          <aside className="card p-5 h-fit space-y-3.5 lg:sticky lg:top-0" aria-label="How ElevenLabs is used">
            <div className="eyebrow">Under the hood</div>
            <div className="text-sm space-y-1.5">
              <Row k="ElevenLabs Agent" v={connected ? 'connected' : connecting ? 'connecting…' : 'idle'} on={connected} />
              <Row k="Speech-to-text + voice" v={connected ? (speaking ? 'agent speaking' : 'listening') : '—'} on={connected} />
              <Row k="Client tools" v={`${TOOL_NAMES.length} registered`} on />
              <Row k="Tool calls this session" v={String(toolEvents.length)} on={toolEvents.length > 0} />
              <Row k="Avg tool latency" v={avg ? avg + ' ms' : '—'} on={!!avg} />
              <Row k="Read-aloud (TTS) / Mic (STT)" v={vstatus ? `${vstatus.tts_ready ? 'TTS ✓' : 'TTS –'} · ${vstatus.stt_ready ? 'STT ✓' : 'STT –'}` : '…'} on={!!vstatus?.tts_ready} />
            </div>
            <div className="text-xs text-slate-400 desc-glow leading-relaxed">The agent only talks. It cannot grade you or change your mastery — every answer goes through SAARTHI's tools, which run the same engines as the text app.</div>
            <div className="eyebrow pt-1">Tool calls</div>
            <div className="space-y-2 max-h-80 overflow-auto">
              {toolEvents.length === 0 && <div className="text-xs text-slate-400 desc-glow">Tool calls appear here as the agent uses them.</div>}
              {toolEvents.map(e => (
                <details key={e.id} className="rounded-xl border border-[rgba(210,225,235,0.14)] bg-[rgba(15,25,35,0.40)] px-3 py-2 text-xs">
                  <summary className="cursor-pointer font-mono font-bold text-white hover:text-[#FF8A24] transition-colors">{e.name} <span className="text-slate-400 font-sans font-medium">{e.ms ? `· ${e.ms} ms` : '· running…'}</span></summary>
                  <pre className="whitespace-pre-wrap mt-1 text-[10.5px] leading-snug text-slate-300 font-mono">{JSON.stringify({ args: e.args, result: e.result?.say ?? e.result }, null, 1).slice(0, 900)}</pre>
                </details>
              ))}
            </div>
            {status === 'connecting' && <Spinner label="Connecting to the agent…" />}
          </aside>
        </div>
      </div>
    </div>
  )
}

function Row({ k, v, on }: { k: string; v: string; on?: boolean }) {
  return <div className="flex items-center justify-between gap-2"><span className="text-muted">{k}</span><span className={`font-bold ${on ? 'text-teal' : 'text-muted'}`}>{v}</span></div>
}
