import type { Video } from '../../../lib/api/types'
import LibraryTableRow from './LibraryTableRow'
import './LibraryTable.css'

export type LibraryTableColumns = 'full' | 'core' | 'curation'

interface LibraryTableProps {
  videos: Video[]
  selectedIds: Set<number>
  columns: LibraryTableColumns
  onToggleSelection: (id: number) => void
  onSelectAll: () => void
  onClearAll: () => void
  onVideoClick: (video: Video) => void
  onPlayVideo?: (video: Video) => void
}

export default function LibraryTable({
  videos,
  selectedIds,
  columns,
  onToggleSelection,
  onSelectAll,
  onClearAll,
  onVideoClick,
  onPlayVideo,
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

  const columnsClass =
    columns === 'full'
      ? 'libraryTableColumnsFull'
      : columns === 'core'
        ? 'libraryTableColumnsCore'
        : 'libraryTableColumnsCuration'

  const showFull = columns === 'full'
  const showCore = columns === 'core'
  const showCuration = columns === 'curation'

  return (
    <div className={`libraryTable ${columnsClass}`} role="grid" aria-label="Video library table">
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
        {(showFull || showCore) && (
          <div className="libraryTableHeaderCell">Album</div>
        )}
        {showFull && (
          <>
            <div className="libraryTableHeaderCell">Year</div>
            <div className="libraryTableHeaderCell libraryTableCellHideTablet">Director</div>
            <div className="libraryTableHeaderCell libraryTableCellHideTablet">Label</div>
            <div className="libraryTableHeaderCell">Duration</div>
          </>
        )}
        {showCore && (
          <div className="libraryTableHeaderCell">Genre</div>
        )}
        {showCuration && (
          <>
            <div className="libraryTableHeaderCell">Genre</div>
            <div className="libraryTableHeaderCell">ISRC</div>
            <div className="libraryTableHeaderCell">Tags</div>
          </>
        )}
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
              columns={columns}
              onToggleSelection={onToggleSelection}
              onVideoClick={onVideoClick}
              onPlayVideo={onPlayVideo}
            />
          )
        })}
      </div>
    </div>
  )
}
