import { Component, type ReactNode } from 'react'

export default class ErrorBoundary extends Component<{ children: ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null }
  static getDerivedStateFromError(err: Error) { return { err } }
  componentDidCatch(err: Error) { console.error('UI error', err) }
  render() {
    if (!this.state.err) return this.props.children
    return (
      <div className="min-h-full flex items-center justify-center p-6">
        <div className="card p-6 max-w-md text-center space-y-3">
          <div className="text-3xl" aria-hidden>🛟</div>
          <h1 className="text-xl font-extrabold text-navy">Something went wrong on this screen</h1>
          <p className="text-sm text-muted">Your progress is saved on the server. Reload the page; if it keeps happening, tell the team what you were doing.</p>
          <button className="btn btn-primary" onClick={() => { this.setState({ err: null }); window.location.reload() }}>Reload</button>
        </div>
      </div>
    )
  }
}
