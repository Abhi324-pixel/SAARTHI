import { useEffect, useSyncExternalStore } from 'react'
import { apiC05 } from '../api_ext/C05'

// One poll for the whole app (bell, nav badge, per-case chips). Pauses while the tab is hidden, refreshes on focus, backs off on errors.
export interface NotifSummary { unread: number; messages_unread: number; cases: Record<string, number> }

let state: NotifSummary = { unread: 0, messages_unread: 0, cases: {} }
const listeners = new Set<() => void>()
let timer: ReturnType<typeof setTimeout> | undefined
let users = 0
let failures = 0
const BASE_MS = 30000

function emit() { listeners.forEach(l => l()) }

export async function refreshNotifications() {
  try {
    const s = await apiC05.summary()
    failures = 0
    if (JSON.stringify(s) !== JSON.stringify(state)) { state = s; emit() }
  } catch { failures = Math.min(failures + 1, 4) }
}

function schedule() {
  clearTimeout(timer)
  if (users === 0) return
  timer = setTimeout(async () => { if (document.visibilityState === 'visible') await refreshNotifications(); schedule() }, BASE_MS * 2 ** failures)
}

function onVisible() { if (document.visibilityState === 'visible' && users > 0) { refreshNotifications(); schedule() } }

export function useNotifications(): NotifSummary {
  useEffect(() => {
    users++
    if (users === 1) { document.addEventListener('visibilitychange', onVisible); window.addEventListener('focus', onVisible) }
    refreshNotifications(); schedule()
    return () => {
      users--
      if (users === 0) { document.removeEventListener('visibilitychange', onVisible); window.removeEventListener('focus', onVisible); clearTimeout(timer) }
    }
  }, [])
  return useSyncExternalStore(cb => { listeners.add(cb); return () => { listeners.delete(cb) } }, () => state)
}
