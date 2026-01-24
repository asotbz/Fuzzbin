import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import HomePage from '../Home'

describe('HomePage', () => {
  it('renders the logo', () => {
    render(<HomePage />)

    expect(screen.getByAltText('Fuzzbin')).toBeInTheDocument()
  })

  it('has correct logo source', () => {
    render(<HomePage />)

    const logo = screen.getByAltText('Fuzzbin')
    expect(logo).toHaveAttribute('src', '/fuzzbin-logo.png')
  })

  it('renders within centered page container', () => {
    const { container } = render(<HomePage />)

    expect(container.querySelector('.centeredPage')).toBeInTheDocument()
  })

  it('renders logo within panel', () => {
    const { container } = render(<HomePage />)

    expect(container.querySelector('.panel .splash')).toBeInTheDocument()
  })
})
