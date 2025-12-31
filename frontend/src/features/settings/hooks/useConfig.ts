import { useQuery } from '@tanstack/react-query'
import { getConfig } from '../../../lib/api/endpoints/config'
import { configKeys } from '../../../lib/api/queryKeys'
import type { ConfigResponse } from '../../../lib/api/endpoints/config'

/**
 * Hook to fetch the current configuration.
 */
export function useConfig() {
  return useQuery<ConfigResponse>({
    queryKey: configKeys.config(),
    queryFn: getConfig,
    staleTime: 30000, // 30 seconds
    refetchOnWindowFocus: true,
  })
}
