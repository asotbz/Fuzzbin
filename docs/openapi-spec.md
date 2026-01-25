# Fuzzbin API UI Spec

## Health
Health check and status endpoints

- `GET` `/health` — Health check
  - Check API health status.

Returns basic health information including API version.

## Authentication
User authentication, token management, and password operations

- `POST` `/auth/login` — Authenticate user
  - Authenticate a user and return JWT access token.

Validates username and password, returns access token in response body
and sets refresh token as an httpOnly cookie for security.

If the user's password_must_change flag is set, returns 403 with
instructions to use /auth/set-initial-password endpoint.

Rate limited: 5 failed attempts per minute per IP address.
- `POST` `/auth/refresh` — Refresh access token
  - Refresh an access token using a valid refresh token.

The refresh token is read from the httpOnly cookie set during login.
Returns new access token in response body and rotates the refresh
token cookie.
- `POST` `/auth/password` — Change password
  - Change the password for the authenticated user.

Requires authentication. Validates current password before updating.
Note: Password change does not guarantee immediate server-side revocation of
previously issued JWTs. Clients should discard existing tokens and re-authenticate.

Remediation note: implement true "revoke all tokens" with a DB-backed mechanism
(e.g., per-user token versioning) so old tokens are reliably rejected.
- `POST` `/auth/logout` — Logout and revoke tokens
  - Logout and revoke the current access token.

The provided Bearer token will be added to the revocation list,
preventing it from being used again even if it hasn't expired.

Also clears the httpOnly refresh token cookie.
- `POST` `/auth/set-initial-password` — Set initial password for first-time setup
  - Set a new password for users requiring password rotation.

This endpoint is used during first-time setup or when an admin has
reset a user's password. It validates the current password, sets
the new password, clears the password_must_change flag, and returns
authentication tokens.

Unlike /auth/password, this endpoint does not require prior authentication
and is specifically for users who cannot log in due to password rotation
requirements.

## Videos
Video CRUD operations and metadata management

- `GET` `/videos/{video_id}/stream` — Stream video file
  - Stream video file with HTTP Range support for seeking.
- `GET` `/videos` — List videos
  - Get a paginated list of videos with optional filters and sorting.
- `POST` `/videos` — Create video
  - Create a new video record.
- `GET` `/videos/{video_id}` — Get video by ID
  - Get detailed information about a specific video.
- `PATCH` `/videos/{video_id}` — Update video
  - Update video metadata. Only provided fields are updated.
- `DELETE` `/videos/{video_id}` — Soft delete video
  - Soft delete a video (can be restored later).
- `PATCH` `/videos/{video_id}/status` — Update video status
  - Update the status of a video with optional reason and metadata.
- `POST` `/videos/{video_id}/tags/{tag_id}` — Add tag to video
  - Add a tag to a video.
- `DELETE` `/videos/{video_id}/tags/{tag_id}` — Remove tag from video
  - Remove a tag from a video.
- `POST` `/videos/{video_id}/restore` — Restore video
  - Restore a soft-deleted video.
- `POST` `/videos/{video_id}/download` — Queue video download
  - Queue download job for a video with a YouTube ID. Downloads to temp, organizes to configured path, and generates NFO.
- `POST` `/videos/{video_id}/enrich/musicbrainz` — Enrich video with MusicBrainz
  - Enrich video metadata from MusicBrainz using ISRC (preferred) or title/artist search. Returns enrichment result for user preview/approval.
- `GET` `/videos/{video_id}/jobs` — Get jobs for video
  - Get active and pending jobs associated with a specific video. Returns jobs where metadata.video_id matches the requested video.
- `DELETE` `/videos/{video_id}/permanent` — Permanently delete video
  - Permanently delete a video. This cannot be undone.
- `GET` `/videos/{video_id}/status-history` — Get status history
  - Get the status change history for a video.
- `GET` `/videos/{video_id}/thumbnail` — Get video thumbnail
  - Get or generate a thumbnail for a video.
- `POST` `/videos/{video_id}/refresh` — Refresh video properties and thumbnail
  - Re-analyze video file with ffprobe and regenerate thumbnail.
- `POST` `/videos/backfill-imvdb-urls` — Backfill Imvdb Urls
  - Backfill missing IMVDb URLs for videos that have imvdb_video_id.

This endpoint is useful for fixing videos that were imported with
imvdb_video_id but missing imvdb_url (e.g., due to bugs or data migration).

Args:
    limit: Optional limit on number of videos to process
    video_id: Optional video ID to target a single video
    video_service: Injected video service
    imvdb_client: Injected IMVDb client

Returns:
    Dict with counts: total_found, updated, failed
- `POST` `/videos/sync-decade-tags` — Sync Decade Tags
  - Manually trigger decade tag synchronization across the library.

This endpoint submits a background job to synchronize auto-decade tags
across all videos in the library based on the current configuration.

The job will:
- Apply decade tags to all videos with a year field (if enabled)
- Remove auto-decade tags (if disabled)
- Update NFO files for affected videos (if auto-export enabled)

Use WebSocket connection to track job progress.

Returns:
    Job ID and confirmation message

## Artists
Artist management and video associations

- `GET` `/artists` — List artists
  - Get a paginated list of artists.
- `POST` `/artists` — Create or update artist
  - Create a new artist or update if name already exists (upsert).
- `GET` `/artists/{artist_id}` — Get artist by ID
  - Get detailed information about a specific artist.
- `PATCH` `/artists/{artist_id}` — Update artist
  - Update artist information. Only provided fields are updated.
- `DELETE` `/artists/{artist_id}` — Soft delete artist
  - Soft delete an artist.
- `GET` `/artists/{artist_id}/videos` — Get artist's videos
  - Get videos associated with an artist.
- `POST` `/artists/{artist_id}/videos/{video_id}` — Link artist to video
  - Link an artist to a video with specified role.
- `DELETE` `/artists/{artist_id}/videos/{video_id}` — Unlink artist from video
  - Remove the link between an artist and a video.

## Collections
Collection management for organizing videos

- `GET` `/collections` — List collections
  - Get a paginated list of collections.
- `POST` `/collections` — Create collection
  - Create a new collection.
- `GET` `/collections/{collection_id}` — Get collection by ID
  - Get detailed information about a specific collection.
- `PATCH` `/collections/{collection_id}` — Update collection
  - Update collection information. Only provided fields are updated.
- `DELETE` `/collections/{collection_id}` — Soft delete collection
  - Soft delete a collection.
- `GET` `/collections/{collection_id}/videos` — Get collection videos
  - Get videos in a collection, ordered by position.
- `POST` `/collections/{collection_id}/videos/{video_id}` — Add video to collection
  - Add a video to a collection with optional position.
- `DELETE` `/collections/{collection_id}/videos/{video_id}` — Remove video from collection
  - Remove a video from a collection.

## Tags
Tag management and video categorization

- `GET` `/tags` — List tags
  - Get a paginated list of tags.
- `POST` `/tags` — Create tag
  - Create a new tag (name will be normalized to lowercase if tags.normalize is enabled).
- `GET` `/tags/{tag_id}` — Get tag by ID
  - Get detailed information about a specific tag.
- `DELETE` `/tags/{tag_id}` — Delete tag
  - Delete a tag. Tags with usage_count > 0 cannot be deleted directly.
- `GET` `/tags/{tag_id}/videos` — Get videos with tag
  - Get videos that have a specific tag.
- `POST` `/tags/videos/{video_id}/set` — Set video tags
  - Replace all tags on a video with the provided list.
- `POST` `/tags/videos/{video_id}/add` — Add tags to video
  - Add tags to a video without removing existing ones.
- `DELETE` `/tags/videos/{video_id}/{tag_id}` — Remove tag from video
  - Remove a specific tag from a video.

## Search
Full-text search across the video library

- `GET` `/search` — Search videos
  - Full-text search across video metadata using FTS5. Supports AND, OR, NOT operators and phrase matching with quotes.
- `GET` `/search/suggestions` — Get search suggestions
  - Get autocomplete suggestions based on partial query.
- `GET` `/search/facets` — Get search facets
  - Get faceted counts for building filter UIs. Results are cached briefly.
- `GET` `/search/saved` — List saved searches
  - Get all saved searches.
- `POST` `/search/saved` — Create saved search
  - Save a search query for later reuse.
- `GET` `/search/saved/{search_id}` — Get saved search
  - Get a saved search by ID.
- `DELETE` `/search/saved/{search_id}` — Delete saved search
  - Delete a saved search.

## Files
File operations: organize, delete, restore, verify, and duplicate detection

- `POST` `/files/videos/{video_id}/organize` — Organize video files
  - Move video (and NFO) files to organized location based on path pattern.
- `DELETE` `/files/videos/{video_id}` — Delete video files
  - Delete video files (soft delete to trash or hard delete permanently).
- `POST` `/files/videos/{video_id}/restore` — Restore video from trash
  - Restore a soft-deleted video from the trash directory.
- `GET` `/files/trash` — List trashed videos
  - List all videos in the trash (soft-deleted).
- `GET` `/files/trash/stats` — Get trash statistics
  - Get count and total size of items in trash.
- `POST` `/files/trash/empty` — Empty trash
  - Permanently delete all items in the trash.
- `GET` `/files/videos/{video_id}/duplicates` — Find duplicate videos
  - Find potential duplicate videos by hash and/or metadata.
- `POST` `/files/duplicates/resolve` — Resolve duplicate videos
  - Keep one video and remove the duplicates.
- `GET` `/files/library/verify` — Verify library integrity
  - Scan database and filesystem to find missing files, orphans, and broken links.
- `POST` `/files/library/repair` — Repair library issues
  - Automatically repair issues found during verification.

## Jobs
Background job submission, status tracking, and cancellation

- `POST` `/jobs` — Submit a background job
  - Submit a new background job for async processing. Returns 202 Accepted with job details.
- `GET` `/jobs` — List jobs
  - List all jobs with optional status filter.
- `GET` `/jobs/metrics` — Get job queue metrics
  - Get monitoring metrics for the job queue including success rate, average duration, queue depth, and per-type breakdowns.
- `POST` `/jobs/scheduled` — Create scheduled task
  - Create a new scheduled task with cron expression.
- `GET` `/jobs/scheduled` — List scheduled tasks
  - List all scheduled tasks with optional filtering.
- `GET` `/jobs/scheduled/{task_id}` — Get scheduled task
  - Get a scheduled task by ID.
- `PATCH` `/jobs/scheduled/{task_id}` — Update scheduled task
  - Update a scheduled task's settings.
- `DELETE` `/jobs/scheduled/{task_id}` — Delete scheduled task
  - Delete a scheduled task.
- `POST` `/jobs/scheduled/{task_id}/run` — Run scheduled task now
  - Manually trigger a scheduled task to run immediately.
- `GET` `/jobs/{job_id}` — Get job status
  - Get the current status and progress of a job.
- `DELETE` `/jobs/{job_id}` — Cancel a job
  - Cancel a pending or running job. Has no effect on completed jobs.

## WebSocket
Real-time progress updates via WebSocket


## Bulk Operations
Batch operations for updating, deleting, tagging, and organizing multiple videos

- `POST` `/videos/bulk/update` — Bulk update videos
  - Update multiple videos with the same field values in a single transaction.
- `POST` `/videos/bulk/delete` — Bulk delete videos
  - Delete multiple videos. Optionally also delete files from disk (moved to trash).
- `POST` `/videos/bulk/status` — Bulk update status
  - Update status for multiple videos in a single transaction.
- `POST` `/videos/bulk/tags` — Bulk apply tags
  - Apply tags to multiple videos. Can add to existing tags or replace them.
- `POST` `/videos/bulk/collections` — Bulk add to collection
  - Add multiple videos to a collection in a single transaction.
- `POST` `/videos/bulk/organize` — Bulk update file paths
  - Update file paths for multiple videos after file organization.
- `POST` `/videos/bulk/download` — Bulk download videos
  - Queue download jobs for multiple videos with YouTube IDs. Skips videos without YouTube IDs.

## IMVDb
IMVDb music video database: search videos/entities, get metadata and credits

- `GET` `/imvdb/search/videos` — Search for music videos
  - Search IMVDb for music videos by artist and track title.

Returns paginated results with video thumbnails, release year, and artist info.
Use `/imvdb/videos/{video_id}` to get full details including credits and sources.

**Rate Limited:** Shares rate limit with other IMVDb endpoints.

**Cached:** Results are cached for 30 minutes.
- `GET` `/imvdb/search/entities` — Search for artists/directors/entities
  - Search IMVDb for entities (artists, directors, production companies, etc.).

Returns paginated results with entity IDs, Discogs links, and video counts.
Use `/imvdb/entities/{entity_id}` to get full details including video listings.

**Rate Limited:** Shares rate limit with other IMVDb endpoints.

**Cached:** Results are cached for 30 minutes.
- `GET` `/imvdb/videos/{video_id}` — Get video details
  - Get detailed metadata for an IMVDb video.

Returns full video information including:
- Primary and featured artists
- Directors and full crew credits
- Video sources (YouTube, Vimeo, etc.)
- Multiple version information
- Production status and release year

**Rate Limited:** Shares rate limit with other IMVDb endpoints.

**Cached:** Results are cached for 30 minutes.
- `GET` `/imvdb/entities/{entity_id}` — Get entity details
  - Get detailed metadata for an IMVDb entity (artist, director, etc.).

Returns full entity information including:
- Profile information and biography
- Discogs ID for cross-referencing
- Videos as primary artist
- Videos as featured artist

**Rate Limited:** Shares rate limit with other IMVDb endpoints.

**Cached:** Results are cached for 30 minutes.
- `GET` `/imvdb/entities/{entity_id}/videos` — Get paginated artist videos
  - Get paginated artist videos for an IMVDb entity.

Supports lazy loading for the artist import workflow. Returns videos
in the order they appear on IMVDb (typically by release year descending).

Use `has_more` to determine if additional pages are available.

**Rate Limited:** Shares rate limit with other IMVDb endpoints.

**Cached:** Results are cached for 30 minutes.

## Discogs
Discogs music database: search releases, get master/release details and artist discographies

- `GET` `/discogs/search` — Search for releases
  - Search Discogs for music releases by artist and/or track title.

Returns paginated results with release thumbnails, year, format, and label info.
Use `/discogs/masters/{master_id}` or `/discogs/releases/{release_id}` for full details.

**Search modes:**
- Use `artist` + `track` for targeted music video lookups
- Use `q` for general free-text search
- Default type is `master` (canonical release), use `release` for specific pressings

**Rate Limited:** 60 requests/minute (authenticated). Shares rate limit with other Discogs endpoints.

**Cached:** Results are cached for 2 hours.
- `GET` `/discogs/masters/{master_id}` — Get master release details
  - Get detailed metadata for a Discogs master release.

A master release represents the canonical version of an album across
all its various pressings and formats.

Returns full information including:
- Complete tracklist with durations
- Artists with proper credits
- Genres and styles
- Cover images at various sizes
- Related videos (music videos, documentaries)
- Market statistics (for sale count, lowest price)
- Links to all release versions

**Rate Limited:** 60 requests/minute (authenticated).

**Cached:** Results are cached for 2 hours.
- `GET` `/discogs/releases/{release_id}` — Get specific release details
  - Get detailed metadata for a specific Discogs release.

A release represents a specific pressing/version of an album with
unique catalog numbers, barcodes, and format details.

Returns full information including:
- Complete tracklist with durations
- Label and catalog information
- Format details (vinyl, CD, etc.)
- All identifiers (barcodes, matrix numbers)
- Extra artists (producers, engineers, etc.)
- Release notes and credits
- Cover images
- Related videos

**Rate Limited:** 60 requests/minute (authenticated).

**Cached:** Results are cached for 2 hours.
- `GET` `/discogs/artists/{artist_id}/releases` — Get artist discography
  - Get an artist's complete discography from Discogs.

Returns a paginated list of all releases associated with an artist,
including albums, singles, compilations, and appearances.

Each release includes:
- Release/Master ID and type
- Title and year
- Artist role (Main, Remix, Producer, etc.)
- Thumbnail image
- Community statistics (want/have counts)

**Rate Limited:** 60 requests/minute (authenticated).

**Cached:** Results are cached for 2 hours.

## Spotify
Spotify Web API: get playlists, tracks, and collect all metadata from a playlist

- `GET` `/spotify/playlists/{playlist_id}` — Get playlist metadata
  - Retrieve metadata for a Spotify playlist by ID.
- `GET` `/spotify/playlists/{playlist_id}/tracks` — Get playlist tracks (paginated)
  - Retrieve tracks from a Spotify playlist with pagination.
- `GET` `/spotify/playlists/{playlist_id}/tracks/all` — Get all playlist tracks
  - Retrieve all tracks from a Spotify playlist (handles pagination automatically).
- `GET` `/spotify/tracks/{track_id}` — Get track metadata
  - Retrieve metadata for a Spotify track by ID.

## Exports
Export NFO metadata files and generate playlists

- `POST` `/exports/nfo` — Export NFO files
  - Regenerate NFO files for videos. NFO files are written alongside video files in the library.
- `POST` `/exports/nfo/all` — Export all NFO files (background job)
  - Start a background job to export all video and artist NFO files from the database. Uses content hash comparison to skip writing files that haven't changed.
- `POST` `/exports/playlist` — Export playlist
  - Export videos as a playlist in M3U, CSV, or JSON format.

## Backup
System backup creation, listing, download, and verification

- `GET` `/backup` — List backups
  - List all available backup archives.

Returns backup metadata including filename, size, creation timestamp,
and contents. Results are sorted by creation time (newest first).
- `POST` `/backup` — Create backup
  - Trigger an on-demand system backup.

Creates a background job that generates a .zip archive containing:
- **config.yaml**: User configuration file
- **fuzzbin.db**: Library database (using SQLite backup API)
- **.thumbnails/**: Cached thumbnail images

The backup job runs asynchronously. Use the returned `job_id` to track
progress via `GET /jobs/{job_id}` or WebSocket `/ws/jobs/{job_id}`.

Old backups exceeding the retention count are automatically deleted.
- `GET` `/backup/{filename}` — Download backup
  - Download a backup archive by filename.

Returns the .zip file as a binary download. The archive can be
extracted and restored manually without the program running.
- `GET` `/backup/{filename}/verify` — Verify backup integrity
  - Verify a backup archive's integrity.

Checks:
- ZIP file structure and CRC checksums
- Database SQLite integrity (if database is included)
- Presence of expected files

Returns verification results including any errors found.

## Configuration
Runtime configuration management with history/undo support and safety level enforcement

- `GET` `/config` — Get current configuration
  - Retrieve the complete current configuration as a nested dictionary.

The configuration includes all settings for HTTP, logging, database, APIs,
and other subsystems. API credentials are returned in full (single-user mode).
- `PATCH` `/config` — Update configuration
  - Update one or more configuration fields.

**Safety Levels:**
- `safe`: Changes apply immediately with no side effects
- `requires_reload`: Components need reloading (API clients, connections)
- `affects_state`: Changes affect persistent state (database paths, directories)

For `requires_reload` or `affects_state` fields, returns **409 Conflict** unless
`force=true` is set. The response includes `required_actions` describing what
needs to happen to fully apply the changes.

**Examples:**
```json
{
    "updates": {
        "http.timeout": 60,
        "logging.level": "DEBUG"
    },
    "description": "Increased timeout for slow network"
}
```
- `GET` `/config/field/{path}` — Get configuration field
  - Retrieve a specific configuration field by dot-notation path.

Examples:
- `http.timeout` - HTTP timeout setting
- `apis.discogs.rate_limit.requests_per_minute` - Discogs rate limit
- `logging.level` - Current log level
- `GET` `/config/history` — Get configuration history
  - Retrieve recent configuration change history.

History entries include timestamps, descriptions, and undo/redo availability.
Use this to review changes before performing undo/redo operations.
- `POST` `/config/undo` — Undo configuration change
  - Undo the most recent configuration change.

Restores the previous configuration state from history.
The change is automatically saved to the configuration file.
- `POST` `/config/redo` — Redo configuration change
  - Redo a previously undone configuration change.

Restores the next configuration state from history.
The change is automatically saved to the configuration file.
- `GET` `/config/safety/{path}` — Get field safety level
  - Get the safety level for a configuration field path.

Use this to check what side effects a configuration change may have
before submitting an update request.

**Safety Levels:**
- `safe`: No side effects, changes apply immediately
- `requires_reload`: Components need reloading after change
- `affects_state`: Changes affect persistent state
- `GET` `/config/clients` — List registered API clients
  - List all API clients registered with the configuration manager.

Registered clients can be hot-reloaded when their configuration changes.
- `GET` `/config/clients/{name}/stats` — Get API client statistics
  - Get real-time statistics for a registered API client.

Statistics include:
- Active request count
- Concurrency utilization
- Rate limit token availability
- Rate limit capacity percentage

## yt-dlp
YouTube video search, metadata retrieval, and download with progress tracking

- `GET` `/ytdlp/search` — Search YouTube for videos
  - Search YouTube for music videos by artist and track title.

Uses yt-dlp to query YouTube and returns metadata for matching videos.
Results are sorted by relevance. The search query combines artist and track
title for best results.

**Example query:** `artist=Nirvana&track_title=Smells Like Teen Spirit&max_results=5`
- `GET` `/ytdlp/info/{video_id}` — Get video metadata
  - Get detailed metadata for a single YouTube video.

Accepts either a YouTube video ID (e.g., `dQw4w9WgXcQ`) or a full URL.
Returns video title, channel, view count, duration, and other metadata.
- `POST` `/ytdlp/download` — Download a YouTube video
  - Submit a YouTube video download job.

The download runs as a background job. Connect to `/ws/jobs/{job_id}` for
real-time progress updates via WebSocket.

**Path validation:** The `output_path` must be within the configured library
directory. Relative paths are resolved relative to the library directory.

**Progress tracking:** Progress updates include download percentage, speed,
and ETA. Subscribe to the WebSocket endpoint to receive real-time updates.

**Cancellation:** Use `DELETE /ytdlp/download/{job_id}` to cancel an
in-progress download.
- `DELETE` `/ytdlp/download/{job_id}` — Cancel a download
  - Cancel an in-progress YouTube video download.

Cancellation is cooperative - the download will stop at the next progress
check. Already downloaded data may be partially saved or cleaned up.

Returns 204 No Content on successful cancellation.
Returns 400 if the job has already completed, failed, or been cancelled.
Returns 404 if the job does not exist.

## Library Scan
Scan directories for music videos and import into library with full or discovery mode

- `POST` `/scan/preview` — Preview directory scan
  - Scan a directory and preview what would be imported without making changes.
- `POST` `/scan` — Scan and import music videos
  - Scan a directory for music videos and import them into the library.

**Import Modes:**
- `full`: Import all metadata from NFO files, set status to 'imported'
- `discovery`: Only import title/artist, set status to 'discovered' for follow-on workflows

The scan runs as a background job. Track progress via:
- `GET /jobs/{job_id}` for status polling
- `WebSocket /ws/jobs/{job_id}` for real-time updates
- `GET` `/scan/statuses` — Get video status definitions
  - Get the list of video statuses and their meanings for workflow planning.

## Add
Import hub endpoints: batch preview and import job submission

- `POST` `/add/preview-batch` — Preview a batch import
  - Preview what would be imported for Spotify playlists or NFO directory scans.
- `POST` `/add/spotify` — Submit a Spotify playlist import job
  - Submit a background job that imports playlist tracks into the DB.
- `POST` `/add/nfo-scan` — Submit an NFO directory scan/import job
  - Alias of POST /scan for UI cohesion under /add.
- `POST` `/add/search` — Search for a single video across sources
  - Aggregates IMVDb, Discogs, and YouTube (yt-dlp) search results into a single UI-friendly list.
- `GET` `/add/preview/{source}/{item_id}` — Preview a selected search result
  - Fetches a detail payload suitable for a UI preview for one of the supported sources.
- `GET` `/add/check-exists` — Check if video already exists in library
  - Check if a video with the given IMVDb ID or YouTube ID already exists in the library.
- `POST` `/add/import` — Submit a single-video import job
  - Creates/updates a video record based on a selected search result (IMVDb/Discogs/YouTube).
- `POST` `/add/spotify/enrich-track` — Enrich Spotify track with MusicBrainz and IMVDb metadata
  - Unified enrichment using ISRC → MusicBrainz → IMVDb pipeline
- `POST` `/add/youtube/search` — Search YouTube for videos
  - Search YouTube using yt-dlp for video results. Returns results in the same format as /add/search.
- `POST` `/add/spotify/import-selected` — Import selected tracks from Spotify playlist
  - Submit a job to import only the selected tracks from a Spotify playlist with optional metadata overrides and auto-download.
- `POST` `/add/youtube/metadata` — Get YouTube video metadata
  - Fetch YouTube video metadata (view count, duration, channel) using yt-dlp.
- `POST` `/add/search/artist` — Search for artists on IMVDb
  - Search for artists by name and return those with videos available.
- `GET` `/add/artist/preview/{entity_id}` — Get paginated artist videos for selection
  - Fetch videos for an artist with duplicate detection against existing library.
- `POST` `/add/enrich/imvdb-video` — Enrich a single IMVDb video with MusicBrainz data
  - Fetch full video details from IMVDb and enrich with MusicBrainz metadata.
- `POST` `/add/artist/import` — Import selected videos from an artist
  - Submit a batch import job for selected artist videos.
