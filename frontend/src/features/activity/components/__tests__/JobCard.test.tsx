import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import JobCard from '../JobCard'
import type { JobData } from '../../hooks/useActivityWebSocket'

const createMockJob = (overrides: Partial<JobData> = {}): JobData => ({
  job_id: 'job-123',
  job_type: 'download_youtube',
  status: 'running',
  progress: 0.5,
  current_step: 'Downloading video...',
  total_items: 10,
  processed_items: 5,
  result: undefined,
  error: undefined,
  created_at: '2024-01-01T10:00:00Z',
  started_at: '2024-01-01T10:00:01Z',
  completed_at: undefined,
  metadata: {},
  ...overrides,
})

describe('JobCard', () => {
  describe('rendering', () => {
    it('renders job type label', () => {
      render(<JobCard job={createMockJob({ job_type: 'download_youtube' })} />)

      expect(screen.getByText('YouTube Download')).toBeInTheDocument()
    })

    it('renders formatted job type for unknown types', () => {
      render(<JobCard job={createMockJob({ job_type: 'some_custom_job' })} />)

      expect(screen.getByText('Some Custom Job')).toBeInTheDocument()
    })

    it('renders job ID', () => {
      render(<JobCard job={createMockJob({ job_id: 'test-job-456' })} />)

      expect(screen.getByText('test-job-456')).toBeInTheDocument()
    })

    it('renders video label when metadata includes video details', () => {
      render(
        <JobCard
          job={createMockJob({
            metadata: {
              video_id: 42,
              video_title: 'Test Title',
              video_artist: 'Test Artist',
            },
          })}
        />
      )

      expect(screen.getByText('Test Artist - Test Title (42)')).toBeInTheDocument()
    })

    it('renders current step', () => {
      render(<JobCard job={createMockJob({ current_step: 'Processing files...' })} />)

      expect(screen.getByText('Processing files...')).toBeInTheDocument()
    })

    it('renders item counts', () => {
      render(
        <JobCard job={createMockJob({ processed_items: 7, total_items: 20 })} />
      )

      // Text appears in both progress bar and job meta sections
      expect(screen.getAllByText(/7\/20 tasks/).length).toBeGreaterThan(0)
    })

    it('renders progress bar', () => {
      const { container } = render(<JobCard job={createMockJob({ progress: 0.5 })} />)

      expect(container.querySelector('.progressBarFill')).toBeInTheDocument()
    })

    it('renders pipeline steps for import_pipeline jobs', () => {
      const { container } = render(
        <JobCard
          job={createMockJob({
            job_type: 'import_pipeline',
            status: 'running',
            progress: 0.35,
          })}
        />
      )

      const steps = container.querySelectorAll('.jobCardPipeline .pipelineStep')
      expect(steps).toHaveLength(4)
      expect(screen.getByText('Download')).toBeInTheDocument()
      expect(screen.getByText('Process')).toBeInTheDocument()
      expect(screen.getByText('Organize')).toBeInTheDocument()
      expect(screen.getByText('Save NFO')).toBeInTheDocument()
    })
  })

  describe('job type labels', () => {
    const jobTypeCases = [
      ['download_youtube', 'YouTube Download'],
      ['import_pipeline', 'Import Pipeline'],
      ['import_spotify_batch', 'Spotify Batch Import'],
      ['import_nfo', 'NFO Import'],
      ['import_add_single', 'Single Video Import'],
      ['metadata_enrich', 'Metadata Enrichment'],
      ['file_organize', 'File Organization'],
      ['library_scan', 'Library Scan'],
      ['backup', 'System Backup'],
      ['video_post_process', 'Video Processing'],
    ]

    it.each(jobTypeCases)('displays "%s" as "%s"', (jobType, expectedLabel) => {
      render(<JobCard job={createMockJob({ job_type: jobType })} />)

      expect(screen.getByText(expectedLabel)).toBeInTheDocument()
    })
  })

  describe('status classes', () => {
    it('applies running class for running status', () => {
      const { container } = render(<JobCard job={createMockJob({ status: 'running' })} />)

      expect(container.querySelector('.jobCardRunning')).toBeInTheDocument()
    })

    it('applies running class for pending status', () => {
      const { container } = render(<JobCard job={createMockJob({ status: 'pending' })} />)

      expect(container.querySelector('.jobCardRunning')).toBeInTheDocument()
    })

    it('applies completed class for completed status', () => {
      const { container } = render(
        <JobCard
          job={createMockJob({
            status: 'completed',
            progress: 1,
            completed_at: '2024-01-01T10:05:00Z',
          })}
        />
      )

      expect(container.querySelector('.jobCardCompleted')).toBeInTheDocument()
    })

    it('applies failed class for failed status', () => {
      const { container } = render(
        <JobCard job={createMockJob({ status: 'failed', error: 'Something went wrong' })} />
      )

      expect(container.querySelector('.jobCardFailed')).toBeInTheDocument()
    })

    it('applies failed class for cancelled status', () => {
      const { container } = render(
        <JobCard job={createMockJob({ status: 'cancelled' })} />
      )

      expect(container.querySelector('.jobCardFailed')).toBeInTheDocument()
    })

    it('applies failed class for timeout status', () => {
      const { container } = render(
        <JobCard job={createMockJob({ status: 'timeout' })} />
      )

      expect(container.querySelector('.jobCardFailed')).toBeInTheDocument()
    })
  })

  describe('actions', () => {
    it('shows Cancel button for running jobs when onCancel provided', () => {
      const onCancel = vi.fn()
      render(<JobCard job={createMockJob({ status: 'running' })} onCancel={onCancel} />)

      expect(screen.getByRole('button', { name: /cancel job/i })).toBeInTheDocument()
    })

    it('does not show Cancel button when onCancel not provided', () => {
      render(<JobCard job={createMockJob({ status: 'running' })} />)

      expect(screen.queryByRole('button', { name: /cancel job/i })).not.toBeInTheDocument()
    })

    it('does not show Cancel button for completed jobs', () => {
      const onCancel = vi.fn()
      render(
        <JobCard
          job={createMockJob({ status: 'completed', completed_at: '2024-01-01T10:05:00Z' })}
          onCancel={onCancel}
        />
      )

      expect(screen.queryByRole('button', { name: /cancel job/i })).not.toBeInTheDocument()
    })

    it('calls onCancel with job ID when Cancel clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      render(<JobCard job={createMockJob({ job_id: 'job-xyz' })} onCancel={onCancel} />)

      await user.click(screen.getByRole('button', { name: /cancel job/i }))

      expect(onCancel).toHaveBeenCalledWith('job-xyz')
    })

    it('shows Retry button for failed jobs when onRetry provided', () => {
      const onRetry = vi.fn()
      render(<JobCard job={createMockJob({ status: 'failed' })} onRetry={onRetry} />)

      expect(screen.getByRole('button', { name: /retry job/i })).toBeInTheDocument()
    })

    it('does not show Retry button when onRetry not provided', () => {
      render(<JobCard job={createMockJob({ status: 'failed' })} />)

      expect(screen.queryByRole('button', { name: /retry job/i })).not.toBeInTheDocument()
    })

    it('calls onRetry with job when Retry clicked', async () => {
      const user = userEvent.setup()
      const onRetry = vi.fn()
      const job = createMockJob({ status: 'failed' })
      render(<JobCard job={job} onRetry={onRetry} />)

      await user.click(screen.getByRole('button', { name: /retry job/i }))

      expect(onRetry).toHaveBeenCalledWith(job)
    })

    it('shows Clear button for non-running jobs when onClear provided', () => {
      const onClear = vi.fn()
      render(
        <JobCard
          job={createMockJob({ status: 'completed', completed_at: '2024-01-01T10:05:00Z' })}
          onClear={onClear}
        />
      )

      expect(screen.getByRole('button', { name: /clear job/i })).toBeInTheDocument()
    })

    it('does not show Clear button for running jobs', () => {
      const onClear = vi.fn()
      render(<JobCard job={createMockJob({ status: 'running' })} onClear={onClear} />)

      expect(screen.queryByRole('button', { name: /clear job/i })).not.toBeInTheDocument()
    })

    it('calls onClear with job ID when Clear clicked', async () => {
      const user = userEvent.setup()
      const onClear = vi.fn()
      render(
        <JobCard
          job={createMockJob({ job_id: 'job-abc', status: 'completed', completed_at: '2024-01-01T10:05:00Z' })}
          onClear={onClear}
        />
      )

      await user.click(screen.getByRole('button', { name: /clear job/i }))

      expect(onClear).toHaveBeenCalledWith('job-abc')
    })
  })

  describe('details toggle', () => {
    it('shows Details button', () => {
      render(<JobCard job={createMockJob()} />)

      expect(screen.getByRole('button', { name: /toggle job details/i })).toBeInTheDocument()
    })

    it('toggles to show details on click', async () => {
      const user = userEvent.setup()
      render(
        <JobCard
          job={createMockJob({
            metadata: { source: 'test' },
          })}
        />
      )

      await user.click(screen.getByRole('button', { name: /toggle job details/i }))

      expect(screen.getByText('Hide')).toBeInTheDocument()
      expect(screen.getByText(/"source": "test"/)).toBeInTheDocument()
    })

    it('shows error in details when present', async () => {
      const user = userEvent.setup()
      render(
        <JobCard
          job={createMockJob({
            status: 'failed',
            error: 'Connection timeout',
          })}
        />
      )

      await user.click(screen.getByRole('button', { name: /toggle job details/i }))

      expect(screen.getByText('Error:')).toBeInTheDocument()
      expect(screen.getByText('Connection timeout')).toBeInTheDocument()
    })

    it('shows result in details when present', async () => {
      const user = userEvent.setup()
      render(
        <JobCard
          job={createMockJob({
            status: 'completed',
            completed_at: '2024-01-01T10:05:00Z',
            result: { imported: 5 },
          })}
        />
      )

      await user.click(screen.getByRole('button', { name: /toggle job details/i }))

      expect(screen.getByText('Result:')).toBeInTheDocument()
      expect(screen.getByText(/"imported": 5/)).toBeInTheDocument()
    })

    it('hides details on second click', async () => {
      const user = userEvent.setup()
      render(
        <JobCard
          job={createMockJob({
            metadata: { source: 'test' },
          })}
        />
      )

      const toggle = screen.getByRole('button', { name: /toggle job details/i })
      await user.click(toggle) // show
      await user.click(toggle) // hide

      expect(screen.getByText('Details')).toBeInTheDocument()
      expect(screen.queryByText(/"source": "test"/)).not.toBeInTheDocument()
    })
  })
})
