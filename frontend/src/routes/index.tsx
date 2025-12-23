import { createBrowserRouter, Navigate } from 'react-router-dom';
import App from '@/App';
import { ProtectedRoute } from '@/features/auth/components/ProtectedRoute';
import { AppShell } from '@/components/layout/AppShell';
import LoginPage from '@/features/auth/pages/LoginPage';
import LibraryPage from '@/features/library/pages/LibraryPage';
import VideoDetailPage from '@/features/library/pages/VideoDetailPage';
import ImportPage from '@/features/import/pages/ImportPage';

// Placeholder pages (to be built)
const PlayerPage = () => <div className="p-8"><h1 className="font-display text-3xl uppercase text-player">Video Player - Coming Soon</h1></div>;
const ManagePage = () => <div className="p-8"><h1 className="font-display text-3xl uppercase text-manage">Library Management - Coming Soon</h1></div>;
const SystemPage = () => <div className="p-8"><h1 className="font-display text-3xl uppercase text-system">System Settings - Coming Soon</h1></div>;

/**
 * Fuzzbin Application Routes
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        path: 'login',
        element: <LoginPage />,
      },
      {
        path: '/',
        element: (
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        ),
        children: [
          {
            index: true,
            element: <Navigate to="/library" replace />,
          },
          {
            path: 'library',
            element: <LibraryPage />,
          },
          {
            path: 'library/videos/:id',
            element: <VideoDetailPage />,
          },
          {
            path: 'import',
            element: <ImportPage />,
          },
          {
            path: 'player',
            element: <PlayerPage />,
          },
          {
            path: 'manage',
            element: <ManagePage />,
          },
          {
            path: 'system',
            element: <SystemPage />,
          },
        ],
      },
      // Catch all - redirect to library
      {
        path: '*',
        element: <Navigate to="/library" replace />,
      },
    ],
  },
]);
