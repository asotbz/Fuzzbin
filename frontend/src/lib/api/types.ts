import type { paths } from './generated'

type QueryOf<T> = T extends { parameters: { query?: infer Q } } ? Q : never

type JsonOfStatus<T, Code extends number> = T extends { responses: infer R }
	? Code extends keyof R
		? R[Code] extends { content: { 'application/json': infer J } }
			? J
			: never
		: never
	: never

type BodyOf<T> = T extends { requestBody: { content: { 'application/json': infer J } } } ? J : never

export type ListVideosQuery = QueryOf<paths['/videos']['get']>
export type ListVideosResponse = JsonOfStatus<paths['/videos']['get'], 200>
export type GetVideoResponse = JsonOfStatus<paths['/videos/{video_id}']['get'], 200>

export type FacetsQuery = QueryOf<paths['/search/facets']['get']>
export type FacetsResponse = JsonOfStatus<paths['/search/facets']['get'], 200>

export type SuggestionQuery = QueryOf<paths['/search/suggestions']['get']>
export type SuggestionsResponse = JsonOfStatus<paths['/search/suggestions']['get'], 200>

export type Video = ListVideosResponse extends { items: Array<infer V> } ? V : never

export type SortOrder = 'asc' | 'desc'

export type AddSearchRequest = BodyOf<paths['/add/search']['post']>
export type AddSearchResponse = JsonOfStatus<paths['/add/search']['post'], 200>

export type AddPreviewResponse = JsonOfStatus<paths['/add/preview/{source}/{item_id}']['get'], 200>

export type AddSingleImportRequest = BodyOf<paths['/add/import']['post']>
export type AddSingleImportResponse = JsonOfStatus<paths['/add/import']['post'], 202>

export type BatchPreviewRequest = BodyOf<paths['/add/preview-batch']['post']>
export type BatchPreviewResponse = JsonOfStatus<paths['/add/preview-batch']['post'], 200>

export type BatchPreviewItem = NonNullable<BatchPreviewResponse['items']>[number]

export type SpotifyImportRequest = BodyOf<paths['/add/spotify']['post']>
export type SpotifyImportResponse = JsonOfStatus<paths['/add/spotify']['post'], 202>

export type NFOScanRequest = BodyOf<paths['/add/nfo-scan']['post']>
export type NFOScanResponse = JsonOfStatus<paths['/add/nfo-scan']['post'], 202>

export type SpotifyTrackEnrichRequest = BodyOf<paths['/add/spotify/enrich-track']['post']>
export type SpotifyTrackEnrichResponse = JsonOfStatus<paths['/add/spotify/enrich-track']['post'], 200>

export type SpotifyBatchImportRequest = BodyOf<paths['/add/spotify/import-selected']['post']>
export type SpotifyBatchImportResponse = JsonOfStatus<paths['/add/spotify/import-selected']['post'], 202>

export type YouTubeSearchRequest = BodyOf<paths['/add/youtube/search']['post']>

// Temporary manual types until OpenAPI schema is regenerated
export interface YouTubeMetadataRequest {
  youtube_id: string
}

export interface YouTubeMetadataResponse {
  youtube_id: string
  available: boolean
  view_count: number | null
  duration: number | null
  channel: string | null
  title: string | null
  error: string | null
}

export type GetJobResponse = JsonOfStatus<paths['/jobs/{job_id}']['get'], 200>

// Artist Import Types (manual until OpenAPI schema is regenerated)
export interface ArtistSearchRequest {
  artist_name: string
  per_page?: number
}

export interface ArtistSearchResultItem {
  id: number
  name: string | null
  slug: string | null
  url: string | null
  image: string | null
  discogs_id: number | null
  artist_video_count: number
  featured_video_count: number
  sample_tracks: string[]
}

export interface ArtistSearchResponse {
  artist_name: string
  total_results: number
  results: ArtistSearchResultItem[]
}

export interface ArtistVideoPreviewItem {
  id: number
  song_title: string | null
  year: number | null
  url: string | null
  thumbnail_url: string | null
  production_status: string | null
  version_name: string | null
  already_exists: boolean
  existing_video_id: number | null
}

export interface ArtistVideosPreviewResponse {
  entity_id: number
  entity_name: string | null
  entity_slug: string | null
  total_videos: number
  current_page: number
  per_page: number
  total_pages: number
  has_more: boolean
  videos: ArtistVideoPreviewItem[]
  existing_count: number
  new_count: number
}

export interface ArtistVideoEnrichRequest {
  imvdb_id: number
  artist: string
  track_title: string
  year?: number | null
  thumbnail_url?: string | null
}

export interface MusicBrainzEnrichmentData {
  recording_mbid: string | null
  release_mbid: string | null
  canonical_title: string | null
  canonical_artist: string | null
  album: string | null
  year: number | null
  label: string | null
  genre: string | null
  classified_genre: string | null
  all_genres: string[]
  match_score: number
  match_method: string
  confident_match: boolean
}

export interface ArtistVideoEnrichResponse {
  imvdb_id: number
  directors: string | null
  featured_artists: string | null
  youtube_ids: string[]
  imvdb_url: string | null
  musicbrainz: MusicBrainzEnrichmentData
  title: string
  artist: string
  album: string | null
  year: number | null
  label: string | null
  genre: string | null
  thumbnail_url: string | null
  enrichment_status: 'success' | 'partial' | 'not_found'
  already_exists: boolean
  existing_video_id: number | null
}

export interface SelectedArtistVideoImport {
  imvdb_id: number
  metadata: Record<string, unknown>
  imvdb_url?: string | null
  youtube_id?: string | null
  youtube_url?: string | null
  thumbnail_url?: string | null
}

export interface ArtistBatchImportRequest {
  entity_id: number
  entity_name?: string | null
  videos: SelectedArtistVideoImport[]
  initial_status?: string
  auto_download?: boolean
}

export interface ArtistBatchImportResponse {
  job_id: string
  entity_id: number
  video_count: number
  auto_download: boolean
  status: string
}
