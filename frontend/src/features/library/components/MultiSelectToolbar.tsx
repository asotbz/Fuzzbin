import './MultiSelectToolbar.css'

interface MultiSelectToolbarProps {
  count: number
  onAddTags: () => void
  onRemoveTags: () => void
  onWriteNFO: () => void
  onOrganize: () => void
  onDownload: () => void
  onDelete: () => void
  onClear: () => void
}

export default function MultiSelectToolbar({
  count,
  onAddTags,
  onRemoveTags,
  onWriteNFO,
  onOrganize,
  onDownload,
  onDelete,
  onClear,
}: MultiSelectToolbarProps) {
  return (
    <div className="multiSelectToolbar" role="toolbar" aria-label="Bulk operations toolbar">
      <div className="multiSelectToolbarCount">
        ✓ {count} video{count !== 1 ? 's' : ''} selected
      </div>

      <div className="multiSelectToolbarDivider" />

      <button
        className="multiSelectToolbarButton"
        type="button"
        onClick={onAddTags}
        aria-label="Add tags"
      >
        Add Tags
      </button>

      <button
        className="multiSelectToolbarButton"
        type="button"
        onClick={onRemoveTags}
        aria-label="Remove tags"
      >
        Remove Tags
      </button>

      <button
        className="multiSelectToolbarButton"
        type="button"
        onClick={onWriteNFO}
        aria-label="Write NFO files"
      >
        Write NFO
      </button>

      <button
        className="multiSelectToolbarButton"
        type="button"
        onClick={onOrganize}
        aria-label="Organize files"
      >
        Organize Files
      </button>

      <button
        className="multiSelectToolbarButton"
        type="button"
        onClick={onDownload}
        aria-label="Download selected videos"
      >
        Download Videos
      </button>

      <div className="multiSelectToolbarDivider" />

      <button
        className="multiSelectToolbarButton multiSelectToolbarButtonDanger"
        type="button"
        onClick={onDelete}
        aria-label="Delete selected videos"
      >
        Delete
      </button>

      <div className="multiSelectToolbarDivider" />

      <button
        className="multiSelectToolbarButton multiSelectToolbarButtonClear"
        type="button"
        onClick={onClear}
        aria-label="Clear selection"
      >
        Clear
      </button>
    </div>
  )
}
