/* eslint-disable @typescript-eslint/no-explicit-any -- Settings system uses dynamic config types */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { updateConfig } from '../../../lib/api/endpoints/config'
import { configKeys } from '../../../lib/api/queryKeys'
import type {
  ConfigUpdateRequest,
  ConfigUpdateResponse,
  ConfigConflictError,
} from '../../../lib/api/endpoints/config'

export interface UseConfigUpdateOptions {
  onConflict?: (error: ConfigConflictError) => void
}

/**
 * Hook to update configuration with safety checks and conflict handling.
 *
 * Automatically handles:
 * - Success toast notifications based on safety level
 * - Config query invalidation
 * - 409 Conflict errors (calls onConflict callback)
 * - Other errors (shows error toast)
 */
export function useConfigUpdate(options?: UseConfigUpdateOptions) {
  const queryClient = useQueryClient()

  return useMutation<ConfigUpdateResponse, any, ConfigUpdateRequest>({
    mutationFn: updateConfig,
    onSuccess: (response) => {
      // Show toast based on safety level
      if (response.safety_level === 'safe') {
        toast.success('Settings updated', {
          description: 'Changes applied successfully',
        })
      } else if (response.safety_level === 'requires_reload') {
        const actions = response.required_actions.map((a) => a.description).join(', ')
        toast.warning('Settings updated - reload required', {
          description: actions || 'Some components may need to be reloaded',
        })
      } else if (response.safety_level === 'affects_state') {
        const actions = response.required_actions.map((a) => a.description).join(', ')
        toast.warning('Settings updated - restart may be required', {
          description: actions || 'Restart the application for changes to take effect',
        })
      }

      // Invalidate config queries
      queryClient.invalidateQueries({ queryKey: configKeys.all })
    },
    onError: (error: any) => {
      // Handle 409 Conflict (unsafe change without force=true)
      if (error.status === 409 && error.detail) {
        const conflictError = error.detail as ConfigConflictError
        if (options?.onConflict) {
          options.onConflict(conflictError)
        }
        return
      }

      // Other errors
      toast.error('Failed to update settings', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })
}
