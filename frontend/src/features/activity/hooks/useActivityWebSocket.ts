/**
 * Activity Monitor WebSocket hook.
 *
 * This is a thin wrapper around the unified useJobEvents hook that provides
 * backwards-compatible interface for the Activity Monitor page.
 *
 * Composes useJobEvents to subscribe to all jobs with active state.
 */

import { useJobEvents, type JobState, type WSConnectionState } from '../../../lib/ws/useJobEvents'

// Re-export JobData as alias for JobState for backwards compatibility
export type JobData = JobState

// Map connection states for backwards compatibility
type WSState = 'connecting' | 'connected' | 'disconnected' | 'error'

function mapConnectionState(state: WSConnectionState): WSState {
  switch (state) {
    case 'idle':
      return 'disconnected'
    case 'connecting':
      return 'connecting'
    case 'connected':
      return 'connected'
    case 'disconnected':
      return 'disconnected'
    case 'error':
      return 'error'
  }
}

export function useActivityWebSocket(accessToken: string | null) {
  const {
    connectionState,
    jobs,
    lastError,
  } = useJobEvents(accessToken, {
    // Subscribe to all jobs with active state for activity monitor
    jobIds: null,
    jobTypes: null,
    videoIds: null,
    includeActiveState: true,
    autoConnect: true,
  })

  return {
    state: mapConnectionState(connectionState),
    jobs,
    lastError,
  }
}
