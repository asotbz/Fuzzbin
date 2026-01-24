import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConfirmChangeModal from '../ConfirmChangeModal'
import type { ConfigConflictError } from '../../../../lib/api/endpoints/config'

const createMockConflict = (overrides: Partial<ConfigConflictError> = {}): ConfigConflictError => ({
  message: 'Configuration change requires confirmation',
  affected_fields: [
    {
      path: 'server.port',
      current_value: 8000,
      requested_value: 9000,
      safety_level: 'requires_reload',
    },
  ],
  required_actions: [
    {
      action_type: 'reload',
      target: null,
      description: 'Reload the application for changes to take effect',
    },
  ],
  ...overrides,
})

describe('ConfirmChangeModal', () => {
  const defaultProps = {
    conflict: createMockConflict(),
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  }

  describe('rendering', () => {
    it('renders title', () => {
      render(<ConfirmChangeModal {...defaultProps} />)

      expect(screen.getByText('CONFIRM CONFIGURATION CHANGE')).toBeInTheDocument()
    })

    it('renders conflict message', () => {
      render(<ConfirmChangeModal {...defaultProps} />)

      expect(screen.getByText('Configuration change requires confirmation')).toBeInTheDocument()
    })

    it('renders affected fields section', () => {
      render(<ConfirmChangeModal {...defaultProps} />)

      expect(screen.getByText('AFFECTED FIELDS')).toBeInTheDocument()
      expect(screen.getByText('server.port')).toBeInTheDocument()
    })

    it('renders current and new values', () => {
      render(<ConfirmChangeModal {...defaultProps} />)

      expect(screen.getByText('CURRENT:')).toBeInTheDocument()
      expect(screen.getByText('8000')).toBeInTheDocument()
      expect(screen.getByText('NEW:')).toBeInTheDocument()
      expect(screen.getByText('9000')).toBeInTheDocument()
    })

    it('renders required actions', () => {
      render(<ConfirmChangeModal {...defaultProps} />)

      expect(screen.getByText('REQUIRED ACTIONS')).toBeInTheDocument()
      expect(screen.getByText('Reload the application for changes to take effect')).toBeInTheDocument()
    })

    it('renders safety badge for affected fields', () => {
      render(<ConfirmChangeModal {...defaultProps} />)

      expect(screen.getByText('RELOAD REQUIRED')).toBeInTheDocument()
    })

    it('renders Cancel button', () => {
      render(<ConfirmChangeModal {...defaultProps} />)

      expect(screen.getByRole('button', { name: 'CANCEL' })).toBeInTheDocument()
    })

    it('renders Apply Changes button', () => {
      render(<ConfirmChangeModal {...defaultProps} />)

      expect(screen.getByRole('button', { name: 'APPLY CHANGES' })).toBeInTheDocument()
    })

    it('hides affected fields section when empty', () => {
      render(
        <ConfirmChangeModal
          {...defaultProps}
          conflict={createMockConflict({ affected_fields: [] })}
        />
      )

      expect(screen.queryByText('AFFECTED FIELDS')).not.toBeInTheDocument()
    })

    it('hides required actions section when empty', () => {
      render(
        <ConfirmChangeModal
          {...defaultProps}
          conflict={createMockConflict({ required_actions: [] })}
        />
      )

      expect(screen.queryByText('REQUIRED ACTIONS')).not.toBeInTheDocument()
    })
  })

  describe('interactions', () => {
    it('calls onCancel when Cancel clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      render(<ConfirmChangeModal {...defaultProps} onCancel={onCancel} />)

      await user.click(screen.getByRole('button', { name: 'CANCEL' }))

      expect(onCancel).toHaveBeenCalled()
    })

    it('calls onConfirm when Apply Changes clicked', async () => {
      const user = userEvent.setup()
      const onConfirm = vi.fn()
      render(<ConfirmChangeModal {...defaultProps} onConfirm={onConfirm} />)

      await user.click(screen.getByRole('button', { name: 'APPLY CHANGES' }))

      expect(onConfirm).toHaveBeenCalled()
    })

    it('calls onCancel when close button clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      render(<ConfirmChangeModal {...defaultProps} onCancel={onCancel} />)

      await user.click(screen.getByRole('button', { name: 'Close' }))

      expect(onCancel).toHaveBeenCalled()
    })

    it('calls onCancel when overlay clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      const { container } = render(<ConfirmChangeModal {...defaultProps} onCancel={onCancel} />)

      const overlay = container.querySelector('.confirmChangeOverlay')
      await user.click(overlay!)

      expect(onCancel).toHaveBeenCalled()
    })

    it('does not call onCancel when modal content clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      const { container } = render(<ConfirmChangeModal {...defaultProps} onCancel={onCancel} />)

      const modal = container.querySelector('.confirmChangeModal')
      await user.click(modal!)

      expect(onCancel).not.toHaveBeenCalled()
    })

    it('calls onCancel when Escape key pressed', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      render(<ConfirmChangeModal {...defaultProps} onCancel={onCancel} />)

      await user.keyboard('{Escape}')

      expect(onCancel).toHaveBeenCalled()
    })
  })

  describe('accessibility', () => {
    it('has dialog role', () => {
      render(<ConfirmChangeModal {...defaultProps} />)

      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('has aria-modal attribute', () => {
      render(<ConfirmChangeModal {...defaultProps} />)

      expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true')
    })

    it('has aria-labelledby pointing to title', () => {
      render(<ConfirmChangeModal {...defaultProps} />)

      const dialog = screen.getByRole('dialog')
      expect(dialog).toHaveAttribute('aria-labelledby', 'confirm-change-title')
    })
  })
})
