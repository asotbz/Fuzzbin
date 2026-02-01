import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { getApiBaseUrl } from '../../../api/client'
import { useAuthTokens } from '../../../auth/useAuthTokens'
import JobCard from '../components/JobCard'
import JobGroup from '../components/JobGroup'
import { cancelJob, type JobItem } from '../../../lib/api/endpoints/jobs'
import { useActiveJobs } from '../hooks/useJobsQuery'
import { useJobEvents, type JobState } from '../../../lib/ws/useJobEvents'
import { SCHEDULED_MAINTENANCE_JOB_TYPES } from '../constants'
import './ActiveJobsTab.css'

// Adapter: Convert REST JobItem to JobState format used by components
function toJobState(job: JobItem): JobState {
  return {
    job_id: job.id,
    job_type: job.type,
    status: job.status as JobState['status'],
    progress: job.progress,
    current_step: job.current_step,
    processed_items: job.processed_items,
    total_items: job.total_items,
    created_at: job.created_at,
    started_at: job.started_at,
    completed_at: job.completed_at,
    metadata: {
      ...job.metadata,
      video_id: job.video_id,
      video_title: job.video_title,
      video_artist: job.video_artist,
    },
    error: job.error ?? undefined,
    result: job.result ?? undefined,
  }
}

interface JobGroupData {
  videoId: number
  videoTitle?: string
  videoArtist?: string
  jobs: JobState[]
  overallProgress: number
  groupStatus: 'running' | 'pending' | 'completed' | 'failed'
}

type ActiveJobCard =
  | { kind: 'group'; key: string; isRunning: boolean; order: number; group: JobGroupData }
  | { kind: 'job'; key: string; isRunning: boolean; order: number; job: JobState }

function groupJobsByVideo(jobs: JobState[]): { grouped: JobGroupData[]; ungrouped: JobState[] } {
  const videoJobs = new Map<number, JobState[]>()
  const ungrouped: JobState[] = []

  // Only include active jobs (not scheduled maintenance)
  const activeJobs = jobs.filter(j => 
    ['pending', 'waiting', 'running'].includes(j.status) &&
    !SCHEDULED_MAINTENANCE_JOB_TYPES.has(j.job_type)
  )

  for (const job of activeJobs) {
    const videoId = job.metadata?.video_id as number | undefined
    if (videoId) {
      if (!videoJobs.has(videoId)) {
        videoJobs.set(videoId, [])
      }
      videoJobs.get(videoId)!.push(job)
    } else {
      ungrouped.push(job)
    }
  }

  const grouped: JobGroupData[] = []
  for (const [videoId, videoJobsList] of videoJobs) {
    if (videoJobsList.length === 1) {
      // Single job for video, show ungrouped
      ungrouped.push(videoJobsList[0])
    } else {
      // Multiple jobs for same video, group them
      const hasRunning = videoJobsList.some(j => j.status === 'running')
      const hasFailed = videoJobsList.some(j => ['failed', 'cancelled', 'timeout'].includes(j.status))
      const allCompleted = videoJobsList.every(j => j.status === 'completed')

      const avgProgress = videoJobsList.reduce((sum, j) => sum + j.progress, 0) / videoJobsList.length

      grouped.push({
        videoId,
        videoTitle: (videoJobsList[0].metadata?.video_title || videoJobsList[0].metadata?.title) as string | undefined,
        videoArtist: (videoJobsList[0].metadata?.video_artist || videoJobsList[0].metadata?.artist) as string | undefined,
        jobs: videoJobsList,
        overallProgress: avgProgress,
        groupStatus: hasRunning ? 'running' : hasFailed ? 'failed' : allCompleted ? 'completed' : 'pending',
      })
    }
  }

  return { grouped, ungrouped }
}

export default function ActiveJobsTab() {
  const { accessToken } = useAuthTokens()
  const [maintenancePending, setMaintenancePending] = useState<Record<string, boolean>>({})

  // Fetch initial state from REST API
  const { data: restData } = useActiveJobs()

  // Subscribe to WebSocket for real-time updates
  const { jobs: wsJobs } = useJobEvents(accessToken, {
    includeActiveState: false, // We have REST for initial state
    autoConnect: true,
  })

  // Merge REST data with WebSocket updates
  // WS updates take priority (more recent), REST as fallback
  const mergedJobs = useMemo(() => {
    const jobMap = new Map<string, JobState>()

    // Start with REST data
    if (restData?.jobs) {
      for (const job of restData.jobs) {
        jobMap.set(job.id, toJobState(job))
      }
    }

    // Overlay WebSocket data (more recent), preserving REST metadata
    for (const [jobId, wsJob] of wsJobs) {
      const existing = jobMap.get(jobId)
      if (existing) {
        jobMap.set(jobId, {
          ...existing,
          ...wsJob,
          metadata: {
            ...existing.metadata,
            ...wsJob.metadata,
          },
        })
      } else {
        jobMap.set(jobId, wsJob)
      }
    }

    return jobMap
  }, [restData, wsJobs])

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

  const activeJobs = useMemo(() => {
    return Array.from(mergedJobs.values()).filter(j => 
      ['pending', 'waiting', 'running'].includes(j.status)
    )
  }, [mergedJobs])

  const { grouped, ungrouped } = useMemo(() => groupJobsByVideo(activeJobs), [activeJobs])

  const jobCards = useMemo<ActiveJobCard[]>(() => {
    const combined: ActiveJobCard[] = []

    grouped.forEach((group) => {
      combined.push({
        kind: 'group',
        key: `group-${group.videoId}`,
        isRunning: group.groupStatus === 'running',
        order: combined.length,
        group,
      })
    })

    ungrouped.forEach((job) => {
      combined.push({
        kind: 'job',
        key: `job-${job.job_id}`,
        isRunning: job.status === 'running',
        order: combined.length,
        job,
      })
    })

    return combined.sort((a, b) => {
      if (a.isRunning === b.isRunning) {
        return a.order - b.order
      }
      return a.isRunning ? -1 : 1
    })
  }, [grouped, ungrouped])

  const handleCancelJob = async (jobId: string) => {
    try {
      await cancelJob(jobId)
      toast.success('Job cancelled successfully')
    } catch (error) {
      console.error('Failed to cancel job:', error)
      toast.error('Failed to cancel job')
    }
  }

  const handleCancelGroup = async (videoId: number) => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/jobs/groups/${videoId}`, {
        method: 'DELETE',
        headers: {
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
      })

      if (!response.ok) {
        throw new Error('Failed to cancel jobs')
      }

      toast.success('All jobs for video cancelled')
    } catch (error) {
      console.error('Failed to cancel video jobs:', error)
      toast.error('Failed to cancel jobs')
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

  return (
    <div className="activeJobsTab">
      {/* Active Jobs Section */}
      <section className="activeJobsSection">
        <h2 className="sectionTitle">Active Jobs</h2>
        {grouped.length === 0 && ungrouped.length === 0 ? (
          <div className="emptyState">
            <div className="emptyIcon">⚙️</div>
            <div className="emptyMessage">No active jobs</div>
          </div>
        ) : (
          <div className="jobsContainer">
            {jobCards.map(card => {
              if (card.kind === 'group') {
                const group = card.group
                return (
                  <JobGroup
                    key={card.key}
                    videoId={group.videoId}
                    videoTitle={group.videoTitle}
                    videoArtist={group.videoArtist}
                    jobs={group.jobs}
                    overallProgress={group.overallProgress}
                    groupStatus={group.groupStatus}
                    onCancelGroup={handleCancelGroup}
                  />
                )
              }

              return (
                <JobCard
                  key={card.key}
                  job={card.job}
                  onCancel={handleCancelJob}
                />
              )
            })}
          </div>
        )}
      </section>

      {/* Maintenance Section */}
      <section className="maintenanceSection">
        <h2 className="sectionTitle">Maintenance</h2>
        <p className="maintenanceSubtitle">
          Run scheduled tasks on-demand without waiting for the next cycle.
        </p>
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
      </section>
    </div>
  )
}
