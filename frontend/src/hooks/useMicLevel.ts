import { useEffect, useRef, useState } from 'react'
import { classifyVoice, dbFromRms, LIMITS, rmsOf, type VoiceLevel } from '../lib/measure'

export interface MicStats { speakingMs: number; goodMs: number; peakDb: number }

/** Live microphone loudness (dBFS: 0 is the loudest possible, quiet rooms sit near -60). Measured with the Web Audio API in
 *  this browser; the audio itself is not stored by this hook. */
export function useMicLevel(stream: MediaStream | null) {
  const [db, setDb] = useState(-100)
  const [level, setLevel] = useState<VoiceLevel>('silent')
  const stats = useRef<MicStats>({ speakingMs: 0, goodMs: 0, peakDb: -100 })

  useEffect(() => {
    stats.current = { speakingMs: 0, goodMs: 0, peakDb: -100 }
    const track = stream?.getAudioTracks()[0]
    if (!stream || !track) { setDb(-100); setLevel('silent'); return }
    const AC: typeof AudioContext = (window as any).AudioContext || (window as any).webkitAudioContext
    if (!AC) return
    const ctx = new AC()
    const src = ctx.createMediaStreamSource(new MediaStream([track]))
    const an = ctx.createAnalyser()
    an.fftSize = 1024
    src.connect(an)
    const buf = new Float32Array(an.fftSize)
    const STEP = 100
    const timer = window.setInterval(() => {
      if (ctx.state === 'suspended') ctx.resume().catch(() => {})
      an.getFloatTimeDomainData(buf)
      const d = dbFromRms(rmsOf(buf))
      const lv = classifyVoice(d)
      setDb(d); setLevel(lv)
      const s = stats.current
      if (d > s.peakDb) s.peakDb = d
      if (d >= LIMITS.speakingDb) { s.speakingMs += STEP; if (lv === 'good') s.goodMs += STEP }
    }, STEP)
    return () => { window.clearInterval(timer); try { src.disconnect() } catch { /* ignore */ } ctx.close().catch(() => {}) }
  }, [stream])

  return { db, level, stats }
}
