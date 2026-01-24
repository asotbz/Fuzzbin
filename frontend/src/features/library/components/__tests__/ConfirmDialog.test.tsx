import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConfirmDialog from '../ConfirmDialog'

describe('ConfirmDialog', () => {
  const defaultProps = {
    title: 'Confirm Action',
    message: 'Are you sure you want to proceed?',
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  }

  describe('rendering', () => {
    it('renders title', () => {
      render(<ConfirmDialog {...defaultProps} />)

      expect(screen.getByText('Confirm Action')).toBeInTheDocument()
    })

    it('renders message', () => {
      render(<ConfirmDialog {...defaultProps} />)

      expect(screen.getByText('Are you sure you want to proceed?')).toBeInTheDocument()
    })

    it('renders default confirm button text', () => {
      render(<ConfirmDialog {...defaultProps} />)

      expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument()
    })

    it('renders default cancel button text', () => {
      render(<ConfirmDialog {...defaultProps} />)

      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    })

    it('renders custom confirm button text', () => {
      render(<ConfirmDialog {...defaultProps} confirmLabel="Delete" />)

      expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
    })

    it('renders custom cancel button text', () => {
      render(<ConfirmDialog {...defaultProps} cancelLabel="Go Back" />)

      expect(screen.getByRole('button', { name: 'Go Back' })).toBeInTheDocument()
    })

    it('has proper dialog role', () => {
      render(<ConfirmDialog {...defaultProps} />)

      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('has aria-modal attribute', () => {
      render(<ConfirmDialog {...defaultProps} />)

      expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true')
    })
  })

  describe('variants', () => {
    it('applies danger variant class', () => {
      const { container } = render(<ConfirmDialog {...defaultProps} variant="danger" />)

      expect(container.querySelector('.confirmDialog-danger')).toBeInTheDocument()
    })

    it('applies warning variant class', () => {
      const { container } = render(<ConfirmDialog {...defaultProps} variant="warning" />)

      expect(container.querySelector('.confirmDialog-warning')).toBeInTheDocument()
    })

    it('applies info variant class', () => {
      const { container } = render(<ConfirmDialog {...defaultProps} variant="info" />)

      expect(container.querySelector('.confirmDialog-info')).toBeInTheDocument()
    })

    it('defaults to warning variant', () => {
      const { container } = render(<ConfirmDialog {...defaultProps} />)

      expect(container.querySelector('.confirmDialog-warning')).toBeInTheDocument()
    })
  })

  describe('interactions', () => {
    it('calls onConfirm when confirm button clicked', async () => {
      const user = userEvent.setup()
      const onConfirm = vi.fn()
      render(<ConfirmDialog {...defaultProps} onConfirm={onConfirm} />)

      await user.click(screen.getByRole('button', { name: 'Confirm' }))

      expect(onConfirm).toHaveBeenCalled()
    })

    it('calls onCancel when cancel button clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      render(<ConfirmDialog {...defaultProps} onCancel={onCancel} />)

      await user.click(screen.getByRole('button', { name: 'Cancel' }))

      expect(onCancel).toHaveBeenCalled()
    })

    it('calls onCancel when overlay clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      const { container } = render(<ConfirmDialog {...defaultProps} onCancel={onCancel} />)

      const overlay = container.querySelector('.confirmDialogOverlay')
      expect(overlay).toBeInTheDocument()
      await user.click(overlay!)

      expect(onCancel).toHaveBeenCalled()
    })

    it('does not call onCancel when dialog content clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      const { container } = render(<ConfirmDialog {...defaultProps} onCancel={onCancel} />)

      const dialog = container.querySelector('.confirmDialog')
      await user.click(dialog!)

      expect(onCancel).not.toHaveBeenCalled()
    })

    it('calls onCancel when Escape key pressed', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      render(<ConfirmDialog {...defaultProps} onCancel={onCancel} />)

      await user.keyboard('{Escape}')

      expect(onCancel).toHaveBeenCalled()
    })

    it('calls onConfirm when Enter key pressed', async () => {
      const user = userEvent.setup()
      const onConfirm = vi.fn()
      render(<ConfirmDialog {...defaultProps} onConfirm={onConfirm} />)

      await user.keyboard('{Enter}')

      expect(onConfirm).toHaveBeenCalled()
    })
  })

  describe('checkbox', () => {
    it('does not render checkbox by default', () => {
      render(<ConfirmDialog {...defaultProps} />)

      expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    })

    it('renders checkbox when checkboxLabel provided', () => {
      render(<ConfirmDialog {...defaultProps} checkboxLabel="Also delete files" />)

      expect(screen.getByRole('checkbox')).toBeInTheDocument()
      expect(screen.getByText('Also delete files')).toBeInTheDocument()
    })

    it('checkbox is unchecked by default', () => {
      render(<ConfirmDialog {...defaultProps} checkboxLabel="Option" />)

      expect(screen.getByRole('checkbox')).not.toBeChecked()
    })

    it('checkbox can be pre-checked', () => {
      render(
        <ConfirmDialog
          {...defaultProps}
          checkboxLabel="Option"
          checkboxDefaultChecked={true}
        />
      )

      expect(screen.getByRole('checkbox')).toBeChecked()
    })

    it('checkbox can be toggled', async () => {
      const user = userEvent.setup()
      render(<ConfirmDialog {...defaultProps} checkboxLabel="Option" />)

      const checkbox = screen.getByRole('checkbox')
      expect(checkbox).not.toBeChecked()

      await user.click(checkbox)

      expect(checkbox).toBeChecked()
    })

    it('passes checkbox value to onConfirm', async () => {
      const user = userEvent.setup()
      const onConfirm = vi.fn()
      render(
        <ConfirmDialog
          {...defaultProps}
          checkboxLabel="Delete files"
          onConfirm={onConfirm}
        />
      )

      await user.click(screen.getByRole('checkbox'))
      await user.click(screen.getByRole('button', { name: 'Confirm' }))

      expect(onConfirm).toHaveBeenCalledWith(true)
    })

    it('passes false to onConfirm when checkbox unchecked', async () => {
      const user = userEvent.setup()
      const onConfirm = vi.fn()
      render(
        <ConfirmDialog
          {...defaultProps}
          checkboxLabel="Delete files"
          onConfirm={onConfirm}
        />
      )

      await user.click(screen.getByRole('button', { name: 'Confirm' }))

      expect(onConfirm).toHaveBeenCalledWith(false)
    })

    it('passes undefined to onConfirm when no checkbox', async () => {
      const user = userEvent.setup()
      const onConfirm = vi.fn()
      render(<ConfirmDialog {...defaultProps} onConfirm={onConfirm} />)

      await user.click(screen.getByRole('button', { name: 'Confirm' }))

      expect(onConfirm).toHaveBeenCalledWith(undefined)
    })
  })
})
