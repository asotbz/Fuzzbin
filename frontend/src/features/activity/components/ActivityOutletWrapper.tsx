import ActiveJobsTab from '../tabs/ActiveJobsTab'
import CompletedJobsTab from '../tabs/CompletedJobsTab'
import { FailedJobsTab } from '../tabs/FailedJobsTab'

interface ActivityOutletWrapperProps {
  tab: 'active' | 'completed' | 'failed'
}

export default function ActivityOutletWrapper({ tab }: ActivityOutletWrapperProps) {
  switch (tab) {
    case 'active':
      return <ActiveJobsTab />
    case 'completed':
      return <CompletedJobsTab />
    case 'failed':
      return <FailedJobsTab />
    default:
      return <ActiveJobsTab />
  }
}
