# Advanced Configuration

This document describes configuration options that are not exposed in the Settings UI but can be manually added to your `config.yaml` file for advanced use cases.

> **Note**: These settings use sensible defaults that work well for most users. Only modify them if you have a specific need.

## API Client Settings

Each API client (imvdb, discogs, spotify) supports the following additional settings beyond authentication:

### Rate Limiting

Control request frequency to avoid API throttling.

```yaml
apis:
  imvdb:
    auth:
      app_key: "your-key"
    # Optional rate limiting overrides
    rate_limit:
      requests_per_minute: 30    # Default: 25 for IMVDb, 25 for Discogs, 30 for Spotify
      burst_size: 5              # Default: 5
```

### Concurrency

Control parallel request limits.

```yaml
apis:
  discogs:
    auth:
      api_key: "your-key"
      api_secret: "your-secret"
    # Optional concurrency override
    concurrency:
      max_concurrent_requests: 5  # Default: 5
```

### HTTP Settings

Override timeout and retry behavior per API.

```yaml
apis:
  spotify:
    auth:
      client_id: "your-id"
      client_secret: "your-secret"
    # Optional HTTP settings
    http:
      timeout: 30                 # Default: 30 seconds
      retry:
        max_attempts: 3           # Default: 3
        backoff_multiplier: 2.0   # Default: 2.0
        min_wait: 1.0             # Default: 1.0 seconds
        max_wait: 60.0            # Default: 60.0 seconds
        status_codes:             # HTTP codes that trigger retry
          - 429
          - 500
          - 502
          - 503
          - 504
```

### Response Caching

Configure HTTP response caching (uses Hishel).

```yaml
apis:
  discogs:
    auth:
      api_key: "your-key"
      api_secret: "your-secret"
    # Optional caching settings
    cache:
      enabled: true               # Default: true
      ttl: 3600                   # Default: 3600 seconds (1 hour)
      stale_while_revalidate: 300 # Default: 300 seconds
      cacheable_methods:          # HTTP methods to cache
        - GET
      cacheable_status_codes:     # Status codes to cache
        - 200
        - 301
```

## yt-dlp Settings

Advanced options for the YouTube downloader.

```yaml
ytdlp:
  binary_path: null               # Auto-detected if null
  default_download_path: null     # Uses library_dir/downloads if null
  format: "bestvideo+bestaudio/best"
  extract_audio: false
  audio_format: "mp3"
  
  # Advanced options (not in UI)
  geo_bypass: true                # Default: true - bypass geo-restrictions
  quiet: false                    # Default: false - suppress yt-dlp output
  timeout: 300                    # Default: 300 seconds
```

## Thumbnail Settings

Configure video thumbnail generation.

```yaml
thumbnail:
  cache_dir: null                 # Uses config_dir/thumbnails if null
  
  # Advanced options (not in UI)
  default_timestamp: "00:00:05"   # Default: 5 seconds into video
  width: 320                      # Default: 320 pixels
  height: 180                     # Default: 180 pixels  
  quality: 85                     # Default: 85 (JPEG quality 1-100)
  max_file_size: 104857600        # Default: 100MB max video size
  timeout: 30                     # Default: 30 seconds
```

## File Manager Settings

Configure file operations.

```yaml
file_manager:
  trash_dir: ".trash"             # Relative to library_dir
  auto_empty_trash_days: 30       # 0 to disable
  
  # Advanced options (not in UI)
  hash_algorithm: "sha256"        # Default: sha256 (options: md5, sha1, sha256)
  verify_after_move: true         # Default: true - verify file integrity after move
  max_file_size: null             # Default: null (no limit)
  chunk_size: 8192                # Default: 8192 bytes for streaming
```

## Search Settings

Configure search behavior.

```yaml
# These are hardcoded defaults (cannot be changed via config)
# facet_cache_ttl: 60             # Facet cache duration in seconds
# max_bulk_items: 500             # Maximum items in bulk operations
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

## Example: Power User Config

For users who need fine-grained control:

```yaml
apis:
  imvdb:
    auth:
      app_key: "your-imvdb-key"
    rate_limit:
      requests_per_minute: 20     # Be conservative
      burst_size: 3
    http:
      timeout: 60                 # Allow longer timeouts

  discogs:
    auth:
      api_key: "your-discogs-key"
      api_secret: "your-discogs-secret"
    rate_limit:
      requests_per_minute: 20     # Discogs has strict limits
    cache:
      ttl: 86400                  # Cache for 24 hours

ytdlp:
  format: "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
  timeout: 600                    # 10 minutes for large files

thumbnail:
  width: 640
  height: 360
  quality: 90

file_manager:
  verify_after_move: true
  hash_algorithm: "sha256"

# Database settings (not normally needed)
database:
  database_path: "fuzzbin.db"     # Relative to config_dir
  enable_wal_mode: true           # Better concurrency
  connection_timeout: 30          # Seconds
  backup_dir: "backups"           # Relative to config_dir
```

## Database Settings

Database configuration uses hardcoded defaults that should not normally be changed:

| Setting | Default | Description |
|---------|---------|-------------|
| `database_path` | `fuzzbin.db` | SQLite database file (relative to config_dir) |
| `enable_wal_mode` | `true` | Enable Write-Ahead Logging for better concurrency |
| `connection_timeout` | `30` | Database connection timeout in seconds |
| `backup_dir` | `backups` | Backup archive directory (relative to config_dir) |

> **Warning**: Changing database settings can cause data loss or corruption. Only modify if you understand the implications.

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
