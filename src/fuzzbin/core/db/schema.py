"""Database schema constants and SQL statements."""

# Schema migration tracking table
SCHEMA_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
"""

# Core tables schema
VIDEOS_TABLE = """
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
    youtube_id TEXT UNIQUE,
    vimeo_id TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    is_deleted INTEGER DEFAULT 0 NOT NULL,
    CHECK (is_deleted IN (0, 1))
);
"""

ARTISTS_TABLE = """
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
"""

VIDEO_ARTISTS_TABLE = """
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
"""

ALBUMS_TABLE = """
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
"""

DIRECTORS_TABLE = """
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
"""

VIDEO_SOURCES_TABLE = """
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
"""

IMVDB_METADATA_TABLE = """
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
"""

DISCOGS_METADATA_TABLE = """
CREATE TABLE IF NOT EXISTS discogs_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER,
    album_id INTEGER,
    master_id INTEGER,
    release_id INTEGER,
    genres TEXT,
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
"""

# All table creation statements in order
ALL_TABLES = [
    SCHEMA_MIGRATIONS_TABLE,
    VIDEOS_TABLE,
    ARTISTS_TABLE,
    VIDEO_ARTISTS_TABLE,
    ALBUMS_TABLE,
    DIRECTORS_TABLE,
    VIDEO_SOURCES_TABLE,
    IMVDB_METADATA_TABLE,
    DISCOGS_METADATA_TABLE,
]
