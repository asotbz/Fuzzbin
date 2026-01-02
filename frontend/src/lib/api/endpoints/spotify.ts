/**
 * API endpoints for enhanced Spotify import functionality.
 */

import { apiJson } from '../../../api/client'
import type {
  SpotifyTrackEnrichRequest,
  SpotifyTrackEnrichResponse,
  SpotifyBatchImportRequest,
  SpotifyBatchImportResponse,
  YouTubeSearchRequest,
  YouTubeMetadataRequest,
  YouTubeMetadataResponse,
  AddSearchResponse,
} from '../types'

/**
 * Request to enrich a Spotify track with Discogs metadata.
 */
export interface DiscogsEnrichRequest {
  spotify_track_id: string
  track_title: string
  artist_name: string
  discogs_artist_id?: number | null
}

/**
 * Response after enriching a Spotify track with Discogs metadata.
 */
export interface DiscogsEnrichResponse {
  spotify_track_id: string
  match_found: boolean
  discogs_artist_id?: number | null
  discogs_master_id?: number | null
  album?: string | null
  label?: string | null
  genre?: string | null
  year?: number | null
  match_score: number
  match_method: string
}

/**
 * Enrich a single Spotify track with IMVDb metadata.
 *
 * Searches IMVDb for the track, applies fuzzy matching, extracts YouTube IDs,
 * and checks if the track already exists in the library.
 *
 * @param request - Track enrichment request with artist, title, and Spotify ID
 * @returns Enrichment response with match status, IMVDb ID, YouTube IDs, and metadata
 */
export async function enrichSpotifyTrack(
  request: SpotifyTrackEnrichRequest
): Promise<SpotifyTrackEnrichResponse> {
  return apiJson<SpotifyTrackEnrichResponse>({
    method: 'POST',
    path: '/add/spotify/enrich-track',
    body: request,
  })
}

/**
 * Import selected tracks from a Spotify playlist.
 *
 * Creates a background job that imports only the selected tracks with
 * optional metadata overrides and auto-download capability.
 *
 * @param request - Batch import request with playlist ID, selected tracks, and options
 * @returns Import response with job ID and status
 */
export async function importSelectedTracks(
  request: SpotifyBatchImportRequest
): Promise<SpotifyBatchImportResponse> {
  return apiJson<SpotifyBatchImportResponse>({
    method: 'POST',
    path: '/add/spotify/import-selected',
    body: request,
  })
}

/**
 * Search YouTube for videos matching artist and track title.
 *
 * This is a thin wrapper around the existing YouTube search functionality,
 * used when IMVDb doesn't have a match and the user wants to manually select a video.
 *
 * @param request - YouTube search request with artist, title, and max results
 * @returns Search response with YouTube video results
 */
export async function searchYouTube(
  request: YouTubeSearchRequest
): Promise<AddSearchResponse> {
  return apiJson<AddSearchResponse>({
    method: 'POST',
    path: '/add/youtube/search',
    body: request,
  })
}

/**
 * Get YouTube video metadata using yt-dlp.
 *
 * Fetches video information including view count, duration, and channel name.
 * Returns error information if the video is unavailable or cannot be accessed.
 *
 * @param request - YouTube metadata request with video ID
 * @returns Metadata response with video details or error information
 */
export async function getYouTubeMetadata(
  request: YouTubeMetadataRequest
): Promise<YouTubeMetadataResponse> {
  return apiJson<YouTubeMetadataResponse>({
    method: 'POST',
    path: '/add/youtube/metadata',
    body: request,
  })
}

/**
 * Enrich a single Spotify track with Discogs metadata.
 *
 * Searches Discogs for the track to find album, label, and genre information
 * from the earliest album appearance. Prefers artist ID search when available
 * for more accurate results.
 *
 * @param request - Discogs enrichment request with artist, title, and optional Discogs ID
 * @returns Enrichment response with album, label, genre from Discogs
 */
export async function enrichSpotifyTrackDiscogs(
  request: DiscogsEnrichRequest
): Promise<DiscogsEnrichResponse> {
  return apiJson<DiscogsEnrichResponse>({
    method: 'POST',
    path: '/add/spotify/enrich-track-discogs',
    body: request,
  })
}
