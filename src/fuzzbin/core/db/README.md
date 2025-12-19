# Fuzzbin Database Module

Central SQLite database for music video library metadata with full CRUD operations, FTS5 search, soft delete support, and NFO export capabilities.

## Features

- **Async SQLite** with aiosqlite for non-blocking operations
- **Fluent Query Builder** for intuitive filtering and searching
- **FTS5 Full-Text Search** for fast searches across video metadata
- **Soft Delete** with restore capability
- **Relationship Management** between videos, artists, albums, and directors
- **External ID Tracking** for IMVDb, Discogs, YouTube, Vimeo integration
- **NFO Export** to generate Kodi-compatible metadata files
- **Database Backup/Restore** with integrity verification
- **Transaction Support** for complex multi-step operations
- **WAL Mode** enabled for better concurrency

## Quick Start

```python
import fuzzbin
from pathlib import Path

# Initialize fuzzbin (async required)
await fuzzbin.configure(config_path=Path("config.yaml"))

# Get repository instance
repo = await fuzzbin.get_repository()

# Create a video
video_id = await repo.create_video(
    title="Smells Like Teen Spirit",
    artist="Nirvana",
    album="Nevermind",
    year=1991,
    director="Samuel Bayer",
    genre="Grunge",
    imvdb_video_id="nv001",
    youtube_id="hTWKbfoikeg",
)

# Create and link artists
artist_id = await repo.upsert_artist(
    name="Nirvana",
    imvdb_entity_id="12345",
)
await repo.link_video_artist(video_id, artist_id, role="primary")

# Query videos
videos = await repo.query()\\
    .where_artist("Nirvana")\\
    .where_year_range(1990, 1995)\\
    .order_by("year")\\
    .execute()

# Full-text search
results = await repo.search_videos("Grunge AND Nevermind")

# Export to NFO
exporter = fuzzbin.NFOExporter(repo)
await exporter.export_video_to_nfo(video_id, Path("video.nfo"))
```

## Configuration

Add to your `config.yaml`:

```yaml
database:
  database_path: ".db/fuzzbin_metadata.db"
  workspace_root: "/path/to/videos"  # Optional, for relative paths
  enable_wal_mode: true
  connection_timeout: 30
  backup_dir: ".db/backups"
```

## Schema Overview

### Core Tables

- **videos** - Music video metadata with soft delete support
- **artists** - Artist information with external IDs
- **video_artists** - Many-to-many relationship (primary/featured roles)
- **albums** - Album information with Discogs IDs
- **directors** - Director information with IMVDb entity IDs
- **video_sources** - Platform-specific IDs (YouTube, Vimeo, etc.)

### Extended Metadata

- **imvdb_metadata** - Extended IMVDb data (credits, images, etc.)
- **discogs_metadata** - Extended Discogs data (genres, styles, tracklist)

### Indexes

- All external IDs (imvdb_video_id, youtube_id, discogs IDs)
- File paths for quick lookup
- Foreign keys for relationship queries
- FTS5 virtual table for full-text search

## Query Examples

### Basic Queries

```python
# Find by external ID
video = await repo.get_video_by_youtube_id("hTWKbfoikeg")
video = await repo.get_video_by_imvdb_id("nv001")

# Find by file path
video = await repo.get_video_by_path("/path/to/video.mp4")
```

### Fluent Query Builder

```python
# Simple filter
videos = await repo.query().where_artist("Madonna").execute()

# Multiple filters
videos = await repo.query()\\
    .where_genre("Rock")\\
    .where_year_range(1990, 2000)\\
    .where_director("smith")\\
    .execute()

# Ordering and limiting
videos = await repo.query()\\
    .where_artist("Nirvana")\\
    .order_by("year", desc=True)\\
    .limit(10)\\
    .execute()

# Count results
count = await repo.query().where_genre("Grunge").count()

# Include soft-deleted
all_videos = await repo.query().include_deleted().execute()
```

### Full-Text Search (FTS5)

```python
# Simple search
videos = await repo.search_videos("rock")

# Boolean search
videos = await repo.search_videos("rock AND alternative")
videos = await repo.search_videos("rock OR punk")
videos = await repo.search_videos("rock NOT metal")

# Phrase search
videos = await repo.search_videos('"official video"')

# Field-specific search
videos = await repo.search_videos("director:smith")
videos = await repo.search_videos("genre:rock AND artist:nirvana")
```

## Bulk Operations

```python
# Bulk create videos
video_data = [
    {"title": "Video 1", "artist": "Artist A", "year": 2020},
    {"title": "Video 2", "artist": "Artist A", "year": 2021},
]
video_ids = await repo.bulk_create_videos(video_data)

# Bulk link artists
await repo.bulk_link_artists(
    video_id=video_id,
    artist_links=[
        {"artist_id": 10, "role": "primary", "position": 0},
        {"artist_id": 20, "role": "featured", "position": 1},
    ]
)
```

## Transactions

```python
# Explicit transaction
async with repo.transaction():
    video_id = await repo.create_video(...)
    artist_id = await repo.upsert_artist(...)
    await repo.link_video_artist(video_id, artist_id)
    # All operations committed together
```

## Soft Delete

```python
# Soft delete (sets is_deleted=1, deleted_at=timestamp)
await repo.delete_video(video_id)

# Restore
await repo.restore_video(video_id)

# Hard delete (permanent)
await repo.hard_delete_video(video_id)

# Query including deleted
videos = await repo.query().include_deleted().execute()
```

## Backup and Restore

```python
from pathlib import Path

# Backup database
await fuzzbin.DatabaseBackup.backup(
    source_db=Path(".db/fuzzbin_metadata.db"),
    backup_path=Path(".db/backups/backup_2025-12-18.db"),
)

# Verify backup
is_valid = await fuzzbin.DatabaseBackup.verify_backup(backup_path)

# Restore from backup
await fuzzbin.DatabaseBackup.restore(
    backup_path=Path(".db/backups/backup_2025-12-18.db"),
    target_db=Path(".db/fuzzbin_metadata.db"),
)

# List available backups
backups = fuzzbin.DatabaseBackup.list_backups(Path(".db/backups"))
```

## NFO Export

```python
exporter = fuzzbin.NFOExporter(repo)

# Export single video
await exporter.export_video_to_nfo(
    video_id=1,
    nfo_path=Path("videos/artist - title.nfo")
)

# Export artist
await exporter.export_artist_to_nfo(
    artist_id=1,
    nfo_path=Path("artists/artist/artist.nfo")
)
```

## Context Manager Support

```python
# Automatic connection management
async with await fuzzbin.get_repository() as repo:
    videos = await repo.query().execute()
    # Connection closed automatically
```

## Testing

```python
import pytest
import pytest_asyncio

@pytest_asyncio.fixture
async def test_repo(tmp_path):
    from fuzzbin.core.db import VideoRepository, DatabaseConfig
    
    config = DatabaseConfig(
        database_path=str(tmp_path / "test.db"),
        workspace_root=str(tmp_path),
    )
    
    repo = await VideoRepository.from_config(config)
    yield repo
    await repo.close()

@pytest.mark.asyncio
async def test_create_video(test_repo):
    video_id = await test_repo.create_video(
        title="Test",
        artist="Artist",
    )
    assert video_id > 0
```

## Error Handling

```python
from fuzzbin.core.db import (
    VideoNotFoundError,
    ArtistNotFoundError,
    QueryError,
    TransactionError,
    DatabaseConnectionError,
)

try:
    video = await repo.get_video_by_id(99999)
except VideoNotFoundError as e:
    print(f"Video not found: {e.video_id}")

try:
    async with repo.transaction():
        # Operations that might fail
        raise Exception("Rollback!")
except TransactionError:
    print("Transaction rolled back")
```

## Migration System

Migrations are automatically applied on first connection via `VideoRepository.from_config()`.

Migration files are located in `src/fuzzbin/core/db/migrations/`:
- `001_initial_schema.sql` - Core tables and constraints
- `002_create_fts_index.sql` - FTS5 full-text search setup
- `003_add_indexes.sql` - Performance indexes

Migrations are tracked in the `schema_migrations` table with checksums to prevent duplicate execution.

## Best Practices

1. **Always use `await configure()`** at application startup
2. **Use transactions** for multi-step operations
3. **Leverage FTS5** for complex searches instead of multiple LIKE queries
4. **Create backups** before major schema changes or bulk operations
5. **Use soft delete** to preserve data and enable undo functionality
6. **Store both absolute and relative paths** for portability
7. **Index external IDs** for fast lookups from API data
8. **Close repository** when done: `await repo.close()`

## Performance Tips

- WAL mode is enabled by default for better concurrency
- FTS5 index is automatically synchronized via triggers
- Use bulk operations for creating multiple records
- Queries are parameterized to prevent SQL injection
- Connection pooling is handled automatically by aiosqlite

## See Also

- [database_example.py](../../examples/database_example.py) - Comprehensive usage example
- [test_database.py](../../tests/unit/test_database.py) - Test examples
- [Schema Documentation](schema.py) - Complete table definitions
