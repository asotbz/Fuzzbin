import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import PageHeader from '../PageHeader'

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('PageHeader', () => {
  it('renders title', () => {
    renderWithRouter(<PageHeader title="Test Page" />)

    expect(screen.getByRole('heading', { name: 'Test Page' })).toBeInTheDocument()
  })

  it('renders icon when provided', () => {
    renderWithRouter(<PageHeader title="Test" iconSrc="/test-icon.png" iconAlt="Test Icon" />)

    const icon = screen.getByAltText('Test Icon')
    expect(icon).toBeInTheDocument()
    expect(icon).toHaveAttribute('src', '/test-icon.png')
  })

  it('uses title as icon alt text if iconAlt not provided', () => {
    renderWithRouter(<PageHeader title="Test Page" iconSrc="/test-icon.png" />)

    expect(screen.getByAltText('Test Page')).toBeInTheDocument()
  })

  it('renders actions when provided', () => {
    renderWithRouter(
      <PageHeader
        title="Test"
        actions={<button type="button">Action Button</button>}
      />
    )

    expect(screen.getByRole('button', { name: 'Action Button' })).toBeInTheDocument()
  })

  it('renders nav items', () => {
    renderWithRouter(
      <PageHeader
        title="Test"
        navItems={[
          { label: 'Tab 1', to: '/tab1' },
          { label: 'Tab 2', to: '/tab2' },
        ]}
      />
    )

    expect(screen.getByRole('link', { name: 'Tab 1' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Tab 2' })).toBeInTheDocument()
  })

  it('renders sub-nav items', () => {
    renderWithRouter(
      <PageHeader
        title="Test"
        subNavItems={[
          { label: 'Sub 1', to: '/sub1' },
          { label: 'Sub 2', to: '/sub2' },
        ]}
        subNavLabel="Secondary"
      />
    )

    expect(screen.getByRole('link', { name: 'Sub 1' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sub 2' })).toBeInTheDocument()
  })

  it('applies custom className', () => {
    const { container } = renderWithRouter(
      <PageHeader title="Test" className="custom-class" />
    )

    expect(container.querySelector('.pageHeader.custom-class')).toBeInTheDocument()
  })

  it('applies accent color styles', () => {
    const { container } = renderWithRouter(
      <PageHeader title="Test" accent="#ff0000" />
    )

    const header = container.querySelector('.pageHeader') as HTMLElement
    expect(header.style.getPropertyValue('--header-accent')).toBe('#ff0000')
    expect(header.style.getPropertyValue('--nav-accent')).toBe('#ff0000')
  })

  it('does not apply style when no accent', () => {
    const { container } = renderWithRouter(<PageHeader title="Test" />)

    const header = container.querySelector('.pageHeader') as HTMLElement
    expect(header.style.getPropertyValue('--header-accent')).toBe('')
  })

  it('applies aria-label to nav links', () => {
    renderWithRouter(
      <PageHeader
        title="Test"
        navItems={[
          { label: 'Tab', to: '/tab', ariaLabel: 'Navigate to tab' },
        ]}
      />
    )

    expect(screen.getByRole('link', { name: 'Navigate to tab' })).toBeInTheDocument()
  })
})
