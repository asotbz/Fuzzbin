import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MultiSelectToolbar from '../MultiSelectToolbar'

describe('MultiSelectToolbar', () => {
  const defaultProps = {
    count: 5,
    onAddTags: vi.fn(),
    onRemoveTags: vi.fn(),
    onWriteNFO: vi.fn(),
    onOrganize: vi.fn(),
    onDownload: vi.fn(),
    onDelete: vi.fn(),
    onClear: vi.fn(),
  }

  describe('rendering', () => {
    it('renders count with plural for multiple videos', () => {
      render(<MultiSelectToolbar {...defaultProps} count={5} />)

      expect(screen.getByText(/5 videos selected/)).toBeInTheDocument()
    })

    it('renders count with singular for one video', () => {
      render(<MultiSelectToolbar {...defaultProps} count={1} />)

      expect(screen.getByText(/1 video selected/)).toBeInTheDocument()
    })

    it('renders Add Tags button', () => {
      render(<MultiSelectToolbar {...defaultProps} />)

      expect(screen.getByRole('button', { name: /add tags/i })).toBeInTheDocument()
    })

    it('renders Remove Tags button', () => {
      render(<MultiSelectToolbar {...defaultProps} />)

      expect(screen.getByRole('button', { name: /remove tags/i })).toBeInTheDocument()
    })

    it('renders Write NFO button', () => {
      render(<MultiSelectToolbar {...defaultProps} />)

      expect(screen.getByRole('button', { name: /write nfo/i })).toBeInTheDocument()
    })

    it('renders Organize Files button', () => {
      render(<MultiSelectToolbar {...defaultProps} />)

      expect(screen.getByRole('button', { name: /organize files/i })).toBeInTheDocument()
    })

    it('renders Download Videos button', () => {
      render(<MultiSelectToolbar {...defaultProps} />)

      expect(screen.getByRole('button', { name: /download selected videos/i })).toBeInTheDocument()
    })

    it('renders Delete button', () => {
      render(<MultiSelectToolbar {...defaultProps} />)

      expect(screen.getByRole('button', { name: /delete selected videos/i })).toBeInTheDocument()
    })

    it('renders Clear button', () => {
      render(<MultiSelectToolbar {...defaultProps} />)

      expect(screen.getByRole('button', { name: /clear selection/i })).toBeInTheDocument()
    })

    it('has toolbar role', () => {
      render(<MultiSelectToolbar {...defaultProps} />)

      expect(screen.getByRole('toolbar')).toBeInTheDocument()
    })

    it('has proper aria-label', () => {
      render(<MultiSelectToolbar {...defaultProps} />)

      expect(screen.getByRole('toolbar')).toHaveAttribute(
        'aria-label',
        'Bulk operations toolbar'
      )
    })
  })

  describe('interactions', () => {
    it('calls onAddTags when Add Tags clicked', async () => {
      const user = userEvent.setup()
      const onAddTags = vi.fn()
      render(<MultiSelectToolbar {...defaultProps} onAddTags={onAddTags} />)

      await user.click(screen.getByRole('button', { name: /add tags/i }))

      expect(onAddTags).toHaveBeenCalled()
    })

    it('calls onRemoveTags when Remove Tags clicked', async () => {
      const user = userEvent.setup()
      const onRemoveTags = vi.fn()
      render(<MultiSelectToolbar {...defaultProps} onRemoveTags={onRemoveTags} />)

      await user.click(screen.getByRole('button', { name: /remove tags/i }))

      expect(onRemoveTags).toHaveBeenCalled()
    })

    it('calls onWriteNFO when Write NFO clicked', async () => {
      const user = userEvent.setup()
      const onWriteNFO = vi.fn()
      render(<MultiSelectToolbar {...defaultProps} onWriteNFO={onWriteNFO} />)

      await user.click(screen.getByRole('button', { name: /write nfo/i }))

      expect(onWriteNFO).toHaveBeenCalled()
    })

    it('calls onOrganize when Organize Files clicked', async () => {
      const user = userEvent.setup()
      const onOrganize = vi.fn()
      render(<MultiSelectToolbar {...defaultProps} onOrganize={onOrganize} />)

      await user.click(screen.getByRole('button', { name: /organize files/i }))

      expect(onOrganize).toHaveBeenCalled()
    })

    it('calls onDownload when Download Videos clicked', async () => {
      const user = userEvent.setup()
      const onDownload = vi.fn()
      render(<MultiSelectToolbar {...defaultProps} onDownload={onDownload} />)

      await user.click(screen.getByRole('button', { name: /download selected videos/i }))

      expect(onDownload).toHaveBeenCalled()
    })

    it('calls onDelete when Delete clicked', async () => {
      const user = userEvent.setup()
      const onDelete = vi.fn()
      render(<MultiSelectToolbar {...defaultProps} onDelete={onDelete} />)

      await user.click(screen.getByRole('button', { name: /delete selected videos/i }))

      expect(onDelete).toHaveBeenCalled()
    })

    it('calls onClear when Clear clicked', async () => {
      const user = userEvent.setup()
      const onClear = vi.fn()
      render(<MultiSelectToolbar {...defaultProps} onClear={onClear} />)

      await user.click(screen.getByRole('button', { name: /clear selection/i }))

      expect(onClear).toHaveBeenCalled()
    })
  })

  describe('styling', () => {
    it('applies danger class to delete button', () => {
      render(<MultiSelectToolbar {...defaultProps} />)

      const deleteButton = screen.getByRole('button', { name: /delete selected videos/i })
      expect(deleteButton).toHaveClass('multiSelectToolbarButtonDanger')
    })

    it('applies clear class to clear button', () => {
      render(<MultiSelectToolbar {...defaultProps} />)

      const clearButton = screen.getByRole('button', { name: /clear selection/i })
      expect(clearButton).toHaveClass('multiSelectToolbarButtonClear')
    })
  })
})
