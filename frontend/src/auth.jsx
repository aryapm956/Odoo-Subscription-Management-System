import { createContext, useContext, useMemo, useState } from 'react'
import { api, clearSession, getStoredUser, setSession } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => getStoredUser())

  const value = useMemo(
    () => ({
      user,
      isAdmin: user?.role === 'admin',
      isStaff: user?.role === 'admin' || user?.role === 'internal',
      isCustomer: user?.role === 'customer',
      login: async (email, password) => {
        const res = await api('/auth/login', {
          method: 'POST',
          body: { email, password },
          auth: false,
        })
        const nextUser = { id: res.user_id, name: res.name, role: res.role }
        setSession(res.access_token, nextUser)
        setUser(nextUser)
        return nextUser
      },
      signup: async (name, email, password) => {
        const res = await api('/auth/signup', {
          method: 'POST',
          body: { name, email, password },
          auth: false,
        })
        const nextUser = { id: res.user_id, name: res.name, role: res.role }
        setSession(res.access_token, nextUser)
        setUser(nextUser)
        return nextUser
      },
      logout: () => {
        clearSession()
        setUser(null)
        window.location.hash = '#/login'
      },
    }),
    [user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
