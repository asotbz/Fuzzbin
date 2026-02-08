import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuthTokens } from '../auth/useAuthTokens'
import LibraryPage from '../features/library/pages/LibraryPage'
import ActivityMonitorPage from '../features/activity/pages/ActivityMonitorPage'
import ActivityOutletWrapper from '../features/activity/components/ActivityOutletWrapper'
import SettingsPage from '../features/settings/pages/SettingsPage'
import SearchWizard from '../pages/add/SearchWizard'
import SpotifyImport from '../pages/add/SpotifyImport'
import ArtistImport from '../pages/add/ArtistImport'
import NFOImport from '../pages/add/NFOImport'
import LoginPage from '../pages/Login'
import OidcCallbackPage from '../pages/OidcCallback'
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
      <Route path="/oidc/callback" element={<OidcCallbackPage />} />
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
        path="/import"
        element={
          <RequireAuth>
            <SearchWizard />
          </RequireAuth>
        }
      />

      <Route
        path="/import/search"
        element={
          <RequireAuth>
            <Navigate to="/import" replace />
          </RequireAuth>
        }
      />

      <Route
        path="/import/spotify"
        element={
          <RequireAuth>
            <SpotifyImport />
          </RequireAuth>
        }
      />

      <Route
        path="/import/artist"
        element={
          <RequireAuth>
            <ArtistImport />
          </RequireAuth>
        }
      />

      <Route
        path="/import/nfo"
        element={
          <RequireAuth>
            <NFOImport />
          </RequireAuth>
        }
      />

      <Route
        path="/activity"
        element={
          <RequireAuth>
            <ActivityMonitorPage />
          </RequireAuth>
        }
      >
        <Route index element={<ActivityOutletWrapper tab="active" />} />
        <Route path="active" element={<ActivityOutletWrapper tab="active" />} />
        <Route path="history" element={<ActivityOutletWrapper tab="history" />} />
      </Route>

      <Route
        path="/settings"
        element={
          <RequireAuth>
            <SettingsPage />
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
