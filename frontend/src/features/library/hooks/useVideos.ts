import { useQuery } from '@tanstack/react-query'
import { listVideos } from '../../../lib/api/endpoints/videos'
import { videosKeys } from '../../../lib/api/queryKeys'
import type { ListVideosQuery, ListVideosResponse } from '../../../lib/api/types'

export function useVideos(query: ListVideosQuery) {
  return useQuery<ListVideosResponse>({
    queryKey: videosKeys.list(query),
    queryFn: () => listVideos(query),
  })
}
