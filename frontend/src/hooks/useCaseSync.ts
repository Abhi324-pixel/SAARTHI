import { useEffect, useRef, useState, useCallback } from 'react'
import { apiC04, CaseState, StateResult, MessagesResult, SyncMessage, unreadSince } from '../api_ext/C04'

export { unreadSince }

export interface UseCaseSyncOptions {
  fetchState?: (etag?: string) => Promise<StateResult>
  fetchMessages?: (since?: string) => Promise<MessagesResult>
  onMessages?: (messages: SyncMessage[]) => void
  onStatus?: (status: string) => void
  active?: boolean
  role?: 'learner' | 'mentor'
  otherPartyName?: string
}

const ACTIVE_STATUSES = new Set(['open', 'matched', 'accepted', 'scheduled', 'held'])

export function useCaseSync(caseId: string | null | undefined, options: UseCaseSyncOptions = {}) {
  const {
    fetchState: customFetchState,
    fetchMessages: customFetchMessages,
    onMessages,
    onStatus,
    active = true,
    role = 'learner',
    otherPartyName = 'your mentor',
  } = options

  const [announcement, setAnnouncement] = useState<string>('')
  const [lastState, setLastState] = useState<CaseState | null>(null)

  const etagRef = useRef<string | undefined>(undefined)
  const cursorRef = useRef<string | undefined>(undefined)
  const stateRef = useRef<CaseState | null>(null)
  const delayRef = useRef<number>(3000)
  const timerRef = useRef<any>(null)
  const isPollingRef = useRef<boolean>(false)

  // Use either custom fetchers or defaults based on role and caseId
  const doFetchState = useCallback(
    async (etag?: string): Promise<StateResult> => {
      if (customFetchState) return customFetchState(etag)
      if (!caseId) throw new Error('No caseId')
      return role === 'mentor' ? apiC04.mentorState(caseId, etag) : apiC04.learnerState(caseId, etag)
    },
    [caseId, role, customFetchState]
  )

  const doFetchMessages = useCallback(
    async (since?: string): Promise<MessagesResult> => {
      if (customFetchMessages) return customFetchMessages(since)
      if (!caseId) throw new Error('No caseId')
      return role === 'mentor' ? apiC04.mentorMessages(caseId, since) : apiC04.learnerMessages(caseId, since)
    },
    [caseId, role, customFetchMessages]
  )

  const poll = useCallback(async () => {
    if (!caseId || document.visibilityState === 'hidden') {
      return
    }
    if (isPollingRef.current) return
    isPollingRef.current = true

    try {
      const res = await doFetchState(etagRef.current)
      if (!res.notModified && res.data) {
        etagRef.current = res.etag
        const prev = stateRef.current
        stateRef.current = res.data
        setLastState(res.data)

        if (prev && res.data.status !== prev.status) {
          onStatus?.(res.data.status)
        }

        const msgChanged =
          !prev ||
          res.data.last_message_at !== prev.last_message_at ||
          res.data.message_count !== prev.message_count

        if (msgChanged) {
          const msgRes = await doFetchMessages(cursorRef.current)
          if (msgRes.messages.length > 0) {
            cursorRef.current = msgRes.next_since || cursorRef.current
            onMessages?.(msgRes.messages)

            // Screen reader announcement for incoming message
            const otherSender = role === 'learner' ? 'mentor' : 'learner'
            const hasOtherMsg = msgRes.messages.some(m => m.sender === otherSender)
            if (hasOtherMsg) {
              setAnnouncement(`New message from ${otherPartyName}`)
            }
          }
        }
      }

      // Success: reset delay
      const isCaseActive = stateRef.current ? ACTIVE_STATUSES.has(stateRef.current.status) : active
      const baseDelay = isCaseActive ? 3000 : 15000
      delayRef.current = baseDelay
    } catch {
      // Exponential back-off up to 30s
      delayRef.current = Math.min(30000, Math.max(3000, delayRef.current * 1.5))
    } finally {
      isPollingRef.current = false
      if ((document.visibilityState as string) !== 'hidden') {
        timerRef.current = setTimeout(poll, delayRef.current)
      }
    }
  }, [caseId, active, role, otherPartyName, doFetchState, doFetchMessages, onMessages, onStatus])

  // Lifecycle & visibility change handling
  useEffect(() => {
    if (!caseId) return

    // Reset refs on caseId change
    etagRef.current = undefined
    cursorRef.current = undefined
    stateRef.current = null
    delayRef.current = 3000

    poll()

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        clearTimeout(timerRef.current)
        delayRef.current = 3000
        poll()
      } else {
        clearTimeout(timerRef.current)
      }
    }

    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      clearTimeout(timerRef.current)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [caseId, poll])

  return {
    state: lastState,
    announcement,
    syncNow: poll,
  }
}
