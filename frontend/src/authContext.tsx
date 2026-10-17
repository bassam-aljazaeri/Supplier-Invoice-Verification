import { createContext, useContext, useSyncExternalStore } from 'react'
import type { BrowserSession } from './session.ts'
import { canCreate } from './authTypes.ts'

export const SessionContext = createContext<BrowserSession | null>(null)
export function useSession() {
  const session = useContext(SessionContext)
  if (!session) throw new Error('A session provider is required.')
  const state = useSyncExternalStore(session.subscribe, session.snapshot, session.snapshot)
  return { session, ...state }
}
export function useCanCreate() { return canCreate(useSession().selected?.role) }
