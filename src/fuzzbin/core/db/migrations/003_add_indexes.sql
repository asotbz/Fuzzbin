-- Performance indexes migration
-- Version: 003
-- Description: Create indexes for common queries and foreign key lookups

-- Videos table indexes
CREATE INDEX IF NOT EXISTS idx_videos_imvdb_id ON videos(imvdb_video_id) WHERE imvdb_video_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_youtube_id ON videos(youtube_id) WHERE youtube_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_vimeo_id ON videos(vimeo_id) WHERE vimeo_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_file_path ON videos(video_file_path) WHERE video_file_path IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_is_deleted ON videos(is_deleted);
CREATE INDEX IF NOT EXISTS idx_videos_artist ON videos(artist) WHERE artist IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_year ON videos(year) WHERE year IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_genre ON videos(genre) WHERE genre IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status) WHERE status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_videos_download_source ON videos(download_source) WHERE download_source IS NOT NULL;

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
