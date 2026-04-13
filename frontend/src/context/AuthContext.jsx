import { createContext, useState, useContext, useCallback } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('sm_user')
      return saved ? JSON.parse(saved) : null
    } catch { return null }
  })

  const loginUser = useCallback((userData) => {
    setUser(userData)
    localStorage.setItem('sm_user', JSON.stringify(userData))
  }, [])

  const logoutUser = useCallback(() => {
    setUser(null)
    localStorage.removeItem('sm_user')
  }, [])

  return (
    <AuthContext.Provider value={{ user, loginUser, logoutUser, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
