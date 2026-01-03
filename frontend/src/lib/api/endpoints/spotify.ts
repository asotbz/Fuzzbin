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
 * Enrich a single Spotify track with MusicBrainz and IMVDb metadata.
 *
 * This endpoint performs unified enrichment:
 * 1. Searches MusicBrainz using ISRC (preferred) or artist/title
 * 2. Extracts canonical metadata, album, label, year, genres
 * 3. Classifies genres from MusicBrainz tags (with Spotify fallback)
 * 4. Searches IMVDb using canonical artist/title for better matching
 * 5. Extracts directors, featured artists, YouTube IDs
 * 6. Checks if track already exists in library
 *
 * @param request - Track enrichment request with artist, title, ISRC, and Spotify ID
 * @returns Enrichment response with MusicBrainz and IMVDb data
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
