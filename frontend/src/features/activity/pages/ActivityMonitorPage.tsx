import { Outlet, useLocation } from 'react-router-dom'
import { useAuthTokens } from '../../../auth/useAuthTokens'
import { useJobEvents } from '../../../lib/ws/useJobEvents'
import { useActiveJobs, useCompletedJobs, useFailedJobs } from '../hooks/useJobsQuery'
import PageHeader from '../../../components/layout/PageHeader'
import './ActivityMonitorPage.css'

export default function ActivityMonitorPage() {
  const { accessToken } = useAuthTokens()
  const location = useLocation()

  // WebSocket connection for live indicator
  const { connectionState } = useJobEvents(accessToken, {
    includeActiveState: false,
    autoConnect: true,
  })

  // Fetch counts for tab badges from REST API
  const { data: activeData } = useActiveJobs({ enabled: true })
  const { data: completedData } = useCompletedJobs({ limit: 1 }, { enabled: true })
  const { data: failedData } = useFailedJobs({ limit: 1 }, { enabled: true })

  const activeCount = activeData?.total ?? 0
  const completedCount = completedData?.total ?? 0
  const failedCount = failedData?.total ?? 0

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
          { label: `Completed (${completedCount})`, to: '/activity/completed' },
          { label: `Failed (${failedCount})`, to: '/activity/failed' },
        ]}
      />

      <div className="activityContent">
        <Outlet />
      </div>
    </div>
  )
}
