-- Add MusicBrainz enrichment fields to videos table
-- Migration 002: MusicBrainz Integration
-- Note: source_genres field already exists from 001_initial_schema.sql

-- Add MusicBrainz reference columns
ALTER TABLE videos ADD COLUMN recording_mbid TEXT;
ALTER TABLE videos ADD COLUMN release_mbid TEXT;
ALTER TABLE videos ADD COLUMN isrc TEXT;
ALTER TABLE videos ADD COLUMN mb_canonical_title TEXT;
ALTER TABLE videos ADD COLUMN mb_canonical_artist TEXT;
ALTER TABLE videos ADD COLUMN label TEXT;

-- Create indexes for lookups
CREATE INDEX IF NOT EXISTS idx_videos_recording_mbid 
  ON videos(recording_mbid) WHERE recording_mbid IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_videos_release_mbid 
  ON videos(release_mbid) WHERE release_mbid IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_videos_isrc 
  ON videos(isrc) WHERE isrc IS NOT NULL;
