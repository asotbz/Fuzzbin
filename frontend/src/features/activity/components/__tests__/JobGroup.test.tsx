import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import JobGroup from '../JobGroup'
import type { JobData } from '../../hooks/useActivityWebSocket'

const createMockJob = (overrides: Partial<JobData> = {}): JobData => ({
  job_id: 'job-123',
  job_type: 'import_pipeline',
  status: 'running',
  progress: 0.55,
  current_step: 'Organizing to library...',
  total_items: 100,
  processed_items: 55,
  result: undefined,
  error: undefined,
  created_at: '2024-01-01T10:00:00Z',
  started_at: '2024-01-01T10:00:01Z',
  completed_at: undefined,
  metadata: {},
  ...overrides,
})

describe('JobGroup', () => {
  it('renders fixed pipeline steps for import_pipeline jobs', () => {
    const job = createMockJob()
    const { container } = render(
      <JobGroup
        videoId={42}
        jobs={[job]}
        overallProgress={job.progress}
        groupStatus="running"
      />
    )

    const steps = container.querySelectorAll('.jobGroupPipeline .pipelineStep')
    expect(steps).toHaveLength(4)
    expect(screen.getByText('Download')).toBeInTheDocument()
    expect(screen.getByText('Process')).toBeInTheDocument()
    expect(screen.getByText('Organize')).toBeInTheDocument()
    expect(screen.getByText('Save NFO')).toBeInTheDocument()
  })

  it('maps pipeline progress to step status classes', () => {
    const job = createMockJob({ progress: 0.55 })
    const { container } = render(
      <JobGroup
        videoId={42}
        jobs={[job]}
        overallProgress={job.progress}
        groupStatus="running"
      />
    )

    const steps = container.querySelectorAll('.jobGroupPipeline .pipelineStep')
    expect(steps[0].className).toContain('pipelineStepCompleted')
    expect(steps[1].className).toContain('pipelineStepCompleted')
    expect(steps[2].className).toContain('pipelineStepRunning')
    expect(steps[3].className).toContain('pipelineStepPending')
  })

  it('renders pipeline step rows when expanded', async () => {
    const user = userEvent.setup()
    const job = createMockJob()
    const { container } = render(
      <JobGroup
        videoId={42}
        jobs={[job]}
        overallProgress={job.progress}
        groupStatus="running"
      />
    )

    const header = container.querySelector('.jobGroupHeader')
    expect(header).toBeTruthy()
    if (!header) return

    await user.click(header)

    const stepRows = container.querySelectorAll('.jobGroupJobs .jobGroupJobType')
    expect(stepRows).toHaveLength(4)
    // Check step labels within the expanded job rows (not the header pipeline)
    const stepLabels = Array.from(stepRows).map((el) => el.textContent)
    expect(stepLabels).toContain('Download')
    expect(stepLabels).toContain('Process')
    expect(stepLabels).toContain('Organize')
    expect(stepLabels).toContain('Save NFO')
  })
})
