import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiC05 } from '../api_ext/C05'
import { refreshNotifications, useNotifications } from '../hooks/useNotifications'
import { useApp } from '../store'

/** Bell with an unread badge and a dropdown. Sentences come from the translation dictionary (`notif.<kind>`), never from the server. */
export default function NotificationBell() {
  const { t } = useApp()
  const nav = useNavigate()
  const s = useNotifications()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<any[] | null>(null)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    apiC05.list().then(r => setItems(r.notifications)).catch(() => setItems([]))
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', close); document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc) }
  }, [open, s.unread])

  // the tab title shows the count, so a hidden tab still tells you
  useEffect(() => {
    const base = 'SAARTHI'
    document.title = s.unread > 0 ? `(${s.unread}) ${base}` : base
    return () => { document.title = base }
  }, [s.unread])

  async function go(n: any) {
    setOpen(false)
    if (!n.read) { try { await apiC05.markRead([n.id]); refreshNotifications() } catch { /* ignore */ } }
    if (n.link) nav(n.link)
  }
  async function readAll() { try { await apiC05.markAllRead(); setItems(l => l?.map(x => ({ ...x, read: true })) ?? l); refreshNotifications() } catch { /* ignore */ } }

  return (
    <div className="relative" ref={box}>
      <button className="relative btn btn-sm" style={{ background: 'rgba(255,255,255,.12)', color: '#fff' }} aria-label={`${t('notifications')}${s.unread ? `, ${s.unread} unread` : ''}`} aria-expanded={open} onClick={() => setOpen(o => !o)}>
        🔔{s.unread > 0 && <span className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] px-1 rounded-full bg-saffron text-white text-[10px] font-extrabold flex items-center justify-center">{s.unread > 99 ? '99+' : s.unread}</span>}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 max-w-[90vw] bg-white text-ink rounded-2xl shadow-2xl border border-line z-50 overflow-hidden" role="dialog" aria-label={t('notifications')}>
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-line"><b className="text-navy">{t('notifications')}</b>{s.unread > 0 && <button className="text-xs underline text-teal font-semibold" onClick={readAll}>{t('mark_all_read')}</button>}</div>
          <div className="max-h-96 overflow-auto">
            {items === null && <div className="p-4 text-sm text-muted">…</div>}
            {items?.length === 0 && <div className="p-4 text-sm text-muted">{t('no_notifications')}</div>}
            {items?.map(n => (
              <button key={n.id} onClick={() => go(n)} className={`w-full text-left px-4 py-2.5 border-b border-line last:border-0 hover:bg-paper ${n.read ? '' : 'bg-saffron-soft/60'}`}>
                <div className={`text-sm ${n.read ? '' : 'font-bold'}`}>{t('notif.' + n.kind, n.params)}</div>
                <div className="text-[11px] text-muted">{n.at.replace('T', ' ').slice(0, 16)}</div>
              </button>))}
          </div>
        </div>)}
    </div>
  )
}
