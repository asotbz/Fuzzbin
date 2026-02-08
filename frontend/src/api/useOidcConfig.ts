import { useQuery } from '@tanstack/react-query'
import { getOidcConfig, type OIDCConfigResponse } from '../lib/api/endpoints/oidc'

const oidcKeys = {
  all: ['oidc'] as const,
  config: () => [...oidcKeys.all, 'config'] as const,
}

/**
 * Hook to check whether OIDC login is available.
 * Cached for the session lifetime (staleTime: Infinity).
 */
export function useOidcConfig() {
  return useQuery<OIDCConfigResponse>({
    queryKey: oidcKeys.config(),
    queryFn: getOidcConfig,
    staleTime: Infinity,
    retry: false,
  })
}
