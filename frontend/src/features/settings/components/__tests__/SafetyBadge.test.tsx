import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SafetyBadge from '../SafetyBadge'

describe('SafetyBadge', () => {
  it('returns null for safe level', () => {
    const { container } = render(<SafetyBadge level="safe" />)

    expect(container.firstChild).toBeNull()
  })

  it('renders reload required badge', () => {
    render(<SafetyBadge level="requires_reload" />)

    expect(screen.getByText('RELOAD REQUIRED')).toBeInTheDocument()
    expect(screen.getByText('↻')).toBeInTheDocument()
  })

  it('renders restart required badge for affects_state', () => {
    render(<SafetyBadge level="affects_state" />)

    expect(screen.getByText('RESTART REQUIRED')).toBeInTheDocument()
    expect(screen.getByText('⚠')).toBeInTheDocument()
  })

  it('applies correct class for requires_reload', () => {
    const { container } = render(<SafetyBadge level="requires_reload" />)

    expect(container.querySelector('.safetyBadge--requires_reload')).toBeInTheDocument()
  })

  it('applies correct class for affects_state', () => {
    const { container } = render(<SafetyBadge level="affects_state" />)

    expect(container.querySelector('.safetyBadge--affects_state')).toBeInTheDocument()
  })

  it('applies custom className', () => {
    const { container } = render(<SafetyBadge level="requires_reload" className="custom-class" />)

    expect(container.querySelector('.custom-class')).toBeInTheDocument()
  })

  it('has correct title for reload required', () => {
    const { container } = render(<SafetyBadge level="requires_reload" />)

    const badge = container.querySelector('.safetyBadge')
    expect(badge).toHaveAttribute('title', 'Component reload needed for changes to take effect')
  })

  it('has correct title for affects_state', () => {
    const { container } = render(<SafetyBadge level="affects_state" />)

    const badge = container.querySelector('.safetyBadge')
    expect(badge).toHaveAttribute('title', 'Application restart may be required')
  })
})
