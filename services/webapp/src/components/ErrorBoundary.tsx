import { Component, type ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { hasError: boolean }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="mx-auto max-w-2xl rounded-2xl border border-rose-900/60 bg-slate-950/95 p-6 text-slate-100 shadow-[0_0_40px_rgba(244,63,94,0.12)]">
          <p className="text-xs uppercase tracking-[0.35em] text-rose-400">BETMAN_DATA</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">We lost this panel.</h2>
          <p className="mt-2 text-sm text-slate-300">
            A render error interrupted the current view. Refresh the page or switch back to Demo mode to keep exploring.
          </p>
        </div>
      )
    }

    return this.props.children
  }
}
