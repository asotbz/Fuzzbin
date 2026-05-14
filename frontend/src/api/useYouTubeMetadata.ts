import { useQuery } from '@tanstack/react-query'
import { getYouTubeMetadata } from '../lib/api/endpoints/spotify'
import type { YouTubeMetadataResponse } from '../lib/api/types'

/**
 * Fetches YouTube video metadata (channel, view count, duration, availability)
 * for a given YouTube ID. Query is disabled when `youtubeId` is null/empty,
 * mirroring the previous "if (!youtubeId) return null" behavior of the in-row
 * effect this hook replaces.
 */
export function useYouTubeMetadata(youtubeId: string | null | undefined): {
  data: YouTubeMetadataResponse | null
  isLoading: boolean
} {
  const query = useQuery<YouTubeMetadataResponse>({
    queryKey: ['youtube-metadata', youtubeId],
    queryFn: () => getYouTubeMetadata({ youtube_id: youtubeId! }),
    enabled: Boolean(youtubeId),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })

  return {
    data: query.data ?? null,
    isLoading: Boolean(youtubeId) && query.isLoading,
  }
}
