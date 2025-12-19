-- FTS5 full-text search index migration
-- Version: 002
-- Description: Create FTS5 virtual table for full-text search on videos

-- Create FTS5 virtual table for video search
CREATE VIRTUAL TABLE IF NOT EXISTS videos_fts USING fts5(
    title,
    artist,
    album,
    director,
    genre,
    studio,
    content=videos,
    content_rowid=id
);

-- Populate FTS index with existing data (excluding soft-deleted)
INSERT INTO videos_fts(rowid, title, artist, album, director, genre, studio)
SELECT id, title, artist, album, director, genre, studio
FROM videos
WHERE is_deleted = 0;

-- Trigger to keep FTS index in sync on INSERT
CREATE TRIGGER IF NOT EXISTS videos_fts_insert
AFTER INSERT ON videos WHEN new.is_deleted = 0
BEGIN
    INSERT INTO videos_fts(rowid, title, artist, album, director, genre, studio)
    VALUES (new.id, new.title, new.artist, new.album, new.director, new.genre, new.studio);
END;

-- Trigger to keep FTS index in sync on UPDATE
CREATE TRIGGER IF NOT EXISTS videos_fts_update
AFTER UPDATE ON videos
BEGIN
    -- Always delete from FTS first
    DELETE FROM videos_fts WHERE rowid = old.id;
END;

-- Separate trigger to re-insert if not deleted
CREATE TRIGGER IF NOT EXISTS videos_fts_update_reinsert
AFTER UPDATE ON videos WHEN new.is_deleted = 0
BEGIN
    -- Re-insert into FTS if not deleted
    INSERT INTO videos_fts(rowid, title, artist, album, director, genre, studio)
    VALUES (new.id, new.title, new.artist, new.album, new.director, new.genre, new.studio);
END;

-- Trigger to keep FTS index in sync on DELETE
CREATE TRIGGER IF NOT EXISTS videos_fts_delete
AFTER DELETE ON videos
BEGIN
    DELETE FROM videos_fts WHERE rowid = old.id;
END;
