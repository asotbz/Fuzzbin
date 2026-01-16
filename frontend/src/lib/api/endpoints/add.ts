import { apiJson } from '../../../api/client'
import type {
  AddPreviewResponse,
  AddSearchRequest,
  AddSearchResponse,
  AddSingleImportRequest,
  AddSingleImportResponse,
  ArtistBatchImportRequest,
  ArtistBatchImportResponse,
  ArtistSearchRequest,
  ArtistSearchResponse,
  ArtistVideoEnrichRequest,
  ArtistVideoEnrichResponse,
  ArtistVideosPreviewResponse,
  BatchPreviewRequest,
  BatchPreviewResponse,
  NFOScanRequest,
  NFOScanResponse,
  SpotifyImportRequest,
  SpotifyImportResponse,
  YouTubeMetadataRequest,
  YouTubeMetadataResponse,
} from '../types'

export async function addSearch(request: AddSearchRequest): Promise<AddSearchResponse> {
  return apiJson<AddSearchResponse>({
    method: 'POST',
    path: '/add/search',
    body: request,
  })
}

export async function addPreview(source: string, itemId: string): Promise<AddPreviewResponse> {
  return apiJson<AddPreviewResponse>({
    path: `/add/preview/${encodeURIComponent(source)}/${encodeURIComponent(itemId)}`,
  })
}

export async function addImport(request: AddSingleImportRequest): Promise<AddSingleImportResponse> {
  return apiJson<AddSingleImportResponse>({
    method: 'POST',
    path: '/add/import',
    body: request,
  })
}

export async function addPreviewBatch(request: BatchPreviewRequest): Promise<BatchPreviewResponse> {
  return apiJson<BatchPreviewResponse>({
    method: 'POST',
    path: '/add/preview-batch',
    body: request,
  })
}

export async function addSpotifyImport(request: SpotifyImportRequest): Promise<SpotifyImportResponse> {
  return apiJson<SpotifyImportResponse>({
    method: 'POST',
    path: '/add/spotify',
    body: request,
  })
}

export async function addNFOScan(request: NFOScanRequest): Promise<NFOScanResponse> {
  return apiJson<NFOScanResponse>({
    method: 'POST',
    path: '/add/nfo-scan',
    body: request,
  })
}

export async function getYouTubeMetadata(request: YouTubeMetadataRequest): Promise<YouTubeMetadataResponse> {
  return apiJson<YouTubeMetadataResponse>({
    method: 'POST',
    path: '/add/youtube/metadata',
    body: request,
  })
}

export interface CheckExistsResponse {
  exists: boolean
  video_id: number | null
  title: string | null
  artist: string | null
}

export async function checkVideoExists(params: {
  imvdb_id?: string
  youtube_id?: string
}): Promise<CheckExistsResponse> {
  const queryParams = new URLSearchParams()
  if (params.imvdb_id) {
    queryParams.append('imvdb_id', params.imvdb_id)
  }
  if (params.youtube_id) {
    queryParams.append('youtube_id', params.youtube_id)
  }

  return apiJson<CheckExistsResponse>({
    path: `/add/check-exists?${queryParams.toString()}`,
  })
}

// Artist Import API Functions

export async function searchArtists(request: ArtistSearchRequest): Promise<ArtistSearchResponse> {
  return apiJson<ArtistSearchResponse>({
    method: 'POST',
    path: '/add/search/artist',
    body: request,
  })
}

export async function previewArtistVideos(
  entityId: number,
  page: number = 1,
  perPage: number = 50
): Promise<ArtistVideosPreviewResponse> {
  const queryParams = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
  })
  return apiJson<ArtistVideosPreviewResponse>({
    path: `/add/artist/preview/${entityId}?${queryParams.toString()}`,
  })
}

export async function enrichImvdbVideo(request: ArtistVideoEnrichRequest): Promise<ArtistVideoEnrichResponse> {
  return apiJson<ArtistVideoEnrichResponse>({
    method: 'POST',
    path: '/add/enrich/imvdb-video',
    body: request,
  })
}

export async function importArtistVideos(request: ArtistBatchImportRequest): Promise<ArtistBatchImportResponse> {
  return apiJson<ArtistBatchImportResponse>({
    method: 'POST',
    path: '/add/artist/import',
    body: request,
  })
}
