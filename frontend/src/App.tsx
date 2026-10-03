import { useState } from 'react'
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useNotifications } from './hooks/useNotifications'
import { useApp } from './store'
import AutoTranslate from './components/AutoTranslate'
import NotificationBell from './components/NotificationBell'
import StuckModal from './components/StuckModal'
import VoiceDrawer from './components/VoiceDrawer'
import ChatDrawer from './components/ChatDrawer'
import { DemoBadge, Spinner } from './components/ui'
import {
  LogOut,
  Mic,
  MessageSquare,
  HelpCircle,
  User,
  Menu,
  X,
  LayoutDashboard,
  BookOpen,
  Code2,
  Compass,
  Briefcase,
  Dna,
  Users,
  GraduationCap,
  ShieldCheck,
  Settings,
} from 'lucide-react'
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
import SettingsPage from './pages/Settings'
import Reviews from './pages/Reviews'
import Profile from './pages/Profile'

function Shell({ children }: { children: React.ReactNode }) {
  const { me, health, t, openStuck, logout, roadmapNote, setRoadmapNote, voice, openVoice, closeVoice, chatOpen, openChat, closeChat } = useApp()
  const loc = useLocation()
  const notif = useNotifications()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const nb = (to: string) =>
    (to === '/mentors' || to === '/mentor-console') && notif.messages_unread > 0 ? (
      <span
        className="ml-auto inline-flex min-w-[18px] h-[18px] px-1 rounded-full bg-saffron text-white text-[10px] font-extrabold items-center justify-center shadow-[0_0_8px_rgba(255,138,36,0.5)]"
        aria-label={`${notif.messages_unread} unread`}
      >
        {notif.messages_unread}
      </span>
    ) : null

  const navFeatures = [
    { to: '/', label: t('dashboard'), icon: LayoutDashboard },
    { to: '/placement', label: t('learn'), icon: BookOpen },
    { to: '/practice', label: t('practice'), icon: Code2 },
    { to: '/roadmap', label: t('roadmap'), icon: Compass },
    { to: '/interview', label: t('interview'), icon: Briefcase },
    { to: '/genome', label: t('genome'), icon: Dna },
    { to: '/mentors', label: t('mentors'), icon: Users },
    { to: '/teacher', label: t('teacher'), icon: GraduationCap },
    ...(me?.is_mentor ? [{ to: '/mentor-console', label: 'Mentor console', icon: ShieldCheck }] : []),
    ...(me?.is_admin ? [{ to: '/admin', label: 'Admin', icon: Settings }] : []),
  ]

  return (
    <div className="min-h-full flex flex-col">
      {health?.test_llm && (
        <div className="bg-lvl-unknown text-white text-center text-xs font-bold py-1.5">
          TEST LLM MODE — offline keyword grader, not real grading. Never use in the demo.
        </div>
      )}


      {/* Top Navigation Bar: Brand on Left, Actions on Right */}
      <header className="nav-glass text-white sticky top-0 z-40 w-full shadow-[0_4px_24px_rgba(0,0,0,0.25)]">
        <div className="w-full px-3 sm:px-6 h-16 flex items-center justify-between gap-3">
          {/* Left: Mobile hamburger menu toggle + SAARTHI Brand */}
          <div className="flex items-center gap-3 shrink-0">
            <button
              type="button"
              className="lg:hidden p-2 rounded-xl text-slate-200 hover:text-white hover:bg-white/10 transition-colors border border-white/10"
              onClick={() => setSidebarOpen(o => !o)}
              aria-label="Toggle navigation menu"
            >
              {sidebarOpen ? <X className="w-5 h-5 text-[var(--accent-orange)]" /> : <Menu className="w-5 h-5" />}
            </button>

            <Link to="/" className="font-extrabold text-lg lg:text-xl tracking-tight flex items-center gap-2.5 group" aria-label="SAARTHI home">
              <span className="relative inline-flex h-9 w-9 rounded-xl overflow-hidden bg-black/40 backdrop-blur-md items-center justify-center border border-[rgba(255,138,36,0.35)] shadow-sm group-hover:border-[#FF8A24] group-hover:shadow-[0_0_14px_rgba(255,138,36,0.45)] transition-all">
                <img src="/logo.png" alt="SAARTHI Logo" className="w-full h-full object-cover transform group-hover:scale-110 transition-transform duration-300" />
              </span>
              <span className="tracking-wide text-white heading-glow font-extrabold hidden min-[400px]:inline">SAARTHI</span>
            </Link>
          </div>

          {/* Right Action Cluster: Notification, Ask Saarthi, Stuck?, Profile, Sign Out */}
          <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
            <NotificationBell />

            <button 
              className="btn btn-sm btn-secondary py-1.5 px-3 text-xs flex items-center gap-1.5 font-semibold" 
              onClick={() => openChat()}
              title="Ask Saarthi"
            >
              <MessageSquare className="w-3.5 h-3.5 text-[#4D9DFF]" />
              <span className="hidden sm:inline">Ask Saarthi</span>
            </button>

            <button 
              className="btn btn-sm btn-ghost py-1.5 px-2.5 text-xs flex items-center gap-1.5 border border-[rgba(210,225,235,0.14)] text-slate-200 hover:text-white" 
              onClick={() => openStuck()}
              title={t('stuck')}
            >
              <HelpCircle className="w-3.5 h-3.5 text-[#FF8A24]" />
              <span className="hidden min-[480px]:inline">{t('stuck')}</span>
            </button>

            <Link 
              to="/profile" 
              className="flex items-center gap-1.5 text-xs sm:text-sm font-semibold text-slate-200 hover:text-white px-2.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 transition-colors" 
              title="Profile"
            >
              <User className="w-3.5 h-3.5 text-[#FF8A24]" />
              <span className="hidden sm:inline max-w-[90px] truncate">{me?.name?.split(' ')[0] || 'Profile'}</span>
            </Link>

            <button 
              className="btn btn-sm btn-ghost py-1.5 px-2.5 text-xs text-rose-300 hover:text-rose-100 hover:bg-rose-500/20 hover:border-rose-500/40 border border-white/10 transition-colors flex items-center gap-1.5" 
              onClick={logout}
              title={t('signout')}
              aria-label={t('signout')}
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{t('signout')}</span>
            </button>
          </div>
        </div>
      </header>

      {/* Floating Glassmorphic Sidebar (Desktop: Fixed floating; Mobile: Off-canvas drawer) */}
      {/* Mobile Backdrop Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Floating Glassmorphic Side Bar */}
      <aside
        className={`fixed top-20 bottom-6 left-4 w-64 z-30 flex flex-col rounded-2xl border border-[rgba(210,225,235,0.16)] bg-[rgba(16,28,42,0.48)] backdrop-blur-2xl shadow-[0_16px_40px_rgba(0,0,0,0.38),inset_0_1px_0_rgba(255,255,255,0.10)] transition-all duration-300 ease-in-out ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-[calc(100%+2rem)] lg:translate-x-0'
        }`}
        aria-label="Features sidebar navigation"
      >
        {/* Floating Sidebar Header */}
        <div className="px-4 pt-3.5 pb-2.5 flex items-center justify-between border-b border-[rgba(210,225,235,0.08)]">
          <div className="text-[11px] font-bold uppercase tracking-wider text-[var(--accent-orange)] flex items-center gap-2">
            <span className="relative inline-flex h-4 w-4 rounded-md overflow-hidden border border-[rgba(255,138,36,0.35)] shadow-[0_0_6px_rgba(255,138,36,0.25)]">
              <img src="/logo.png" alt="" className="w-full h-full object-cover" />
            </span>
            <span>Platform Features</span>
          </div>
          <button
            type="button"
            className="lg:hidden p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Feature Nav Links with Glassmorphic Active states */}
        <nav className="flex-1 overflow-y-auto p-2.5 space-y-1" aria-label="Main features">
          {navFeatures.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `group flex items-center justify-between px-3 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all duration-150 border ${
                  isActive
                    ? 'bg-gradient-to-r from-[rgba(255,138,36,0.22)] to-[rgba(255,138,36,0.08)] text-white border-[rgba(255,138,36,0.42)] shadow-[0_4px_16px_rgba(255,138,36,0.18),inset_0_1px_0_rgba(255,255,255,0.12)]'
                    : 'text-[rgba(220,235,245,0.74)] border-transparent hover:text-white hover:bg-[rgba(255,255,255,0.06)] hover:border-[rgba(210,225,235,0.10)]'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Icon
                      className={`w-4 h-4 shrink-0 transition-transform group-hover:scale-110 ${
                        isActive ? 'text-[var(--accent-orange)]' : 'text-slate-400 group-hover:text-slate-200'
                      }`}
                    />
                    <span className="truncate">{label}</span>
                  </div>
                  <div className="shrink-0 flex items-center">
                    {nb(to)}
                    {isActive && (
                      <span className="ml-1 w-1.5 h-1.5 rounded-full bg-[var(--accent-orange)] shadow-[0_0_6px_var(--accent-orange)]" />
                    )}
                  </div>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Sidebar Footer Live Status */}
        <div className="p-3 border-t border-[rgba(210,225,235,0.08)] bg-[rgba(10,18,26,0.25)] rounded-b-2xl">
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#35D07F] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#35D07F]"></span>
            </span>
            <span className="font-semibold text-slate-200">Adaptive AI Twin</span>
          </div>
          <div className="text-[10px] text-[var(--text-muted)] mt-0.5 truncate">
            Real-time mastery tracking
          </div>
        </div>
      </aside>

      {/* Main Content Area with sidebar offset on desktop */}
      <div className="flex-1 lg:pl-72 flex flex-col min-w-0">
        {roadmapNote && (
          <div
            className="bg-[rgba(255,138,36,0.15)] backdrop-blur-md border-b border-[rgba(255,138,36,0.35)] text-sm px-4 py-2.5 flex items-center justify-between gap-3 pop shadow-md"
            role="status"
          >
            <span className="text-slate-100 desc-glow">
              <b className="text-[#FF8A24]">↻ Your roadmap just changed.</b> {roadmapNote}
            </span>
            <span className="flex gap-2 shrink-0">
              {loc.pathname !== '/roadmap' && (
                <Link className="btn btn-ghost btn-sm" to="/roadmap" onClick={() => setRoadmapNote(null)}>
                  See why
                </Link>
              )}
              <button className="btn btn-ghost btn-sm" onClick={() => setRoadmapNote(null)} aria-label="Dismiss">
                ✕
              </button>
            </span>
          </div>
        )}
        <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6">{children}</main>
        <footer className="text-center text-xs text-slate-400 py-6 backdrop-blur-md bg-[rgba(10,20,30,0.45)] border-t border-[rgba(210,225,235,0.12)] mt-8 shadow-lg">
          <div className="max-w-6xl mx-auto px-4 desc-glow">
            SAARTHI · adaptive AI mentor · voice by ElevenLabs ·{' '}
            {health?.adapters?.mock_areas?.length ? (
              <>
                Mock areas: {health.adapters.mock_areas.join(', ')} <DemoBadge label="demo data" />
              </>
            ) : (
              'all data is live'
            )}
            {health?.content_review?.includes('pending') && <> · Curriculum content is AI-drafted, pending expert review</>}
          </div>
        </footer>
      </div>
      {/* Floating Pulse Circle Button: Talk to Saarthi */}
      <div className="fixed bottom-5 right-5 z-40 flex items-center gap-2.5 group">
        <span className="pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 px-3 py-1 rounded-xl bg-[rgba(14,24,36,0.92)] border border-[rgba(255,138,36,0.40)] text-white text-xs font-semibold shadow-xl backdrop-blur-md desc-glow whitespace-nowrap">
          Talk to Saarthi
        </span>

        <button
          type="button"
          onClick={() => openVoice()}
          className="relative flex items-center justify-center w-12 h-12 rounded-full bg-gradient-to-tr from-[#E06D10] via-[#FF8A24] to-[#FFA045] text-white border-2 border-white/40 shadow-[0_6px_24px_rgba(255,138,36,0.45),0_0_16px_rgba(255,138,36,0.35)] hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer"
          title="Talk to Saarthi"
          aria-label="Talk to Saarthi"
        >
          {/* Continuous pulsing ping ring */}
          <span className="absolute inset-0 rounded-full bg-[#FF8A24] opacity-50 animate-ping pointer-events-none" />
          {/* Soft outer glow ring */}
          <span className="absolute -inset-1 rounded-full bg-gradient-to-r from-[#FF8A24] to-amber-300 opacity-35 blur-sm animate-pulse pointer-events-none" />

          {/* Mic Icon */}
          <Mic className="relative z-10 w-5 h-5 drop-shadow-md text-white stroke-[2.2]" />
        </button>
      </div>
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
        <Route path="/settings" element={<Guard><SettingsPage /></Guard>} />
        <Route path="/profile" element={<Guard><Profile /></Guard>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
