import type { JobData } from '../hooks/useActivityWebSocket'

interface JobProgressBarProps {
  job: JobData
}

function formatSpeed(speed: number | undefined): string | null {
  if (!speed) return null
  return `${speed.toFixed(1)} MB/s`
}

function formatETA(seconds: number | undefined): string | null {
  if (!seconds) return null
  if (seconds < 60) return `${Math.round(seconds)}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.round(seconds % 60)
  return `${minutes}m ${remainingSeconds}s`
}

export default function JobProgressBar({ job }: JobProgressBarProps) {
  const percentage = Math.round(job.progress * 100)
  const isRunning = job.status === 'running'
  const isCompleted = job.status === 'completed'
  const isFailed = ['failed', 'cancelled', 'timeout'].includes(job.status)

  const speed = formatSpeed(job.download_speed)
  const eta = formatETA(job.eta_seconds)

  return (
    <div className="jobProgress">
      <div className="progressBarContainer">
        <div
          className={`progressBarFill ${isRunning ? 'progressBarFillRunning' : ''} ${isCompleted ? 'progressBarFillCompleted' : ''} ${isFailed ? 'progressBarFillFailed' : ''}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="progressStats">
        <span className={`progressPercentage ${isRunning ? 'progressRunning' : ''} ${isCompleted ? 'progressCompleted' : ''} ${isFailed ? 'progressFailed' : ''}`}>
          {percentage}%
        </span>
        {speed && <span className="progressSpeed">{speed}</span>}
        {eta && <span className="progressEta">ETA: {eta}</span>}
        {!speed && !eta && (
          <span className="progressItems">
            {job.processed_items}/{job.total_items} tasks
          </span>
        )}
      </div>
    </div>
  )
}
