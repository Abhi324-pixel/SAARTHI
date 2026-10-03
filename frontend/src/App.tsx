import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useNotifications } from './hooks/useNotifications'
import { useApp } from './store'
import AutoTranslate from './components/AutoTranslate'
import NotificationBell from './components/NotificationBell'
import StuckModal from './components/StuckModal'
import VoiceDrawer from './components/VoiceDrawer'
import ChatDrawer from './components/ChatDrawer'
import { DemoBadge, Spinner } from './components/ui'
import GuardianConsent from './pages/GuardianConsent'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import Placement from './pages/Placement'
import CompleteProfile from './pages/CompleteProfile'
import Admin from './pages/Admin'
import Dashboard from './pages/Dashboard'
import Learn from './pages/Learn'
import Practice from './pages/Practice'
import Roadmap from './pages/Roadmap'
import Genome from './pages/Genome'
import MentorApply from './pages/MentorApply'
import MentorConsole from './pages/MentorConsole'
import Mentors from './pages/Mentors'
import Interview from './pages/Interview'
import VideoInterview from './pages/VideoInterview'
import Teacher from './pages/Teacher'
import Settings from './pages/Settings'
import Reviews from './pages/Reviews'
import Profile from './pages/Profile'

function Shell({ children }: { children: React.ReactNode }) {
  const { me, health, t, openStuck, logout, roadmapNote, setRoadmapNote, voice, openVoice, closeVoice, chatOpen, openChat, closeChat } = useApp()
  const loc = useLocation()
  const notif = useNotifications()
  const nb = (to: string) => ((to === '/mentors' || to === '/mentor-console') && notif.messages_unread > 0
    ? <span className="ml-1.5 inline-flex min-w-[18px] h-[18px] px-1 rounded-full bg-saffron text-white text-[10px] font-extrabold items-center justify-center" aria-label={`${notif.messages_unread} unread`}>{notif.messages_unread}</span> : null)
  const nav = [
    ['/', t('dashboard')], ['/placement', t('learn')], ['/practice', t('practice')], ['/roadmap', t('roadmap')],
    ['/interview', t('interview')], ['/genome', t('genome')], ['/mentors', t('mentors')], ['/teacher', t('teacher')],
    ...(me?.is_mentor ? [['/mentor-console', 'Mentor console']] : []),
    ...(me?.is_admin ? [['/admin', 'Admin']] : []),
  ]
  return (
    <div className="min-h-full flex flex-col">
      {health?.test_llm && <div className="bg-lvl-unknown text-white text-center text-xs font-bold py-1.5">TEST LLM MODE — offline keyword grader, not real grading. Never use in the demo.</div>}
      <header className="bg-navy text-white sticky top-0 z-40 shadow">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-4">
          <Link to="/" className="font-extrabold text-lg tracking-tight flex items-center gap-2" aria-label="SAARTHI home">
            <span className="inline-flex h-8 w-8 rounded-lg bg-white/10 items-center justify-center"><svg width="20" height="20" viewBox="0 0 64 64"><path d="M18 44c8 6 24 4 24-6 0-12-22-6-22-16 0-8 14-10 22-4" fill="none" stroke="#E07A1F" strokeWidth="7" strokeLinecap="round" /></svg></span>
            SAARTHI
          </Link>
          <nav className="hidden lg:flex items-center gap-0.5 text-sm font-semibold overflow-x-auto" aria-label="Main">
            {nav.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `px-3 py-1.5 rounded-lg whitespace-nowrap ${isActive ? 'bg-white/15 text-white' : 'text-white/75 hover:bg-white/10 hover:text-white'}`}>{label}{nb(to)}</NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <NotificationBell />
            <button className="btn btn-sm btn-saffron" onClick={() => openVoice()}>🎙 <span className="hidden sm:inline">{t('talk')}</span></button>
            <button className="btn btn-sm bg-teal text-white hover:bg-teal/90" onClick={() => openChat()}>💬 <span className="hidden sm:inline">{t('T07.chat.title')}</span></button>
            <button className="btn btn-sm hidden sm:inline-flex" style={{ background: 'rgba(255,255,255,.12)', color: '#fff' }} onClick={() => openStuck()}>{t('stuck')}</button>
            <Link to="/profile" className="text-sm font-semibold text-white/85 hover:text-white hidden md:block" title="Profile">{me?.name?.split(' ')[0]}</Link>
            <button className="text-xs text-white/60 hover:text-white" onClick={logout}>{t('signout')}</button>
          </div>
        </div>
        <nav className="lg:hidden flex gap-1 overflow-x-auto px-3 pb-2 text-xs font-semibold" aria-label="Main mobile">
          {nav.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `px-2.5 py-1 rounded-lg whitespace-nowrap ${isActive ? 'bg-white/20' : 'bg-white/5 text-white/75'}`}>{label}{nb(to)}</NavLink>
          ))}
        </nav>
      </header>
      {roadmapNote && (
        <div className="bg-saffron-soft border-b border-saffron/30 text-sm px-4 py-2 flex items-center justify-between gap-3 pop" role="status">
          <span><b className="text-saffron">↻ Your roadmap just changed.</b> {roadmapNote}</span>
          <span className="flex gap-2 shrink-0">
            {loc.pathname !== '/roadmap' && <Link className="btn btn-ghost btn-sm" to="/roadmap" onClick={() => setRoadmapNote(null)}>See why</Link>}
            <button className="btn btn-ghost btn-sm" onClick={() => setRoadmapNote(null)} aria-label="Dismiss">✕</button>
          </span>
        </div>
      )}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">{children}</main>
      <footer className="text-center text-xs text-muted py-5">
        SAARTHI · adaptive AI mentor · voice by ElevenLabs · {health?.adapters?.mock_areas?.length ? <>Mock areas: {health.adapters.mock_areas.join(', ')} <DemoBadge label="demo data" /></> : 'all data is live'}
        {health?.content_review?.includes('pending') && <> · Curriculum content is AI-drafted, pending expert review</>}
      </footer>
      <button className="sm:hidden fixed bottom-4 right-4 z-40 btn btn-primary shadow-xl" onClick={() => openStuck()}>{t('stuck')}</button>
      <VoiceDrawer open={voice.open} onClose={closeVoice} initialMode={voice.mode} initialConcept={voice.concept} initialUseResume={voice.useResume} />
      <ChatDrawer open={chatOpen} onClose={closeChat} />
      <StuckModal />
    </div>
  )
}

function Guard({ children, needOnboard = true }: { children: React.ReactNode; needOnboard?: boolean }) {
  const { me, ready } = useApp()
  if (!ready) return <div className="p-10 flex justify-center"><Spinner label="Starting SAARTHI…" /></div>
  if (!me) return <Navigate to="/login" replace />
  if (me.needs_profile) return <Navigate to="/complete-profile" replace />
  if (needOnboard && !me.onboarded) return <Navigate to="/onboarding" replace />
  return <Shell>{children}</Shell>
}

export default function App() {
  const { me, ready } = useApp()
  return (
    <BrowserRouter>
      <AutoTranslate />
      <Routes>
        <Route path="/guardian/withdraw/:token" element={<GuardianConsent withdraw />} />
        <Route path="/guardian/:token" element={<GuardianConsent />} />
        <Route path="/login" element={ready && me ? <Navigate to="/" replace /> : <Login />} />
        <Route path="/complete-profile" element={ready && !me ? <Navigate to="/login" replace /> : ready && me && !me.needs_profile ? <Navigate to="/" replace /> : <CompleteProfile />} />
        <Route path="/onboarding" element={ready && !me ? <Navigate to="/login" replace /> : ready && me?.needs_profile ? <Navigate to="/complete-profile" replace /> : <Onboarding />} />
        <Route path="/" element={<Guard><Dashboard /></Guard>} />
        <Route path="/placement" element={<Guard><Placement /></Guard>} />
        <Route path="/learn/:conceptId" element={<Guard><Learn /></Guard>} />
        <Route path="/practice" element={<Guard><Practice /></Guard>} />
        <Route path="/reviews" element={<Guard><Reviews /></Guard>} />
        <Route path="/roadmap" element={<Guard><Roadmap /></Guard>} />
        <Route path="/genome" element={<Guard><Genome /></Guard>} />
        <Route path="/mentors" element={<Guard><Mentors /></Guard>} />
        <Route path="/mentors/:caseId" element={<Guard><Mentors /></Guard>} />
        <Route path="/mentor-apply" element={<Guard><MentorApply /></Guard>} />
        <Route path="/mentor-console" element={<Guard><MentorConsole /></Guard>} />
        <Route path="/mentor-console/:caseId" element={<Guard><MentorConsole /></Guard>} />
        <Route path="/admin" element={<Guard><Admin /></Guard>} />
        <Route path="/interview" element={<Guard><Interview /></Guard>} />
        <Route path="/video-interview" element={<Guard><VideoInterview /></Guard>} />
        <Route path="/teacher" element={<Guard><Teacher /></Guard>} />
        <Route path="/settings" element={<Guard><Settings /></Guard>} />
        <Route path="/profile" element={<Guard><Profile /></Guard>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
