import { useEffect, useMemo, useRef, useState } from 'react'
import { getApiBaseUrl } from '../../../api/client'

type WSState = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface JobData {
  job_id: string
  job_type: string
  status: 'pending' | 'waiting' | 'running' | 'completed' | 'failed' | 'cancelled' | 'timeout'
  progress: number  // 0-1
  current_step: string
  processed_items: number
  total_items: number
  created_at: string
  started_at: string | null
  completed_at?: string | null
  metadata: Record<string, unknown>
  error?: string
  result?: Record<string, unknown>
  download_speed?: number  // MB/s for download jobs
  eta_seconds?: number     // ETA for download jobs
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

export function useActivityWebSocket(accessToken: string | null) {
  const [state, setState] = useState<WSState>('disconnected')
  const [jobs, setJobs] = useState<Map<string, JobData>>(new Map())
  const [lastError, setLastError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttempts = useRef(0)

  const wsUrl = useMemo(() => {
    const base = toWsBaseUrl(getApiBaseUrl())
    return `${base}/ws/events`
  }, [])

  useEffect(() => {
    if (!accessToken) {
      setState('disconnected')
      return
    }

    function connect() {
      if (!accessToken) return

      setState('connecting')
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        // Send auth message
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
              setState('connected')
              setLastError(null)
              reconnectAttempts.current = 0

              // Subscribe to all jobs with active state
              try {
                ws.send(JSON.stringify({
                  type: 'subscribe_jobs',
                  job_types: null,
                  job_ids: null,
                  include_active_state: true
                }))
              } catch (err) {
                console.error('Failed to subscribe to jobs:', err)
              }
              return
            }

            if (any.type === 'auth_error') {
              setState('error')
              setLastError(typeof any.message === 'string' ? any.message : 'WebSocket auth failed')
              return
            }

            // Handle subscribe success
            if (any.type === 'subscribe_jobs_success') {
              console.log('Subscribed to job events')
              return
            }

            // Handle job state (initial state snapshot)
            if (any.type === 'job_state' && Array.isArray(any.jobs)) {
              const jobsMap = new Map<string, JobData>()
              for (const job of any.jobs) {
                if (isValidJobData(job)) {
                  jobsMap.set(job.job_id, job as JobData)
                }
              }
              setJobs(jobsMap)
              return
            }

            // Handle job events
            if (any.event_type && typeof any.event_type === 'string') {
              handleJobEvent(any as WSEvent)
              return
            }
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      ws.onerror = () => {
        setState('error')
        setLastError('WebSocket error')
      }

      ws.onclose = () => {
        setState('disconnected')
        wsRef.current = null

        // Attempt reconnection with exponential backoff
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
        reconnectAttempts.current += 1

        reconnectTimeoutRef.current = setTimeout(() => {
          if (accessToken) {
            connect()
          }
        }, delay)
      }
    }

    function handleJobEvent(event: WSEvent) {
      const { event_type, timestamp, payload } = event

      switch (event_type) {
        case 'job_started':
          if (isValidJobData(payload)) {
            setJobs(prev => {
              const next = new Map(prev)
              next.set(payload.job_id, {
                ...payload as JobData,
                created_at: payload.created_at || timestamp,
                started_at: timestamp,
              })
              return next
            })
          }
          break

        case 'job_progress':
          if (payload.job_id && typeof payload.job_id === 'string') {
            setJobs(prev => {
              const job = prev.get(payload.job_id as string)
              if (!job) return prev

              const next = new Map(prev)
              next.set(payload.job_id as string, {
                ...job,
                progress: typeof payload.progress === 'number' ? payload.progress : job.progress,
                current_step: typeof payload.current_step === 'string' ? payload.current_step : job.current_step,
                processed_items: typeof payload.processed_items === 'number' ? payload.processed_items : job.processed_items,
                total_items: typeof payload.total_items === 'number' ? payload.total_items : job.total_items,
                download_speed: typeof payload.download_speed === 'number' ? payload.download_speed : job.download_speed,
                eta_seconds: typeof payload.eta_seconds === 'number' ? payload.eta_seconds : job.eta_seconds,
              })
              return next
            })
          }
          break

        case 'job_completed':
        case 'job_failed':
        case 'job_cancelled':
        case 'job_timeout':
          if (payload.job_id && typeof payload.job_id === 'string') {
            const status = event_type.replace('job_', '') as JobData['status']
            setJobs(prev => {
              const job = prev.get(payload.job_id as string)
              if (!job) return prev

              const next = new Map(prev)
              next.set(payload.job_id as string, {
                ...job,
                status,
                completed_at: timestamp,
                error: typeof payload.error === 'string' ? payload.error : undefined,
                result: typeof payload.result === 'object' && payload.result !== null ? payload.result as Record<string, unknown> : undefined,
              })
              return next
            })
          }
          break
      }
    }

    function isValidJobData(data: unknown): data is Partial<JobData> & { job_id: string } {
      if (!data || typeof data !== 'object') return false
      const any = data as Record<string, unknown>
      return typeof any.job_id === 'string'
    }

    // Start connection
    connect()

    // Cleanup
    return () => {
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
    }
  }, [wsUrl, accessToken])

  return { state, jobs, lastError }
}
