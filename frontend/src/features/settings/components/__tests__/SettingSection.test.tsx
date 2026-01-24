import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SettingSection from '../SettingSection'

describe('SettingSection', () => {
  it('renders title', () => {
    render(
      <SettingSection title="API Settings">
        <div>Content</div>
      </SettingSection>
    )

    expect(screen.getByText('API Settings')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(
      <SettingSection title="API Settings" description="Configure your API keys">
        <div>Content</div>
      </SettingSection>
    )

    expect(screen.getByText('Configure your API keys')).toBeInTheDocument()
  })

  it('does not render description when not provided', () => {
    const { container } = render(
      <SettingSection title="API Settings">
        <div>Content</div>
      </SettingSection>
    )

    expect(container.querySelector('.settingSectionDescription')).not.toBeInTheDocument()
  })

  it('renders children content', () => {
    render(
      <SettingSection title="Settings">
        <button>Save</button>
        <input type="text" placeholder="Enter value" />
      </SettingSection>
    )

    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Enter value')).toBeInTheDocument()
  })

  it('applies correct class names', () => {
    const { container } = render(
      <SettingSection title="Test">
        <div>Content</div>
      </SettingSection>
    )

    expect(container.querySelector('.settingSection')).toBeInTheDocument()
    expect(container.querySelector('.settingSectionHeader')).toBeInTheDocument()
    expect(container.querySelector('.settingSectionTitle')).toBeInTheDocument()
    expect(container.querySelector('.settingSectionFields')).toBeInTheDocument()
  })
})
