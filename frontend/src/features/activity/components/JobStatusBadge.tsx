import type { JobData } from '../hooks/useActivityWebSocket'

interface JobStatusBadgeProps {
  status: JobData['status']
}

export default function JobStatusBadge({ status }: JobStatusBadgeProps) {
  const statusClass = `jobStatusBadge jobStatusBadge${status.charAt(0).toUpperCase() + status.slice(1)}`

  return (
    <span className={statusClass}>
      {status.toUpperCase()}
    </span>
  )
}
