-- File operations migration
-- Version: 005
-- Description: Add index for file checksum duplicate detection

-- Add index on file_checksum for efficient duplicate detection
-- Using partial index since most videos won't have checksum computed initially
CREATE INDEX IF NOT EXISTS idx_videos_file_checksum ON videos(file_checksum) WHERE file_checksum IS NOT NULL;
