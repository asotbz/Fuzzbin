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
