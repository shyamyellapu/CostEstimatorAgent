import { useContext } from 'react'
import { AuthContext } from '../auth/AuthProvider'
import type { AuthContextValue } from '../auth/AuthProvider'

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
