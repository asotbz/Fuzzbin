import { useQuery } from '@tanstack/react-query'
import { getConfigHistory } from '../../../lib/api/endpoints/config'
import { configKeys } from '../../../lib/api/queryKeys'
import type { ConfigHistoryResponse } from '../../../lib/api/endpoints/config'

/**
 * Hook to fetch configuration change history.
 */
export function useConfigHistory() {
  return useQuery<ConfigHistoryResponse>({
    queryKey: configKeys.history(),
    queryFn: getConfigHistory,
    staleTime: 10000, // 10 seconds
  })
}
