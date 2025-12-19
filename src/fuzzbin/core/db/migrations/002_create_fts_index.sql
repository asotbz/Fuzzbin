-- FTS5 full-text search index migration
-- Version: 002
-- Description: Create FTS5 virtual table for full-text search on videos

-- Create FTS5 virtual table for video search (including tags)
-- Note: tags is not in the videos table, so we use contentless FTS
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
