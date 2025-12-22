# Fuzzbin API UI Spec

## Health
Health check and status endpoints

- `GET` `/health` — Health check
  - Check API health status.

Returns basic health information including API version.

## Authentication
User authentication, token management, and password operations

- `POST` `/auth/login` — Authenticate user
  - Authenticate a user and return JWT tokens.

Validates username and password, returns access and refresh tokens
on successful authentication.

Rate limited: 5 failed attempts per minute per IP address.
- `POST` `/auth/refresh` — Refresh access token
  - Refresh an access token using a valid refresh token.

Returns new access and refresh tokens.
- `POST` `/auth/password` — Change password
  - Change the password for the authenticated user.

Requires authentication. Validates current password before updating.
- `POST` `/auth/logout` — Logout (no-op for stateless JWT)
  - Logout endpoint (no-op for stateless JWT).

Since JWT tokens are stateless, this endpoint doesn't invalidate tokens.
Clients should discard tokens on logout.

Note: For true token invalidation, implement a token blacklist
(requires Redis or database storage - out of scope for single-user auth).

## Videos
Video CRUD operations and metadata management

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
- `DELETE` `/videos/{video_id}/permanent` — Permanently delete video
  - Permanently delete a video. This cannot be undone.
- `GET` `/videos/{video_id}/status-history` — Get status history
  - Get the status change history for a video.
- `GET` `/videos/{video_id}/stream` — Stream video file
  - Stream video file with HTTP Range support for seeking.
- `GET` `/videos/{video_id}/thumbnail` — Get video thumbnail
  - Get or generate a thumbnail image for a video.

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
  - Create a new tag (name will be normalized to lowercase).
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
  - Delete multiple videos (soft delete by default, hard delete optional).
- `POST` `/videos/bulk/status` — Bulk update status
  - Update status for multiple videos in a single transaction.
- `POST` `/videos/bulk/tags` — Bulk apply tags
  - Apply tags to multiple videos. Can add to existing tags or replace them.
- `POST` `/videos/bulk/collections` — Bulk add to collection
  - Add multiple videos to a collection in a single transaction.
- `POST` `/videos/bulk/organize` — Bulk update file paths
  - Update file paths for multiple videos after file organization.

## Imports
Import workflows for YouTube and IMVDb content

- `POST` `/imports/youtube` — Import from YouTube
  - Import videos from YouTube URLs. Small batches run synchronously, larger batches require background task queue.
- `POST` `/imports/imvdb` — Import from IMVDb
  - Import video metadata from IMVDb by ID or search query.

## Exports
Export NFO metadata files and generate playlists

- `POST` `/exports/nfo` — Export NFO files
  - Regenerate NFO files for videos. NFO files are written alongside video files in the library.
- `POST` `/exports/playlist` — Export playlist
  - Export videos as a playlist in M3U, CSV, or JSON format.
