import { useQuery } from '@tanstack/react-query'
import { getHealth, type HealthCheckResponse } from '../lib/api/endpoints/health'
import { healthKeys } from '../lib/api/queryKeys'

/**
 * Hook to fetch API health status.
 */
export function useHealth() {
  return useQuery<HealthCheckResponse>({
    queryKey: healthKeys.status(),
    queryFn: getHealth,
    staleTime: 60000, // 1 minute
    retry: 1,
  })
}
