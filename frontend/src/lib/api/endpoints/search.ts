import { apiJson } from '../../../api/client'
import type { FacetsQuery, FacetsResponse, SuggestionQuery, SuggestionsResponse } from '../types'
import { toQueryString } from '../queryString'

export async function getFacets(query: FacetsQuery): Promise<FacetsResponse> {
  return apiJson<FacetsResponse>({
    path: `/search/facets${toQueryString(query as Record<string, unknown>)}`,
  })
}

export async function getSuggestions(query: SuggestionQuery): Promise<SuggestionsResponse> {
  return apiJson<SuggestionsResponse>({
    path: `/search/suggestions${toQueryString(query as Record<string, unknown>)}`,
  })
}
