import { createContext, useContext } from 'react'
import type { Reviewer } from '../api/types'

export interface CorporateSession {
  subject_id: string
  reviewer: Reviewer
  capabilities: string[]
  logout: () => void
}

export const SessionContext = createContext<CorporateSession | null>(null)
export function useCorporateSession() { return useContext(SessionContext) }
export function useCapability(capability: string) {
  const session = useCorporateSession()
  return !session || session.capabilities.includes(capability)
}
