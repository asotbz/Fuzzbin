import { useState } from 'react'
import type { JobData } from '../hooks/useActivityWebSocket'
import JobStatusBadge from './JobStatusBadge'
import JobProgressBar from './JobProgressBar'
import './JobGroup.css'

interface JobGroupProps {
  videoId: number
  videoTitle?: string | null
  videoArtist?: string | null
  jobs: JobData[]
  overallProgress: number
  groupStatus: 'running' | 'pending' | 'completed' | 'failed'
  onCancelGroup?: (videoId: number) => void
}

type PipelineStepStatus = 'pending' | 'running' | 'completed' | 'failed'

const JOB_TYPE_ORDER = [
  'import_pipeline',
  'download_youtube',
  'import_download',
  'video_post_process',
  'file_organize',
  'import_organize',
  'import_nfo_generate',
  'metadata_enrich',
]

function sortJobsByPipeline(jobs: JobData[]): JobData[] {
  return [...jobs].sort((a, b) => {
    const aIndex = JOB_TYPE_ORDER.indexOf(a.job_type)
    const bIndex = JOB_TYPE_ORDER.indexOf(b.job_type)
    // Unknown types go at the end
    const aOrder = aIndex === -1 ? 999 : aIndex
    const bOrder = bIndex === -1 ? 999 : bIndex
    return aOrder - bOrder
  })
}

const JOB_TYPE_LABELS: Record<string, string> = {
  'import_pipeline': 'Pipeline',
  'download_youtube': 'Download',
  'import_download': 'Download',
  'video_post_process': 'Process',
  'file_organize': 'Organize',
  'import_organize': 'Organize',
  'import_nfo_generate': 'Save NFO',
  'metadata_enrich': 'Enrich',
}

const PIPELINE_STEPS = ['Download', 'Process', 'Organize', 'Save NFO'] as const

function getStepLabel(jobType: string): string {
  return JOB_TYPE_LABELS[jobType] || jobType.replace(/_/g, ' ')
}

function getStepStatus(job: JobData): 'pending' | 'running' | 'completed' | 'failed' {
  if (['failed', 'cancelled', 'timeout'].includes(job.status)) return 'failed'
  if (job.status === 'completed') return 'completed'
  if (job.status === 'running') return 'running'
  return 'pending'
}

function getPipelineStepStatuses(job: JobData): PipelineStepStatus[] {
  if (job.status === 'completed') {
    return PIPELINE_STEPS.map(() => 'completed')
  }

  const failed = ['failed', 'cancelled', 'timeout'].includes(job.status)
  const percent = Math.max(0, Math.min(100, Math.round(job.progress * 100)))
  const currentIndex = Math.min(PIPELINE_STEPS.length - 1, Math.floor(percent / 25))

  return PIPELINE_STEPS.map((_, index) => {
    if (index < currentIndex) return 'completed'
    if (index === currentIndex) {
      if (failed) return 'failed'
      return job.status === 'running' ? 'running' : 'pending'
    }
    return 'pending'
  })
}

export default function JobGroup({
  videoId,
  videoTitle,
  videoArtist,
  jobs,
  overallProgress,
  groupStatus,
  onCancelGroup,
}: JobGroupProps) {
  const [expanded, setExpanded] = useState(false)
  const sortedJobs = sortJobsByPipeline(jobs)
  const pipelineJob = sortedJobs.find(job => job.job_type === 'import_pipeline')
  const pipelineSteps = pipelineJob ? getPipelineStepStatuses(pipelineJob) : null
  const currentJob = sortedJobs.find(j => j.status === 'running')
  const displayTitle = videoTitle || `Video #${videoId}`

  return (
    <div className={`jobGroup jobGroup${groupStatus.charAt(0).toUpperCase() + groupStatus.slice(1)}`}>
      <div className="jobGroupHeader" onClick={() => setExpanded(!expanded)}>
        <div className="jobGroupInfo">
          <div className="jobGroupTitle">
            {videoArtist && <span className="jobGroupArtist">{videoArtist}</span>}
            <span className="jobGroupVideoTitle">{displayTitle}</span>
          </div>
          <div className="jobGroupStep">
            {currentJob ? currentJob.current_step : 'Waiting...'}
          </div>
        </div>

        <div className="jobGroupPipeline">
          {pipelineSteps ? (
            PIPELINE_STEPS.map((label, index) => {
              const status = pipelineSteps[index]
              return (
                <div
                  key={label}
                  className={`pipelineStep pipelineStep${status.charAt(0).toUpperCase() + status.slice(1)}`}
                  title={`${label}: ${status}`}
                >
                  <div className="pipelineStepDot" />
                  <span className="pipelineStepLabel">{label}</span>
                </div>
              )
            })
          ) : (
            sortedJobs.map((job) => {
              const status = getStepStatus(job)
              return (
                <div
                  key={job.job_id}
                  className={`pipelineStep pipelineStep${status.charAt(0).toUpperCase() + status.slice(1)}`}
                  title={`${getStepLabel(job.job_type)}: ${job.status}`}
                >
                  <div className="pipelineStepDot" />
                  <span className="pipelineStepLabel">{getStepLabel(job.job_type)}</span>
                </div>
              )
            })
          )}
        </div>

        <div className="jobGroupProgress">
          <div className="jobGroupProgressBar">
            <div
              className="jobGroupProgressFill"
              style={{ width: `${overallProgress * 100}%` }}
            />
          </div>
          <span className="jobGroupProgressText">{Math.round(overallProgress * 100)}%</span>
        </div>

        <div className="jobGroupActions">
          {(groupStatus === 'running' || groupStatus === 'pending') && onCancelGroup && (
            <button
              className="groupCancelBtn"
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                onCancelGroup(videoId)
              }}
              aria-label="Cancel all jobs for this video"
            >
              Cancel
            </button>
          )}
          <span className={`expandArrow ${expanded ? 'expandArrowExpanded' : ''}`}>
            ▼
          </span>
        </div>
      </div>

      {expanded && (
        <div className="jobGroupJobs">
          {pipelineJob && pipelineSteps ? (
            PIPELINE_STEPS.map((label, index) => {
              const status = pipelineSteps[index]
              const statusText =
                status === 'running'
                  ? pipelineJob.current_step
                  : status === 'failed'
                    ? pipelineJob.error ?? 'Failed'
                    : status === 'completed'
                      ? 'Completed'
                      : 'Pending'
              const badgeStatus =
                status === 'completed'
                  ? 'completed'
                  : status === 'failed'
                    ? 'failed'
                    : status === 'running'
                      ? 'running'
                      : 'pending'

              return (
                <div key={label} className="jobGroupJobItem">
                  <div className="jobGroupJobType">{label}</div>
                  <div className="jobGroupJobStep">{statusText}</div>
                  <JobProgressBar job={pipelineJob} />
                  <JobStatusBadge status={badgeStatus} />
                </div>
              )
            })
          ) : (
            sortedJobs.map((job) => (
              <div key={job.job_id} className="jobGroupJobItem">
                <div className="jobGroupJobType">{getStepLabel(job.job_type)}</div>
                <div className="jobGroupJobStep">{job.current_step}</div>
                <JobProgressBar job={job} />
                <JobStatusBadge status={job.status} />
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
