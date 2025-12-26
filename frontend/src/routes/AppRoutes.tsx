import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuthTokens } from '../auth/useAuthTokens'
import LibraryPage from '../features/library/pages/LibraryPage'
import ImportHub from '../pages/add/ImportHub'
import SearchWizard from '../pages/add/SearchWizard'
import SpotifyImport from '../pages/add/SpotifyImport'
import NFOImport from '../pages/add/NFOImport'
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
        path="/add"
        element={
          <RequireAuth>
            <ImportHub />
          </RequireAuth>
        }
      />

      <Route
        path="/add/search"
        element={
          <RequireAuth>
            <SearchWizard />
          </RequireAuth>
        }
      />

      <Route
        path="/add/spotify"
        element={
          <RequireAuth>
            <SpotifyImport />
          </RequireAuth>
        }
      />

      <Route
        path="/add/nfo"
        element={
          <RequireAuth>
            <NFOImport />
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
