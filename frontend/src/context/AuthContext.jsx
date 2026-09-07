import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { endpoints, TOKEN_KEY } from '../services/api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // Restore the session on refresh by validating the stored token server side.
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) { setLoading(false); return }
    endpoints.me()
      .then((me) => setUser(me))
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (username, password) => {
    const data = await endpoints.login(username, password)
    localStorage.setItem(TOKEN_KEY, data.access_token)
    const me = { username: data.username, role: data.role, student_id: data.student_id }
    setUser(me)
    return me
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
