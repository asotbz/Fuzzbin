import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useCallback } from 'react'
import { getApiBaseUrl, APIError } from './client'
import { getTokens } from '../auth/tokenStore'

/**
 * Fetches a video thumbnail with authentication and returns a blob URL.
 * Includes automatic retry on 401 via the standard token refresh flow.
 * 
 * @param videoId - Video ID
 * @param cacheBustTimestamp - Optional timestamp to bypass browser cache
 */
async function fetchThumbnailBlob(videoId: number, cacheBustTimestamp?: number): Promise<string> {
  let url = `${getApiBaseUrl()}/videos/${videoId}/thumbnail`
  
  // Add cache-busting query param if timestamp provided
  if (cacheBustTimestamp) {
    url += `?t=${cacheBustTimestamp}`
  }
  
  const tokens = getTokens()
  const headers: Record<string, string> = {}
  
  if (tokens.accessToken) {
    headers.Authorization = `Bearer ${tokens.accessToken}`
  }

  const response = await fetch(url, {
    method: 'GET',
    headers,
    credentials: 'include',
  })

  if (!response.ok) {
    throw new APIError(
      response.statusText || 'Failed to fetch thumbnail',
      response.status
    )
  }

  const blob = await response.blob()
  return URL.createObjectURL(blob)
}

interface UseVideoThumbnailOptions {
  /** Whether to enable the query */
  enabled?: boolean
  /** Timestamp for cache-busting (e.g., from video_updated WebSocket event) */
  cacheBustTimestamp?: number
}

interface UseVideoThumbnailResult {
  /** The blob URL for the thumbnail, or undefined if not loaded */
  thumbnailUrl: string | undefined
  /** Whether the thumbnail is currently loading */
  isLoading: boolean
  /** Whether there was an error loading the thumbnail */
  isError: boolean
  /** The error object if loading failed */
  error: Error | null
  /** Force refetch the thumbnail (for manual refresh) */
  refetch: () => void
}

/**
 * Hook to fetch and manage a video thumbnail with authentication.
 * 
 * Handles:
 * - Authenticated fetch via Bearer token
 * - Blob URL creation and cleanup to prevent memory leaks
 * - Caching via TanStack Query
 * - Cache-busting via optional timestamp parameter
 * 
 * @param videoId - The ID of the video to fetch the thumbnail for
 * @param options - Optional configuration including cacheBustTimestamp
 * @returns Object with thumbnailUrl, loading state, error info, and refetch function
 */
export function useVideoThumbnail(
  videoId: number | null | undefined,
  options: UseVideoThumbnailOptions = {}
): UseVideoThumbnailResult {
  const { enabled = true, cacheBustTimestamp } = options
  const queryClient = useQueryClient()
  
  // Track blob URLs for cleanup
  const blobUrlRef = useRef<string | null>(null)

  // Include cacheBustTimestamp in query key so changes trigger refetch
  const query = useQuery({
    queryKey: ['video-thumbnail', videoId, cacheBustTimestamp],
    queryFn: async () => {
      if (!videoId) throw new Error('No video ID')
      return fetchThumbnailBlob(videoId, cacheBustTimestamp)
    },
    enabled: enabled && videoId != null,
    staleTime: 1000 * 60 * 60, // 1 hour - thumbnails rarely change
    gcTime: 1000 * 60 * 60 * 24, // Keep in cache for 24 hours
    retry: (failureCount, error) => {
      // Don't retry on 404 (video not found) or 401 (auth failure after refresh)
      if (error instanceof APIError && (error.status === 404 || error.status === 401)) {
        return false
      }
      return failureCount < 2
    },
  })

  // Cleanup previous blob URL when a new one is created or on unmount
  useEffect(() => {
    const currentUrl = query.data
    const previousUrl = blobUrlRef.current

    // If we have a new URL and it's different from the previous one
    if (currentUrl && currentUrl !== previousUrl) {
      // Revoke the old URL to free memory
      if (previousUrl) {
        URL.revokeObjectURL(previousUrl)
      }
      blobUrlRef.current = currentUrl
    }

    // Cleanup on unmount
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current)
        blobUrlRef.current = null
      }
    }
  }, [query.data])

  // Manual refetch that invalidates cache
  const refetch = useCallback(() => {
    if (videoId != null) {
      // Invalidate all thumbnail queries for this video (any timestamp)
      queryClient.invalidateQueries({ 
        queryKey: ['video-thumbnail', videoId],
        exact: false,
      })
    }
  }, [videoId, queryClient])

  return {
    thumbnailUrl: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch,
  }
}
