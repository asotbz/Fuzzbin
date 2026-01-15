import { useState, useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import type { Video } from '../../../lib/api/types'
import { searchKeys, videosKeys } from '../../../lib/api/queryKeys'
import { bulkDeleteVideos, getVideo } from '../../../lib/api/endpoints/videos'
import { apiJson } from '../../../api/client'
import { useVideoThumbnail } from '../../../api/useVideoThumbnail'
import MetadataFetchModal from './MetadataFetchModal'
import YouTubeSearchModal from '../../../pages/add/components/YouTubeSearchModal'
import ConfirmDialog from './ConfirmDialog'
import './VideoDetailsModal.css'

interface RefreshResponse {
  video_id: number
  media_info: Record<string, unknown>
  thumbnail_path: string | null
  thumbnail_timestamp: number | null
}

interface VideoDetailsModalProps {
  video: Video
  onClose: () => void
  /** Timestamp for thumbnail cache-busting (from WebSocket events) */
  thumbnailTimestamp?: number
}

function formatDuration(seconds: unknown): string {
  const sec = typeof seconds === 'number' && Number.isFinite(seconds) ? Math.max(0, Math.round(seconds)) : null
  if (sec === null) return '—'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatFileSize(bytes: unknown): string {
  const size = typeof bytes === 'number' && Number.isFinite(bytes) ? bytes : null
  if (size === null) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(2)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function getFeaturedArtists(video: Video): string[] {
  const anyVideo = video as unknown as Record<string, unknown>
  const artists = Array.isArray(anyVideo.artists) ? anyVideo.artists : []

  return artists
    .filter((a: unknown) => {
      if (!a || typeof a !== 'object') return false
      const artist = a as Record<string, unknown>
      return artist.role === 'featured'
    })
    .map((a: unknown) => {
      const artist = a as Record<string, unknown>
      return typeof artist.name === 'string' ? artist.name : ''
    })
    .filter(Boolean)
}

function getTagLabels(video: Video): string[] {
  const anyVideo = video as unknown as Record<string, unknown>
  const tags = Array.isArray(anyVideo.tags) ? anyVideo.tags : []

  return tags
    .map((tag: unknown) => {
      if (!tag || typeof tag !== 'object') return null
      const tagObj = tag as Record<string, unknown>
      const label = tagObj.name ?? tagObj.tag_name ?? tagObj.value
      return typeof label === 'string' && label.trim().length > 0 ? label.trim() : null
    })
    .filter((t): t is string => Boolean(t))
}

export default function VideoDetailsModal({ video, onClose, thumbnailTimestamp }: VideoDetailsModalProps) {
  const queryClient = useQueryClient()
  const [isEditing, setIsEditing] = useState(false)
  const [fetchModalSource, setFetchModalSource] = useState<'imvdb' | 'discogs_master' | 'musicbrainz' | null>(null)
  const [youtubeSearchOpen, setYoutubeSearchOpen] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [localThumbnailTimestamp, setLocalThumbnailTimestamp] = useState<number | undefined>(thumbnailTimestamp)

  const initialVideo = video as Record<string, unknown>
  const videoId = typeof initialVideo.id === 'number' ? initialVideo.id : null

  const videoQuery = useQuery({
    queryKey: videosKeys.byId(videoId ?? 0),
    queryFn: () => getVideo(videoId as number),
    enabled: !!videoId,
  })

  const currentVideo = (videoQuery.data ?? video) as Video
  const anyVideo = currentVideo as Record<string, unknown>

  // Track if we've already attempted backfill for this video to avoid repeated attempts
  const backfillAttemptedRef = useRef<number | null>(null)

  // Use the latest timestamp from WebSocket or local refresh
  const effectiveThumbnailTimestamp = thumbnailTimestamp ?? localThumbnailTimestamp

  // Thumbnail hook with cache-busting
  const { thumbnailUrl, isLoading: thumbnailLoading, refetch: refetchThumbnail } = useVideoThumbnail(
    videoId,
    { 
      enabled: !!videoId,
      cacheBustTimestamp: effectiveThumbnailTimestamp,
    }
  )

  // Form state
  const [editedTitle, setEditedTitle] = useState(
    (typeof initialVideo.title === 'string' && initialVideo.title.trim().length > 0 ? initialVideo.title : 'Untitled') as string
  )
  const [editedArtist, setEditedArtist] = useState(
    (typeof initialVideo.artist === 'string' && initialVideo.artist.trim().length > 0 ? initialVideo.artist : '') as string
  )
  const [editedAlbum, setEditedAlbum] = useState(typeof initialVideo.album === 'string' ? initialVideo.album : '')
  const [editedYear, setEditedYear] = useState(typeof initialVideo.year === 'number' ? String(initialVideo.year) : '')
  const [editedGenre, setEditedGenre] = useState(typeof initialVideo.genre === 'string' ? initialVideo.genre : '')
  const [editedDirector, setEditedDirector] = useState(typeof initialVideo.director === 'string' ? initialVideo.director : '')
  const [editedLabel, setEditedLabel] = useState(typeof initialVideo.studio === 'string' ? initialVideo.studio : '')
  const [editedIsrc, setEditedIsrc] = useState(typeof initialVideo.isrc === 'string' ? initialVideo.isrc : '')
  const [isrcError, setIsrcError] = useState('')

  const normalizedTitle = typeof anyVideo.title === 'string' && anyVideo.title.trim().length > 0 ? anyVideo.title : 'Untitled'
  const normalizedArtist = typeof anyVideo.artist === 'string' && anyVideo.artist.trim().length > 0 ? anyVideo.artist : ''
  const normalizedAlbum = typeof anyVideo.album === 'string' ? anyVideo.album : ''
  const normalizedYear = typeof anyVideo.year === 'number' ? String(anyVideo.year) : ''
  const normalizedGenre = typeof anyVideo.genre === 'string' ? anyVideo.genre : ''
  const normalizedDirector = typeof anyVideo.director === 'string' ? anyVideo.director : ''
  const normalizedLabel = typeof anyVideo.studio === 'string' ? anyVideo.studio : ''
  const normalizedIsrc = typeof anyVideo.isrc === 'string' ? anyVideo.isrc : ''

  const resetEdits = () => {
    setEditedTitle(normalizedTitle)
    setEditedArtist(normalizedArtist)
    setEditedAlbum(normalizedAlbum)
    setEditedYear(normalizedYear)
    setEditedGenre(normalizedGenre)
    setEditedDirector(normalizedDirector)
    setEditedLabel(normalizedLabel)
    setEditedIsrc(normalizedIsrc)
    setIsrcError('')
  }

  const currentTitle = isEditing ? editedTitle : normalizedTitle
  const currentArtist = isEditing ? editedArtist : normalizedArtist
  const currentAlbum = isEditing ? editedAlbum : normalizedAlbum
  const currentYear = isEditing ? editedYear : normalizedYear
  const currentGenre = isEditing ? editedGenre : normalizedGenre
  const currentDirector = isEditing ? editedDirector : normalizedDirector
  const currentLabel = isEditing ? editedLabel : normalizedLabel
  const currentIsrc = isEditing ? editedIsrc : normalizedIsrc

  // ISRC validation function (format: CC-XXX-YY-NNNNN, 12 chars without hyphens)
  const validateIsrc = (value: string): boolean => {
    if (!value.trim()) {
      setIsrcError('')
      return true // Empty is valid
    }
    // Remove hyphens for validation
    const cleaned = value.replace(/-/g, '')
    // Must be exactly 12 alphanumeric characters
    if (cleaned.length !== 12 || !/^[A-Z0-9]{12}$/i.test(cleaned)) {
      setIsrcError('ISRC must be 12 characters (format: CC-XXX-YY-NNNNN)')
      return false
    }
    setIsrcError('')
    return true
  }

  // Display values
  const title = currentTitle
  const artist = currentArtist || '—'
  const album = currentAlbum || '—'
  const year = currentYear || '—'
  const genre = currentGenre || '—'
  const director = currentDirector || '—'
  const label = currentLabel || '—'
  const status = typeof anyVideo.status === 'string' ? anyVideo.status : 'unknown'

  const imvdbUrl = typeof anyVideo.imvdb_url === 'string' ? anyVideo.imvdb_url : null
  const youtubeId = typeof anyVideo.youtube_id === 'string' ? anyVideo.youtube_id : null
  const vimeoId = typeof anyVideo.vimeo_id === 'string' ? anyVideo.vimeo_id : null

  const videoFilePath = typeof anyVideo.video_file_path === 'string' ? anyVideo.video_file_path : null
  const duration = formatDuration(anyVideo.duration)
  const width = typeof anyVideo.width === 'number' ? anyVideo.width : null
  const height = typeof anyVideo.height === 'number' ? anyVideo.height : null
  const resolution = width && height ? `${width}×${height}` : '—'
  const videoCodec = typeof anyVideo.video_codec === 'string' ? anyVideo.video_codec : '—'
  const audioCodec = typeof anyVideo.audio_codec === 'string' ? anyVideo.audio_codec : '—'
  const fileSize = formatFileSize(anyVideo.file_size)

  const featuredArtists = getFeaturedArtists(currentVideo)
  const tags = getTagLabels(currentVideo)

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      if (!videoId) throw new Error('No video ID')

      // Call PATCH endpoint to update video metadata
      const updated = await apiJson<Video>({
        method: 'PATCH',
        path: `/videos/${videoId}`,
        body: data,
      })

      // Auto-write NFO file after successful save
      try {
        await apiJson<{ exported_count: number }>({
          method: 'POST',
          path: '/exports/nfo',
          body: {
            video_ids: [videoId],
            overwrite_existing: true,
          },
        })
      } catch (nfoError) {
        // Log but don't fail the save if NFO export fails
        console.warn('Failed to export NFO:', nfoError)
      }

      return updated
    },
    onSuccess: () => {
      toast.success('Video updated successfully')
      queryClient.invalidateQueries({ queryKey: videosKeys.all })
      queryClient.invalidateQueries({ queryKey: searchKeys.all })
      setIsEditing(false)
    },
    onError: (error) => {
      toast.error('Failed to update video', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (deleteFiles: boolean) => {
      if (!videoId) throw new Error('No video ID')
      // Use bulk delete endpoint with one ID to support delete_files parameter
      await bulkDeleteVideos([videoId], deleteFiles)
    },
    onSuccess: (_, deleteFiles) => {
      if (deleteFiles) {
        toast.success('Video and files deleted successfully')
      } else {
        toast.success('Video deleted successfully')
      }
      queryClient.invalidateQueries({ queryKey: videosKeys.all })
      queryClient.invalidateQueries({ queryKey: searchKeys.all })
      onClose()
    },
    onError: (error) => {
      toast.error('Failed to delete video', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  // Download mutation
  const downloadMutation = useMutation({
    mutationFn: async () => {
      if (!videoId || !youtubeId) throw new Error('No YouTube ID')

      return await apiJson<{ id: string }>({
        method: 'POST',
        path: `/videos/${videoId}/download`,
      })
    },
    onSuccess: (data) => {
      toast.success('Download queued successfully', {
        description: data.id ? `Job ID: ${data.id}` : undefined,
      })
    },
    onError: (error) => {
      toast.error('Failed to queue download', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  // Refresh video properties and thumbnail mutation
  const refreshMutation = useMutation({
    mutationFn: async () => {
      if (!videoId) throw new Error('No video ID')

      return await apiJson<RefreshResponse>({
        method: 'POST',
        path: `/videos/${videoId}/refresh?regenerate_thumbnail=true`,
      })
    },
    onSuccess: (data) => {
      // Update local timestamp for immediate cache-bust
      if (data.thumbnail_timestamp) {
        setLocalThumbnailTimestamp(data.thumbnail_timestamp)
      }
      // Refetch thumbnail with new timestamp
      refetchThumbnail()
      // Invalidate video queries to get updated metadata
      queryClient.invalidateQueries({ queryKey: videosKeys.all })
      toast.success('Video refreshed', {
        description: 'File properties and thumbnail updated',
      })
    },
    onError: (error) => {
      toast.error('Failed to refresh video', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  // Backfill IMVDb URL mutation
  const backfillImvdbUrlMutation = useMutation({
    mutationFn: async () => {
      if (!videoId) throw new Error('No video ID')
      return await apiJson<{ total_found: number; updated: number; failed: number }>({
        method: 'POST',
        path: `/videos/backfill-imvdb-urls?video_id=${videoId}`,
      })
    },
    onSuccess: (data) => {
      if (data.updated > 0 && videoId) {
        // Refresh the video data to get the new URL
        queryClient.invalidateQueries({ queryKey: videosKeys.byId(videoId) })
      }
    },
    onError: (error) => {
      console.warn('Failed to backfill IMVDb URL:', error)
    },
  })

  // Automatically backfill missing IMVDb URL if we have the video ID
  const imvdbVideoId = typeof anyVideo.imvdb_video_id === 'string' ? anyVideo.imvdb_video_id : null
  useEffect(() => {
    // Only attempt backfill if:
    // 1. We have an IMVDb video ID
    // 2. We don't have an IMVDb URL
    // 3. We have a valid video ID
    // 4. We haven't already attempted backfill for this video
    if (imvdbVideoId && !imvdbUrl && videoId && backfillAttemptedRef.current !== videoId) {
      backfillAttemptedRef.current = videoId
      backfillImvdbUrlMutation.mutate()
    }
  }, [imvdbVideoId, imvdbUrl, videoId, backfillImvdbUrlMutation])

  const handleSave = () => {
    // Validate ISRC before saving
    if (!validateIsrc(editedIsrc)) {
      toast.error('Invalid ISRC format')
      return
    }

    const updates: Record<string, unknown> = {}

    if (editedTitle.trim() !== anyVideo.title) updates.title = editedTitle.trim()
    if (editedArtist.trim() !== anyVideo.artist) updates.artist = editedArtist.trim() || null
    if (editedAlbum.trim() !== anyVideo.album) updates.album = editedAlbum.trim() || null
    if (editedGenre.trim() !== anyVideo.genre) updates.genre = editedGenre.trim() || null
    if (editedDirector.trim() !== anyVideo.director) updates.director = editedDirector.trim() || null
    if (editedLabel.trim() !== anyVideo.studio) updates.studio = editedLabel.trim() || null
    if (editedIsrc.trim() !== anyVideo.isrc) updates.isrc = editedIsrc.trim() || null

    const yearNum = editedYear ? parseInt(editedYear, 10) : null
    if (yearNum !== anyVideo.year) updates.year = yearNum

    if (Object.keys(updates).length === 0) {
      setIsEditing(false)
      return
    }

    updateMutation.mutate(updates)
  }

  const handleCancel = () => {
    // Reset to original values
    resetEdits()
    setIsEditing(false)
  }

  const handleEditStart = () => {
    if (isEditing) return
    resetEdits()
    setIsEditing(true)
  }

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      if (isEditing) {
        handleCancel()
      } else {
        onClose()
      }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      if (isEditing) {
        handleCancel()
      } else {
        onClose()
      }
    }
  }

  const handleApplyFetchedMetadata = (metadata: Partial<{
    title: string
    artist: string
    album: string
    year: number
    genre: string
    director: string
    label: string
    imvdb_url: string
    imvdb_video_id: string
  }>) => {
    // Apply fetched metadata to form state
    if (metadata.title !== undefined) setEditedTitle(metadata.title)
    if (metadata.artist !== undefined) setEditedArtist(metadata.artist)
    if (metadata.album !== undefined) setEditedAlbum(metadata.album)
    if (metadata.year !== undefined) setEditedYear(String(metadata.year))
    if (metadata.genre !== undefined) setEditedGenre(metadata.genre)
    if (metadata.director !== undefined) setEditedDirector(metadata.director)
    if (metadata.label !== undefined) setEditedLabel(metadata.label)

    // If IMVDb data is provided, save it directly (not editable in form)
    if (metadata.imvdb_url || metadata.imvdb_video_id) {
      const imvdbUpdates: Record<string, unknown> = {}
      if (metadata.imvdb_url) imvdbUpdates.imvdb_url = metadata.imvdb_url
      if (metadata.imvdb_video_id) imvdbUpdates.imvdb_video_id = metadata.imvdb_video_id
      updateMutation.mutate(imvdbUpdates)
    }

    // Switch to edit mode if not already editing
    if (!isEditing) {
      setIsEditing(true)
    }

    toast.success('Metadata applied', {
      description: 'Review and save changes to update the video',
    })
  }

  const handleYouTubeSelect = (youtubeId: string) => {
    // Update the video with the new YouTube ID
    updateMutation.mutate({ youtube_id: youtubeId })
    setYoutubeSearchOpen(false)
  }

  const handleDelete = (hardDelete?: boolean) => {
    deleteMutation.mutate(hardDelete ?? false)
    setShowDeleteConfirm(false)
  }

  const youtubeSearchLabel = youtubeId ? 'Change YouTube Video' : 'Search YouTube'
  const downloadLabel = downloadMutation.isPending ? 'Queueing download' : 'Download Video'

  return (
    <div
      className="videoDetailsModalOverlay"
      onClick={handleOverlayClick}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-labelledby="video-details-title"
    >
      <div className="videoDetailsModal">
        <div className="videoDetailsModalHeader">
          <h2 id="video-details-title" className="videoDetailsModalTitle">
            Video Details
          </h2>
          <div className="videoDetailsHeaderActions">
            {!isEditing && youtubeId ? (
              <button
                type="button"
                className="videoDetailsHeaderActionButton"
                onClick={() => downloadMutation.mutate()}
                disabled={downloadMutation.isPending}
                title={downloadLabel}
                aria-label={downloadLabel}
                aria-busy={downloadMutation.isPending}
              >
                {downloadMutation.isPending ? (
                  <span className="videoDetailsHeaderActionSpinner" aria-hidden="true">⟳</span>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" x2="12" y1="15" y2="3" />
                  </svg>
                )}
              </button>
            ) : null}
            {!isEditing ? (
              <button
                type="button"
                className="videoDetailsHeaderActionButton"
                onClick={() => setYoutubeSearchOpen(true)}
                title={youtubeSearchLabel}
                aria-label={youtubeSearchLabel}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8" />
                  <path d="M21 21l-4.35-4.35" />
                </svg>
              </button>
            ) : null}
            {!isEditing ? (
              <button
                type="button"
                className="videoDetailsHeaderActionButton"
                onClick={handleEditStart}
                aria-label="Edit video"
                title="Edit video"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              </button>
            ) : null}
            <button
              type="button"
              className="videoDetailsModalClose"
              onClick={isEditing ? handleCancel : onClose}
              aria-label="Close"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        <div className="videoDetailsModalBody">
          {/* Basic Metadata */}
          <section className="videoDetailsSection">
            <h3 className="videoDetailsSectionTitle">Metadata</h3>
            <div className="videoDetailsGrid">
              <div className="videoDetailsField">
                <label className="videoDetailsLabel">Title</label>
                {isEditing ? (
                  <input
                    type="text"
                    className="videoDetailsInput"
                    value={editedTitle}
                    onChange={(e) => setEditedTitle(e.target.value)}
                    required
                  />
                ) : (
                  <div className="videoDetailsValue">{title}</div>
                )}
              </div>

              <div className="videoDetailsField">
                <label className="videoDetailsLabel">Artist</label>
                {isEditing ? (
                  <input
                    type="text"
                    className="videoDetailsInput"
                    value={editedArtist}
                    onChange={(e) => setEditedArtist(e.target.value)}
                  />
                ) : (
                  <div className="videoDetailsValue">{artist}</div>
                )}
              </div>

              {featuredArtists.length > 0 && !isEditing && (
                <div className="videoDetailsField videoDetailsFieldFull">
                  <label className="videoDetailsLabel">Featured Artists</label>
                  <div className="videoDetailsValue">{featuredArtists.join(', ')}</div>
                </div>
              )}

              <div className="videoDetailsField">
                <label className="videoDetailsLabel">Album</label>
                {isEditing ? (
                  <input
                    type="text"
                    className="videoDetailsInput"
                    value={editedAlbum}
                    onChange={(e) => setEditedAlbum(e.target.value)}
                  />
                ) : (
                  <div className="videoDetailsValue">{album}</div>
                )}
              </div>

              <div className="videoDetailsField">
                <label className="videoDetailsLabel">Year</label>
                {isEditing ? (
                  <input
                    type="number"
                    className="videoDetailsInput"
                    value={editedYear}
                    onChange={(e) => setEditedYear(e.target.value)}
                    min="1900"
                    max="2100"
                  />
                ) : (
                  <div className="videoDetailsValue">{year}</div>
                )}
              </div>

              <div className="videoDetailsField">
                <label className="videoDetailsLabel">Genre</label>
                {isEditing ? (
                  <input
                    type="text"
                    className="videoDetailsInput"
                    value={editedGenre}
                    onChange={(e) => setEditedGenre(e.target.value)}
                  />
                ) : (
                  <div className="videoDetailsValue">{genre}</div>
                )}
              </div>

              <div className="videoDetailsField">
                <label className="videoDetailsLabel">Director</label>
                {isEditing ? (
                  <input
                    type="text"
                    className="videoDetailsInput"
                    value={editedDirector}
                    onChange={(e) => setEditedDirector(e.target.value)}
                  />
                ) : (
                  <div className="videoDetailsValue">{director}</div>
                )}
              </div>

              <div className="videoDetailsField">
                <label className="videoDetailsLabel">Label</label>
                {isEditing ? (
                  <input
                    type="text"
                    className="videoDetailsInput"
                    value={editedLabel}
                    onChange={(e) => setEditedLabel(e.target.value)}
                  />
                ) : (
                  <div className="videoDetailsValue">{label}</div>
                )}
              </div>

              <div className="videoDetailsField">
                <label className="videoDetailsLabel">ISRC</label>
                {isEditing ? (
                  <div>
                    <input
                      type="text"
                      className="videoDetailsInput"
                      value={editedIsrc}
                      onChange={(e) => {
                        const value = e.target.value.toUpperCase()
                        setEditedIsrc(value)
                        validateIsrc(value)
                      }}
                      placeholder="CC-XXX-YY-NNNNN"
                      maxLength={15}
                    />
                    {isrcError && (
                      <div style={{ color: 'var(--color-error, #ef4444)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                        {isrcError}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="videoDetailsValue">{currentIsrc || '—'}</div>
                )}
              </div>

              <div className="videoDetailsField">
                <label className="videoDetailsLabel">Status</label>
                <div className="videoDetailsValue">
                  <span className="videoDetailsStatusBadge">{status}</span>
                </div>
              </div>
            </div>

          </section>

          {!isEditing && (
            <section className="videoDetailsSection">
              <div className="videoDetailsSectionRow">
                <div className="videoDetailsSectionHeading">
                  <h3 className="videoDetailsSectionTitle videoDetailsSectionTitleInline">Metadata Search</h3>
                  <span className="videoDetailsSectionHelper videoDetailsSectionHelperInline">
                    Search external catalogs to enrich titles, artists, and credits.
                  </span>
                </div>
                <div className="videoDetailsFetchActions">
                  <button
                    type="button"
                    className="videoDetailsFetchButton"
                    onClick={() => setFetchModalSource('imvdb')}
                  >
                    IMVDb
                  </button>
                  <button
                    type="button"
                    className="videoDetailsFetchButton"
                    onClick={() => setFetchModalSource('discogs_master')}
                  >
                    Discogs
                  </button>
                  <button
                    type="button"
                    className="videoDetailsFetchButton"
                    onClick={() => setFetchModalSource('musicbrainz')}
                  >
                    MusicBrainz
                  </button>
                </div>
              </div>
            </section>
          )}

          {/* External Links */}
          <section className="videoDetailsSection">
            <div className="videoDetailsSectionRow">
              <div className="videoDetailsSectionHeading">
                <h3 className="videoDetailsSectionTitle videoDetailsSectionTitleInline">External Links</h3>
                <span className="videoDetailsSectionHelper videoDetailsSectionHelperInline">
                  Open source pages for this video.
                </span>
              </div>
              <div className="videoDetailsLinks">
                {imvdbUrl ? (
                  <a
                    href={imvdbUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="videoDetailsLinkButton"
                  >
                    View on IMVDb
                  </a>
                ) : (
                  <button
                    type="button"
                    className="videoDetailsLinkButton"
                    disabled
                    title="No IMVDb URL available"
                  >
                    View on IMVDb
                  </button>
                )}
                {youtubeId && (
                  <a
                    href={`https://youtube.com/watch?v=${youtubeId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="videoDetailsLinkButton"
                  >
                    View on YouTube
                  </a>
                )}
                {vimeoId && (
                  <a
                    href={`https://vimeo.com/${vimeoId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="videoDetailsLinkButton"
                  >
                    View on Vimeo
                  </a>
                )}
              </div>
            </div>
          </section>

          {/* File Information */}
          {videoFilePath && (
            <section className="videoDetailsSection">
              <div className="videoDetailsSectionHeader">
                <h3 className="videoDetailsSectionTitle">File Information</h3>
                <button
                  type="button"
                  className="videoDetailsRefreshButton"
                  onClick={() => refreshMutation.mutate()}
                  disabled={refreshMutation.isPending || isEditing}
                  title="Refresh file properties and regenerate thumbnail"
                >
                  {refreshMutation.isPending ? (
                    <span className="videoDetailsRefreshSpinner">⟳</span>
                  ) : (
                    '⟳'
                  )}
                  {refreshMutation.isPending ? 'Refreshing...' : 'Refresh'}
                </button>
              </div>
              
              {/* Thumbnail Preview */}
              <div className="videoDetailsThumbnailPreview">
                {thumbnailLoading ? (
                  <div className="videoDetailsThumbnailPlaceholder">Loading...</div>
                ) : thumbnailUrl ? (
                  <img
                    src={thumbnailUrl}
                    alt={`Thumbnail for ${title}`}
                    className="videoDetailsThumbnailImage"
                  />
                ) : (
                  <div className="videoDetailsThumbnailPlaceholder">No thumbnail</div>
                )}
              </div>

              <div className="videoDetailsGrid">
                <div className="videoDetailsField videoDetailsFieldFull">
                  <label className="videoDetailsLabel">File Path</label>
                  <div className="videoDetailsValue videoDetailsValueCode">{videoFilePath}</div>
                </div>

                <div className="videoDetailsField">
                  <label className="videoDetailsLabel">Duration</label>
                  <div className="videoDetailsValue">{duration}</div>
                </div>

                <div className="videoDetailsField">
                  <label className="videoDetailsLabel">Resolution</label>
                  <div className="videoDetailsValue">{resolution}</div>
                </div>

                <div className="videoDetailsField">
                  <label className="videoDetailsLabel">Video Codec</label>
                  <div className="videoDetailsValue">{videoCodec}</div>
                </div>

                <div className="videoDetailsField">
                  <label className="videoDetailsLabel">Audio Codec</label>
                  <div className="videoDetailsValue">{audioCodec}</div>
                </div>

                <div className="videoDetailsField">
                  <label className="videoDetailsLabel">File Size</label>
                  <div className="videoDetailsValue">{fileSize}</div>
                </div>
              </div>
            </section>
          )}

          {/* Tags */}
          {tags.length > 0 && (
            <section className="videoDetailsSection">
              <h3 className="videoDetailsSectionTitle">Tags</h3>
              <div className="videoDetailsTags">
                {tags.map((tag) => (
                  <span key={tag} className="videoDetailsTag">
                    {tag}
                  </span>
                ))}
              </div>
            </section>
          )}
        </div>

        <div className="videoDetailsModalFooter">
          <div style={{ marginRight: 'auto' }}>
            {!isEditing && (
              <button
                type="button"
                className="videoDetailsModalButton videoDetailsModalButtonDanger"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={deleteMutation.isPending}
              >
                Delete
              </button>
            )}
          </div>
          <button
            type="button"
            className="videoDetailsModalButton videoDetailsModalButtonSecondary"
            onClick={isEditing ? handleCancel : onClose}
          >
            {isEditing ? 'Cancel' : 'Close'}
          </button>
          {isEditing && (
            <button
              type="button"
              className="videoDetailsModalButton videoDetailsModalButtonPrimary"
              onClick={handleSave}
              disabled={updateMutation.isPending || !editedTitle.trim()}
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </button>
          )}
        </div>
      </div>

      {fetchModalSource && (
        <MetadataFetchModal
          artist={currentArtist}
          title={currentTitle}
          isrc={currentIsrc}
          videoId={videoId ?? undefined}
          source={fetchModalSource}
          onApply={handleApplyFetchedMetadata}
          onClose={() => setFetchModalSource(null)}
        />
      )}

      {youtubeSearchOpen && (
        <YouTubeSearchModal
          artist={currentArtist}
          trackTitle={currentTitle}
          onSelect={handleYouTubeSelect}
          onCancel={() => setYoutubeSearchOpen(false)}
        />
      )}

      {showDeleteConfirm && (
        <ConfirmDialog
          title="Delete Video"
          message={`Are you sure you want to delete "${title}"?`}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          variant="danger"
          checkboxLabel="Also delete video files from disk (cannot be undone)"
          checkboxDefaultChecked={false}
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteConfirm(false)}
        />
      )}
    </div>
  )
}
