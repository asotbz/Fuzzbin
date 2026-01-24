import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BulkTagModal from '../BulkTagModal'

describe('BulkTagModal', () => {
  const defaultProps = {
    count: 5,
    availableTags: ['Rock', 'Pop', 'Metal', 'Jazz'],
    onApply: vi.fn(),
    onCancel: vi.fn(),
  }

  describe('rendering', () => {
    it('renders title with video count (plural)', () => {
      render(<BulkTagModal {...defaultProps} count={5} />)

      expect(screen.getByText('Manage Tags - 5 videos selected')).toBeInTheDocument()
    })

    it('renders title with video count (singular)', () => {
      render(<BulkTagModal {...defaultProps} count={1} />)

      expect(screen.getByText('Manage Tags - 1 video selected')).toBeInTheDocument()
    })

    it('renders Add Tags section', () => {
      render(<BulkTagModal {...defaultProps} />)

      expect(screen.getByText('Add Tags')).toBeInTheDocument()
    })

    it('renders Remove Tags section', () => {
      render(<BulkTagModal {...defaultProps} />)

      expect(screen.getByText('Remove Tags')).toBeInTheDocument()
    })

    it('renders available tags', () => {
      render(<BulkTagModal {...defaultProps} />)

      // Tags appear twice (add section and remove section)
      expect(screen.getAllByText('Rock').length).toBe(2)
      expect(screen.getAllByText('Pop').length).toBe(2)
      expect(screen.getAllByText('Metal').length).toBe(2)
      expect(screen.getAllByText('Jazz').length).toBe(2)
    })

    it('renders tag input field', () => {
      render(<BulkTagModal {...defaultProps} />)

      expect(screen.getByPlaceholderText(/type tag name/i)).toBeInTheDocument()
    })

    it('renders Apply Changes button', () => {
      render(<BulkTagModal {...defaultProps} />)

      expect(screen.getByRole('button', { name: 'Apply Changes' })).toBeInTheDocument()
    })

    it('renders Cancel button', () => {
      render(<BulkTagModal {...defaultProps} />)

      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    })
  })

  describe('adding tags', () => {
    it('adds custom tag via input', async () => {
      const user = userEvent.setup()
      render(<BulkTagModal {...defaultProps} />)

      const input = screen.getByPlaceholderText(/type tag name/i)
      await user.type(input, 'NewTag')
      await user.click(screen.getByRole('button', { name: 'Add' }))

      expect(screen.getByText('NewTag ×')).toBeInTheDocument()
    })

    it('adds custom tag via Enter key', async () => {
      const user = userEvent.setup()
      render(<BulkTagModal {...defaultProps} />)

      const input = screen.getByPlaceholderText(/type tag name/i)
      await user.type(input, 'KeyTag{enter}')

      expect(screen.getByText('KeyTag ×')).toBeInTheDocument()
    })

    it('clears input after adding tag', async () => {
      const user = userEvent.setup()
      render(<BulkTagModal {...defaultProps} />)

      const input = screen.getByPlaceholderText(/type tag name/i)
      await user.type(input, 'TestTag{enter}')

      expect(input).toHaveValue('')
    })

    it('disables Add button when input is empty', () => {
      render(<BulkTagModal {...defaultProps} />)

      expect(screen.getByRole('button', { name: 'Add' })).toBeDisabled()
    })

    it('toggles available tag selection', async () => {
      const user = userEvent.setup()
      render(<BulkTagModal {...defaultProps} />)

      // Click available tag 'Rock' to add it
      const availableRockButtons = screen.getAllByText('Rock')
      await user.click(availableRockButtons[0])

      // Should show in "Tags to add" section
      expect(screen.getByText('Tags to add:')).toBeInTheDocument()
      expect(screen.getByText('Rock ×')).toBeInTheDocument()
    })

    it('removes tag from add list when clicking chip', async () => {
      const user = userEvent.setup()
      render(<BulkTagModal {...defaultProps} />)

      const input = screen.getByPlaceholderText(/type tag name/i)
      await user.type(input, 'RemoveMe{enter}')

      // Click the chip to remove
      await user.click(screen.getByText('RemoveMe ×'))

      expect(screen.queryByText('RemoveMe ×')).not.toBeInTheDocument()
    })
  })

  describe('removing tags', () => {
    it('toggles tag for removal', async () => {
      const user = userEvent.setup()
      render(<BulkTagModal {...defaultProps} />)

      // Find the remove section buttons (there are 2 lists of tags - add and remove)
      const tagButtons = screen.getAllByRole('button', { name: 'Pop' })
      // Click the second occurrence (in remove section)
      await user.click(tagButtons[1])

      expect(screen.getByText('Tags to remove:')).toBeInTheDocument()
    })
  })

  describe('modal actions', () => {
    it('calls onCancel when Cancel clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      render(<BulkTagModal {...defaultProps} onCancel={onCancel} />)

      await user.click(screen.getByRole('button', { name: 'Cancel' }))

      expect(onCancel).toHaveBeenCalled()
    })

    it('calls onCancel when close button clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      render(<BulkTagModal {...defaultProps} onCancel={onCancel} />)

      await user.click(screen.getByRole('button', { name: 'Close' }))

      expect(onCancel).toHaveBeenCalled()
    })

    it('calls onCancel when overlay clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      const { container } = render(<BulkTagModal {...defaultProps} onCancel={onCancel} />)

      const overlay = container.querySelector('.bulkTagModalOverlay')
      await user.click(overlay!)

      expect(onCancel).toHaveBeenCalled()
    })

    it('does not call onCancel when modal content clicked', async () => {
      const user = userEvent.setup()
      const onCancel = vi.fn()
      const { container } = render(<BulkTagModal {...defaultProps} onCancel={onCancel} />)

      const modal = container.querySelector('.bulkTagModal')
      await user.click(modal!)

      expect(onCancel).not.toHaveBeenCalled()
    })

    it('disables Apply Changes when no changes made', () => {
      render(<BulkTagModal {...defaultProps} />)

      expect(screen.getByRole('button', { name: 'Apply Changes' })).toBeDisabled()
    })

    it('enables Apply Changes when tags to add', async () => {
      const user = userEvent.setup()
      render(<BulkTagModal {...defaultProps} />)

      const input = screen.getByPlaceholderText(/type tag name/i)
      await user.type(input, 'NewTag{enter}')

      expect(screen.getByRole('button', { name: 'Apply Changes' })).toBeEnabled()
    })

    it('calls onApply with added and removed tags', async () => {
      const user = userEvent.setup()
      const onApply = vi.fn()
      render(<BulkTagModal {...defaultProps} onApply={onApply} />)

      // Add a custom tag
      const input = screen.getByPlaceholderText(/type tag name/i)
      await user.type(input, 'NewTag{enter}')

      // Click Apply
      await user.click(screen.getByRole('button', { name: 'Apply Changes' }))

      expect(onApply).toHaveBeenCalledWith(['NewTag'], [])
    })
  })
})
