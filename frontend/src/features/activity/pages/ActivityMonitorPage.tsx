import { useEffect, useSyncExternalStore } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useAuthTokens } from '../../../auth/useAuthTokens'
import { useJobEvents, type JobState, type JobStatus } from '../../../lib/ws/useJobEvents'
import { useActiveJobs, useCompletedJobs, useFailedJobs } from '../hooks/useJobsQuery'
import { SCHEDULED_MAINTENANCE_JOB_TYPES } from '../constants'
import PageHeader from '../../../components/layout/PageHeader'
import './ActivityMonitorPage.css'

type JobDeltaState = {
  active: number
  completed: number
  failed: number
}

const jobDeltaStore = (() => {
  const listeners = new Set<() => void>()
  const failedStatuses = new Set<JobStatus>(['failed', 'cancelled', 'timeout'])
  const activeStatuses = new Set<JobStatus>(['pending', 'waiting', 'running'])

  let baselineKey: string | null = null
  let initialized = false
  let jobStatus = new Map<string, JobStatus>()
  let deltas: JobDeltaState = { active: 0, completed: 0, failed: 0 }

  const emit = () => {
    for (const listener of listeners) {
      listener()
    }
  }

  return {
    subscribe(listener: () => void) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    getSnapshot(): JobDeltaState {
      return deltas
    },
    reset(nextKey: string) {
      if (baselineKey === nextKey) return
      baselineKey = nextKey
      initialized = false
      jobStatus = new Map()
      deltas = { active: 0, completed: 0, failed: 0 }
      emit()
    },
    update(wsJobsMap: Map<string, JobState>, maintenanceTypes: Set<string>) {
      if (!initialized) {
        jobStatus = new Map()
        for (const [jobId, job] of wsJobsMap) {
          jobStatus.set(jobId, job.status)
        }
        initialized = true
        return
      }

      const currentIds = new Set(wsJobsMap.keys())
      for (const jobId of jobStatus.keys()) {
        if (!currentIds.has(jobId)) {
          jobStatus.delete(jobId)
        }
      }

      let activeDeltaNext = 0
      let completedDeltaNext = 0
      let failedDeltaNext = 0

      for (const [jobId, job] of wsJobsMap) {
        const prevStatus = jobStatus.get(jobId)
        if (prevStatus === job.status) continue

        if (!maintenanceTypes.has(job.job_type)) {
          if (prevStatus && activeStatuses.has(prevStatus)) {
            activeDeltaNext -= 1
          }
          if (activeStatuses.has(job.status)) {
            activeDeltaNext += 1
          }
        }

        if (prevStatus === 'completed') {
          completedDeltaNext -= 1
        } else if (prevStatus && failedStatuses.has(prevStatus)) {
          failedDeltaNext -= 1
        }

        if (job.status === 'completed') {
          completedDeltaNext += 1
        } else if (failedStatuses.has(job.status)) {
          failedDeltaNext += 1
        }

        jobStatus.set(jobId, job.status)
      }

      if (activeDeltaNext || completedDeltaNext || failedDeltaNext) {
        deltas = {
          active: deltas.active + activeDeltaNext,
          completed: deltas.completed + completedDeltaNext,
          failed: deltas.failed + failedDeltaNext,
        }
        emit()
      }
    },
  }
})()

export default function ActivityMonitorPage() {
  const { accessToken } = useAuthTokens()
  const location = useLocation()

  // WebSocket connection for live indicator
  const { connectionState, jobs: wsJobs } = useJobEvents(accessToken, {
    includeActiveState: false,
    autoConnect: true,
  })

  // Fetch counts for tab badges from REST API
  const { data: activeData } = useActiveJobs({ enabled: true })
  const { data: completedData } = useCompletedJobs({ limit: 1 }, { enabled: true })
  const { data: failedData } = useFailedJobs({ limit: 1 }, { enabled: true })

  const activeBaseline = activeData?.jobs
    ? activeData.jobs.filter(job => !SCHEDULED_MAINTENANCE_JOB_TYPES.has(job.type)).length
    : 0

  const completedTotal = completedData?.total ?? 0
  const failedTotal = failedData?.total ?? 0
  const baselineKey = `${activeBaseline}|${completedTotal}|${failedTotal}`

  const deltas = useSyncExternalStore(
    jobDeltaStore.subscribe,
    jobDeltaStore.getSnapshot,
  )

  useEffect(() => {
    jobDeltaStore.reset(baselineKey)
  }, [baselineKey])

  useEffect(() => {
    if (!completedData || !failedData) return
    jobDeltaStore.update(wsJobs, SCHEDULED_MAINTENANCE_JOB_TYPES)
  }, [wsJobs, completedData, failedData, baselineKey])

  const activeCount = Math.max(0, activeBaseline + deltas.active)
  const historyCount = Math.max(0, completedTotal + deltas.completed) + Math.max(0, failedTotal + deltas.failed)

  // Determine which tab should be highlighted for "end" matching
  const isActiveTab = location.pathname === '/activity' || location.pathname === '/activity/active'

  const wsConnected = connectionState === 'connected'

  return (
    <div className="activityMonitor">
      <PageHeader
        title="Activity Monitor"
        iconSrc="/fuzzbin-icon.png"
        iconAlt="Fuzzbin"
        accent="var(--channel-manage)"
        actions={
          <div className="activityLiveIndicator">
            <div className={`liveDot ${wsConnected ? 'liveDotConnected' : ''}`} />
            <span>{wsConnected ? 'LIVE' : connectionState === 'connecting' ? 'CONNECTING...' : 'DISCONNECTED'}</span>
          </div>
        }
        navItems={[
          { label: 'Library', to: '/library' },
          { label: 'Import', to: '/import' },
          { label: 'Activity', to: '/activity' },
          { label: 'Settings', to: '/settings' },
        ]}
        subNavItems={[
          { label: `Active (${activeCount})`, to: '/activity/active', end: isActiveTab },
          { label: `History (${historyCount})`, to: '/activity/history' },
        ]}
        subNavLabel="Job States"
      />

      <div className="activityContent">
        <Outlet />
      </div>
    </div>
  )
}
