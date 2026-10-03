import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, tokenStore } from './api'
import { supabase } from './supabase'

type Lang = 'english' | 'hindi' | 'hinglish'

interface Ctx {
  me: any | null
  health: any | null
  ready: boolean
  refreshMe: () => Promise<void>
  logout: () => void
  toast: (msg: string, kind?: 'ok' | 'warn' | 'err') => void
  lang: Lang
  t: (k: string, params?: Record<string, string | number>) => string
  /** bump to make dashboards re-fetch after something changed */
  version: number
  bump: () => void
  /** last roadmap change, surfaced as a banner */
  roadmapNote: string | null
  setRoadmapNote: (s: string | null) => void
  openStuck: (prefill?: { text?: string; query?: string; task_id?: string; concept_id?: string }) => void
  stuckState: { open: boolean; prefill?: any }
  closeStuck: () => void
  voice: { open: boolean; mode: string; concept?: string; useResume?: boolean }
  openVoice: (mode?: string, concept?: string, opts?: { useResume?: boolean }) => void
  closeVoice: () => void
  chatOpen: boolean
  openChat: () => void
  closeChat: () => void
}

const C = createContext<Ctx>(null as unknown as Ctx)
export const useApp = () => useContext(C)

export function knownUiTexts(lang: 'hindi' | 'hinglish'): Set<string> {
  const out = new Set<string>()
  for (const v of Object.values(DICT)) if (v[lang]) out.add(v[lang])
  return out
}

const DICT: Record<string, Record<Lang, string>> = {
  dashboard: { english: 'Dashboard', hindi: 'डैशबोर्ड', hinglish: 'Dashboard' },
  learn: { english: 'Learn', hindi: 'सीखें', hinglish: 'Seekhein' },
  practice: { english: 'Practice SQL', hindi: 'SQL अभ्यास', hinglish: 'SQL Abhyaas' },
  roadmap: { english: 'Roadmap', hindi: 'रोडमैप', hinglish: 'Roadmap' },
  genome: { english: 'My Genome', hindi: 'मेरा जीनोम', hinglish: 'Mera Genome' },
  mentors: { english: 'SAKHA', hindi: 'सखा', hinglish: 'SAKHA' },
  interview: { english: 'Interview', hindi: 'इंटरव्यू', hinglish: 'Interview' },
  teacher: { english: 'Class view', hindi: 'कक्षा व्यू', hinglish: 'Class view' },
  stuck: { english: "I'm stuck", hindi: 'मैं अटक गया', hinglish: 'Main atak gaya' },
  mission: { english: "Today's mission", hindi: 'आज का मिशन', hinglish: 'Aaj ka mission' },
  talk: { english: 'Talk to SAARTHI', hindi: 'SAARTHI से बात करें', hinglish: 'SAARTHI se baat karein' },
  teachback: { english: 'Teach it back', hindi: 'समझाकर बताइए', hinglish: 'Samjhakar batayein' },
  whythis: { english: 'Why this?', hindi: 'यह क्यों?', hinglish: 'Yeh kyun?' },
  signout: { english: 'Sign out', hindi: 'साइन आउट', hinglish: 'Sign out' },
  'notifications': { english: 'Notifications', hindi: 'सूचनाएँ', hinglish: 'Suchnaayein' },
  'mark_all_read': { english: 'Mark all read', hindi: 'सब पढ़ा हुआ करें', hinglish: 'Sab padha hua karein' },
  'no_notifications': { english: 'Nothing new.', hindi: 'कुछ नया नहीं।', hinglish: 'Kuch naya nahi.' },
  'notif.case_assigned': { english: 'A new case was matched to you: {concept}', hindi: 'आपको एक नया केस मिला है: {concept}', hinglish: 'Aapko ek naya case mila hai: {concept}' },
  'notif.case_accepted': { english: '{mentor} accepted your case', hindi: '{mentor} ने आपका केस स्वीकार किया', hinglish: '{mentor} ne aapka case accept kiya' },
  'notif.case_message': { english: 'New message from {name}', hindi: '{name} का नया संदेश', hinglish: '{name} ka naya message' },
  'notif.case_outcome': { english: '{mentor} recorded the outcome of your session', hindi: '{mentor} ने आपके सत्र का नतीजा दर्ज किया', hinglish: '{mentor} ne aapke session ka nateeja darj kiya' },
  'notif.consent_granted': { english: 'Your guardian approved mentor sessions', hindi: 'आपके अभिभावक ने मेंटर सत्र की अनुमति दी', hinglish: 'Aapke guardian ne mentor sessions ki permission di' },
  'notif.consent_declined': { english: 'Your guardian did not approve mentor sessions', hindi: 'आपके अभिभावक ने मेंटर सत्र की अनुमति नहीं दी', hinglish: 'Aapke guardian ne mentor sessions ki permission nahi di' },
  'notif.consent_withdrawn': { english: 'Your guardian withdrew their approval; open cases are paused', hindi: 'आपके अभिभावक ने अनुमति वापस ली; खुले केस रुके हैं', hinglish: 'Aapke guardian ne permission wapas li; open cases ruke hain' },
  'notif.reviews_due': { english: '{n} review(s) are due', hindi: '{n} रिव्यू बाकी हैं', hinglish: '{n} review baaki hain' },
  'notif.mentor_application': { english: 'A mentor application is waiting for review', hindi: 'एक मेंटर आवेदन समीक्षा के लिए रुका है', hinglish: 'Ek mentor application review ke liye ruki hai' },
  'notif.safeguarding_report': { english: 'A safeguarding report needs attention', hindi: 'एक सुरक्षा रिपोर्ट पर ध्यान चाहिए', hinglish: 'Ek safeguarding report par dhyan chahiye' },
  'T07.chat.title': { english: 'Ask SAARTHI', hindi: 'SAARTHI से पूछें', hinglish: 'SAARTHI se poochein' },
  'T04.streak.title': { english: 'Study streak', hindi: 'अध्ययन की लय', hinglish: 'Study streak' },
  'T04.streak.goal': { english: "Today's goal", hindi: 'आज का लक्ष्य', hinglish: "Aaj ka goal" },
  'T04.streak.best': { english: 'Best', hindi: 'सर्वश्रेष्ठ', hinglish: 'Best' },
  'T04.streak.freeze': { english: 'freeze held', hindi: 'फ्रीज़ उपलब्ध', hinglish: 'freeze held' },
  'T05.phases': { english: 'Phases', hindi: 'चरण', hinglish: 'Phases' },
  'T05.checkpoints': { english: 'Personal Checkpoints', hindi: 'निजी चेकपॉइंट्स', hinglish: 'Personal Checkpoints' },
  'T05.check_me': { english: 'Check me on this phase', hindi: 'इस चरण पर मेरी जांच करें', hinglish: 'Is phase par check karo' },
  'T05.deadline': { english: 'Deadline', hindi: 'अंतिम तिथि', hinglish: 'Deadline' },
  'T05.target_date': { english: 'Target date', hindi: 'लक्षित तिथि', hinglish: 'Target date' },
  'T05.on_track': { english: 'On track', hindi: 'समय पर', hinglish: 'On track' },
  'T05.behind': { english: 'Behind schedule', hindi: 'समय से पीछे', hinglish: 'Behind schedule' },
  'T01.intake.title': { english: 'Tell SAARTHI in your own words', hindi: 'SAARTHI को अपने शब्दों में बताएं', hinglish: 'SAARTHI ko apne words mein batayein' },
  'T01.intake.understood': { english: 'What SAARTHI understood', hindi: 'SAARTHI ने क्या समझा', hinglish: 'SAARTHI ne kya samjha' },
  'T01.intake.confirm': { english: 'Looks right — Start placement →', hindi: 'बिल्कुल सही — प्लेसमेंट शुरू करें →', hinglish: 'Looks right — Placement shuru karein →' },
  'T01.intake.edit': { english: 'Edit manually below', hindi: 'नीचे खुद बदलें', hinglish: 'Neeche manually edit karein' },
  'T01.intake.fallback': { english: 'AI intake is currently offline — please use the sliders below.', hindi: 'AI इनटेक अभी उपलब्ध नहीं है — कृपया नीचे दिए गए स्लाइडर्स का उपयोग करें।', hinglish: 'AI intake offline hai — please neeche diye sliders use karein.' },
  'C06.profile.title': { english: 'Learner Profile', hindi: 'शिक्षार्थी प्रोफ़ाइल', hinglish: 'Learner Profile' },
  'C06.identity': { english: 'Identity', hindi: 'पहचान', hinglish: 'Identity' },
  'C06.activity': { english: 'Activity & Mastery', hindi: 'गतिविधि और प्रवीणता', hinglish: 'Activity aur Mastery' },
  'C06.privacy': { english: 'Privacy & Safeguarding', hindi: 'गोपनीयता और सुरक्षा', hinglish: 'Privacy aur Safeguarding' },
  'C06.save': { english: 'Save changes', hindi: 'बदलाव सहेजें', hinglish: 'Save changes' },
  'C06.saved': { english: 'Profile updated', hindi: 'प्रोफ़ाइल अपडेट हो गई', hinglish: 'Profile update ho gayi' },
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<any | null>(null)
  const [health, setHealth] = useState<any | null>(null)
  const [ready, setReady] = useState(false)
  const [version, setVersion] = useState(0)
  const [roadmapNote, setRoadmapNote] = useState<string | null>(null)
  const [toasts, setToasts] = useState<{ id: number; msg: string; kind: string }[]>([])
  const [stuckState, setStuckState] = useState<{ open: boolean; prefill?: any }>({ open: false })
  const [voice, setVoice] = useState<{ open: boolean; mode: string; concept?: string; useResume?: boolean }>({ open: false, mode: 'explain_back' })
  const [chatOpen, setChatOpen] = useState(false)
  const nid = useRef(1)

  const refreshMe = useCallback(async () => {
    if (!tokenStore.get()) { setMe(null); return }
    try { setMe(await api.me()) } catch { setMe(null) }
  }, [])

  useEffect(() => {
    (async () => {
      let h: any = { ok: false }
      try { h = await api.health(); setHealth(h) } catch { setHealth(h) }
      if (supabase && h?.adapters?.auth === 'supabase') {
        // the access token lives in localStorage['saarthi.token']; supabase-js refreshes it and we mirror every change
        const { data } = await supabase.auth.getSession()
        if (data.session) tokenStore.set(data.session.access_token); else tokenStore.clear()
        supabase.auth.onAuthStateChange((_evt, session) => {
          if (session) tokenStore.set(session.access_token)
          else { tokenStore.clear(); setMe(null) }
        })
      }
      await refreshMe()
      setReady(true)
    })()
    const off = () => setMe(null)
    window.addEventListener('saarthi:unauth', off)
    return () => window.removeEventListener('saarthi:unauth', off)
  }, [refreshMe])

  const toast = useCallback((msg: string, kind: 'ok' | 'warn' | 'err' = 'ok') => {
    const id = nid.current++
    setToasts(t => [...t, { id, msg, kind }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4200)
  }, [])

  const lang: Lang = (me?.language as Lang) || 'english'
  const t = useCallback((k: string, params?: Record<string, string | number>) => {
    let s = DICT[k]?.[lang] ?? DICT[k]?.english ?? k
    if (params) for (const [a, b] of Object.entries(params)) s = s.split('{' + a + '}').join(String(b))
    return s
  }, [lang])

  const value = useMemo<Ctx>(() => ({
    me, health, ready, refreshMe,
    logout: () => { if (supabase && health?.adapters?.auth === 'supabase') supabase.auth.signOut().catch(() => {}); tokenStore.clear(); setMe(null) },
    toast, lang, t, version, bump: () => setVersion(v => v + 1), roadmapNote, setRoadmapNote,
    openStuck: (prefill) => setStuckState({ open: true, prefill }),
    stuckState, closeStuck: () => setStuckState({ open: false }),
    voice, openVoice: (mode = 'explain_back', concept, opts) => setVoice({ open: true, mode, concept, useResume: !!opts?.useResume }), closeVoice: () => setVoice(v => ({ ...v, open: false })),
    chatOpen, openChat: () => setChatOpen(true), closeChat: () => setChatOpen(false),
  }), [me, health, ready, refreshMe, toast, lang, t, version, roadmapNote, stuckState, voice, chatOpen])

  return (
    <C.Provider value={value}>
      {children}
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 items-center" aria-live="polite">
        {toasts.map(x => (
          <div key={x.id} className={`pop rounded-xl px-4 py-2.5 text-sm font-semibold shadow-lg text-white ${x.kind === 'err' ? 'bg-lvl-unknown' : x.kind === 'warn' ? 'bg-saffron' : 'bg-navy'}`}>
            {x.msg}
          </div>
        ))}
      </div>
    </C.Provider>
  )
}
