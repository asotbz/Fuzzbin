-- Initial schema migration
-- Version: 001
-- Description: Complete database schema including all tables, indexes, triggers,
--              FTS5 full-text search, and seed data.

-- Enable foreign key constraints and WAL mode
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

--------------------------------------------------------------------------------
-- CORE TABLES
--------------------------------------------------------------------------------

-- Videos table (core entity)
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    artist TEXT,
    album TEXT,
    year INTEGER,
    director TEXT,
    genre TEXT,
    studio TEXT,
    video_file_path TEXT,
    video_file_path_relative TEXT,
    nfo_file_path TEXT,
    nfo_file_path_relative TEXT,
    imvdb_video_id TEXT UNIQUE,
    imvdb_url TEXT,
    youtube_id TEXT UNIQUE,
    vimeo_id TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    is_deleted INTEGER DEFAULT 0 NOT NULL,
    -- Status tracking columns
    status TEXT DEFAULT 'discovered',
    status_changed_at TEXT,
    status_message TEXT,
    -- File verification fields
    file_size INTEGER,
    file_checksum TEXT,
    file_verified_at TEXT,
    -- Video file metadata fields (from ffprobe)
    duration REAL,
    width INTEGER,
    height INTEGER,
    video_codec TEXT,
    audio_codec TEXT,
    container_format TEXT,
    bitrate INTEGER,
    frame_rate REAL,
    audio_channels INTEGER,
    audio_sample_rate INTEGER,
    aspect_ratio TEXT,
    -- Download tracking fields
    download_source TEXT,
    download_attempts INTEGER DEFAULT 0,
    last_download_attempt_at TEXT,
    last_download_error TEXT,
    -- Source genres (JSON array from Spotify, Discogs, etc.)
    source_genres TEXT,
    CHECK (is_deleted IN (0, 1))
);

-- Artists table
CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    imvdb_entity_id TEXT UNIQUE,
    discogs_artist_id INTEGER UNIQUE,
    biography TEXT,
    image_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    is_deleted INTEGER DEFAULT 0 NOT NULL,
    CHECK (is_deleted IN (0, 1))
);

-- Video-Artist relationship table (many-to-many)
CREATE TABLE IF NOT EXISTS video_artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    artist_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('primary', 'featured')),
    position INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
    UNIQUE(video_id, artist_id, role)
);

-- Albums table
CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    release_year INTEGER,
    discogs_master_id INTEGER UNIQUE,
    discogs_release_id INTEGER UNIQUE,
    country TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    is_deleted INTEGER DEFAULT 0 NOT NULL,
    CHECK (is_deleted IN (0, 1))
);

-- Directors table
CREATE TABLE IF NOT EXISTS directors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    imvdb_entity_id TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    is_deleted INTEGER DEFAULT 0 NOT NULL,
    CHECK (is_deleted IN (0, 1))
);

-- Video sources table (YouTube, Vimeo, etc.)
CREATE TABLE IF NOT EXISTS video_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    source_video_id TEXT NOT NULL,
    is_primary INTEGER DEFAULT 0 NOT NULL,
    url TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    UNIQUE(video_id, platform, source_video_id),
    CHECK (is_primary IN (0, 1))
);

-- IMVDb extended metadata
CREATE TABLE IF NOT EXISTS imvdb_metadata (
    video_id INTEGER PRIMARY KEY,
    production_status TEXT,
    song_slug TEXT,
    multiple_versions INTEGER DEFAULT 0,
    version_name TEXT,
    version_number INTEGER,
    is_imvdb_pick INTEGER DEFAULT 0,
    aspect_ratio TEXT,
    verified_credits INTEGER DEFAULT 0,
    release_date_stamp INTEGER,
    release_date_string TEXT,
    image_urls TEXT,
    full_credits TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    CHECK (multiple_versions IN (0, 1)),
    CHECK (is_imvdb_pick IN (0, 1)),
    CHECK (verified_credits IN (0, 1))
);

-- Discogs extended metadata (without genres column - use videos.source_genres instead)
CREATE TABLE IF NOT EXISTS discogs_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER,
    album_id INTEGER,
    master_id INTEGER,
    release_id INTEGER,
    styles TEXT,
    country TEXT,
    catno TEXT,
    barcode TEXT,
    data_quality TEXT,
    tracklist TEXT,
    labels TEXT,
    images TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE
);

-- Schema migrations tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

-- Video status history table
CREATE TABLE IF NOT EXISTS video_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    reason TEXT,
    changed_by TEXT,
    metadata TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

-- Collections table (internal-only grouping of videos)
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    is_deleted INTEGER DEFAULT 0 NOT NULL,
    CHECK (is_deleted IN (0, 1))
);

-- Video-Collection junction table (many-to-many with ordering)
CREATE TABLE IF NOT EXISTS video_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    collection_id INTEGER NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    UNIQUE(video_id, collection_id)
);

-- Tags table (user-defined metadata written to NFO files)
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    normalized_name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    usage_count INTEGER DEFAULT 0 NOT NULL
);

-- Video-Tag junction table (many-to-many)
CREATE TABLE IF NOT EXISTS video_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    added_at TEXT NOT NULL,
    source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'auto')),
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
    UNIQUE(video_id, tag_id)
);

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active INTEGER DEFAULT 1 NOT NULL,
    password_must_change INTEGER DEFAULT 0 NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT,
    CHECK (is_active IN (0, 1)),
    CHECK (password_must_change IN (0, 1))
);

-- Saved searches table for storing user search presets
CREATE TABLE IF NOT EXISTS saved_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    query_json TEXT NOT NULL,  -- JSON-serialized VideoFilterParams
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Scheduled tasks table for cron-based job scheduling
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    job_type TEXT NOT NULL,  -- Maps to JobType enum
    cron_expression TEXT NOT NULL,  -- e.g., "0 2 * * *" for daily at 2 AM
    enabled INTEGER DEFAULT 1 NOT NULL,
    metadata_json TEXT,  -- Optional JSON metadata passed to job handler
    last_run_at TEXT,
    next_run_at TEXT,
    last_status TEXT,  -- Last execution status: success, failed, cancelled
    last_error TEXT,  -- Error message if last run failed
    run_count INTEGER DEFAULT 0 NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (enabled IN (0, 1))
);

-- Revoked tokens table for JWT invalidation
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,  -- JWT token ID (unique identifier)
    user_id INTEGER NOT NULL,  -- User who owned the token
    revoked_at TEXT NOT NULL DEFAULT (datetime('now')),  -- When token was revoked
    expires_at TEXT NOT NULL,  -- When token would have expired (for cleanup)
    reason TEXT,  -- Optional reason for revocation
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

--------------------------------------------------------------------------------
-- INDEXES
--------------------------------------------------------------------------------

-- Videos table indexes
CREATE INDEX IF NOT EXISTS idx_videos_imvdb_id ON videos(imvdb_video_id) WHERE imvdb_video_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_imvdb_url ON videos(imvdb_url) WHERE imvdb_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_youtube_id ON videos(youtube_id) WHERE youtube_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_vimeo_id ON videos(vimeo_id) WHERE vimeo_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_file_path ON videos(video_file_path) WHERE video_file_path IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_file_checksum ON videos(file_checksum) WHERE file_checksum IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_is_deleted ON videos(is_deleted);
CREATE INDEX IF NOT EXISTS idx_videos_artist ON videos(artist) WHERE artist IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_year ON videos(year) WHERE year IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_genre ON videos(genre) WHERE genre IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status) WHERE status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_download_source ON videos(download_source) WHERE download_source IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_duration ON videos(duration) WHERE duration IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_resolution ON videos(width, height) WHERE width IS NOT NULL AND height IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_video_codec ON videos(video_codec) WHERE video_codec IS NOT NULL;

-- Artists table indexes
CREATE INDEX IF NOT EXISTS idx_artists_imvdb_entity_id ON artists(imvdb_entity_id) WHERE imvdb_entity_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_artists_discogs_id ON artists(discogs_artist_id) WHERE discogs_artist_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_artists_is_deleted ON artists(is_deleted);
CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name);

-- Video-Artists relationship indexes
CREATE INDEX IF NOT EXISTS idx_video_artists_video_id ON video_artists(video_id);
CREATE INDEX IF NOT EXISTS idx_video_artists_artist_id ON video_artists(artist_id);
CREATE INDEX IF NOT EXISTS idx_video_artists_role ON video_artists(role);

-- Albums table indexes
CREATE INDEX IF NOT EXISTS idx_albums_discogs_master_id ON albums(discogs_master_id) WHERE discogs_master_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_albums_discogs_release_id ON albums(discogs_release_id) WHERE discogs_release_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_albums_is_deleted ON albums(is_deleted);

-- Directors table indexes
CREATE INDEX IF NOT EXISTS idx_directors_imvdb_entity_id ON directors(imvdb_entity_id) WHERE imvdb_entity_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_directors_is_deleted ON directors(is_deleted);
CREATE INDEX IF NOT EXISTS idx_directors_name ON directors(name);

-- Video sources indexes
CREATE INDEX IF NOT EXISTS idx_video_sources_video_id ON video_sources(video_id);
CREATE INDEX IF NOT EXISTS idx_video_sources_platform ON video_sources(platform);
CREATE INDEX IF NOT EXISTS idx_video_sources_source_id ON video_sources(source_video_id);
CREATE INDEX IF NOT EXISTS idx_video_sources_is_primary ON video_sources(is_primary) WHERE is_primary = 1;

-- IMVDb metadata indexes
CREATE INDEX IF NOT EXISTS idx_imvdb_metadata_song_slug ON imvdb_metadata(song_slug) WHERE song_slug IS NOT NULL;

-- Discogs metadata indexes
CREATE INDEX IF NOT EXISTS idx_discogs_metadata_video_id ON discogs_metadata(video_id) WHERE video_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_discogs_metadata_album_id ON discogs_metadata(album_id) WHERE album_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_discogs_metadata_master_id ON discogs_metadata(master_id) WHERE master_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_discogs_metadata_release_id ON discogs_metadata(release_id) WHERE release_id IS NOT NULL;

-- Video status history indexes
CREATE INDEX IF NOT EXISTS idx_video_status_history_video_id ON video_status_history(video_id);
CREATE INDEX IF NOT EXISTS idx_video_status_history_changed_at ON video_status_history(changed_at);

-- Collections and tags indexes
CREATE INDEX IF NOT EXISTS idx_video_collections_video_id ON video_collections(video_id);
CREATE INDEX IF NOT EXISTS idx_video_collections_collection_id ON video_collections(collection_id);
CREATE INDEX IF NOT EXISTS idx_video_tags_video_id ON video_tags(video_id);
CREATE INDEX IF NOT EXISTS idx_video_tags_tag_id ON video_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_tags_normalized_name ON tags(normalized_name);

-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Saved searches indexes
CREATE INDEX IF NOT EXISTS idx_saved_searches_name ON saved_searches(name);
CREATE INDEX IF NOT EXISTS idx_saved_searches_created ON saved_searches(created_at DESC);

-- Scheduled tasks indexes
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_enabled ON scheduled_tasks(enabled);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_next_run ON scheduled_tasks(next_run_at) WHERE enabled = 1;
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_job_type ON scheduled_tasks(job_type);

-- Revoked tokens indexes
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expires_at ON revoked_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_user_id ON revoked_tokens(user_id);

--------------------------------------------------------------------------------
-- TRIGGERS
--------------------------------------------------------------------------------

-- Triggers to maintain tag usage_count and auto-delete unused tags
CREATE TRIGGER IF NOT EXISTS tags_usage_increment 
AFTER INSERT ON video_tags
BEGIN
    UPDATE tags SET usage_count = usage_count + 1 WHERE id = NEW.tag_id;
END;

CREATE TRIGGER IF NOT EXISTS tags_usage_decrement 
AFTER DELETE ON video_tags
BEGIN
    UPDATE tags SET usage_count = usage_count - 1 WHERE id = OLD.tag_id;
    -- Auto-delete tag if no longer used
    DELETE FROM tags WHERE id = OLD.tag_id AND usage_count = 0;
END;

--------------------------------------------------------------------------------
-- FTS5 FULL-TEXT SEARCH
-- Note: The FTS population query below references the tags and video_tags tables.
-- These tables must be created before this section runs (they are defined above).
--------------------------------------------------------------------------------

-- Create FTS5 virtual table for video search (including tags)
CREATE VIRTUAL TABLE IF NOT EXISTS videos_fts USING fts5(
    title,
    artist,
    album,
    director,
    genre,
    studio,
    tags
);

-- Populate FTS index with existing data (excluding soft-deleted)
INSERT INTO videos_fts(title, artist, album, director, genre, studio, tags, rowid)
SELECT 
    v.title, 
    v.artist, 
    v.album, 
    v.director, 
    v.genre, 
    v.studio,
    COALESCE(
        (SELECT GROUP_CONCAT(t.name, ' ')
         FROM video_tags vt
         JOIN tags t ON vt.tag_id = t.id
         WHERE vt.video_id = v.id),
        ''
    ) as tags,
    v.id
FROM videos v
WHERE v.is_deleted = 0;

-- Trigger to keep FTS index in sync on INSERT
CREATE TRIGGER IF NOT EXISTS videos_fts_insert
AFTER INSERT ON videos WHEN new.is_deleted = 0
BEGIN
    INSERT INTO videos_fts(title, artist, album, director, genre, studio, tags, rowid)
    SELECT 
        new.title, 
        new.artist, 
        new.album, 
        new.director, 
        new.genre, 
        new.studio,
        COALESCE(
            (SELECT GROUP_CONCAT(t.name, ' ')
             FROM video_tags vt
             JOIN tags t ON vt.tag_id = t.id
             WHERE vt.video_id = new.id),
            ''
        ),
        new.id;
END;

-- Trigger to keep FTS index in sync on UPDATE
-- For contentless FTS5, we need to use DELETE+INSERT with INSERT OR REPLACE
CREATE TRIGGER IF NOT EXISTS videos_fts_update
AFTER UPDATE ON videos
BEGIN
    -- Delete the old FTS row
    DELETE FROM videos_fts WHERE rowid = old.id;
    
    -- Re-insert if not deleted (using INSERT OR REPLACE to handle rowid reuse)
    INSERT INTO videos_fts(title, artist, album, director, genre, studio, tags, rowid)
    SELECT 
        new.title, 
        new.artist, 
        new.album, 
        new.director, 
        new.genre, 
        new.studio,
        COALESCE(
            (SELECT GROUP_CONCAT(t.name, ' ')
             FROM video_tags vt
             JOIN tags t ON vt.tag_id = t.id
             WHERE vt.video_id = new.id),
            ''
        ),
        new.id
    WHERE new.is_deleted = 0;
END;

-- Trigger to keep FTS index in sync on DELETE
CREATE TRIGGER IF NOT EXISTS videos_fts_delete
AFTER DELETE ON videos
BEGIN
    DELETE FROM videos_fts WHERE rowid = old.id;
END;

-- Trigger to update FTS when tags are added to a video
CREATE TRIGGER IF NOT EXISTS videos_fts_tag_insert
AFTER INSERT ON video_tags
BEGIN
    -- Delete and re-insert the video to update tags in FTS
    DELETE FROM videos_fts WHERE rowid = NEW.video_id;
    INSERT INTO videos_fts(title, artist, album, director, genre, studio, tags, rowid)
    SELECT 
        v.title, 
        v.artist, 
        v.album, 
        v.director, 
        v.genre, 
        v.studio,
        COALESCE(
            (SELECT GROUP_CONCAT(t.name, ' ')
             FROM video_tags vt
             JOIN tags t ON vt.tag_id = t.id
             WHERE vt.video_id = v.id),
            ''
        ),
        v.id
    FROM videos v
    WHERE v.id = NEW.video_id AND v.is_deleted = 0;
END;

-- Trigger to update FTS when tags are removed from a video
CREATE TRIGGER IF NOT EXISTS videos_fts_tag_delete
AFTER DELETE ON video_tags
BEGIN
    -- Delete and re-insert the video to update tags in FTS
    DELETE FROM videos_fts WHERE rowid = OLD.video_id;
    INSERT INTO videos_fts(title, artist, album, director, genre, studio, tags, rowid)
    SELECT 
        v.title, 
        v.artist, 
        v.album, 
        v.director, 
        v.genre, 
        v.studio,
        COALESCE(
            (SELECT GROUP_CONCAT(t.name, ' ')
             FROM video_tags vt
             JOIN tags t ON vt.tag_id = t.id
             WHERE vt.video_id = v.id),
            ''
        ),
        v.id
    FROM videos v
    WHERE v.id = OLD.video_id AND v.is_deleted = 0;
END;

--------------------------------------------------------------------------------
-- SEED DATA
--------------------------------------------------------------------------------

-- Seed initial admin user with default password 'changeme'
-- SECURITY: Change this password immediately after first login!
-- Default password hash is for 'changeme' - generated with bcrypt
-- password_must_change = 1 forces password change on first login
INSERT OR IGNORE INTO users (username, password_hash, is_active, password_must_change, created_at, updated_at)
VALUES (
    'admin',
    '$2b$12$7TBJrDjfUukBIYBrrLaBiecdSJKLXGbkJHvzNT.j9PAsAvbLJaG1S',
    1,
    1,
    datetime('now'),
    datetime('now')
);
