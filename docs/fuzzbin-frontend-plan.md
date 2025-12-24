# Fuzzbin Browser UI Implementation Plan

## Overview

Build a modern, browser-based control plane for Fuzzbin music video library management using React + TypeScript + Vite with a Neo-MTV Maximalism design aesthetic. The UI provides a complete end-to-end pipeline for video library import, curation, download, search, and management.

**Design Philosophy:** Color-coded "channels" (Library=Cyan, Import=Magenta, Player=Yellow, Manage=Green, System=Purple) with chunky geometric components, bold animations, and music-first design inspired by MTV's heyday.

## Technology Stack

**Core:**
- React 18 + TypeScript + Vite
- Monorepo structure: `/frontend` folder in existing repo

**State Management:**
- React Query (server state: caching, pagination, refetching)
- Zustand (client state: auth, UI, player, preferences)

**Key Libraries:**
- React Router v6 (routing with lazy loading)
- Axios (HTTP client with JWT interceptors)
- Framer Motion (spring physics animations)
- React Hook Form + Zod (type-safe form validation)
- Video.js (HTML5 player with HTTP range support)
- React Window (virtual scrolling for large lists)

**API Integration:**
- Type generation from OpenAPI spec using `openapi-typescript`
- Custom WebSocket manager with reconnection logic
- JWT authentication with automatic token refresh

## Project Structure

```
/Users/jbruns/src/Fuzzbin/frontend/
├── package.json                    # Dependencies & scripts
├── vite.config.ts                  # Build config with proxy to :8000
├── tsconfig.json                   # TypeScript configuration
├── .env.development                # API_BASE_URL, WS_BASE_URL
│
├── public/
│   └── fonts/                      # Barlow Condensed, Outfit, Barlow
│
└── src/
    ├── main.tsx                    # App entry point with providers
    ├── App.tsx                     # Root component
    │
    ├── styles/                     # Global CSS + design tokens
    │   ├── variables.css           # Channel colors, spacing, shadows
    │   └── animations.css          # Keyframe animations
    │
    ├── lib/
    │   ├── api/
    │   │   ├── client.ts           # Axios instance with JWT interceptors
    │   │   ├── types.ts            # Generated from OpenAPI spec
    │   │   ├── endpoints/          # API functions (videos, artists, etc.)
    │   │   └── queryKeys.ts        # React Query key factory
    │   │
    │   ├── ws/
    │   │   ├── manager.ts          # WebSocket connection manager
    │   │   └── hooks.ts            # useWebSocketEvent, useJobProgress
    │   │
    │   └── utils/
    │       ├── formatting.ts       # Date, duration, file size
    │       └── storage.ts          # Encrypted localStorage wrapper
    │
    ├── stores/                     # Zustand stores
    │   ├── authStore.ts            # Tokens, user, isAuthenticated
    │   ├── uiStore.ts              # Sidebar, modals, view mode
    │   └── playerStore.ts          # Current video, playlist, playback state
    │
    ├── components/
    │   ├── layout/                 # AppShell, Sidebar, Header
    │   ├── ui/                     # Button, Input, Card, Modal, Progress
    │   ├── video/                  # VideoCard, VideoGrid, VideoPlayer
    │   ├── filters/                # FilterBar, TagFilter, SortControls
    │   └── search/                 # SearchBar, SearchSuggestions
    │
    ├── features/                   # Feature modules
    │   ├── auth/                   # Login, ProtectedRoute
    │   ├── library/                # Video browsing (Cyan channel)
    │   ├── player/                 # Video playback (Yellow channel)
    │   ├── import/                 # YouTube import (Magenta channel)
    │   ├── manage/                 # Collections/Artists/Tags (Green)
    │   └── system/                 # Config/Backup/Jobs (Purple)
    │
    ├── routes/
    │   └── index.tsx               # Route definitions with lazy loading
    │
    └── config/
        └── channels.ts             # Channel definitions (colors, icons)
```

## Key Implementation Decisions

### 1. Deployment Strategy
**Option A: Separate Deployment (Recommended)**
- Frontend: Vite dev server on port 3000
- Backend: FastAPI on port 8000 (unchanged)
- Vite proxy routes API requests during development
- CORS already configured in FastAPI
- Production: Serve frontend from CDN/Nginx, reverse proxy to backend

**Why:** Clean separation, better DX with HMR, independent scaling

### 2. Type Safety
- Generate TypeScript types from OpenAPI spec using `openapi-typescript`
- Run `npm run generate-types` after backend changes
- Type-safe API calls with auto-complete and validation

### 3. WebSocket Architecture
- Global event bus WebSocket: `/ws/events` (config changes, system events)
- Job-specific WebSocket: `/ws/jobs/{job_id}` (download progress)
- Custom manager with exponential backoff reconnection
- First-message authentication protocol
- React hooks for easy integration

### 4. State Management Philosophy
- **Server State (React Query):** Videos, artists, collections, tags, jobs
  - 5-minute stale time, automatic caching
  - Optimistic updates with rollback
  - Pagination and infinite scroll support
- **Client State (Zustand):** Auth tokens, UI state, player state, preferences
  - Persisted to encrypted localStorage (auth)
  - Ephemeral (UI state)

### 5. Performance Optimizations
- Route-based code splitting with `React.lazy()`
- Vendor chunking (react, query, ui, video)
- Virtual scrolling for large video lists
- Thumbnail lazy loading with Intersection Observer
- Debounced search (300ms)
- React Query caching strategy

## Design System Reference

Detailed design system created at:
- **Design Tokens:** `/Users/jbruns/.claude/plans/fuzzbin-design-system.md`
- **Component Examples:** `/Users/jbruns/.claude/plans/fuzzbin-component-examples.tsx`

**Key Elements:**
- Channel colors with signature glows
- Barlow Condensed (display), Outfit (body), Barlow (UI) fonts
- Chunky geometric shapes with deep shadows
- Spring physics animations via Framer Motion
- Gradient mesh backgrounds
- Sticker-style badges with rotation

## Critical Files to Create First

### Phase 1: Foundation
1. **`package.json`** - Complete dependencies list (React, TypeScript, Vite, Tailwind, React Query, Zustand, Axios, Framer Motion, Video.js)
2. **`vite.config.ts`** - Proxy to localhost:8000, path aliases, build optimization
3. **`tsconfig.json`** - Strict TypeScript config with path mapping
4. **`src/main.tsx`** - App entry with QueryClientProvider, RouterProvider, Toaster
5. **`src/styles/variables.css`** - Neo-MTV design tokens (channel colors, spacing, shadows)

### Phase 2: API Integration
6. **`src/lib/api/client.ts`** - Axios instance with JWT interceptors and token refresh logic
7. **`src/lib/api/queryKeys.ts`** - React Query key factory for cache management
8. **`src/lib/api/endpoints/videos.ts`** - Videos API functions (list, get, create, update, delete, stream)
9. **`src/lib/ws/manager.ts`** - WebSocket connection manager with reconnection
10. **`src/lib/ws/hooks.ts`** - `useWebSocketEvent`, `useJobProgress` hooks

### Phase 3: Auth & Routing
11. **`src/stores/authStore.ts`** - Zustand store for tokens and user state (persisted, encrypted)
12. **`src/features/auth/pages/LoginPage.tsx`** - Login page with branding
13. **`src/features/auth/components/LoginForm.tsx`** - React Hook Form + Zod validation
14. **`src/routes/index.tsx`** - Route definitions with lazy loading and protected routes
15. **`src/components/layout/AppShell.tsx`** - Main layout with sidebar and header

### Phase 4: Core Features
16. **`src/components/ui/Button.tsx`** - Chunky button with channel color variants
17. **`src/components/video/VideoCard.tsx`** - Video card with thumbnail, metadata, hover effects
18. **`src/features/library/pages/LibraryPage.tsx`** - Main video library with grid/filters
19. **`src/features/library/hooks/useVideos.ts`** - React Query hook for videos with filters
20. **`src/features/import/pages/ImportPage.tsx`** - YouTube search and download queue

## Feature Breakdown

### Authentication (All Pages Protected)
**Flow:**
1. Login with username/password → POST `/auth/login`
2. Receive `access_token` (30min) + `refresh_token` (24h)
3. Store in encrypted localStorage via authStore
4. Axios interceptor adds Bearer token to all requests
5. On 401, auto-refresh token via `/auth/refresh`
6. Logout: POST `/auth/logout`, clear tokens, redirect

**Files:**
- `features/auth/pages/LoginPage.tsx`
- `features/auth/components/LoginForm.tsx`
- `features/auth/hooks/useLogin.ts`
- `routes/ProtectedRoutes.tsx`

---

### Video Library (Cyan Channel) `/library`
**Features:**
- Grid/list view toggle
- Search with autocomplete suggestions (GET `/search/suggestions`)
- Filters: tags, artists, collections, status, year range
- Sort: title, artist, year, created_at (asc/desc)
- Pagination or infinite scroll
- Click video → detail page

**Components:**
- `VideoGrid.tsx` - Responsive CSS grid (auto-fill minmax)
- `VideoCard.tsx` - Thumbnail, title, artist, tags, duration, status
- `FilterBar.tsx` - All filter controls
- `SortControls.tsx` - Sort dropdown + order toggle
- `SearchBar.tsx` - Input with debounced search + suggestions

**API:**
- GET `/videos` with query params (page, page_size, tags, artist_id, status, sort_by, order)
- GET `/search` for full-text search
- GET `/search/suggestions` for autocomplete

---

### Video Detail & Player (Yellow Channel) `/library/videos/:id`
**Features:**
- Video player with HTTP range support for seeking
- Tabbed metadata panel (Details, Tags, Artists, Collections, History)
- Edit metadata inline
- Add/remove tags with autocomplete
- Manage artist associations (primary/featured)
- View status history timeline
- Play button → fullscreen player mode

**Components:**
- `VideoPlayer.tsx` - Video.js wrapper with custom controls
- `VideoMetadata.tsx` - Tabbed panel
- `TagEditor.tsx` - Tag chips with add/remove
- `StatusTimeline.tsx` - Vertical timeline of status changes

**API:**
- GET `/videos/{id}` - Video details
- GET `/videos/{id}/stream` - Video file stream (Range support)
- PATCH `/videos/{id}` - Update metadata
- GET `/videos/{id}/status-history` - Status timeline
- POST/DELETE `/videos/{id}/tags/{tag_id}` - Tag management

---

### IMVDb add to library (Magenta Channel) `/add`
**Features:**
- Search IMVDb by artist + track title
- Get YouTube metadata for sources
- Preview results with thumbnails, metadata
- Download button starts background job
- Real-time progress via WebSocket
- Download queue shows all active downloads
- Success → invalidate videos query, show toast

**Components:**
- `YouTubeSearchForm.tsx` - Artist + track input
- `YouTubeResultCard.tsx` - Search result with import button
- `DownloadQueue.tsx` - List of active downloads
- `ImportProgress.tsx` - Progress bar with WebSocket updates

**API:**
- GET `/ytdlp/search?artist=X&track_title=Y` - Search results
- POST `/ytdlp/download` - Start download → returns `job_id`
- WebSocket `/ws/jobs/{job_id}` - Real-time progress
- DELETE `/ytdlp/download/{job_id}` - Cancel download

**WebSocket Flow:**
1. POST `/ytdlp/download` → `{ job_id: "xyz" }`
2. `useJobProgress("xyz")` hook connects WebSocket
3. Receive `job_progress` events with percentage, speed, ETA
4. Update progress bar in real-time
5. On `job_completed`, show success toast, refetch videos

---

### Library Management (Green Channel) `/manage`

#### Collections `/manage/collections`
- List all collections
- Create, edit, delete collections
- Add videos to collections
- Drag-drop to reorder videos in collection
- View collection as playlist

**API:**
- GET/POST/PATCH/DELETE `/collections`
- GET `/collections/{id}/videos` - Videos in collection
- POST/DELETE `/collections/{id}/videos/{video_id}` - Add/remove video

#### Artists `/manage/artists`
- Artist directory with pagination
- Create, edit, soft-delete artists
- View all videos by artist
- Link/unlink videos to artists with role (primary/featured)

**API:**
- GET/POST/PATCH/DELETE `/artists`
- GET `/artists/{id}/videos` - Artist's videos
- POST/DELETE `/artists/{id}/videos/{video_id}` - Link/unlink

#### Tags `/manage/tags`
- Tag cloud sized by usage count
- Create, rename, delete tags
- View all videos with tag
- Bulk tag operations

**API:**
- GET/POST/DELETE `/tags`
- GET `/tags/{id}/videos` - Videos with tag
- POST `/tags/videos/{video_id}/set` - Replace all tags
- POST `/tags/videos/{video_id}/add` - Add tags

#### Bulk Operations
- Multi-select videos with checkboxes
- Actions: Update metadata, Apply tags, Change status, Move to collection, Delete
- Progress tracking for large batches

**API:**
- POST `/videos/bulk/update` - Bulk metadata update
- POST `/videos/bulk/tags` - Bulk tag application
- POST `/videos/bulk/status` - Bulk status change
- POST `/videos/bulk/delete` - Bulk delete

---

### System/Admin (Purple Channel) `/system`

#### Dashboard `/system/dashboard`
- Health status (API version, auth enabled, database OK)
- Job metrics (success rate, avg duration, queue depth)
- Recent activity feed

**API:**
- GET `/health` - System health
- GET `/jobs/metrics` - Job statistics

#### Configuration `/system/config`
- Runtime config editor (nested JSON)
- Dot-notation path editing (e.g., `http.timeout`)
- Safety level warnings (safe, requires_reload, affects_state)
- Undo/redo history
- WebSocket notifications for changes

**API:**
- GET `/config` - Current config
- PATCH `/config` - Update fields
- GET `/config/field/{path}` - Get specific field
- GET/POST `/config/undo` `/config/redo` - History navigation
- WebSocket `/ws/events` - Listen for `config_changed` events

#### Backup `/system/backup`
- List all backups with metadata
- Create on-demand backup (background job)
- Download backup archive
- Verify backup integrity

**API:**
- GET `/backup` - List backups
- POST `/backup` - Create backup → `job_id`
- GET `/backup/{filename}` - Download archive
- GET `/backup/{filename}/verify` - Verify integrity

#### Jobs `/system/jobs`
- Job queue monitoring
- Filter by type, status
- View job details and progress
- Cancel running jobs
- Real-time updates via WebSocket

**API:**
- GET `/jobs` - List all jobs
- GET `/jobs/{id}` - Job details
- DELETE `/jobs/{id}` - Cancel job
- WebSocket `/ws/events` - Job progress broadcasts

---

## Implementation Phases (8 Weeks)

### Week 1: Foundation
- Initialize project, install dependencies
- Configure Vite, TypeScript, Tailwind
- Set up folder structure
- Create global styles with Neo-MTV tokens
- Build design system primitives (Button, Input, Card, Modal)
- Create API client with interceptors
- Build auth store and login flow
- Create app shell layout

**Deliverable:** Login → protected dashboard → logout

### Week 2: Video Library
- Generate API types from OpenAPI spec
- Set up React Query
- Create videos API functions and hooks
- Build VideoCard and VideoGrid
- Create LibraryPage with filters
- Implement search, sort, pagination
- Add loading states and empty states

**Deliverable:** Browsable video library with filtering

### Week 3: Video Player
- Create VideoDetailPage
- Integrate Video.js for playback
- Configure HTTP range requests
- Build metadata panel with tabs
- Create tag and artist editors
- Add status timeline
- Implement player controls

**Deliverable:** Working video detail and playback

### Week 4: YouTube Import
- Build ImportPage layout
- Create YouTube search form
- Implement search results display
- Set up WebSocket manager
- Create job progress hook
- Build download queue with real-time progress
- Add error handling and success notifications

**Deliverable:** YouTube import with live progress

### Week 5: Library Management
- Build CollectionsPage with CRUD
- Create ArtistsPage
- Build TagsPage with tag cloud
- Implement drag-drop for collections
- Create bulk operations modal
- Add progress tracking for bulk ops

**Deliverable:** Complete management interface

### Week 6: System/Admin
- Build ConfigPage with editor
- Add safety warnings and undo/redo
- Create BackupPage
- Build JobsPage with monitoring
- Create DashboardPage
- Integrate WebSocket for real-time updates

**Deliverable:** Full admin interface

### Week 7: Polish & Optimization
- Add Framer Motion animations
- Implement Neo-MTV visual effects
- Add virtual scrolling for large lists
- Optimize image loading
- Make responsive for mobile
- Add toast notifications
- Create error boundaries
- Optimize bundle size

**Deliverable:** Polished, performant UI

### Week 8: Testing & Documentation
- Write unit tests for utilities
- Write component tests
- Set up E2E tests
- Create user guide
- Write developer documentation
- Fix bugs
- Performance profiling

**Deliverable:** Production-ready application

---

## Development Workflow

### Local Development

**Terminal 1 - Backend:**
```bash
cd /Users/jbruns/src/Fuzzbin
source .venv/bin/activate
fuzzbin-api
# → http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
cd /Users/jbruns/src/Fuzzbin/frontend
npm install
npm run dev
# → http://localhost:3000
# Proxies /api → localhost:8000
```

**Terminal 3 - Type Generation (once):**
```bash
cd /Users/jbruns/src/Fuzzbin/frontend
npm run generate-types
# Generates src/lib/api/types.ts from OpenAPI
```

### Key Commands

```bash
npm run dev              # Start dev server on :3000
npm run build            # Production build to dist/
npm run preview          # Preview production build
npm run lint             # ESLint check
npm run format           # Prettier format
npm run type-check       # TypeScript type checking
npm run generate-types   # Generate types from OpenAPI
npm run test             # Run Vitest tests
```

---

## Vite Configuration Highlights

**Proxy Setup (Dev):**
```typescript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
    '/ws': {
      target: 'ws://localhost:8000',
      ws: true,
    },
  },
}
```

**Build Optimization:**
```typescript
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        'react-vendor': ['react', 'react-dom', 'react-router-dom'],
        'query-vendor': ['@tanstack/react-query'],
        'ui-vendor': ['framer-motion'],
        'video-vendor': ['video.js', 'react-player'],
      },
    },
  },
}
```

---

## Data Flow Patterns

### Query → Display
```
User visits /library
  ↓
useVideos() hook executes
  ↓
React Query: cache check → fetch if stale
  ↓
Render VideoGrid with data
```

### Mutation → Invalidation
```
User deletes video
  ↓
useDeleteVideo() mutation
  ↓
API DELETE /videos/{id}
  ↓
onSuccess: invalidate videos query
  ↓
Auto-refetch → UI updates
```

### WebSocket → Real-time
```
User starts download
  ↓
POST /ytdlp/download → job_id
  ↓
useJobProgress(job_id)
  ↓
WebSocket connects to /ws/jobs/{job_id}
  ↓
Progress events → update state
  ↓
Progress bar re-renders
```

---

## FastAPI Modifications (Optional)

**If serving built frontend from FastAPI:**

Modify `/Users/jbruns/src/Fuzzbin/fuzzbin/web/main.py` after line 398:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_build_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"

if frontend_build_dir.exists():
    app.mount("/assets", StaticFiles(directory=frontend_build_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index_path = frontend_build_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        raise HTTPException(status_code=404)
```

**Recommended:** Keep separate deployment for cleaner architecture.

---

## Success Criteria

✅ **Authentication:** Secure JWT-based auth with auto-refresh
✅ **Video Library:** Fast, filterable browsing with search
✅ **Video Playback:** Smooth streaming with seeking support
✅ **YouTube Import:** Search and download with live progress
✅ **Library Management:** Full CRUD for collections/artists/tags
✅ **Bulk Operations:** Multi-select with progress tracking
✅ **Real-time Updates:** WebSocket integration for jobs/config
✅ **Admin Tools:** Config editor, backup manager, job monitoring
✅ **Performance:** <3s load time, <100ms interactions, virtual scrolling
✅ **Design:** Bold Neo-MTV aesthetic throughout
✅ **Responsive:** Works on desktop, tablet, mobile
✅ **Type Safety:** Full TypeScript coverage, API types generated
✅ **Testing:** Unit, component, E2E tests

---

## Next Steps

1. **Initialize project:**
   ```bash
   cd /Users/jbruns/src/Fuzzbin
   npm create vite@latest frontend -- --template react-ts
   cd frontend
   ```

2. **Install dependencies** from package.json template

3. **Configure Vite** with proxy to backend

4. **Create folder structure** as outlined

5. **Copy design tokens** from `/Users/jbruns/.claude/plans/fuzzbin-design-system.md` to `src/styles/variables.css`

6. **Build core infrastructure:**
   - API client with interceptors
   - Auth store
   - WebSocket manager
   - Route definitions

7. **Start with Phase 1** (Foundation) and progress through phases

8. **Reference component examples** in `/Users/jbruns/.claude/plans/fuzzbin-component-examples.tsx` for implementation patterns

---

## Additional Resources

- **Design System Spec:** `/Users/jbruns/.claude/plans/fuzzbin-design-system.md`
- **Component Examples:** `/Users/jbruns/.claude/plans/fuzzbin-component-examples.tsx`
- **Backend API Docs:** `/Users/jbruns/src/Fuzzbin/docs/openapi-spec.md`
- **WebSocket Spec:** `/Users/jbruns/src/Fuzzbin/docs/websocket-spec.md`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json` (when backend running)

Ready to build! 🎸📺
