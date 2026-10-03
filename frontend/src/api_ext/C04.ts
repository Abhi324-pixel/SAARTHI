import { tokenStore, ApiError } from '../api'

export interface CaseState {
  status: string
  updated_at: string
  last_message_at: string | null
  message_count: number
}

export interface StateResult {
  notModified: boolean
  etag?: string
  data?: CaseState
}

export interface SyncMessage {
  id: string
  sender: 'learner' | 'mentor' | 'system'
  text: string
  is_mock?: boolean
  at: string
  created_at: string
  sending?: boolean
}

export interface MessagesResult {
  messages: SyncMessage[]
  next_since: string | null
}

async function fetchState(url: string, etag?: string): Promise<StateResult> {
  const headers: Record<string, string> = {}
  const t = tokenStore.get()
  if (t) headers['Authorization'] = 'Bearer ' + t
  if (etag) headers['If-None-Match'] = etag

  const res = await fetch(url, { headers })
  if (res.status === 304) {
    return { notModified: true, etag }
  }
  if (!res.ok) {
    let msg = res.statusText
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j)
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, msg)
  }
  const newEtag = res.headers.get('ETag') || undefined
  const data = (await res.json()) as CaseState
  return { notModified: false, etag: newEtag, data }
}

async function fetchMessages(url: string): Promise<MessagesResult> {
  const headers: Record<string, string> = {}
  const t = tokenStore.get()
  if (t) headers['Authorization'] = 'Bearer ' + t

  const res = await fetch(url, { headers })
  if (!res.ok) {
    let msg = res.statusText
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j)
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, msg)
  }
  return (await res.json()) as MessagesResult
}

export const apiC04 = {
  learnerState: (caseId: string, etag?: string) => fetchState(`/api/cases/${caseId}/state`, etag),
  learnerMessages: (caseId: string, since?: string) =>
    fetchMessages(`/api/cases/${caseId}/messages${since ? `?since=${encodeURIComponent(since)}` : ''}`),
  mentorState: (caseId: string, etag?: string) => fetchState(`/api/mentor-console/cases/${caseId}/state`, etag),
  mentorMessages: (caseId: string, since?: string) =>
    fetchMessages(`/api/mentor-console/cases/${caseId}/messages${since ? `?since=${encodeURIComponent(since)}` : ''}`),
}

export function unreadSince(messages: { created_at?: string; at?: string }[], lastSeen: string): number {
  if (!lastSeen) return messages.length
  const lastSeenDate = new Date(lastSeen).getTime()
  return messages.filter(m => {
    const t = new Date(m.created_at || m.at || 0).getTime()
    return t > lastSeenDate
  }).length
}
