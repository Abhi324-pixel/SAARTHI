import { useEffect, useState } from 'react'
import { deleteRecording, getRecordingBlob, humanSize, listRecordings, storageEstimate, type RecordingMeta } from '../../lib/recordings'
import { SectionTitle } from '../ui'

/** The learner's own interview recordings. They live only in this browser, on this device, until deleted here. */
export default function RecordingsPanel({ refreshKey = 0 }: { refreshKey?: number }) {
  const [items, setItems] = useState<RecordingMeta[] | null>(null)
  const [playing, setPlaying] = useState<{ id: string; url: string } | null>(null)
  const [usage, setUsage] = useState<{ used: number; quota: number } | null>(null)
  const [err, setErr] = useState<string | null>(null)

  async function load() {
    try { setItems(await listRecordings()); setUsage(await storageEstimate()) } catch (e: any) { setItems([]); setErr(e.message) }
  }
  useEffect(() => { load() }, [refreshKey])
  useEffect(() => () => { if (playing) URL.revokeObjectURL(playing.url) }, [playing])

  async function play(id: string) {
    setErr(null)
    if (playing) { URL.revokeObjectURL(playing.url); setPlaying(null) }
    const b = await getRecordingBlob(id)
    if (!b) { setErr('This recording has no saved data.'); return }
    setPlaying({ id, url: URL.createObjectURL(b) })
  }
  async function download(r: RecordingMeta) {
    const b = await getRecordingBlob(r.id)
    if (!b) return
    const a = document.createElement('a')
    a.href = URL.createObjectURL(b)
    a.download = `${r.title.replace(/[^\w-]+/g, '_')}.${r.mime.includes('mp4') ? 'mp4' : 'webm'}`
    a.click()
    setTimeout(() => URL.revokeObjectURL(a.href), 4000)
  }
  async function remove(r: RecordingMeta) {
    if (!window.confirm(`Delete "${r.title}" from this device? This cannot be undone.`)) return
    if (playing?.id === r.id) { URL.revokeObjectURL(playing.url); setPlaying(null) }
    await deleteRecording(r.id)
    load()
  }

  return (
    <div className="card p-5 space-y-3">
      <SectionTitle eyebrow="On this device only" title="My interview recordings" />
      <p className="text-xs text-muted">Video and voice are saved in this browser on this device and are never uploaded to SAARTHI. They stay until you delete them here. Clearing your browser data, or using another device, will remove or hide them.</p>
      {items === null && <p className="text-sm text-muted">Loading…</p>}
      {items?.length === 0 && <p className="text-sm text-muted">No recordings yet. They appear here after a video interview.</p>}
      <ul className="divide-y divide-line">
        {items?.map(r => (
          <li key={r.id} className="py-2.5 text-sm flex flex-wrap items-center gap-2 justify-between">
            <div><b className="text-navy">{r.title}</b><div className="text-xs text-muted">{new Date(r.createdAt).toLocaleString()} · {Math.floor(r.durationSec / 60)}m {r.durationSec % 60}s · {humanSize(r.sizeBytes)}{r.complete ? '' : ' · incomplete'}</div></div>
            <div className="flex gap-1.5">
              <button className="btn btn-ghost btn-sm" onClick={() => play(r.id)}>Play</button>
              <button className="btn btn-ghost btn-sm" onClick={() => download(r)}>Download</button>
              <button className="btn btn-ghost btn-sm text-lvl-unknown" onClick={() => remove(r)}>Delete</button>
            </div>
          </li>))}
      </ul>
      {playing && <video src={playing.url} controls className="w-full rounded-xl bg-black max-h-[360px]" aria-label="Recording playback"
        onLoadedMetadata={e => {
          // recorder files carry no length; seeking to the far end once makes the browser work it out so the seek bar works
          const v = e.currentTarget
          if (v.duration === Infinity || Number.isNaN(v.duration)) { v.currentTime = 1e101; v.addEventListener('timeupdate', () => { v.currentTime = 0 }, { once: true }) }
        }} />}
      {usage && usage.quota > 0 && <p className="text-[11px] text-muted">This browser is using {humanSize(usage.used)} of about {humanSize(usage.quota)} available for this site.</p>}
      {err && <p className="text-xs text-lvl-unknown font-semibold" role="alert">{err}</p>}
    </div>
  )
}
