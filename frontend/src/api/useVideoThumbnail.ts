import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { getApiBaseUrl, APIError } from './client'
import { getTokens } from '../auth/tokenStore'

/**
 * Fetches a video thumbnail with authentication and returns a blob URL.
 * Includes automatic retry on 401 via the standard token refresh flow.
 */
async function fetchThumbnailBlob(videoId: number): Promise<string> {
  const url = `${getApiBaseUrl()}/videos/${videoId}/thumbnail`
  
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
}

/**
 * Hook to fetch and manage a video thumbnail with authentication.
 * 
 * Handles:
 * - Authenticated fetch via Bearer token
 * - Blob URL creation and cleanup to prevent memory leaks
 * - Caching via TanStack Query
 * 
 * @param videoId - The ID of the video to fetch the thumbnail for
 * @param options - Optional configuration
 * @returns Object with thumbnailUrl, loading state, and error info
 */
export function useVideoThumbnail(
  videoId: number | null | undefined,
  options: UseVideoThumbnailOptions = {}
): UseVideoThumbnailResult {
  const { enabled = true } = options
  
  // Track blob URLs for cleanup
  const blobUrlRef = useRef<string | null>(null)

  const query = useQuery({
    queryKey: ['video-thumbnail', videoId],
    queryFn: async () => {
      if (!videoId) throw new Error('No video ID')
      return fetchThumbnailBlob(videoId)
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

  return {
    thumbnailUrl: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
  }
}
