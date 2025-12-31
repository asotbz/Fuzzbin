import { useEffect, useMemo, useRef, useState } from 'react'
import { getApiBaseUrl } from '../../api/client'

type WSState = 'idle' | 'connecting' | 'connected' | 'closed' | 'error'

export type JobProgressUpdate = {
  job_id: string
  status: string
  progress: number
  current_step: string
  processed_items: number
  total_items: number
  error?: string | null
  result?: Record<string, unknown> | null
}

function toWsBaseUrl(httpBaseUrl: string): string {
  const trimmed = httpBaseUrl.replace(/\/$/, '')
  if (trimmed.startsWith('https://')) return `wss://${trimmed.slice('https://'.length)}`
  if (trimmed.startsWith('http://')) return `ws://${trimmed.slice('http://'.length)}`
  // fallback: assume already ws(s)
  if (trimmed.startsWith('wss://') || trimmed.startsWith('ws://')) return trimmed
  return `ws://${trimmed}`
}

function isJobProgressUpdate(value: unknown): value is JobProgressUpdate {
  if (!value || typeof value !== 'object') return false
  const any = value as Record<string, unknown>
  return (
    typeof any.job_id === 'string' &&
    typeof any.status === 'string' &&
    typeof any.progress === 'number' &&
    typeof any.current_step === 'string' &&
    typeof any.processed_items === 'number' &&
    typeof any.total_items === 'number'
  )
}

export function useJobWebSocket(jobId: string | null, accessToken: string | null) {
  const [state, setState] = useState<WSState>('idle')
  const [lastUpdate, setLastUpdate] = useState<JobProgressUpdate | null>(null)
  const [lastError, setLastError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)

  const wsUrl = useMemo(() => {
    if (!jobId) return null
    const base = toWsBaseUrl(getApiBaseUrl())
    return `${base}/ws/jobs/${encodeURIComponent(jobId)}`
  }, [jobId])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Resetting state when job changes is intentional
    setLastUpdate(null)
     
    setLastError(null)

    if (!jobId || !wsUrl) {
      setState('idle')
      return
    }

    // If auth is enabled server-side, we must send the auth first-message.
    // If auth is disabled, server will ignore it, so it's safe to send anyway.
    if (!accessToken) {
      setState('error')
      setLastError('Missing access token for WebSocket auth')
      return
    }

    setState('connecting')

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      try {
        ws.send(JSON.stringify({ type: 'auth', token: accessToken }))
      } catch {
        // ignore
      }
    }

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(String(evt.data)) as unknown

        if (data && typeof data === 'object') {
          const any = data as Record<string, unknown>

          // server keepalive ping
          if (any.type === 'ping') {
            try {
              ws.send(JSON.stringify({ type: 'ping' }))
            } catch {
              // ignore
            }
            return
          }

          // auth responses
          if (any.type === 'auth_success') {
            setState('connected')
            return
          }
          if (any.type === 'auth_error') {
            setState('error')
            setLastError(typeof any.message === 'string' ? any.message : 'WebSocket auth failed')
            return
          }
        }

        if (isJobProgressUpdate(data)) {
          setState('connected')
          setLastUpdate(data)
          return
        }

        // ignore unknown messages
      } catch {
        // ignore
      }
    }

    ws.onerror = () => {
      setState('error')
      setLastError('WebSocket error')
    }

    ws.onclose = () => {
      setState('closed')
    }

    return () => {
      try {
        ws.close()
      } catch {
        // ignore
      }
      wsRef.current = null
    }
  }, [jobId, wsUrl, accessToken])

  return { state, lastUpdate, lastError }
}
