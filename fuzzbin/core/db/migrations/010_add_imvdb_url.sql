-- Add IMVDb URL column
-- Version: 010
-- Description: Store the full IMVDb video URL (requires artist/song slugs)

-- Add imvdb_url column to videos table
ALTER TABLE videos ADD COLUMN imvdb_url TEXT;

-- Create index for URL lookups
CREATE INDEX IF NOT EXISTS idx_videos_imvdb_url ON videos(imvdb_url) WHERE imvdb_url IS NOT NULL;
