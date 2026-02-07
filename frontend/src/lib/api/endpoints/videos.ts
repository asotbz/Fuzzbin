import { apiJson } from '../../../api/client'
import type { GetVideoResponse, ListVideosQuery, ListVideosResponse } from '../types'
import { toQueryString } from '../queryString'

export async function listVideos(query: ListVideosQuery): Promise<ListVideosResponse> {
  return apiJson<ListVideosResponse>({
    path: `/videos${toQueryString(query as Record<string, unknown>)}`,
  })
}

export async function getVideo(videoId: number): Promise<GetVideoResponse> {
  return apiJson<GetVideoResponse>({
    path: `/videos/${videoId}`,
  })
}

// Bulk delete response type
export interface BulkDeleteResult {
  success_ids: number[]
  failed_ids: number[]
  errors: Record<string, string>
  file_errors: string[]
  total: number
  success_count: number
  failed_count: number
}

export interface BulkOperationResult {
  success_ids: number[]
  failed_ids: number[]
  errors: Record<string, string>
  file_errors: string[]
  total: number
  success_count: number
  failed_count: number
}

export async function bulkApplyTags(
  videoIds: number[],
  tagNames: string[],
  replace: boolean = false
): Promise<BulkOperationResult> {
  return apiJson<BulkOperationResult>({
    method: 'POST',
    path: '/videos/bulk/tags',
    body: {
      video_ids: videoIds,
      tag_names: tagNames,
      replace,
    },
  })
}

export async function setVideoTags(
  videoId: number,
  tags: string[],
  source: 'manual' | 'auto' = 'manual'
): Promise<unknown> {
  return apiJson<unknown>({
    method: 'POST',
    path: `/tags/videos/${videoId}/set`,
    body: {
      tags,
      source,
    },
  })
}

/**
 * Bulk delete videos.
 * @param videoIds - IDs of videos to delete
 * @param deleteFiles - If true, also delete video/NFO files from disk (moved to trash)
 * @param permanent - If true, permanently delete DB records (default: soft delete)
 */
export async function bulkDeleteVideos(
  videoIds: number[],
  deleteFiles: boolean = false,
  permanent: boolean = false
): Promise<BulkDeleteResult> {
  return apiJson<BulkDeleteResult>({
    method: 'POST',
    path: '/videos/bulk/delete',
    body: {
      video_ids: videoIds,
      delete_files: deleteFiles,
      permanent: permanent,
    },
  })
}

// Trash types
export interface TrashItem {
  video_id: number
  title: string | null
  artist: string | null
  deleted_at: string | null
  trash_path: string | null
  file_size: number | null
}

export interface TrashListResponse {
  items: TrashItem[]
  total: number
  page: number
  page_size: number
}

export interface TrashStatsResponse {
  total_count: number
  total_size_bytes: number
}

export interface EmptyTrashResponse {
  deleted_count: number
  errors: string[]
}

/**
 * List all videos in trash.
 */
export async function listTrash(page: number = 1, pageSize: number = 20): Promise<TrashListResponse> {
  return apiJson<TrashListResponse>({
    path: `/files/trash?page=${page}&page_size=${pageSize}`,
  })
}

/**
 * Get trash statistics.
 */
export async function getTrashStats(): Promise<TrashStatsResponse> {
  return apiJson<TrashStatsResponse>({
    path: '/files/trash/stats',
  })
}

/**
 * Empty trash - permanently delete all trashed items.
 */
export async function emptyTrash(): Promise<EmptyTrashResponse> {
  return apiJson<EmptyTrashResponse>({
    method: 'POST',
    path: '/files/trash/empty',
  })
}
