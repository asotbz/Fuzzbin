import { apiJson } from '../../../api/client'

// ============================================================================
// Type Definitions
// ============================================================================

export type OIDCConfigResponse = {
  enabled: boolean
  provider_name: string
}

export type OIDCStartResponse = {
  auth_url: string
  state: string
}

export type OIDCExchangeResponse = {
  access_token: string
  token_type: string
  expires_in: number
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Check whether OIDC login is available and get the provider display name.
 */
export async function getOidcConfig(): Promise<OIDCConfigResponse> {
  return apiJson<OIDCConfigResponse>({ path: '/auth/oidc/config', auth: 'none' })
}

/**
 * Start the OIDC Authorization Code + PKCE flow.
 * Returns the IdP authorization URL and the opaque state value.
 */
export async function startOidcLogin(): Promise<OIDCStartResponse> {
  return apiJson<OIDCStartResponse>({
    method: 'POST',
    path: '/auth/oidc/start',
    auth: 'none',
  })
}

/**
 * Exchange the IdP authorization code for local JWT tokens.
 */
export async function exchangeOidcCode(code: string, state: string): Promise<OIDCExchangeResponse> {
  return apiJson<OIDCExchangeResponse>({
    method: 'POST',
    path: '/auth/oidc/exchange',
    body: { code, state },
    auth: 'none',
  })
}
