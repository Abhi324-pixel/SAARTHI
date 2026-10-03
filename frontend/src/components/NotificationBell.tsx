import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
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
      <button
        className="relative btn btn-sm p-2 rounded-xl flex items-center justify-center border border-white/10 hover:border-white/20 transition-all cursor-pointer"
        style={{ background: 'rgba(255,255,255,.12)', color: '#fff' }}
        aria-label={`${t('notifications')}${s.unread ? `, ${s.unread} unread` : ''}`}
        aria-expanded={open}
        onClick={() => setOpen(o => !o)}
      >
        <Bell className="w-4 h-4 text-amber-400" />
        {s.unread > 0 && (
          <span className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] px-1 rounded-full bg-[var(--accent-orange)] text-white text-[10px] font-extrabold flex items-center justify-center shadow-[0_2px_8px_rgba(255,138,36,0.6)]">
            {s.unread > 99 ? '99+' : s.unread}
          </span>
        )}
      </button>
      {open && (
        <div
          className="absolute right-0 mt-2.5 w-84 max-w-[90vw] bg-[rgba(10,18,28,0.96)] backdrop-blur-2xl text-white rounded-2xl shadow-[0_16px_40px_rgba(0,0,0,0.6)] border border-[rgba(210,225,235,0.18)] z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-150"
          role="dialog"
          aria-label={t('notifications')}
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-[rgba(210,225,235,0.12)] bg-[rgba(14,24,36,0.7)]">
            <b className="text-white text-sm font-extrabold tracking-tight heading-glow">
              {t('notifications')}
            </b>
            {s.unread > 0 && (
              <button
                className="text-xs underline text-[#4D9DFF] hover:text-[#7ab8ff] font-semibold transition-colors cursor-pointer"
                onClick={readAll}
              >
                {t('mark_all_read')}
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-auto divide-y divide-[rgba(210,225,235,0.08)]">
            {items === null && (
              <div className="p-4 text-sm text-slate-400 text-center">…</div>
            )}
            {items?.length === 0 && (
              <div className="p-4 text-sm text-slate-400 text-center">{t('no_notifications')}</div>
            )}
            {items?.map(n => (
              <button
                key={n.id}
                onClick={() => go(n)}
                className={`w-full text-left px-4 py-3 transition-colors cursor-pointer ${
                  n.read
                    ? 'hover:bg-white/[0.05]'
                    : 'bg-[rgba(255,138,36,0.12)] hover:bg-[rgba(255,138,36,0.18)] border-l-2 border-l-[#FF8A24]'
                }`}
              >
                <div className={`text-sm leading-snug ${n.read ? 'text-slate-300 font-medium' : 'text-white font-bold'}`}>
                  {t('notif.' + n.kind, n.params)}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  {n.at.replace('T', ' ').slice(0, 16)}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

