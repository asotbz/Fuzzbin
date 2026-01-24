import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import JobProgressBar from '../JobProgressBar'
import type { JobData } from '../../hooks/useActivityWebSocket'

const createMockJob = (overrides: Partial<JobData> = {}): JobData => ({
  job_id: 'job-1',
  job_type: 'import',
  status: 'running',
  progress: 0.5,
  current_step: 'Processing...',
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

describe('JobProgressBar', () => {
  it('renders progress percentage', () => {
    render(<JobProgressBar job={createMockJob({ progress: 0.75 })} />)

    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('renders 0% for zero progress', () => {
    render(<JobProgressBar job={createMockJob({ progress: 0 })} />)

    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('renders 100% for completed progress', () => {
    render(<JobProgressBar job={createMockJob({ progress: 1, status: 'completed' })} />)

    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('rounds percentage to nearest integer', () => {
    render(<JobProgressBar job={createMockJob({ progress: 0.333 })} />)

    expect(screen.getByText('33%')).toBeInTheDocument()
  })

  it('displays item progress for running jobs without speed', () => {
    render(
      <JobProgressBar
        job={createMockJob({
          progress: 0.5,
          total_items: 20,
          processed_items: 10,
        })}
      />
    )

    expect(screen.getByText('10/20 items')).toBeInTheDocument()
  })

  it('displays download speed when available', () => {
    render(
      <JobProgressBar
        job={createMockJob({
          download_speed: 5.5,
        })}
      />
    )

    expect(screen.getByText('5.5 MB/s')).toBeInTheDocument()
  })

  it('displays ETA when available', () => {
    render(
      <JobProgressBar
        job={createMockJob({
          download_speed: 2.0,
          eta_seconds: 120,
        })}
      />
    )

    expect(screen.getByText('ETA: 2m 0s')).toBeInTheDocument()
  })

  it('displays ETA in seconds for short times', () => {
    render(
      <JobProgressBar
        job={createMockJob({
          download_speed: 10.0,
          eta_seconds: 45,
        })}
      />
    )

    expect(screen.getByText('ETA: 45s')).toBeInTheDocument()
  })

  it('applies running class for running status', () => {
    const { container } = render(
      <JobProgressBar job={createMockJob({ status: 'running' })} />
    )

    expect(container.querySelector('.progressBarFillRunning')).toBeInTheDocument()
    expect(container.querySelector('.progressRunning')).toBeInTheDocument()
  })

  it('applies completed class for completed status', () => {
    const { container } = render(
      <JobProgressBar job={createMockJob({ status: 'completed', progress: 1 })} />
    )

    expect(container.querySelector('.progressBarFillCompleted')).toBeInTheDocument()
    expect(container.querySelector('.progressCompleted')).toBeInTheDocument()
  })

  it('applies failed class for failed status', () => {
    const { container } = render(
      <JobProgressBar job={createMockJob({ status: 'failed', progress: 0.5 })} />
    )

    expect(container.querySelector('.progressBarFillFailed')).toBeInTheDocument()
    expect(container.querySelector('.progressFailed')).toBeInTheDocument()
  })

  it('applies failed class for cancelled status', () => {
    const { container } = render(
      <JobProgressBar job={createMockJob({ status: 'cancelled', progress: 0.3 })} />
    )

    expect(container.querySelector('.progressBarFillFailed')).toBeInTheDocument()
    expect(container.querySelector('.progressFailed')).toBeInTheDocument()
  })

  it('applies failed class for timeout status', () => {
    const { container } = render(
      <JobProgressBar job={createMockJob({ status: 'timeout', progress: 0.8 })} />
    )

    expect(container.querySelector('.progressBarFillFailed')).toBeInTheDocument()
    expect(container.querySelector('.progressFailed')).toBeInTheDocument()
  })

  it('sets progress bar width correctly', () => {
    const { container } = render(
      <JobProgressBar job={createMockJob({ progress: 0.65 })} />
    )

    const fillElement = container.querySelector('.progressBarFill')
    expect(fillElement).toHaveStyle({ width: '65%' })
  })
})
