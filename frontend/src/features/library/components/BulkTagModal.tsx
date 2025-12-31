import { useState } from 'react'
import './BulkTagModal.css'

interface BulkTagModalProps {
  count: number
  availableTags: string[]
  onApply: (addTags: string[], removeTags: string[]) => void
  onCancel: () => void
}

export default function BulkTagModal({
  count,
  availableTags,
  onApply,
  onCancel,
}: BulkTagModalProps) {
  const [newTagInput, setNewTagInput] = useState('')
  const [tagsToAdd, setTagsToAdd] = useState<Set<string>>(new Set())
  const [tagsToRemove, setTagsToRemove] = useState<Set<string>>(new Set())

  const handleAddTag = (tag: string) => {
    const trimmed = tag.trim()
    if (!trimmed) return

    setTagsToAdd((prev) => {
      const next = new Set(prev)
      next.add(trimmed)
      return next
    })
    setNewTagInput('')
  }

  const handleRemoveFromAdd = (tag: string) => {
    setTagsToAdd((prev) => {
      const next = new Set(prev)
      next.delete(tag)
      return next
    })
  }

  const handleToggleAvailableTag = (tag: string) => {
    setTagsToAdd((prev) => {
      const next = new Set(prev)
      if (next.has(tag)) {
        next.delete(tag)
      } else {
        next.add(tag)
      }
      return next
    })
  }

  const handleToggleRemoveTag = (tag: string) => {
    setTagsToRemove((prev) => {
      const next = new Set(prev)
      if (next.has(tag)) {
        next.delete(tag)
      } else {
        next.add(tag)
      }
      return next
    })
  }

  const handleApply = () => {
    onApply(Array.from(tagsToAdd), Array.from(tagsToRemove))
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAddTag(newTagInput)
    }
  }

  return (
    <div className="bulkTagModalOverlay" onClick={onCancel}>
      <div className="bulkTagModal" onClick={(e) => e.stopPropagation()}>
        <div className="bulkTagModalHeader">
          <h2 className="bulkTagModalTitle">
            Manage Tags - {count} video{count !== 1 ? 's' : ''} selected
          </h2>
          <button
            type="button"
            className="bulkTagModalClose"
            onClick={onCancel}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="bulkTagModalBody">
          {/* Add Tags Section */}
          <section className="bulkTagSection">
            <h3 className="bulkTagSectionTitle">Add Tags</h3>

            <div className="bulkTagInputGroup">
              <input
                type="text"
                className="bulkTagInput"
                placeholder="Type tag name and press Enter..."
                value={newTagInput}
                onChange={(e) => setNewTagInput(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <button
                type="button"
                className="bulkTagAddButton"
                onClick={() => handleAddTag(newTagInput)}
                disabled={!newTagInput.trim()}
              >
                Add
              </button>
            </div>

            {/* Selected tags to add */}
            {tagsToAdd.size > 0 && (
              <div className="bulkTagSelectedGroup">
                <div className="bulkTagSelectedLabel">Tags to add:</div>
                <div className="bulkTagList">
                  {Array.from(tagsToAdd).map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      className="bulkTagChip bulkTagChipAdd"
                      onClick={() => handleRemoveFromAdd(tag)}
                      title="Click to remove"
                    >
                      {tag} ×
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Available tags */}
            {availableTags.length > 0 && (
              <div className="bulkTagAvailableGroup">
                <div className="bulkTagAvailableLabel">
                  Available tags (click to add):
                </div>
                <div className="bulkTagList">
                  {availableTags.slice(0, 20).map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      className={`bulkTagChip ${
                        tagsToAdd.has(tag) ? 'bulkTagChipSelected' : ''
                      }`}
                      onClick={() => handleToggleAvailableTag(tag)}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* Remove Tags Section */}
          <section className="bulkTagSection">
            <h3 className="bulkTagSectionTitle">Remove Tags</h3>
            <p className="bulkTagSectionDescription">
              Select tags to remove from selected videos
            </p>

            {tagsToRemove.size > 0 && (
              <div className="bulkTagSelectedGroup">
                <div className="bulkTagSelectedLabel">Tags to remove:</div>
                <div className="bulkTagList">
                  {Array.from(tagsToRemove).map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      className="bulkTagChip bulkTagChipRemove bulkTagChipSelected"
                      onClick={() => handleToggleRemoveTag(tag)}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="bulkTagAvailableGroup">
              <div className="bulkTagAvailableLabel">
                Click tags to mark for removal:
              </div>
              <div className="bulkTagList">
                {availableTags.slice(0, 20).map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    className={`bulkTagChip bulkTagChipRemove ${
                      tagsToRemove.has(tag) ? 'bulkTagChipSelected' : ''
                    }`}
                    onClick={() => handleToggleRemoveTag(tag)}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>
          </section>
        </div>

        <div className="bulkTagModalFooter">
          <button
            type="button"
            className="bulkTagModalButton bulkTagModalButtonCancel"
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className="bulkTagModalButton bulkTagModalButtonApply"
            onClick={handleApply}
            disabled={tagsToAdd.size === 0 && tagsToRemove.size === 0}
          >
            Apply Changes
          </button>
        </div>
      </div>
    </div>
  )
}
