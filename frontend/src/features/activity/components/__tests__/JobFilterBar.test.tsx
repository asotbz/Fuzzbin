import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import JobFilterBar from '../JobFilterBar'

describe('JobFilterBar', () => {
  const defaultProps = {
    statusFilter: new Set<string>(),
    onStatusFilterChange: vi.fn(),
    jobTypeFilter: new Set<string>(),
    onJobTypeFilterChange: vi.fn(),
    searchQuery: '',
    onSearchQueryChange: vi.fn(),
    availableJobTypes: ['download_youtube', 'import_nfo', 'import_spotify_batch'],
  }

  describe('rendering', () => {
    it('renders status filter buttons', () => {
      render(<JobFilterBar {...defaultProps} />)

      // There are two "All" buttons (one for status, one for job type)
      expect(screen.getAllByRole('button', { name: 'All' })).toHaveLength(2)
      expect(screen.getByRole('button', { name: 'Running' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Pending' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Completed' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Failed' })).toBeInTheDocument()
    })

    it('renders job type filter buttons', () => {
      render(<JobFilterBar {...defaultProps} />)

      expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'NFO Import' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Spotify Import' })).toBeInTheDocument()
    })

    it('renders search input', () => {
      render(<JobFilterBar {...defaultProps} />)

      expect(screen.getByLabelText('Search jobs')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('Search jobs...')).toBeInTheDocument()
    })

    it('shows active state for selected status filters', () => {
      render(
        <JobFilterBar
          {...defaultProps}
          statusFilter={new Set(['running', 'pending'])}
        />
      )

      expect(screen.getByRole('button', { name: 'Running' })).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByRole('button', { name: 'Pending' })).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByRole('button', { name: 'Completed' })).toHaveAttribute('aria-pressed', 'false')
    })

    it('shows All as active when no status filters selected', () => {
      render(<JobFilterBar {...defaultProps} />)

      const allButtons = screen.getAllByRole('button', { name: 'All' })
      expect(allButtons[0]).toHaveAttribute('aria-pressed', 'true')
    })

    it('shows active state for selected job type filters', () => {
      render(
        <JobFilterBar
          {...defaultProps}
          jobTypeFilter={new Set(['download_youtube'])}
        />
      )

      expect(screen.getByRole('button', { name: 'Download' })).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByRole('button', { name: 'NFO Import' })).toHaveAttribute('aria-pressed', 'false')
    })
  })

  describe('status filter interactions', () => {
    it('calls onStatusFilterChange when clicking status button', async () => {
      const user = userEvent.setup()
      const onStatusFilterChange = vi.fn()
      render(
        <JobFilterBar
          {...defaultProps}
          onStatusFilterChange={onStatusFilterChange}
        />
      )

      await user.click(screen.getByRole('button', { name: 'Running' }))

      expect(onStatusFilterChange).toHaveBeenCalledWith(new Set(['running']))
    })

    it('toggles status filter off when clicking selected status', async () => {
      const user = userEvent.setup()
      const onStatusFilterChange = vi.fn()
      render(
        <JobFilterBar
          {...defaultProps}
          statusFilter={new Set(['running'])}
          onStatusFilterChange={onStatusFilterChange}
        />
      )

      await user.click(screen.getByRole('button', { name: 'Running' }))

      expect(onStatusFilterChange).toHaveBeenCalledWith(new Set())
    })

    it('clears all status filters when clicking All', async () => {
      const user = userEvent.setup()
      const onStatusFilterChange = vi.fn()
      render(
        <JobFilterBar
          {...defaultProps}
          statusFilter={new Set(['running', 'pending'])}
          onStatusFilterChange={onStatusFilterChange}
        />
      )

      const allButtons = screen.getAllByRole('button', { name: 'All' })
      await user.click(allButtons[0])

      expect(onStatusFilterChange).toHaveBeenCalledWith(new Set())
    })
  })

  describe('job type filter interactions', () => {
    it('calls onJobTypeFilterChange when clicking job type button', async () => {
      const user = userEvent.setup()
      const onJobTypeFilterChange = vi.fn()
      render(
        <JobFilterBar
          {...defaultProps}
          onJobTypeFilterChange={onJobTypeFilterChange}
        />
      )

      await user.click(screen.getByRole('button', { name: 'Download' }))

      expect(onJobTypeFilterChange).toHaveBeenCalledWith(new Set(['download_youtube']))
    })

    it('toggles job type filter off when clicking selected type', async () => {
      const user = userEvent.setup()
      const onJobTypeFilterChange = vi.fn()
      render(
        <JobFilterBar
          {...defaultProps}
          jobTypeFilter={new Set(['download_youtube'])}
          onJobTypeFilterChange={onJobTypeFilterChange}
        />
      )

      await user.click(screen.getByRole('button', { name: 'Download' }))

      expect(onJobTypeFilterChange).toHaveBeenCalledWith(new Set())
    })

    it('clears all job type filters when clicking All', async () => {
      const user = userEvent.setup()
      const onJobTypeFilterChange = vi.fn()
      render(
        <JobFilterBar
          {...defaultProps}
          jobTypeFilter={new Set(['download_youtube', 'import_nfo'])}
          onJobTypeFilterChange={onJobTypeFilterChange}
        />
      )

      const allButtons = screen.getAllByRole('button', { name: 'All' })
      await user.click(allButtons[1]) // Second All button is for job types

      expect(onJobTypeFilterChange).toHaveBeenCalledWith(new Set())
    })
  })

  describe('search interactions', () => {
    it('calls onSearchQueryChange when typing in search', async () => {
      const user = userEvent.setup()
      const onSearchQueryChange = vi.fn()
      render(
        <JobFilterBar
          {...defaultProps}
          onSearchQueryChange={onSearchQueryChange}
        />
      )

      await user.type(screen.getByLabelText('Search jobs'), 'test query')

      expect(onSearchQueryChange).toHaveBeenCalled()
    })

    it('displays current search query', () => {
      render(
        <JobFilterBar
          {...defaultProps}
          searchQuery="existing search"
        />
      )

      expect(screen.getByLabelText('Search jobs')).toHaveValue('existing search')
    })
  })

  describe('job type labels', () => {
    it('formats unknown job types by replacing underscores', () => {
      render(
        <JobFilterBar
          {...defaultProps}
          availableJobTypes={['custom_job_type']}
        />
      )

      expect(screen.getByRole('button', { name: 'custom job type' })).toBeInTheDocument()
    })

    it('uses predefined labels for known job types', () => {
      render(
        <JobFilterBar
          {...defaultProps}
          availableJobTypes={[
            'download_youtube',
            'import_spotify_batch',
            'import_nfo',
            'import_add_single',
            'metadata_enrich',
            'file_organize',
            'library_scan',
            'video_post_process',
          ]}
        />
      )

      expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Spotify Import' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'NFO Import' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Single Import' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Metadata' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Organize' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Library Scan' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Video Processing' })).toBeInTheDocument()
    })
  })
})
