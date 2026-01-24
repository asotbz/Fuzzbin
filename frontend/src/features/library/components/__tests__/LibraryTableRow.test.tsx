import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LibraryTableRow from '../LibraryTableRow'
import type { Video } from '../../../../lib/api/types'

const createMockVideo = (overrides: Partial<Video> = {}): Video => ({
  id: 1,
  title: 'Test Video',
  artist: 'Test Artist',
  album: 'Test Album',
  year: 2024,
  director: 'Test Director',
  studio: 'Test Studio',
  genre: 'Pop',
  isrc: 'USRC12345678',
  duration: 245, // 4:05
  ...overrides,
} as Video)

describe('LibraryTableRow', () => {
  const defaultProps = {
    video: createMockVideo(),
    selected: false,
    columns: 'full' as const,
    onToggleSelection: vi.fn(),
    onVideoClick: vi.fn(),
  }

  describe('rendering', () => {
    it('renders video title', () => {
      render(<LibraryTableRow {...defaultProps} />)

      expect(screen.getByText('Test Video')).toBeInTheDocument()
    })

    it('renders artist name', () => {
      render(<LibraryTableRow {...defaultProps} />)

      expect(screen.getByText('Test Artist')).toBeInTheDocument()
    })

    it('renders album', () => {
      render(<LibraryTableRow {...defaultProps} />)

      expect(screen.getByText('Test Album')).toBeInTheDocument()
    })

    it('renders year', () => {
      render(<LibraryTableRow {...defaultProps} />)

      expect(screen.getByText('2024')).toBeInTheDocument()
    })

    it('renders director', () => {
      render(<LibraryTableRow {...defaultProps} />)

      expect(screen.getByText('Test Director')).toBeInTheDocument()
    })

    it('renders studio', () => {
      render(<LibraryTableRow {...defaultProps} />)

      expect(screen.getByText('Test Studio')).toBeInTheDocument()
    })

    it('renders formatted duration', () => {
      render(<LibraryTableRow {...defaultProps} video={createMockVideo({ duration: 245 })} />)

      expect(screen.getByText('4:05')).toBeInTheDocument()
    })

    it('renders — for missing duration', () => {
      render(<LibraryTableRow {...defaultProps} video={createMockVideo({ duration: undefined })} />)

      // Duration shows as em-dash when null
      const cells = screen.getAllByText('—')
      expect(cells.length).toBeGreaterThan(0)
    })

    it('renders Untitled for missing title', () => {
      render(<LibraryTableRow {...defaultProps} video={createMockVideo({ title: '' })} />)

      expect(screen.getByText('Untitled')).toBeInTheDocument()
    })

    it('renders — for missing artist', () => {
      render(<LibraryTableRow {...defaultProps} video={createMockVideo({ artist: '' })} />)

      expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    })
  })

  describe('duration formatting', () => {
    it('formats seconds correctly for short durations', () => {
      render(<LibraryTableRow {...defaultProps} video={createMockVideo({ duration: 45 })} />)

      expect(screen.getByText('0:45')).toBeInTheDocument()
    })

    it('formats minutes and seconds', () => {
      render(<LibraryTableRow {...defaultProps} video={createMockVideo({ duration: 183 })} />)

      expect(screen.getByText('3:03')).toBeInTheDocument()
    })

    it('pads seconds to two digits', () => {
      render(<LibraryTableRow {...defaultProps} video={createMockVideo({ duration: 65 })} />)

      expect(screen.getByText('1:05')).toBeInTheDocument()
    })
  })

  describe('selection', () => {
    it('renders checkbox', () => {
      render(<LibraryTableRow {...defaultProps} />)

      expect(screen.getByRole('checkbox')).toBeInTheDocument()
    })

    it('checkbox is unchecked when not selected', () => {
      render(<LibraryTableRow {...defaultProps} selected={false} />)

      expect(screen.getByRole('checkbox')).not.toBeChecked()
    })

    it('checkbox is checked when selected', () => {
      render(<LibraryTableRow {...defaultProps} selected={true} />)

      expect(screen.getByRole('checkbox')).toBeChecked()
    })

    it('calls onToggleSelection when checkbox clicked', async () => {
      const user = userEvent.setup()
      const onToggleSelection = vi.fn()
      render(
        <LibraryTableRow
          {...defaultProps}
          video={createMockVideo({ id: 42 })}
          onToggleSelection={onToggleSelection}
        />
      )

      await user.click(screen.getByRole('checkbox'))

      expect(onToggleSelection).toHaveBeenCalledWith(42)
    })

    it('applies selected class when selected', () => {
      const { container } = render(<LibraryTableRow {...defaultProps} selected={true} />)

      expect(container.querySelector('.libraryTableRowSelected')).toBeInTheDocument()
    })

    it('has aria-selected attribute', () => {
      render(<LibraryTableRow {...defaultProps} selected={true} />)

      expect(screen.getByRole('row')).toHaveAttribute('aria-selected', 'true')
    })
  })

  describe('interactions', () => {
    it('calls onVideoClick when row clicked', async () => {
      const user = userEvent.setup()
      const onVideoClick = vi.fn()
      const video = createMockVideo()
      render(<LibraryTableRow {...defaultProps} video={video} onVideoClick={onVideoClick} />)

      await user.click(screen.getByRole('row'))

      expect(onVideoClick).toHaveBeenCalledWith(video)
    })

    it('shows play button when onPlayVideo provided', () => {
      const onPlayVideo = vi.fn()
      render(<LibraryTableRow {...defaultProps} onPlayVideo={onPlayVideo} />)

      expect(screen.getByRole('button', { name: /play video/i })).toBeInTheDocument()
    })

    it('does not show play button when onPlayVideo not provided', () => {
      render(<LibraryTableRow {...defaultProps} />)

      expect(screen.queryByRole('button', { name: /play video/i })).not.toBeInTheDocument()
    })

    it('calls onPlayVideo when play button clicked', async () => {
      const user = userEvent.setup()
      const onPlayVideo = vi.fn()
      const video = createMockVideo()
      render(<LibraryTableRow {...defaultProps} video={video} onPlayVideo={onPlayVideo} />)

      await user.click(screen.getByRole('button', { name: /play video/i }))

      expect(onPlayVideo).toHaveBeenCalledWith(video)
    })

    it('shows details button', () => {
      render(<LibraryTableRow {...defaultProps} />)

      expect(screen.getByRole('button', { name: /view details/i })).toBeInTheDocument()
    })

    it('calls onVideoClick when details button clicked', async () => {
      const user = userEvent.setup()
      const onVideoClick = vi.fn()
      const video = createMockVideo()
      render(<LibraryTableRow {...defaultProps} video={video} onVideoClick={onVideoClick} />)

      await user.click(screen.getByRole('button', { name: /view details/i }))

      expect(onVideoClick).toHaveBeenCalledWith(video)
    })
  })

  describe('column visibility', () => {
    it('shows all columns in full mode', () => {
      render(<LibraryTableRow {...defaultProps} columns="full" />)

      expect(screen.getByText('Test Album')).toBeInTheDocument()
      expect(screen.getByText('2024')).toBeInTheDocument()
      expect(screen.getByText('Test Director')).toBeInTheDocument()
      expect(screen.getByText('Test Studio')).toBeInTheDocument()
      expect(screen.getByText('4:05')).toBeInTheDocument()
    })

    it('shows album and genre in core mode', () => {
      render(<LibraryTableRow {...defaultProps} columns="core" />)

      expect(screen.getByText('Test Album')).toBeInTheDocument()
      expect(screen.getByText('Pop')).toBeInTheDocument()
    })

    it('hides year and director in core mode', () => {
      render(<LibraryTableRow {...defaultProps} columns="core" />)

      expect(screen.queryByText('2024')).not.toBeInTheDocument()
      expect(screen.queryByText('Test Director')).not.toBeInTheDocument()
    })

    it('shows genre and isrc in curation mode', () => {
      render(<LibraryTableRow {...defaultProps} columns="curation" />)

      expect(screen.getByText('Pop')).toBeInTheDocument()
      expect(screen.getByText('USRC12345678')).toBeInTheDocument()
    })

    it('hides album in curation mode', () => {
      render(<LibraryTableRow {...defaultProps} columns="curation" />)

      expect(screen.queryByText('Test Album')).not.toBeInTheDocument()
    })
  })

  describe('featured artists', () => {
    it('displays featured artists when present', () => {
      const videoWithFeatured = {
        ...createMockVideo(),
        artists: [
          { name: 'Main Artist', role: 'primary' },
          { name: 'Featured One', role: 'featured' },
          { name: 'Featured Two', role: 'featured' },
        ],
      } as unknown as Video

      render(<LibraryTableRow {...defaultProps} video={videoWithFeatured} />)

      expect(screen.getByText('ft. Featured One, Featured Two')).toBeInTheDocument()
    })

    it('does not display featured section when no featured artists', () => {
      render(<LibraryTableRow {...defaultProps} />)

      expect(screen.queryByText(/ft\./)).not.toBeInTheDocument()
    })
  })

  describe('tags', () => {
    it('displays tags when present in curation mode', () => {
      const videoWithTags = {
        ...createMockVideo(),
        tags: [
          { name: 'Rock' },
          { name: 'Live' },
        ],
      } as unknown as Video

      render(<LibraryTableRow {...defaultProps} video={videoWithTags} columns="curation" />)

      expect(screen.getByText('Rock, Live')).toBeInTheDocument()
    })

    it('displays — when no tags in curation mode', () => {
      render(<LibraryTableRow {...defaultProps} columns="curation" />)

      // Multiple cells may show em-dash, just verify at least one exists
      expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    })
  })
})
