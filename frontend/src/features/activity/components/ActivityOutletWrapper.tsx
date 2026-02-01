import ActiveJobsTab from '../tabs/ActiveJobsTab'
import HistoryJobsTab from '../tabs/HistoryJobsTab'

interface ActivityOutletWrapperProps {
  tab: 'active' | 'history'
}

export default function ActivityOutletWrapper({ tab }: ActivityOutletWrapperProps) {
  switch (tab) {
    case 'active':
      return <ActiveJobsTab />
    case 'history':
      return <HistoryJobsTab />
    default:
      return <ActiveJobsTab />
  }
}
