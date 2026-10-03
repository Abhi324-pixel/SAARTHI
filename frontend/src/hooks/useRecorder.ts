import { useCallback, useRef, useState } from 'react'
import { appendChunk, createRecording, discardIfEmpty, finishRecording, pickMime } from '../lib/recordings'

/** Records the live camera + microphone stream into this browser's own storage (see lib/recordings.ts). Never uploaded. */
export function useRecorder() {
  const [state, setState] = useState<'idle' | 'recording' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const rec = useRef<MediaRecorder | null>(null)
  const id = useRef<string | null>(null)
  const started = useRef(0)
  const queue = useRef<Promise<unknown>>(Promise.resolve())
  const failed = useRef(false)

  const pending = useRef<{ stream: MediaStream; p: Promise<string | null> } | null>(null)

  const stopCurrent = useCallback(async (): Promise<{ id: string; durationSec: number } | null> => {
    const mr = rec.current, recId = id.current
    if (!mr || !recId) { setState('idle'); return null }
    await new Promise<void>(res => { mr.onstop = () => res(); if (mr.state !== 'inactive') mr.stop(); else res() })
    await queue.current
    const durationSec = (Date.now() - started.current) / 1000
    await finishRecording(recId, durationSec).catch(() => {})
    const dropped = await discardIfEmpty(recId).catch(() => false)
    if (rec.current === mr) { rec.current = null; id.current = null }
    if (pending.current?.stream === mr.stream) pending.current = null
    setState(s => (s === 'error' ? s : 'idle'))
    return dropped ? null : { id: recId, durationSec }
  }, [])


  const begin = useCallback(async (stream: MediaStream, title: string, interviewId?: string): Promise<string | null> => {
    if (rec.current && rec.current.state !== 'inactive') await stopCurrent()      // never leave an earlier recorder running
    setError(null); failed.current = false
    if (typeof MediaRecorder === 'undefined') { setState('error'); setError('This browser cannot record video.'); return null }
    try {
      const mime = pickMime()
      const recId = `rec_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
      await createRecording({ id: recId, title, createdAt: new Date().toISOString(), mime: mime || 'video/webm', interviewId })
      const mr = new MediaRecorder(stream, { mimeType: mime || undefined, videoBitsPerSecond: 1_000_000, audioBitsPerSecond: 64_000 })
      mr.ondataavailable = e => {
        if (e.data && e.data.size > 0) {
          queue.current = queue.current.then(() => appendChunk(recId, e.data)).catch(() => {
            if (!failed.current) { failed.current = true; setState('error'); setError('Saving to this device failed (is the storage full?). The interview can continue, but this recording is incomplete.') }
          })
        }
      }
      mr.start(1000)
      rec.current = mr; id.current = recId; started.current = Date.now()
      setState('recording')
      return recId
    } catch (e: any) {
      setState('error'); setError(e?.message ?? 'Recording could not start.')
      return null
    }
  }, [stopCurrent])

  const start = useCallback((stream: MediaStream, title: string, interviewId?: string): Promise<string | null> => {
    if (pending.current?.stream === stream) return pending.current.p
    const p = begin(stream, title, interviewId)
    pending.current = { stream, p }
    return p
  }, [begin])

  const stop = stopCurrent

  return { state, error, start, stop }
}
