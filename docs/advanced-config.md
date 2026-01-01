# Advanced Configuration

This document describes configuration options that are not exposed in the Settings UI but can be manually added to your `config.yaml` file for advanced use cases.

> **Note**: These settings use sensible defaults that work well for most users. Only modify them if you have a specific need.

## Hardcoded Defaults

The following settings are **hardcoded** in the application and cannot be changed via `config.yaml`. They are documented here for reference.

### API Rate Limiting and Caching

Each API client (IMVDb, Discogs, Spotify) uses sensible, hardcoded defaults for:
- Rate limiting (requests per minute, burst size)
- Concurrency limits (max concurrent requests)
- HTTP timeouts and retry behavior
- Response caching (TTL, cacheable methods/status codes)

These defaults are tuned to work within each API's rate limits and provide good performance. They cannot be overridden.

### Database Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `database_path` | `fuzzbin.db` | SQLite database file (relative to config_dir) |
| `enable_wal_mode` | `true` | Enable Write-Ahead Logging for better concurrency |
| `connection_timeout` | `30` | Database connection timeout in seconds |
| `backup_dir` | `backups` | Backup archive directory (relative to config_dir) |

### Thumbnail Generation

| Setting | Default | Description |
|---------|---------|-------------|
| `default_timestamp` | `00:00:05` | Timestamp to capture thumbnail (5 seconds into video) |
| `width` | `320` | Thumbnail width in pixels |
| `height` | `180` | Thumbnail height in pixels |
| `quality` | `85` | JPEG quality (1-100) |
| `max_file_size` | `100MB` | Maximum video file size for thumbnail generation |
| `timeout` | `30` | ffmpeg timeout in seconds |

## Configurable Settings (Not in UI)

These settings can be added to your `config.yaml` but are not exposed in the Settings UI.

### Logging - Third Party Library Levels

Control log verbosity for specific third-party libraries:

```yaml
logging:
  level: INFO
  format: json
  file:
    enabled: true
  # Optional: Override log levels for specific libraries
  third_party:
    httpx: WARNING
    httpcore: WARNING
    hishel: WARNING
```

### Backup - Output Directory

```yaml
backup:
  enabled: true
  schedule: "0 2 * * *"
  retention_count: 7
  output_dir: backups  # Relative to config_dir
```

## Example: Minimal Config

Most users only need to specify API keys:

```yaml
apis:
  imvdb:
    auth:
      app_key: "your-imvdb-key"
  
  discogs:
    auth:
      api_key: "your-discogs-key"
      api_secret: "your-discogs-secret"
  
  spotify:
    auth:
      client_id: "your-spotify-id"
      client_secret: "your-spotify-secret"
```

## Example: Full Config

Complete configuration with all user-configurable settings:

```yaml
# Logging
logging:
  level: INFO
  format: json
  file:
    enabled: true

# API Keys (auth only - rate limiting/caching is hardcoded)
apis:
  imvdb:
    auth:
      app_key: "your-imvdb-key"

  discogs:
    auth:
      api_key: "your-discogs-key"
      api_secret: "your-discogs-secret"

  spotify:
    auth:
      client_id: "your-spotify-id"
      client_secret: "your-spotify-secret"

# Media tools
ytdlp:
  ytdlp_path: yt-dlp
  format_spec: "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
  geo_bypass: false

ffprobe:
  ffprobe_path: ffprobe
  timeout: 30

thumbnail:
  cache_dir: ".thumbnails"

# NFO files
nfo:
  write_artist_nfo: true
  write_musicvideo_nfo: true
  featured_artists:
    enabled: false
    append_to_field: artist

# File organization
organizer:
  path_pattern: "{artist}/{title}"
  normalize_filenames: false

# Tags
tags:
  normalize: true
  auto_decade:
    enabled: true
    format: "{decade}s"

# Trash management
trash:
  trash_dir: ".trash"
  enabled: true
  schedule: "0 3 * * *"
  retention_days: 30

# Backups
backup:
  enabled: true
  schedule: "0 2 * * *"
  retention_count: 7
```

## Environment Variables

API credentials can also be set via environment variables (these take precedence over config.yaml):

```bash
# IMVDb
export IMVDB_APP_KEY="your-key"

# Discogs
export DISCOGS_API_KEY="your-key"
export DISCOGS_API_SECRET="your-secret"

# Spotify
export SPOTIFY_CLIENT_ID="your-id"
export SPOTIFY_CLIENT_SECRET="your-secret"
```

## Path Environment Variables

Override the default directories:

```bash
# Override config directory (database, caches, thumbnails)
export FUZZBIN_CONFIG_DIR="/path/to/config"

# Override library directory (video files, NFOs, trash)
export FUZZBIN_LIBRARY_DIR="/path/to/videos"

# Use Docker defaults (/config, /music_videos)
export FUZZBIN_DOCKER=1
```
