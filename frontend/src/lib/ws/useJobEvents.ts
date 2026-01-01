/**
 * Unified WebSocket hook for job event subscriptions.
 *
 * This hook provides a single WebSocket connection to /ws/events with support for:
 * - Authentication via first-message protocol
 * - Job subscriptions filtered by job IDs, job types, or video IDs
 * - Automatic reconnection with exponential backoff
 * - Initial state snapshot on subscription
 *
 * Replaces the deprecated useJobWebSocket hook.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getApiBaseUrl } from '../../api/client'

export type WSConnectionState = 'idle' | 'connecting' | 'connected' | 'disconnected' | 'error'

export type JobStatus = 'pending' | 'waiting' | 'running' | 'completed' | 'failed' | 'cancelled' | 'timeout'

export interface JobState {
  job_id: string
  job_type: string
  status: JobStatus
  progress: number // 0-1
  current_step: string
  processed_items: number
  total_items: number
  created_at: string
  started_at: string | null
  completed_at?: string | null
  metadata: Record<string, unknown>
  error?: string
  result?: Record<string, unknown>
  download_speed?: number // MB/s for download jobs
  eta_seconds?: number // ETA for download jobs
}

export interface UseJobEventsOptions {
  /** Filter to specific job IDs */
  jobIds?: string[] | null
  /** Filter to specific job types */
  jobTypes?: string[] | null
  /** Filter to jobs for specific video IDs (matches metadata.video_id) */
  videoIds?: number[] | null
  /** Whether to request initial active job state on subscription */
  includeActiveState?: boolean
  /** Whether to auto-connect on mount (default: true) */
  autoConnect?: boolean
}

interface WSEvent {
  event_type: string
  timestamp: string
  payload: Record<string, unknown>
}

function toWsBaseUrl(httpBaseUrl: string): string {
  const trimmed = httpBaseUrl.replace(/\/$/, '')
  if (trimmed.startsWith('https://')) return `wss://${trimmed.slice('https://'.length)}`
  if (trimmed.startsWith('http://')) return `ws://${trimmed.slice('http://'.length)}`
  if (trimmed.startsWith('wss://') || trimmed.startsWith('ws://')) return trimmed
  return `ws://${trimmed}`
}

function isValidJobState(data: unknown): data is Partial<JobState> & { job_id: string } {
  if (!data || typeof data !== 'object') return false
  const any = data as Record<string, unknown>
  return typeof any.job_id === 'string'
}

export function useJobEvents(accessToken: string | null, options: UseJobEventsOptions = {}) {
  const {
    jobIds = null,
    jobTypes = null,
    videoIds = null,
    includeActiveState = true,
    autoConnect = true,
  } = options

  const [connectionState, setConnectionState] = useState<WSConnectionState>('idle')
  const [jobs, setJobs] = useState<Map<string, JobState>>(new Map())
  const [lastError, setLastError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttempts = useRef(0)
  const isManualDisconnect = useRef(false)

  // Store options in refs to avoid re-creating connect function
  const optionsRef = useRef({ jobIds, jobTypes, videoIds, includeActiveState })
  optionsRef.current = { jobIds, jobTypes, videoIds, includeActiveState }

  const wsUrl = useMemo(() => {
    const base = toWsBaseUrl(getApiBaseUrl())
    return `${base}/ws/events`
  }, [])

  const handleJobEvent = useCallback((event: WSEvent) => {
    const { event_type, timestamp, payload } = event
    const jobId = payload.job_id as string | undefined

    if (!jobId) return

    // If filtering by videoIds, check if this job matches
    const { videoIds: filterVideoIds } = optionsRef.current
    if (filterVideoIds && filterVideoIds.length > 0) {
      const jobVideoId = (payload.metadata as Record<string, unknown> | undefined)?.video_id
      if (typeof jobVideoId !== 'number' || !filterVideoIds.includes(jobVideoId)) {
        // Check existing job metadata as fallback
        const existingJob = jobs.get(jobId)
        const existingVideoId = existingJob?.metadata?.video_id
        if (typeof existingVideoId !== 'number' || !filterVideoIds.includes(existingVideoId)) {
          return // Skip events for jobs not matching our video filter
        }
      }
    }

    switch (event_type) {
      case 'job_started':
        if (isValidJobState(payload)) {
          setJobs((prev) => {
            const next = new Map(prev)
            next.set(jobId, {
              job_id: jobId,
              job_type: typeof payload.job_type === 'string' ? payload.job_type : 'unknown',
              status: 'running',
              progress: typeof payload.progress === 'number' ? payload.progress : 0,
              current_step: typeof payload.current_step === 'string' ? payload.current_step : '',
              processed_items: typeof payload.processed_items === 'number' ? payload.processed_items : 0,
              total_items: typeof payload.total_items === 'number' ? payload.total_items : 0,
              created_at: typeof payload.created_at === 'string' ? payload.created_at : timestamp,
              started_at: timestamp,
              metadata: typeof payload.metadata === 'object' && payload.metadata !== null
                ? (payload.metadata as Record<string, unknown>)
                : {},
            })
            return next
          })
        }
        break

      case 'job_progress':
        setJobs((prev) => {
          const job = prev.get(jobId)
          if (!job) return prev

          const next = new Map(prev)
          next.set(jobId, {
            ...job,
            status: 'running',
            progress: typeof payload.progress === 'number' ? payload.progress : job.progress,
            current_step: typeof payload.current_step === 'string' ? payload.current_step : job.current_step,
            processed_items: typeof payload.processed_items === 'number' ? payload.processed_items : job.processed_items,
            total_items: typeof payload.total_items === 'number' ? payload.total_items : job.total_items,
            download_speed: typeof payload.download_speed === 'number' ? payload.download_speed : job.download_speed,
            eta_seconds: typeof payload.eta_seconds === 'number' ? payload.eta_seconds : job.eta_seconds,
          })
          return next
        })
        break

      case 'job_completed':
      case 'job_failed':
      case 'job_cancelled':
      case 'job_timeout': {
        const status = event_type.replace('job_', '') as JobStatus
        setJobs((prev) => {
          const job = prev.get(jobId)
          if (!job) {
            // Job wasn't tracked yet, create minimal entry
            const next = new Map(prev)
            next.set(jobId, {
              job_id: jobId,
              job_type: typeof payload.job_type === 'string' ? payload.job_type : 'unknown',
              status,
              progress: 1,
              current_step: status,
              processed_items: 0,
              total_items: 0,
              created_at: timestamp,
              started_at: null,
              completed_at: timestamp,
              metadata: typeof payload.metadata === 'object' && payload.metadata !== null
                ? (payload.metadata as Record<string, unknown>)
                : {},
              error: typeof payload.error === 'string' ? payload.error : undefined,
              result: typeof payload.result === 'object' && payload.result !== null
                ? (payload.result as Record<string, unknown>)
                : undefined,
            })
            return next
          }

          const next = new Map(prev)
          next.set(jobId, {
            ...job,
            status,
            progress: 1,
            completed_at: timestamp,
            error: typeof payload.error === 'string' ? payload.error : job.error,
            result: typeof payload.result === 'object' && payload.result !== null
              ? (payload.result as Record<string, unknown>)
              : job.result,
          })
          return next
        })
        break
      }
    }
  }, [jobs])

  const connect = useCallback(() => {
    if (!accessToken) {
      setConnectionState('error')
      setLastError('Missing access token for WebSocket auth')
      return
    }

    isManualDisconnect.current = false
    setConnectionState('connecting')

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      // Step 1: Send auth message
      try {
        ws.send(JSON.stringify({ type: 'auth', token: accessToken }))
      } catch (err) {
        console.error('Failed to send auth message:', err)
      }
    }

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(String(evt.data)) as unknown

        if (data && typeof data === 'object') {
          const any = data as Record<string, unknown>

          // Handle server ping
          if (any.type === 'ping') {
            try {
              ws.send(JSON.stringify({ type: 'pong' }))
            } catch {
              // ignore
            }
            return
          }

          // Handle auth responses
          if (any.type === 'auth_success') {
            setConnectionState('connected')
            setLastError(null)
            reconnectAttempts.current = 0

            // Step 2: Subscribe to jobs after auth succeeds
            const { jobIds, jobTypes, includeActiveState } = optionsRef.current
            try {
              ws.send(JSON.stringify({
                type: 'subscribe_jobs',
                job_types: jobTypes,
                job_ids: jobIds,
                include_active_state: includeActiveState,
              }))
            } catch (err) {
              console.error('Failed to subscribe to jobs:', err)
            }
            return
          }

          if (any.type === 'auth_error') {
            setConnectionState('error')
            setLastError(typeof any.message === 'string' ? any.message : 'WebSocket auth failed')
            return
          }

          // Handle subscribe success
          if (any.type === 'subscribe_jobs_success') {
            console.log('Subscribed to job events')
            return
          }

          // Handle job state snapshot (initial state)
          if (any.type === 'job_state' && Array.isArray(any.jobs)) {
            const { videoIds: filterVideoIds } = optionsRef.current
            const jobsMap = new Map<string, JobState>()

            for (const job of any.jobs) {
              if (isValidJobState(job)) {
                // Apply videoIds filter if specified
                if (filterVideoIds && filterVideoIds.length > 0) {
                  const jobVideoId = (job.metadata as Record<string, unknown> | undefined)?.video_id
                  if (typeof jobVideoId !== 'number' || !filterVideoIds.includes(jobVideoId)) {
                    continue
                  }
                }

                jobsMap.set(job.job_id, {
                  job_id: job.job_id,
                  job_type: typeof job.job_type === 'string' ? job.job_type : 'unknown',
                  status: (job.status as JobStatus) ?? 'pending',
                  progress: typeof job.progress === 'number' ? job.progress : 0,
                  current_step: typeof job.current_step === 'string' ? job.current_step : '',
                  processed_items: typeof job.processed_items === 'number' ? job.processed_items : 0,
                  total_items: typeof job.total_items === 'number' ? job.total_items : 0,
                  created_at: typeof job.created_at === 'string' ? job.created_at : '',
                  started_at: typeof job.started_at === 'string' ? job.started_at : null,
                  completed_at: typeof job.completed_at === 'string' ? job.completed_at : undefined,
                  metadata: typeof job.metadata === 'object' && job.metadata !== null
                    ? (job.metadata as Record<string, unknown>)
                    : {},
                  error: typeof job.error === 'string' ? job.error : undefined,
                  result: typeof job.result === 'object' && job.result !== null
                    ? (job.result as Record<string, unknown>)
                    : undefined,
                  download_speed: typeof job.download_speed === 'number' ? job.download_speed : undefined,
                  eta_seconds: typeof job.eta_seconds === 'number' ? job.eta_seconds : undefined,
                })
              }
            }

            setJobs(jobsMap)
            return
          }

          // Handle job events
          if (any.event_type && typeof any.event_type === 'string') {
            handleJobEvent(any as unknown as WSEvent)
            return
          }
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err)
      }
    }

    ws.onerror = () => {
      setConnectionState('error')
      setLastError('WebSocket error')
    }

    ws.onclose = () => {
      setConnectionState('disconnected')
      wsRef.current = null

      // Only attempt reconnection if not manually disconnected
      if (!isManualDisconnect.current && accessToken) {
        // Exponential backoff: 1s, 2s, 4s, 8s... up to 30s max
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
        reconnectAttempts.current += 1

        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, delay)
      }
    }
  }, [wsUrl, accessToken, handleJobEvent])

  const disconnect = useCallback(() => {
    isManualDisconnect.current = true

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      try {
        wsRef.current.close()
      } catch {
        // ignore
      }
      wsRef.current = null
    }

    setConnectionState('disconnected')
  }, [])

  const updateSubscription = useCallback((newOptions: Partial<UseJobEventsOptions>) => {
    // Update options ref
    if (newOptions.jobIds !== undefined) optionsRef.current.jobIds = newOptions.jobIds
    if (newOptions.jobTypes !== undefined) optionsRef.current.jobTypes = newOptions.jobTypes
    if (newOptions.videoIds !== undefined) optionsRef.current.videoIds = newOptions.videoIds
    if (newOptions.includeActiveState !== undefined) {
      optionsRef.current.includeActiveState = newOptions.includeActiveState
    }

    // Send new subscription if connected
    if (wsRef.current && connectionState === 'connected') {
      try {
        wsRef.current.send(JSON.stringify({
          type: 'subscribe_jobs',
          job_types: optionsRef.current.jobTypes,
          job_ids: optionsRef.current.jobIds,
          include_active_state: optionsRef.current.includeActiveState,
        }))
      } catch (err) {
        console.error('Failed to update subscription:', err)
      }
    }
  }, [connectionState])

  // Clear jobs when filters change
  useEffect(() => {
    setJobs(new Map())
  }, [jobIds, jobTypes, videoIds])

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect && accessToken) {
      connect()
    }

    return () => {
      disconnect()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, autoConnect])

  // Get job by ID helper
  const getJob = useCallback((jobId: string): JobState | undefined => {
    return jobs.get(jobId)
  }, [jobs])

  // Get jobs by video ID helper
  const getJobsForVideo = useCallback((videoId: number): JobState[] => {
    const result: JobState[] = []
    for (const job of jobs.values()) {
      if (job.metadata?.video_id === videoId) {
        result.push(job)
      }
    }
    return result
  }, [jobs])

  // Check if any job is active for a video
  const hasActiveJobForVideo = useCallback((videoId: number): boolean => {
    for (const job of jobs.values()) {
      if (job.metadata?.video_id === videoId) {
        if (job.status === 'pending' || job.status === 'waiting' || job.status === 'running') {
          return true
        }
      }
    }
    return false
  }, [jobs])

  return {
    connectionState,
    jobs,
    lastError,
    connect,
    disconnect,
    updateSubscription,
    getJob,
    getJobsForVideo,
    hasActiveJobForVideo,
  }
}
