import { useState } from 'react'
import type { BatchPreviewItem } from '../../../lib/api/types'
import './IMVDbRetryModal.css'

interface IMVDbRetryModalProps {
  track: BatchPreviewItem
  onRetry: (artist: string, trackTitle: string) => void
  onCancel: () => void
}

export default function IMVDbRetryModal({ track, onRetry, onCancel }: IMVDbRetryModalProps) {
  const [artist, setArtist] = useState(track.artist)
  const [trackTitle, setTrackTitle] = useState(track.title)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (artist.trim() && trackTitle.trim()) {
      onRetry(artist.trim(), trackTitle.trim())
    }
  }

  return (
    <div className="imvdbRetryModalOverlay" onClick={onCancel}>
      <div className="imvdbRetryModalContent" onClick={(e) => e.stopPropagation()}>
        <div className="imvdbRetryModalHeader">
          <h2 className="imvdbRetryModalTitle">Retry IMVDb Search</h2>
          <button type="button" className="imvdbRetryModalClose" onClick={onCancel}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="imvdbRetryModalBody">
          <p className="imvdbRetryModalDescription">
            Modify the search terms below and retry the IMVDb lookup. Sometimes small changes to
            artist or track names can improve match results.
          </p>

          <form onSubmit={handleSubmit} className="imvdbRetryModalForm">
            <div className="imvdbRetryModalFormGroup">
              <label className="imvdbRetryModalLabel">Artist Name</label>
              <input
                type="text"
                className="imvdbRetryModalInput"
                value={artist}
                onChange={(e) => setArtist(e.target.value)}
                placeholder="Artist name"
                autoFocus
              />
            </div>

            <div className="imvdbRetryModalFormGroup">
              <label className="imvdbRetryModalLabel">Track Title</label>
              <input
                type="text"
                className="imvdbRetryModalInput"
                value={trackTitle}
                onChange={(e) => setTrackTitle(e.target.value)}
                placeholder="Track title"
              />
            </div>

            <div className="imvdbRetryModalActions">
              <button type="button" className="imvdbRetryModalButton" onClick={onCancel}>
                Cancel
              </button>
              <button
                type="submit"
                className="imvdbRetryModalButtonPrimary"
                disabled={!artist.trim() || !trackTitle.trim()}
              >
                Retry Search
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
