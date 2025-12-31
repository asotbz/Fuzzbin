interface JobFilterBarProps {
  statusFilter: Set<string>
  onStatusFilterChange: (status: Set<string>) => void
  jobTypeFilter: Set<string>
  onJobTypeFilterChange: (jobTypes: Set<string>) => void
  searchQuery: string
  onSearchQueryChange: (query: string) => void
  availableJobTypes: string[]
}

const STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'running', label: 'Running' },
  { value: 'pending', label: 'Pending' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
]

const JOB_TYPE_LABELS: Record<string, string> = {
  'download_youtube': 'Download',
  'import_spotify_batch': 'Spotify Import',
  'import_nfo': 'NFO Import',
  'import_add_single': 'Single Import',
  'metadata_enrich': 'Metadata',
  'file_organize': 'Organize',
  'library_scan': 'Library Scan',
}

function formatJobTypeLabel(jobType: string): string {
  return JOB_TYPE_LABELS[jobType] || jobType.replace(/_/g, ' ')
}

export default function JobFilterBar({
  statusFilter,
  onStatusFilterChange,
  jobTypeFilter,
  onJobTypeFilterChange,
  searchQuery,
  onSearchQueryChange,
  availableJobTypes,
}: JobFilterBarProps) {

  const handleStatusClick = (status: string) => {
    if (status === 'all') {
      onStatusFilterChange(new Set())
    } else {
      const newFilter = new Set(statusFilter)
      if (newFilter.has(status)) {
        newFilter.delete(status)
      } else {
        newFilter.add(status)
      }
      onStatusFilterChange(newFilter)
    }
  }

  const handleJobTypeClick = (jobType: string) => {
    if (jobType === 'all') {
      onJobTypeFilterChange(new Set())
    } else {
      const newFilter = new Set(jobTypeFilter)
      if (newFilter.has(jobType)) {
        newFilter.delete(jobType)
      } else {
        newFilter.add(jobType)
      }
      onJobTypeFilterChange(newFilter)
    }
  }

  const isStatusActive = (status: string): boolean => {
    if (status === 'all') return statusFilter.size === 0
    return statusFilter.has(status)
  }

  const isJobTypeActive = (jobType: string): boolean => {
    if (jobType === 'all') return jobTypeFilter.size === 0
    return jobTypeFilter.has(jobType)
  }

  return (
    <div className="filterBar">
      <div className="filterContainer">
        <div className="filterRow">
          <span className="filterLabel">Status:</span>
          <div className="filterChips">
            {STATUS_OPTIONS.map(option => (
              <button
                key={option.value}
                className={`filterChip ${isStatusActive(option.value) ? 'filterChipActive' : ''}`}
                type="button"
                onClick={() => handleStatusClick(option.value)}
                aria-pressed={isStatusActive(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="filterRow" style={{ marginTop: '1rem' }}>
          <span className="filterLabel">Type:</span>
          <div className="filterChips">
            <button
              className={`filterChip ${isJobTypeActive('all') ? 'filterChipActive' : ''}`}
              type="button"
              onClick={() => handleJobTypeClick('all')}
              aria-pressed={isJobTypeActive('all')}
            >
              All
            </button>
            {availableJobTypes.map(jobType => (
              <button
                key={jobType}
                className={`filterChip ${isJobTypeActive(jobType) ? 'filterChipActive' : ''}`}
                type="button"
                onClick={() => handleJobTypeClick(jobType)}
                aria-pressed={isJobTypeActive(jobType)}
              >
                {formatJobTypeLabel(jobType)}
              </button>
            ))}
          </div>
          <input
            type="text"
            className="searchInput"
            placeholder="Search jobs..."
            value={searchQuery}
            onChange={(e) => onSearchQueryChange(e.target.value)}
            aria-label="Search jobs"
          />
        </div>
      </div>
    </div>
  )
}
