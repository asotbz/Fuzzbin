import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './App.css'
import { useAuthTokens } from './auth/useAuthTokens'
import HomePage from './pages/Home'
import LoginPage from './pages/Login'
import SetInitialPasswordPage from './pages/SetInitialPassword'

function RequireAuth({ children }: { children: ReactNode }) {
  const tokens = useAuthTokens()
  if (!tokens.accessToken) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/set-initial-password" element={<SetInitialPasswordPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <HomePage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
