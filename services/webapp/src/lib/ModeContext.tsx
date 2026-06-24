import { createContext, useContext, useState } from 'react'

export type Mode = 'demo' | 'live'

interface ModeContextValue {
  mode: Mode
  setMode: (mode: Mode) => void
}

const ModeContext = createContext<ModeContextValue>({ mode: 'demo', setMode: () => {} })

export function ModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<Mode>(() => {
    try {
      const stored = localStorage.getItem('betman_mode')
      return stored === 'live' ? 'live' : 'demo'
    } catch {
      return 'demo'
    }
  })

  const updateMode = (m: Mode) => {
    setMode(m)
    try {
      localStorage.setItem('betman_mode', m)
    } catch {}
  }

  return <ModeContext.Provider value={{ mode, setMode: updateMode }}>{children}</ModeContext.Provider>
}

export function useMode() {
  return useContext(ModeContext)
}
