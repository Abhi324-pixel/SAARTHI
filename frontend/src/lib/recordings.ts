// Interview recordings are stored ONLY in this browser (IndexedDB) on the learner's own device. They are never sent to the server.
// They stay until the learner deletes them. Chunks are written as they arrive, so closing the tab does not lose the whole video.

export interface RecordingMeta {
  id: string
  title: string
  createdAt: string
  mime: string
  chunks: number
  sizeBytes: number
  durationSec: number
  complete: boolean
  interviewId?: string
}

const DB_NAME = 'saarthi-recordings'
let dbp: Promise<IDBDatabase> | null = null

function open(): Promise<IDBDatabase> {
  if (dbp) return dbp
  dbp = new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') { reject(new Error('This browser cannot save recordings (no local storage available).')); return }
    const r = indexedDB.open(DB_NAME, 1)
    r.onupgradeneeded = () => {
      const d = r.result
      d.createObjectStore('meta', { keyPath: 'id' })
      d.createObjectStore('chunks')            // key: `${id}:${n}`
    }
    r.onsuccess = () => resolve(r.result)
    r.onerror = () => reject(r.error ?? new Error('Could not open local storage.'))
  })
  return dbp
}

function tx<T>(stores: string[], mode: IDBTransactionMode, run: (t: IDBTransaction) => IDBRequest<T> | void): Promise<T | undefined> {
  return open().then(d => new Promise<T | undefined>((resolve, reject) => {
    const t = d.transaction(stores, mode)
    const req = run(t)
    t.oncomplete = () => resolve(req ? (req as IDBRequest<T>).result : undefined)
    t.onerror = () => reject(t.error ?? new Error('Local storage failed.'))
    t.onabort = () => reject(t.error ?? new Error('Local storage is full or was blocked.'))
  }))
}

/** Ask the browser not to evict our data under storage pressure ("keep until the learner deletes it"). Best effort. */
export async function requestPersistence(): Promise<boolean> {
  try { return (await navigator.storage?.persist?.()) ?? false } catch { return false }
}

export async function storageEstimate(): Promise<{ used: number; quota: number } | null> {
  try { const e = await navigator.storage?.estimate?.(); return e ? { used: e.usage ?? 0, quota: e.quota ?? 0 } : null } catch { return null }
}

export async function createRecording(meta: Omit<RecordingMeta, 'chunks' | 'sizeBytes' | 'complete' | 'durationSec'>): Promise<void> {
  await tx(['meta'], 'readwrite', t => t.objectStore('meta').put({ ...meta, chunks: 0, sizeBytes: 0, durationSec: 0, complete: false }))
}

export async function appendChunk(id: string, blob: Blob): Promise<void> {
  await tx(['meta', 'chunks'], 'readwrite', t => {
    const metaStore = t.objectStore('meta')
    const g = metaStore.get(id)
    g.onsuccess = () => {
      const m = g.result as RecordingMeta | undefined
      if (!m) return
      t.objectStore('chunks').put(blob, `${id}:${m.chunks}`)
      metaStore.put({ ...m, chunks: m.chunks + 1, sizeBytes: m.sizeBytes + blob.size })
    }
  })
}

export async function finishRecording(id: string, durationSec: number): Promise<void> {
  await tx(['meta'], 'readwrite', t => {
    const s = t.objectStore('meta')
    const g = s.get(id)
    g.onsuccess = () => { const m = g.result as RecordingMeta | undefined; if (m) s.put({ ...m, complete: true, durationSec: Math.round(durationSec) }) }
  })
}

/** A recording that never received any data (camera failed at the start) is removed so the list has no empty items. */
export async function discardIfEmpty(id: string): Promise<boolean> {
  const meta = await tx<RecordingMeta | undefined>(['meta'], 'readonly', t => t.objectStore('meta').get(id))
  if (meta && meta.chunks === 0) { await deleteRecording(id); return true }
  return false
}

export async function listRecordings(): Promise<RecordingMeta[]> {
  const all = (await tx<RecordingMeta[]>(['meta'], 'readonly', t => t.objectStore('meta').getAll())) ?? []
  return all.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
}

export async function getRecordingBlob(id: string): Promise<Blob | null> {
  const meta = await tx<RecordingMeta | undefined>(['meta'], 'readonly', t => t.objectStore('meta').get(id))
  if (!meta || !meta.chunks) return null
  const parts: Blob[] = []
  for (let i = 0; i < meta.chunks; i++) {
    const b = await tx<Blob | undefined>(['chunks'], 'readonly', t => t.objectStore('chunks').get(`${id}:${i}`))
    if (b) parts.push(b)
  }
  return parts.length ? new Blob(parts, { type: meta.mime }) : null
}

export async function deleteRecording(id: string): Promise<void> {
  const meta = await tx<RecordingMeta | undefined>(['meta'], 'readonly', t => t.objectStore('meta').get(id))
  await tx(['meta', 'chunks'], 'readwrite', t => {
    t.objectStore('meta').delete(id)
    for (let i = 0; i < (meta?.chunks ?? 0); i++) t.objectStore('chunks').delete(`${id}:${i}`)
  })
}

export function humanSize(n: number): string {
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
}

/** Pick a container the browser can both record and play back. */
export function pickMime(): string {
  const options = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4']
  return options.find(o => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(o)) ?? ''
}
