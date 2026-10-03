import { Component, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

export default class ErrorBoundary extends Component<{ children: ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null }
  static getDerivedStateFromError(err: Error) { return { err } }
  componentDidCatch(err: Error) { console.error('UI error', err) }
  render() {
    if (!this.state.err) return this.props.children
    return (
      <div className="min-h-full flex items-center justify-center p-6">
        <div className="card p-8 max-w-md text-center space-y-4 shadow-[0_16px_48px_rgba(0,0,0,0.5)]">
          <div className="w-12 h-12 rounded-2xl bg-[rgba(255,83,100,0.15)] border border-[rgba(255,83,100,0.3)] flex items-center justify-center text-[#FF5364] mx-auto shadow-[0_0_20px_rgba(255,83,100,0.2)]">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-extrabold text-[var(--text-primary)] heading-glow">Something interrupted this view</h1>
          <p className="desc-glow text-sm text-[var(--text-secondary)] leading-relaxed">
            Your learning progression and genome remain safely stored on the server. Reload to resume your session.
          </p>
          <div className="pt-2">
            <button
              className="btn btn-orange py-2.5 px-6 text-sm font-semibold flex items-center gap-2 mx-auto"
              onClick={() => { this.setState({ err: null }); window.location.reload() }}
            >
              <RotateCcw className="w-4 h-4" />
              Reload View
            </button>
          </div>
        </div>
      </div>
    )
  }
}

