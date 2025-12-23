import { useQuery } from '@tanstack/react-query'
import { getFacets } from '../../../lib/api/endpoints/search'
import { searchKeys } from '../../../lib/api/queryKeys'
import type { FacetsQuery, FacetsResponse } from '../../../lib/api/types'

export function useFacets(query: FacetsQuery) {
  return useQuery<FacetsResponse>({
    queryKey: searchKeys.facets(query),
    queryFn: () => getFacets(query),
    staleTime: 10 * 60 * 1000,
  })
}
