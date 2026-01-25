import { apiJson } from '../../../api/client'
import type { components } from '../generated'

// ============================================================================
// Type Definitions
// ============================================================================

export type HealthCheckResponse = components['schemas']['HealthCheckResponse']

// ============================================================================
// API Functions
// ============================================================================

/**
 * Check API health status.
 */
export async function getHealth(): Promise<HealthCheckResponse> {
  return apiJson<HealthCheckResponse>({ path: '/health', auth: 'none' })
}
