import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuthTokens } from '../auth/useAuthTokens'
import LibraryPage from '../features/library/pages/LibraryPage'
import LoginPage from '../pages/Login'
import SetInitialPasswordPage from '../pages/SetInitialPassword'

function RequireAuth({ children }: { children: ReactNode }) {
  const tokens = useAuthTokens()
  if (!tokens.accessToken) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/set-initial-password" element={<SetInitialPasswordPage />} />

      <Route
        path="/library"
        element={
          <RequireAuth>
            <LibraryPage />
          </RequireAuth>
        }
      />

      <Route
        path="/"
        element={
          <RequireAuth>
            <Navigate to="/library" replace />
          </RequireAuth>
        }
      />

      <Route path="*" element={<Navigate to="/library" replace />} />
    </Routes>
  )
}
