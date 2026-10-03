// Thin typed-ish client for the SAARTHI API. All requests carry the learner's token.

const KEY = 'saarthi.token'
export const tokenStore = {
  get(): string | null { try { return localStorage.getItem(KEY) } catch { return null } },
  set(t: string) { try { localStorage.setItem(KEY, t) } catch { /* private mode */ } },
  clear() { try { localStorage.removeItem(KEY) } catch { /* ignore */ } },
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

export async function req<T = any>(path: string, opts: { method?: string; body?: unknown; form?: FormData; raw?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const t = tokenStore.get()
  if (t) headers['Authorization'] = 'Bearer ' + t
  let body: BodyInit | undefined
  if (opts.form) body = opts.form
  else if (opts.body !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(opts.body) }
  const r = await fetch('/api' + path, { method: opts.method ?? (body ? 'POST' : 'GET'), headers, body })
  if (r.status === 401) { tokenStore.clear(); window.dispatchEvent(new Event('saarthi:unauth')) }
  if (!r.ok) {
    let msg = r.statusText
    try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j) } catch { /* not json */ }
    throw new ApiError(r.status, msg)
  }
  if (opts.raw) return r as unknown as T
  return r.json() as Promise<T>
}

export const api = {
  health: () => req('/health'),
  roles: () => req('/roles'),
  login: (b: { name: string; age: number; language: string }) => req('/auth/dev-login', { body: b }),
  demoAccounts: () => req('/dev/demo-accounts'),
  demoLogin: (id: string) => req('/dev/demo-login', { body: { mentor_id: id } }),
  me: () => req('/me'),
  onboard: (b: any) => req('/me/onboard', { body: b }),
  updateMe: (b: any) => req('/me', { method: 'PATCH', body: b }),
  exportMe: () => req('/me/export'),
  deleteMe: () => req('/me', { method: 'DELETE' }),
  dashboard: () => req('/dashboard'),
  graph: () => req('/graph'),
  concept: (id: string) => req('/concepts/' + id),
  probeNext: (count = 1, concept_id?: string) => req('/probe/next', { body: { count, concept_id } }),
  probeAnswer: (b: any) => req('/probe/answer', { body: b }),
  sqlTasks: (concept_id?: string) => req('/sql/tasks' + (concept_id ? `?concept_id=${concept_id}` : '')),
  sqlSchema: () => req('/sql/schema'),
  sqlRun: (query: string) => req('/sql/run', { body: { query } }),
  sqlSubmit: (b: any) => req('/sql/submit', { body: b }),
  teach: (b: any) => req('/teach/explain', { body: b }),
  ebStart: (concept_id: string, channel = 'text') => req('/explainback/start', { body: { concept_id, channel } }),
  ebAnswer: (b: any) => req('/explainback/answer', { body: b }),
  ebFinish: (session_id: string) => req('/explainback/finish', { body: { session_id } }),
  interviewStart: (n_topics = 4, channel = 'text', round = 'technical', pack_id?: string) => req('/interview/start', { body: { n_topics, channel, round, pack_id } }),
  interviewAnswer: (b: any) => req('/interview/answer', { body: b }),
  misconceptions: () => req('/misconceptions'),
  confirmMis: (id: string, confirmed: boolean) => req(`/misconceptions/${id}/confirm`, { body: { confirmed } }),
  disputeMis: (id: string) => req(`/misconceptions/${id}/dispute`, { method: 'POST' }),
  misPlan: (id: string) => req(`/misconception-library/${id}/plan`),
  roadmap: () => req('/roadmap'),
  whatIf: (weekly_hours: number, horizon_weeks: number) => req('/roadmap/what-if', { body: { weekly_hours, horizon_weeks } }),
  whyNot: (id: string) => req('/roadmap/why-not/' + id),
  genome: () => req('/genome'),
  dispute: (b: any) => req('/genome/dispute', { body: b }),
  reviewsDue: () => req('/reviews/due'),
  stuck: (b: any) => req('/stuck', { body: b }),
  mentors: () => req('/mentors'),
  cases: () => req('/cases'),
  createCase: (b: any) => req('/cases', { body: b }),
  caseDetail: (id: string) => req('/cases/' + id),
  sendMsg: (id: string, text: string) => req(`/cases/${id}/messages`, { body: { text } }),
  simulateSession: (id: string, rating = 0.8) => req(`/cases/${id}/simulate-session`, { body: { rating } }),
  followup: (id: string) => req(`/cases/${id}/followup`, { method: 'POST' }),
  consent: () => req('/consent'),
  consentDemo: (scope = 'mentor_sessions') => req('/consent/grant-demo', { body: { scope } }),
  consentSelf: (scope: string) => req('/consent/self-grant', { body: { scope } }),
  consentRevoke: (scope: string) => req('/consent/revoke', { body: { scope } }),
  report: (b: any) => req('/reports', { body: b }),
  cohort: () => req('/cohort'),
  voiceStatus: () => req('/voice/status'),
  voiceConnect: (mode: string, concept_id?: string, use_resume?: boolean) => req('/voice/connect', { body: { mode, concept_id, use_resume: !!use_resume } }),
  voiceTool: (tool: string, args: any, voice_session_id?: string) => req('/voice/tools/' + tool, { body: { args, voice_session_id } }),
  voiceTranscript: (voice_session_id: string, role: string, text: string) => req('/voice/transcript', { body: { voice_session_id, role, text } }),
  tts: async (text: string, language?: string): Promise<Blob> => (await req<Response>('/voice/tts', { body: { text, language }, raw: true })).blob(),
  stt: (blob: Blob, language?: string) => {
    const f = new FormData(); f.append('file', blob, 'speech.webm'); if (language) f.append('language', language)
    return req('/voice/stt', { form: f })
  },
  map: () => req('/map'),
  setMapGoal: (goal_id: string) => req('/map/goal', { body: { goal_id } }),
  inspectNode: (concept_id: string) => req('/map/node/' + concept_id),
  mapHistory: () => req('/map/history'),
  vakhLaunch: (concept_id: string) => req('/vakh/launch/' + concept_id),
  vakhChallenge: (concept_id: string) => req('/vakh/challenges/' + concept_id),
  devAdvance: (days: number) => req('/dev/advance-time', { body: { days } }),
  devStruggle: (concept_id: string) => req('/dev/simulate-struggle', { body: { concept_id } }),
  devSeedDemo: () => req('/dev/seed-demo', { method: 'POST' }),
  devReset: () => req('/dev/reset', { method: 'POST' }),
}
