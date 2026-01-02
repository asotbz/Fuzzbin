-- Migration: Add source_genres column to videos table
-- Version: 011
-- Description: Add source_genres to videos for storing original genre data from sources like Spotify.
--              Drop genres column from discogs_metadata (now using source_genres on videos).

-- Add source_genres column to videos table
-- Stores JSON array of original genres from source (Spotify, Discogs, etc.)
ALTER TABLE videos ADD COLUMN source_genres TEXT;

-- Create temporary table without genres column
CREATE TABLE discogs_metadata_new (
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

-- Copy data from old table (excluding genres column)
INSERT INTO discogs_metadata_new (
    id, video_id, album_id, master_id, release_id,
    styles, country, catno, barcode, data_quality,
    tracklist, labels, images, updated_at
)
SELECT
    id, video_id, album_id, master_id, release_id,
    styles, country, catno, barcode, data_quality,
    tracklist, labels, images, updated_at
FROM discogs_metadata;

-- Drop old table and rename new one
DROP TABLE discogs_metadata;
ALTER TABLE discogs_metadata_new RENAME TO discogs_metadata;

-- Recreate index on discogs_metadata if needed
CREATE INDEX IF NOT EXISTS idx_discogs_metadata_video_id ON discogs_metadata(video_id);
CREATE INDEX IF NOT EXISTS idx_discogs_metadata_album_id ON discogs_metadata(album_id);
