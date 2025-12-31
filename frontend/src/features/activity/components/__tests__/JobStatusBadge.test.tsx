import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import JobStatusBadge from '../JobStatusBadge'

describe('JobStatusBadge', () => {
  it('renders the status text in uppercase', () => {
    render(<JobStatusBadge status="pending" />)

    expect(screen.getByText('PENDING')).toBeInTheDocument()
  })

  it('applies correct CSS class for pending status', () => {
    const { container } = render(<JobStatusBadge status="pending" />)

    const badge = container.querySelector('.jobStatusBadge')
    expect(badge).toHaveClass('jobStatusBadgePending')
  })

  it('applies correct CSS class for running status', () => {
    const { container } = render(<JobStatusBadge status="running" />)

    const badge = container.querySelector('.jobStatusBadge')
    expect(badge).toHaveClass('jobStatusBadgeRunning')
  })

  it('applies correct CSS class for completed status', () => {
    const { container } = render(<JobStatusBadge status="completed" />)

    const badge = container.querySelector('.jobStatusBadge')
    expect(badge).toHaveClass('jobStatusBadgeCompleted')
  })

  it('applies correct CSS class for failed status', () => {
    const { container } = render(<JobStatusBadge status="failed" />)

    const badge = container.querySelector('.jobStatusBadge')
    expect(badge).toHaveClass('jobStatusBadgeFailed')
  })

  it('applies correct CSS class for cancelled status', () => {
    const { container } = render(<JobStatusBadge status="cancelled" />)

    const badge = container.querySelector('.jobStatusBadge')
    expect(badge).toHaveClass('jobStatusBadgeCancelled')
  })

  it('renders as a span element', () => {
    render(<JobStatusBadge status="pending" />)

    const element = screen.getByText('PENDING')
    expect(element.tagName).toBe('SPAN')
  })
})
