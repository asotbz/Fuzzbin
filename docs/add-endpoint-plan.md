# /add Endpoint Implementation Plan

## Overview

The `/add` feature is a unified **Import Hub** that supports three user scenarios for adding videos to the library. This is the **Import Channel** (Hot Magenta `#FF006E`) in the Fuzzbin design system.

### Supported Scenarios

| Scenario | User Input | Backend | Use Case |
|----------|------------|---------|----------|
| **Single Video Search** | Artist + Track Title | IMVDb → Discogs → YouTube search | Add specific music video with full metadata |
| **Spotify Playlist** | Spotify Playlist ID | Spotify API → Search each track | Bulk import from curated playlists |
| **NFO Directory Scan** | Directory Path | NFO file parser → Import existing | Migrate existing library with metadata |

### Import Flow Comparison

**Single Video:**
```
Search → Preview → Edit Metadata → Import → Download → NFO Write
```

**Spotify Playlist:**
```
Fetch Playlist → Preview Tracks → Batch Import → [Per-track: Search → Download → NFO Write]
```

**NFO Scan:**
```
Scan Directory → Preview Files → Import → [Per-file: Create DB Record → Link Video File]
```

---

## Phase 1: Backend API Endpoints

### 1.1 Unified Search Endpoint

**`POST /add/search`** - Multi-source search aggregation

```python
# Request
class AddSearchRequest(BaseModel):
    artist: str
    track_title: str
    sources: list[Literal["imvdb", "discogs", "youtube"]] = ["imvdb", "discogs", "youtube"]
    
# Response
class AddSearchResponse(BaseModel):
    imvdb_results: list[IMVDbSearchResult]
    discogs_results: list[DiscogsSearchResult]
    youtube_results: list[YouTubeSearchResult]
    cross_references: list[CrossReference]  # Links between sources
```

**Implementation Strategy:**
1. **Primary**: IMVDb `search_videos()` - Best metadata, includes YouTube source IDs
2. **Secondary**: Discogs `search()` - Album/release context, may have embedded video links
3. **Fallback**: yt-dlp `search()` - Direct YouTube search when others fail

**Cross-Reference Logic:**
- IMVDb entities have `discogs_id` field → link to Discogs artist
- IMVDb video sources include YouTube video IDs → link to YouTube results
- Discogs masters have `videos[]` with YouTube URIs → link to YouTube

### 1.2 Video Preview Endpoint

**`GET /add/preview/{source}/{source_id}`** - Detailed preview before import

| Source | Source ID | Data Fetched |
|--------|-----------|--------------|
| `imvdb` | IMVDb video ID | Full video details + credits + sources |
| `discogs` | Master ID | Master release + tracklist + images |
| `youtube` | Video ID | yt-dlp metadata (title, duration, formats) |

```python
class PreviewResponse(BaseModel):
    source: str
    source_id: str
    title: str
    artist: str
    album: Optional[str]
    year: Optional[int]
    duration: Optional[int]
    director: Optional[str]
    thumbnail_url: Optional[str]
    available_qualities: list[str]  # ["1080p", "720p", "480p"]
    youtube_id: Optional[str]       # For download
    discogs_id: Optional[int]       # For metadata enrichment
    imvdb_id: Optional[int]         # For metadata enrichment
    credits: Optional[list[Credit]] # Directors, producers, etc.
```

### 1.3 Spotify Playlist Endpoint

**`POST /add/spotify`** - Import Spotify playlist

```python
class SpotifyPlaylistRequest(BaseModel):
    playlist_id: str  # Spotify playlist ID or URL
    download_videos: bool = True
    quality_preset: str = "1080p"
    search_strategy: Literal["imvdb_first", "youtube_only"] = "imvdb_first"

class SpotifyPlaylistResponse(BaseModel):
    job_id: str
    playlist_name: str
    track_count: int
    estimated_duration_minutes: int
```

**Workflow:** Reuses existing `SpotifyPlaylistImporter` from `fuzzbin/workflows/spotify_import.py`, enhanced to:
1. Fetch playlist tracks
2. For each track: Search IMVDb/YouTube (reuse search logic)
3. Download matching videos
4. Create DB records + NFO files

### 1.4 NFO Directory Scan Endpoint

**`POST /add/nfo-scan`** - Scan NFO directory

```python
class NFOScanRequest(BaseModel):
    directory: str
    recursive: bool = True
    skip_existing: bool = True
    import_mode: Literal["discovery", "full"] = "full"
    organize_files: bool = False  # Move to library structure

class NFOScanResponse(BaseModel):
    job_id: str
    preview_count: int  # Number of NFOs found
    existing_count: int  # Already in DB
```

**Workflow:** Reuses existing `NFOImporter` from `fuzzbin/workflows/nfo_importer.py`, enhanced to:
1. Directory scan for `*.nfo` files
2. Parse each NFO
3. Create DB records
4. Optionally link to existing video files
5. Optionally organize files into library structure

### 1.5 Batch Preview Endpoint

**`POST /add/preview-batch`** - Preview batch before import

```python
class BatchPreviewRequest(BaseModel):
    mode: Literal["spotify", "nfo"]
    spotify_playlist_id: Optional[str] = None
    nfo_directory: Optional[str] = None

class BatchPreviewResponse(BaseModel):
    items: list[PreviewItem]  # What will be imported
    total_count: int
    existing_count: int  # Already in library
    new_count: int
    total_size_gb: Optional[float]  # Estimated download size
```

### 1.6 Single Video Import Endpoint

**`POST /add/import`** - Submit single video import job (returns 202 with job_id)

```python
class AddImportRequest(BaseModel):
    # Source identification
    source: Literal["imvdb", "discogs", "youtube"]
    source_id: str
    
    # Metadata (pre-populated from preview, user-editable)
    title: str
    artist: str
    album: Optional[str] = None
    year: Optional[int] = None
    director: Optional[str] = None
    genre: Optional[str] = None
    featured_artists: list[str] = []
    tags: list[str] = []
    
    # Download options
    download_video: bool = True
    format_spec: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    output_directory: Optional[str] = None  # Uses default if None
    
    # Metadata enrichment
    fetch_imvdb_metadata: bool = True
    fetch_discogs_metadata: bool = True
    write_nfo_files: bool = True
    
    # Cross-reference IDs (for enrichment)
    youtube_id: Optional[str] = None
    imvdb_id: Optional[int] = None
    discogs_master_id: Optional[int] = None

class AddImportResponse(BaseModel):
    job_id: str
    status: str  # "pending"
    estimated_steps: int
```

---

## Phase 2: Import Workflow

### 2.1 New Job Types

Add to `fuzzbin/tasks/models.py`:
```python
class JobType(str, Enum):
    # ... existing types ...
    ADD_VIDEO = "add_video"              # Single video search/import
    ADD_SPOTIFY_PLAYLIST = "add_spotify_playlist"  # Bulk Spotify import
    ADD_NFO_SCAN = "add_nfo_scan"       # Bulk NFO import
```

### 2.2 Add Video Workflow

**Location**: `fuzzbin/workflows/add_video.py`

```python
class AddVideoWorkflow:
    """
    End-to-end workflow for adding a new video to the library.
    
    Steps:
    1. Create database records (video + artist)
    2. Fetch IMVDb metadata (if enabled)
    3. Fetch Discogs metadata (if enabled)
    4. Download video file (if enabled)
    5. Generate thumbnail
    6. Write NFO files (if enabled)
    """
    
    STEPS = [
        "create_records",
        "fetch_imvdb",
        "fetch_discogs",
        "download_video",
        "generate_thumbnail",
        "write_nfo",
    ]
```

**Progress Events:**
```python
# Emitted via WebSocket at each step (unified across all import types)
{
    "event_type": "job_progress",
    "data": {
        "job_id": "uuid",
        "job_type": "add_video",  # or "add_spotify_playlist", "add_nfo_scan"
        "status": "running",
        "progress": 0.33,
        "current_step": "Fetching IMVDb metadata...",
        "processed_items": 2,
        "total_items": 6,
        "step_details": {
            "step_name": "fetch_imvdb",
            "video_title": "Blurred Lines",
            "artist": "Robin Thicke"
        },
        "batch_details": {  # For batch jobs (Spotify/NFO)
            "current_track": "Daft Punk - Get Lucky",
            "successful": 5,
            "failed": 1,
            "skipped": 1
        }
    }
}
```

### 2.3 Workflow Step Details

#### Step 1: Create Database Records
```python
async def _create_records(self) -> tuple[int, int]:
    """Create video and artist records in database."""
    async with self.repository.transaction():
        # Upsert artist (returns existing if found)
        artist_id = await self.repository.upsert_artist(
            name=self.params.artist,
            imvdb_entity_id=self.params.imvdb_entity_id,
            discogs_artist_id=self.params.discogs_artist_id,
        )
        
        # Create video record
        video_id = await self.repository.create_video(
            title=self.params.title,
            artist=self.params.artist,
            album=self.params.album,
            year=self.params.year,
            director=self.params.director,
            genre=self.params.genre,
            status="discovered",
            youtube_id=self.params.youtube_id,
            imvdb_video_id=self.params.imvdb_id,
        )
        
        # Link video to artist
        await self.repository.link_video_artist(
            video_id, artist_id, role="primary", position=0
        )
        
        # Handle featured artists
        for idx, featured in enumerate(self.params.featured_artists):
            feat_id = await self.repository.upsert_artist(name=featured)
            await self.repository.link_video_artist(
                video_id, feat_id, role="featured", position=idx + 1
            )
    
    return video_id, artist_id
```

#### Step 2: Fetch IMVDb Metadata
```python
async def _fetch_imvdb(self, video_id: int) -> None:
    """Fetch and store extended IMVDb metadata."""
    if not self.params.imvdb_id:
        return
    
    video_data = await self.imvdb_client.get_video(self.params.imvdb_id)
    
    # Store in imvdb_metadata table
    await self.repository.upsert_imvdb_metadata(
        video_id=video_id,
        production_status=video_data.production_status,
        release_date=video_data.release_date,
        image_urls=video_data.image,
        full_credits=video_data.credits,
    )
    
    # Update video sources table
    for source in video_data.sources:
        await self.repository.upsert_video_source(
            video_id=video_id,
            platform=source.source,  # "youtube", "vimeo"
            source_video_id=source.source_data,
            is_primary=(source.source == "youtube"),
        )
```

#### Step 3: Fetch Discogs Metadata
```python
async def _fetch_discogs(self, video_id: int) -> None:
    """Fetch and store extended Discogs metadata."""
    if not self.params.discogs_master_id:
        return
    
    master = await self.discogs_client.get_master(self.params.discogs_master_id)
    
    # Store in discogs_metadata table
    await self.repository.upsert_discogs_metadata(
        video_id=video_id,
        master_id=master["id"],
        genres=master.get("genres", []),
        styles=master.get("styles", []),
        tracklist=master.get("tracklist", []),
    )
    
    # Update video record with additional data
    await self.repository.update_video(
        video_id,
        genre=master.get("genres", [None])[0],
        studio=master.get("labels", [{}])[0].get("name"),
    )
```

#### Step 4: Download Video
```python
async def _download_video(self, video_id: int) -> Optional[Path]:
    """Download video file via yt-dlp."""
    if not self.params.download_video or not self.params.youtube_id:
        return None
    
    output_path = self._calculate_output_path()
    
    # Progress callback bridges to job progress
    def on_progress(progress: DownloadProgress):
        self.progress_callback(
            step=4,
            total_steps=6,
            message=f"Downloading: {progress.percent:.0f}%",
            details={"speed": progress.speed_bytes_per_sec}
        )
    
    result = await self.ytdlp_client.download(
        url=f"https://youtube.com/watch?v={self.params.youtube_id}",
        output_path=str(output_path),
        format_spec=self.params.format_spec,
        progress_hooks=DownloadProgressHooks(on_progress=on_progress),
    )
    
    # Update video record
    await self.repository.update_video(
        video_id,
        video_file_path=str(result.file_path),
        status="downloaded",
        download_source="youtube",
    )
    
    return result.file_path
```

#### Step 5: Generate Thumbnail
```python
async def _generate_thumbnail(self, video_id: int, video_path: Optional[Path]) -> None:
    """Extract thumbnail from video file."""
    if not video_path:
        return
    
    thumbnail_path = video_path.with_suffix(".jpg")
    
    await self.ffmpeg_client.extract_frame(
        input_path=video_path,
        output_path=thumbnail_path,
        timestamp="00:00:10",  # 10 seconds in
    )
    
    await self.repository.update_video(
        video_id,
        thumbnail_path=str(thumbnail_path),
    )
```

#### Step 6: Write NFO Files
```python
async def _write_nfo(self, video_id: int, artist_id: int) -> None:
    """Write artist.nfo and musicvideo.nfo files."""
    if not self.params.write_nfo_files:
        return
    
    video = await self.repository.get_video_by_id(video_id)
    artist = await self.repository.get_artist_by_id(artist_id)
    
    # Determine paths
    video_path = Path(video.video_file_path) if video.video_file_path else None
    if not video_path:
        return
    
    artist_dir = video_path.parent
    
    # Write artist.nfo
    artist_nfo_path = artist_dir / "artist.nfo"
    if not artist_nfo_path.exists():
        artist_nfo = ArtistNFO(name=artist.name)
        self.artist_nfo_parser.write_file(artist_nfo, artist_nfo_path)
    
    # Write musicvideo.nfo
    video_nfo_path = video_path.with_suffix(".nfo")
    video_nfo = MusicVideoNFO(
        title=video.title,
        artist=video.artist,
        album=video.album,
        year=video.year,
        director=video.director,
        genre=video.genre,
        studio=video.studio,
        tags=await self.repository.get_video_tag_names(video_id),
    )
    self.video_nfo_parser.write_file(video_nfo, video_nfo_path)
    
    # Update video record with NFO path
    await self.repository.update_video(video_id, nfo_file_path=str(video_nfo_path))
```

---

## Phase 3: Frontend Implementation

### 3.1 Route & Page Structure

```
/add                    → AddPage (tabbed: search | spotify | nfo)
/add/preview/:source/:id → PreviewModal (overlay, not separate route)
```

### 3.2 Component Hierarchy

```
AddPage (channel-import / magenta)
├── ModeTabs (Search Video | Spotify Playlist | NFO Library)
├── SingleVideoMode (when tab = 'search')
│   ├── AddSearchForm
│   ├── ArtistInput (with autocomplete from IMVDb entities)
│   ├── TrackInput
│   ├── SourceToggles (IMVDb/Discogs/YouTube checkboxes)
│   └── SearchButton
├── SearchResults
│   ├── SourceTabs (IMVDb | Discogs | YouTube)
│   └── ResultsList
│       └── SearchResultCard (per result)
│           ├── Thumbnail
│           ├── Title + Artist
│           ├── Source Badge
│           ├── Cross-reference Links
│           └── PreviewButton / QuickAddButton
├── PreviewModal (on card click)
│   ├── FullThumbnail
│   ├── MetadataEditor
│   │   ├── EditableTitle
│   │   ├── EditableArtist
│   │   ├── FeaturedArtistsInput
│   │   ├── AlbumInput
│   │   ├── YearPicker
│   │   ├── DirectorInput
│   │   ├── GenrePicker
│   │   └── TagInput
│   ├── DownloadOptions
│   │   ├── QualitySelector
│   │   ├── OutputPathInput
│   │   └── EnrichmentToggles
│   ├── CreditsSection (from IMVDb)
│   └── ImportButton
└── ImportProgressDrawer
    ├── JobProgressBar
    ├── CurrentStepLabel
    ├── StepList (checkmarks for completed)
    └── CancelButton
```

### 3.3 State Management

**Zustand Store**: `useAddStore`

```typescript
interface AddStore {
  // Mode state
  activeMode: 'search' | 'spotify' | 'nfo'
  
  // Search state (single video)
  searchQuery: { artist: string; track: string; sources: string[] }
  searchResults: AddSearchResponse | null
  isSearching: boolean
  
  // Spotify state
  spotifyPlaylistId: string
  spotifyPreview: BatchPreviewResponse | null
  isLoadingSpotifyPreview: boolean
  
  // NFO state
  nfoDirectory: string
  nfoPreview: BatchPreviewResponse | null
  isLoadingNFOPreview: boolean
  
  // Preview state (single video)
  previewSource: string | null
  previewId: string | null
  previewData: PreviewResponse | null
  isLoadingPreview: boolean
  
  // Import form state (editable metadata for single video)
  importForm: AddImportRequest
  
  // Import job state (shared across all modes)
  activeJobId: string | null
  jobProgress: JobProgress | null
  
  // Actions
  setActiveMode: (mode: 'search' | 'spotify' | 'nfo') => void
  setSearchQuery: (query: Partial<typeof searchQuery>) => void
  performSearch: () => Promise<void>
  setSpotifyPlaylistId: (id: string) => void
  fetchSpotifyPreview: () => Promise<void>
  setNFODirectory: (path: string) => void
  fetchNFOPreview: () => Promise<void>
  openPreview: (source: string, id: string) => Promise<void>
  closePreview: () => void
  updateImportForm: (updates: Partial<AddImportRequest>) => void
  submitSingleImport: () => Promise<void>
  submitSpotifyImport: () => Promise<void>
  submitNFOImport: () => Promise<void>
  cancelImport: () => void
}
```

### 3.4 WebSocket Integration

**Hook**: `useJobProgress`

```typescript
function useJobProgress(jobId: string | null) {
  const [progress, setProgress] = useState<JobProgress | null>(null)
  const [isComplete, setIsComplete] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  useEffect(() => {
    if (!jobId) return
    
    const ws = new WebSocket(`/ws/jobs/${jobId}`)
    
    ws.onopen = () => {
      // Send auth token as first message
      ws.send(JSON.stringify({ type: 'auth', token: getAccessToken() }))
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      
      if (data.event_type === 'job_progress') {
        setProgress(data.data)
        
        if (data.data.status === 'completed') {
          setIsComplete(true)
        } else if (data.data.status === 'failed') {
          setError(data.data.error)
        }
      }
    }
    
    return () => ws.close()
  }, [jobId])
  
  return { progress, isComplete, error }
}
```

### 3.5 UI Styling (Neo-MTV Import Channel)

```css
.channel-import {
  --channel-color: var(--channel-import); /* #FF006E */
  --channel-glow: var(--shadow-glow-magenta);
}

/* Search form with magenta accents */
.add-search-form {
  background: var(--bg-surface);
  border: 3px solid var(--channel-import);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  box-shadow: var(--shadow-lg), var(--shadow-glow-magenta);
}

/* Result card with sticker rotation */
.search-result-card {
  transform: rotate(-1deg);
}
.search-result-card:nth-child(even) {
  transform: rotate(1deg);
}
.search-result-card:hover {
  transform: scale(1.02) rotate(0deg);
  border-color: var(--channel-import);
  box-shadow: var(--shadow-xl), var(--shadow-glow-magenta);
}

/* Source badges */
.badge-imvdb { color: var(--channel-library); }
.badge-discogs { color: var(--channel-manage); }
.badge-youtube { color: var(--error); }

/* Progress drawer slides in from right */
.import-progress-drawer {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 400px;
  background: var(--bg-surface);
  border-left: 3px solid var(--channel-import);
  transform: translateX(100%);
  transition: transform 0.3s var(--ease-bounce);
}
.import-progress-drawer.open {
  transform: translateX(0);
}

/* Step progress animation */
@keyframes step-complete {
  0% { transform: scale(1); }
  50% { transform: scale(1.3); }
  100% { transform: scale(1); }
}
.step-complete .step-icon {
  animation: step-complete 0.4s var(--ease-bounce);
  color: var(--success);
}
```

---

## Phase 4: File Structure

### Backend Files to Create/Modify

```
fuzzbin/
├── web/routes/
│   └── add.py                    # NEW: All three import endpoints
├── web/schemas/
│   └── add.py                    # NEW: Request/response models
├── workflows/
│   ├── add_video.py              # NEW: Single video workflow
│   ├── spotify_import.py         # ENHANCE: Add video search/download
│   └── nfo_importer.py           # ENHANCE: Add file organization
├── tasks/
│   ├── models.py                 # MODIFY: Add JobType.ADD_VIDEO, ADD_SPOTIFY_PLAYLIST, ADD_NFO_SCAN
│   └── handlers.py               # MODIFY: Add handlers for all three job types
└── services/
    └── add_service.py            # NEW: Unified service layer
```

### Frontend Files to Create

```
frontend/src/
├── features/add/
│   ├── pages/
│   │   └── AddPage.tsx           # Tabbed interface
│   ├── components/
│   │   ├── ModeTabs.tsx          # Search | Spotify | NFO tabs
│   │   ├── search/
│   │   │   ├── AddSearchForm.tsx
│   │   │   ├── SearchResults.tsx
│   │   │   ├── SearchResultCard.tsx
│   │   │   └── PreviewModal.tsx
│   │   ├── spotify/
│   │   │   ├── SpotifyPlaylistInput.tsx
│   │   │   ├── PlaylistPreview.tsx
│   │   │   └── SpotifyImportOptions.tsx
│   │   ├── nfo/
│   │   │   ├── DirectorySelector.tsx
│   │   │   ├── ScanPreview.tsx
│   │   │   └── NFOImportOptions.tsx
│   │   └── shared/
│   │       ├── ImportProgressDrawer.tsx
│   │       ├── BatchPreviewTable.tsx
│   │       ├── MetadataEditor.tsx
│   │       └── DownloadOptions.tsx
│   ├── hooks/
│   │   ├── useAddSearch.ts       # Single video search
│   │   ├── useSpotifyPlaylist.ts # Spotify preview/import
│   │   ├── useNFOScan.ts         # NFO preview/import
│   │   └── useJobProgress.ts     # WebSocket (shared)
│   ├── stores/
│   │   └── useAddStore.ts        # Unified store
│   └── types.ts                  # Feature-specific types
├── lib/api/endpoints/
│   └── add.ts                    # API client functions
└── routes/
    └── AppRoutes.tsx             # MODIFY: Add /add route
```

---

## Phase 5: Implementation Order

### Sprint 1: Backend - Single Video (2-3 days)
1. ✅ Create `web/schemas/add.py` with request/response models for single video
2. ✅ Create `web/routes/add.py` with search and preview endpoints
3. ✅ Implement cross-reference logic between sources
4. ✅ Add single video import endpoint
5. ✅ Create `workflows/add_video.py` with all steps
6. ✅ Write unit tests for endpoints and workflow

### Sprint 2: Backend - Spotify + NFO (2-3 days)
1. ✅ Add Spotify and NFO request/response models to `web/schemas/add.py`
2. ✅ Add Spotify and NFO endpoints to `web/routes/add.py`
3. ✅ Enhance `workflows/spotify_import.py` with video search/download
4. ✅ Enhance `workflows/nfo_importer.py` with file organization
5. ✅ Add all job types to `tasks/models.py`
6. ✅ Create handlers for all three job types
7. ✅ Write integration tests

### Sprint 3: Frontend - Search UI (2-3 days)
1. ✅ Install Zustand, Framer Motion (if not present)
2. ✅ Create `useAddStore` Zustand store with multi-mode support
3. ✅ Create `AddPage` with mode tabs
4. ✅ Create single video search components
5. ✅ Implement `useAddSearch` hook
6. ✅ Apply magenta channel styling

### Sprint 4: Frontend - Spotify + NFO UI (3-4 days)
1. ✅ Create Spotify playlist components
2. ✅ Create NFO directory scan components
3. ✅ Create shared `BatchPreviewTable` component
4. ✅ Implement `useSpotifyPlaylist` and `useNFOScan` hooks
5. ✅ Create unified `ImportProgressDrawer` with batch support
6. ✅ Implement `useJobProgress` WebSocket hook
7. ✅ Add progress animations

### Sprint 5: Integration + Polish (2 days)
1. ✅ End-to-end testing for all three modes
2. ✅ Error handling and edge cases
3. ✅ Loading states and skeletons
4. ✅ Accessibility (keyboard nav, ARIA)
5. ✅ Responsive design
6. ✅ Documentation

**Total Timeline:** ~14-18 days

---

## API Response Examples

### Search Response
```json
{
  "imvdb_results": [
    {
      "id": 123456,
      "song_title": "Blurred Lines",
      "year": 2013,
      "artists": [{"name": "Robin Thicke", "slug": "robin-thicke"}],
      "image": {"t": "https://imvdb.com/thumb/blurred-lines.jpg"},
      "youtube_id": "zwT6DZCQi9k"
    }
  ],
  "discogs_results": [
    {
      "master_id": 567890,
      "title": "Robin Thicke - Blurred Lines",
      "year": "2013",
      "genre": ["R&B"],
      "thumb": "https://discogs.com/thumb.jpg"
    }
  ],
  "youtube_results": [
    {
      "id": "zwT6DZCQi9k",
      "title": "Robin Thicke - Blurred Lines ft. T.I., Pharrell (Official Video)",
      "channel": "RobinThickeVEVO",
      "view_count": 789000000,
      "duration": 263
    }
  ],
  "cross_references": [
    {
      "imvdb_id": 123456,
      "youtube_id": "zwT6DZCQi9k",
      "discogs_master_id": 567890,
      "confidence": 0.95
    }
  ]
}
```

### Job Progress WebSocket Event
```json
{
  "event_type": "job_progress",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "progress": 0.5,
    "current_step": "Downloading video: 47%",
    "processed_items": 3,
    "total_items": 6,
    "step_details": {
      "step_name": "download_video",
      "download_percent": 47.2,
      "speed_mbps": 12.4,
      "eta_seconds": 23
    }
  }
}
```

---

## User Flow Examples

### Scenario 1: Single Video Search
1. User navigates to `/add`
2. Default tab: "Search Video"
3. Enter artist: "Daft Punk", track: "Get Lucky"
4. Click "Search" → See results from IMVDb, Discogs, YouTube
5. Click result → Preview modal opens with editable metadata
6. Edit metadata if needed (featured artists, year, etc.)
7. Set download quality: "1080p"
8. Click "Import" → Job starts, progress drawer slides in from right
9. Progress updates:
   - ✓ Create database records
   - ✓ Fetch IMVDb metadata
   - ✓ Fetch Discogs metadata
   - ⏳ Downloading video: 47% (12.4 MB/s, 23s remaining)
   - ⋯ Generate thumbnail
   - ⋯ Write NFO files
10. Complete → Video appears in library, drawer shows success summary

### Scenario 2: Spotify Playlist Import
1. User navigates to `/add`
2. Switch to "Spotify Playlist" tab
3. Paste playlist URL: `https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M`
4. Click "Fetch Playlist" → Shows playlist: "Today's Top Hits" - 50 tracks
5. Preview table shows:
   - Track 1: "Flowers" - Miley Cyrus → ✓ Found in IMVDb
   - Track 2: "Anti-Hero" - Taylor Swift → ✓ Found on YouTube
   - Track 3: "Calm Down" - Rema → ⚠️ Already in library
   - ... (47 more tracks)
6. Summary: 45 new videos, 5 already in library, estimated 8.2 GB
7. Set quality: "1080p", search strategy: "IMVDb first"
8. Click "Import Playlist" → Batch job starts
9. Progress updates in drawer:
   - Track 7 of 50: "As It Was" - Harry Styles
   - ✓ 5 successful, ✗ 1 failed (not found), ⊘ 1 skipped
10. Complete → Summary: 42 successful, 3 failed, 5 skipped
11. Failed tracks shown with option to manually search

### Scenario 3: NFO Directory Scan
1. User navigates to `/add`
2. Switch to "NFO Library" tab
3. Click "Select Directory" → File picker opens
4. Choose `/media/old_library/Music Videos/`
5. Click "Scan" → Background scan starts
6. Scan complete: Found 500 NFO files
7. Preview table shows:
   - Nirvana - Smells Like Teen Spirit.nfo → ✓ New
   - Madonna - Vogue.nfo → ⚠️ Already imported
   - Daft Punk - Around the World.nfo → ✓ New, video file found
   - ... (497 more files)
8. Summary: 450 new, 50 already imported, 380 have matching video files
9. Enable "Organize files" to move into Fuzzbin library structure
10. Enable "Recursive scan" to include subdirectories
11. Set import mode: "Full" (complete metadata)
12. Click "Import Library" → Batch job starts
13. Progress updates:
    - NFO 127 of 500: "The Prodigy - Firestarter"
    - ✓ 125 imported, ✗ 1 failed (parse error), ⊘ 1 skipped
14. Complete → Summary: 448 imported, 2 failed, 50 skipped
15. Files organized into: `/library/Artist Name/Video Title.ext`

---

## Error Handling

### Search Errors
| Scenario | HTTP Status | User Message |
|----------|-------------|--------------|
| Rate limited | 429 | "Search is temporarily unavailable. Please wait a moment." |
| No results | 200 | "No videos found matching your search." |
| API timeout | 504 | "Search timed out. Try again or narrow your search." |
| Invalid input | 400 | "Please enter both artist and track title." |

### Import Errors
| Scenario | Job Status | User Message |
|----------|------------|--------------|
| YouTube unavailable | failed | "Video unavailable for download. Try a different source." |
| Disk full | failed | "Not enough disk space. Free up space and try again." |
| Network error | failed | "Network error during download. Job can be retried." |
| Auth expired | failed | "Session expired. Please log in again." |

---

## Future Enhancements

1. **YouTube Playlist Import**: Import all videos from a YouTube playlist (in addition to Spotify)
2. **Smart Matching**: ML-based matching across IMVDb/Discogs/YouTube with confidence scores
3. **Batch Select**: Multi-select search results for queue import (currently one-by-one)
4. **Enhanced Duplicate Detection**: Visual comparison of duplicates before skipping
5. **Format Preferences**: User-level default quality/format/path settings
6. **Import History**: View past imports with one-click retry capability
7. **Scheduled Imports**: Watch artists/playlists for new releases and auto-import
8. **MusicBrainz Integration**: Additional metadata source for cross-referencing
9. **Import Templates**: Save common import configurations (quality, enrichment toggles, etc.)
10. **Dry Run Mode**: Preview all changes before committing to database
