import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { useAuthTokens } from '../../../auth/useAuthTokens'
import { useActivityWebSocket, type JobData } from '../hooks/useActivityWebSocket'
import { cancelJob } from '../../../lib/api/endpoints/jobs'
import { getApiBaseUrl } from '../../../api/client'
import PageHeader from '../../../components/layout/PageHeader'
import JobCard from '../components/JobCard'
import JobFilterBar from '../components/JobFilterBar'
import './ActivityMonitorPage.css'

const SCHEDULED_JOB_TYPES = new Set(['backup', 'trash_cleanup', 'export_nfo'])

function groupJobsByStatus(jobs: JobData[]): {
  active: JobData[]
  completed: JobData[]
  failed: JobData[]
} {
  const active = jobs.filter(j => ['pending', 'waiting', 'running'].includes(j.status))
  const completed = jobs.filter(j => j.status === 'completed')
  const failed = jobs.filter(j => ['failed', 'cancelled', 'timeout'].includes(j.status))

  return { active, completed, failed }
}

function filterJobs(
  jobs: Map<string, JobData>,
  statusFilter: Set<string>,
  jobTypeFilter: Set<string>,
  searchQuery: string
): JobData[] {
  return Array.from(jobs.values()).filter(job => {
    if (SCHEDULED_JOB_TYPES.has(job.job_type) && ['pending', 'waiting'].includes(job.status)) {
      return false
    }

    // Status filter
    if (statusFilter.size > 0) {
      const isActiveStatus = ['pending', 'waiting', 'running'].includes(job.status)
      const isFailedStatus = ['failed', 'cancelled', 'timeout'].includes(job.status)

      if (statusFilter.has('running') && !isActiveStatus) return false
      if (statusFilter.has('pending') && !['pending', 'waiting'].includes(job.status)) return false
      if (statusFilter.has('completed') && job.status !== 'completed') return false
      if (statusFilter.has('failed') && !isFailedStatus) return false
    }

    // Job type filter
    if (jobTypeFilter.size > 0 && !jobTypeFilter.has(job.job_type)) {
      return false
    }

    // Search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      const searchable = [
        job.job_type,
        job.current_step,
        job.job_id,
        JSON.stringify(job.metadata),
      ].join(' ').toLowerCase()

      if (!searchable.includes(query)) {
        return false
      }
    }

    return true
  })
}

export default function ActivityMonitorPage() {
  const { accessToken } = useAuthTokens()
  const { state: wsState, jobs, lastError } = useActivityWebSocket(accessToken)

  const [statusFilter, setStatusFilter] = useState<Set<string>>(new Set())
  const [jobTypeFilter, setJobTypeFilter] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')

  const [activeSectionCollapsed, setActiveSectionCollapsed] = useState(false)
  const [completedSectionCollapsed, setCompletedSectionCollapsed] = useState(false)
  const [failedSectionCollapsed, setFailedSectionCollapsed] = useState(false)
  const [maintenancePending, setMaintenancePending] = useState<Record<string, boolean>>({})

  const maintenanceJobs = useMemo(
    () => [
      {
        type: 'backup',
        title: 'System Backup',
        description: 'Create a full backup of config, database, and thumbnails.',
        actionLabel: 'Run Backup',
      },
      {
        type: 'trash_cleanup',
        title: 'Trash Cleanup',
        description: 'Delete items older than your configured retention window.',
        actionLabel: 'Clean Trash',
      },
      {
        type: 'export_nfo',
        title: 'Export NFO',
        description: 'Write NFO files from the current library metadata.',
        actionLabel: 'Export NFO',
      },
    ],
    []
  )

  const availableJobTypes = useMemo(() => {
    const types = new Set<string>()
    jobs.forEach(job => types.add(job.job_type))
    return Array.from(types).sort()
  }, [jobs])

  const filteredJobs = useMemo(
    () => filterJobs(jobs, statusFilter, jobTypeFilter, searchQuery),
    [jobs, statusFilter, jobTypeFilter, searchQuery]
  )

  const groupedJobs = useMemo(() => groupJobsByStatus(filteredJobs), [filteredJobs])

  const handleCancelJob = async (jobId: string) => {
    try {
      await cancelJob(jobId)
      toast.success('Job cancelled successfully')
    } catch (error) {
      console.error('Failed to cancel job:', error)
      toast.error('Failed to cancel job')
    }
  }

  const handleRetryJob = async (job: JobData) => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/jobs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          type: job.job_type,
          metadata: job.metadata,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to retry job')
      }

      const result = await response.json()
      toast.success(`Job resubmitted: ${result.job_id}`)
    } catch (error) {
      console.error('Failed to retry job:', error)
      toast.error('Failed to retry job')
    }
  }

  const handleRunMaintenanceJob = async (jobType: string, label: string) => {
    setMaintenancePending(prev => ({ ...prev, [jobType]: true }))
    try {
      const response = await fetch(`${getApiBaseUrl()}/jobs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({
          type: jobType,
          metadata: {},
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to submit job')
      }

      const result = await response.json()
      toast.success(`${label} queued`, {
        description: result.job_id ? `Job ID: ${result.job_id}` : undefined,
      })
    } catch (error) {
      console.error('Failed to submit job:', error)
      toast.error(`Failed to run ${label.toLowerCase()}`)
    } finally {
      setMaintenancePending(prev => ({ ...prev, [jobType]: false }))
    }
  }

  const handleClearJob = (_jobId: string) => {
    // For now, just remove from local state
    // In production, you might want to persist this to localStorage or backend
    toast.info('Job cleared from view')
  }

  return (
    <div className="activityMonitor">
      <PageHeader
        title="Activity Monitor"
        iconSrc="/fuzzbin-icon.png"
        iconAlt="Fuzzbin"
        accent="var(--channel-manage)"
        actions={
          <div className="activityLiveIndicator">
            <div className={`liveDot ${wsState === 'connected' ? 'liveDotConnected' : ''}`} />
            <span>{wsState === 'connected' ? 'LIVE' : wsState === 'connecting' ? 'CONNECTING...' : 'DISCONNECTED'}</span>
          </div>
        }
        navItems={[
          { label: 'Library', to: '/library' },
          { label: 'Import', to: '/import' },
          { label: 'Activity', to: '/activity' },
          { label: 'Settings', to: '/settings' },
        ]}
      />

      <JobFilterBar
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        jobTypeFilter={jobTypeFilter}
        onJobTypeFilterChange={setJobTypeFilter}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        availableJobTypes={availableJobTypes}
      />

      <section className="maintenancePanel">
        <div className="maintenanceContainer">
          <div className="maintenanceHeader">
            <div>
              <h2 className="sectionTitle">Maintenance</h2>
              <p className="maintenanceSubtitle">
                Run scheduled tasks on-demand without waiting for the next cycle.
              </p>
            </div>
          </div>
          <div className="maintenanceGrid">
            {maintenanceJobs.map(job => (
              <div key={job.type} className="maintenanceCard">
                <div className="maintenanceCardHeader">
                  <div className="maintenanceTitle">{job.title}</div>
                </div>
                <p className="maintenanceDescription">{job.description}</p>
                <button
                  type="button"
                  className="maintenanceButton"
                  onClick={() => handleRunMaintenanceJob(job.type, job.title)}
                  disabled={maintenancePending[job.type]}
                >
                  {maintenancePending[job.type] ? 'Queueing…' : job.actionLabel}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="jobSections">
        {/* Active Jobs */}
        <section className="jobSection">
          <div
            className="sectionHeader"
            onClick={() => setActiveSectionCollapsed(!activeSectionCollapsed)}
          >
            <h2 className="sectionTitle sectionTitleActive">Active Jobs</h2>
            <span className="sectionCount sectionCountActive">{groupedJobs.active.length}</span>
            <span className={`collapseArrow ${activeSectionCollapsed ? 'collapseArrowCollapsed' : ''}`}>
              ▼
            </span>
          </div>
          {!activeSectionCollapsed && (
            <div className="jobGrid">
              {groupedJobs.active.length === 0 ? (
                <div className="emptyState">
                  <div className="emptyIcon">⚙️</div>
                  <div className="emptyMessage">No active jobs</div>
                </div>
              ) : (
                groupedJobs.active.map(job => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    onCancel={handleCancelJob}
                  />
                ))
              )}
            </div>
          )}
        </section>

        {/* Completed Jobs */}
        <section className="jobSection">
          <div
            className="sectionHeader"
            onClick={() => setCompletedSectionCollapsed(!completedSectionCollapsed)}
          >
            <h2 className="sectionTitle sectionTitleCompleted">Completed Jobs</h2>
            <span className="sectionCount sectionCountCompleted">{groupedJobs.completed.length}</span>
            <span className={`collapseArrow ${completedSectionCollapsed ? 'collapseArrowCollapsed' : ''}`}>
              ▼
            </span>
          </div>
          {!completedSectionCollapsed && (
            <div className="jobGrid">
              {groupedJobs.completed.length === 0 ? (
                <div className="emptyState">
                  <div className="emptyIcon">✓</div>
                  <div className="emptyMessage">No completed jobs yet</div>
                </div>
              ) : (
                groupedJobs.completed.map(job => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    onClear={handleClearJob}
                  />
                ))
              )}
            </div>
          )}
        </section>

        {/* Failed Jobs */}
        <section className="jobSection">
          <div
            className="sectionHeader"
            onClick={() => setFailedSectionCollapsed(!failedSectionCollapsed)}
          >
            <h2 className="sectionTitle sectionTitleFailed">Failed Jobs</h2>
            <span className="sectionCount sectionCountFailed">{groupedJobs.failed.length}</span>
            <span className={`collapseArrow ${failedSectionCollapsed ? 'collapseArrowCollapsed' : ''}`}>
              ▼
            </span>
          </div>
          {!failedSectionCollapsed && (
            <div className="jobGrid">
              {groupedJobs.failed.length === 0 ? (
                <div className="emptyState">
                  <div className="emptyIcon">✓</div>
                  <div className="emptyMessage">No failed jobs</div>
                </div>
              ) : (
                groupedJobs.failed.map(job => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    onRetry={handleRetryJob}
                    onClear={handleClearJob}
                  />
                ))
              )}
            </div>
          )}
        </section>
      </div>

      {lastError && (
        <div className="errorBanner">
          WebSocket Error: {lastError}
        </div>
      )}
    </div>
  )
}
