import type { Video } from '../../../lib/api/types'
import LibraryTableRow from './LibraryTableRow'
import './LibraryTable.css'

interface LibraryTableProps {
  videos: Video[]
  selectedIds: Set<number>
  onToggleSelection: (id: number) => void
  onSelectAll: () => void
  onClearAll: () => void
  onVideoClick: (video: Video) => void
}

export default function LibraryTable({
  videos,
  selectedIds,
  onToggleSelection,
  onSelectAll,
  onClearAll,
  onVideoClick,
}: LibraryTableProps) {
  const allSelected = videos.length > 0 && videos.every((v) => {
    const id = (v as unknown as Record<string, unknown>).id
    return typeof id === 'number' && selectedIds.has(id)
  })

  const handleSelectAllChange = () => {
    if (allSelected) {
      onClearAll()
    } else {
      onSelectAll()
    }
  }

  return (
    <div className="libraryTable" role="grid" aria-label="Video library table">
      <div className="libraryTableHeader" role="row">
        <div className="libraryTableHeaderCell">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={handleSelectAllChange}
            aria-label="Select all videos"
          />
        </div>
        <div className="libraryTableHeaderCell">Artist</div>
        <div className="libraryTableHeaderCell">Title</div>
        <div className="libraryTableHeaderCell">Album</div>
        <div className="libraryTableHeaderCell">Year</div>
        <div className="libraryTableHeaderCell libraryTableCellHideTablet">Director</div>
        <div className="libraryTableHeaderCell libraryTableCellHideTablet">Label</div>
        <div className="libraryTableHeaderCell">Duration</div>
        <div className="libraryTableHeaderCell">Actions</div>
      </div>

      <div className="libraryTableBody">
        {videos.map((video) => {
          const id = (video as unknown as Record<string, unknown>).id
          const videoId = typeof id === 'number' ? id : 0
          const key = videoId || JSON.stringify(video)

          return (
            <LibraryTableRow
              key={key}
              video={video}
              selected={selectedIds.has(videoId)}
              onToggleSelection={onToggleSelection}
              onVideoClick={onVideoClick}
            />
          )
        })}
      </div>
    </div>
  )
}
