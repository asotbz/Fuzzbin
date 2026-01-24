import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import SettingField from '../SettingField'

describe('SettingField', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('text input', () => {
    it('renders label', () => {
      render(
        <SettingField
          path="test.path"
          label="Test Label"
          value="test value"
          type="text"
        />
      )

      expect(screen.getByText('Test Label')).toBeInTheDocument()
    })

    it('renders description', () => {
      render(
        <SettingField
          path="test.path"
          label="Test"
          description="This is a description"
          value="test"
          type="text"
        />
      )

      expect(screen.getByText('This is a description')).toBeInTheDocument()
    })

    it('renders path', () => {
      render(
        <SettingField
          path="library.folder_structure"
          label="Folder Structure"
          value="test"
          type="text"
        />
      )

      expect(screen.getByText('library.folder_structure')).toBeInTheDocument()
    })

    it('renders text input with value', () => {
      render(
        <SettingField
          path="test.path"
          label="Test"
          value="initial value"
          type="text"
        />
      )

      const input = screen.getByRole('textbox')
      expect(input).toHaveValue('initial value')
    })

    it('updates value on change', () => {
      render(
        <SettingField
          path="test.path"
          label="Test"
          value="initial"
          type="text"
        />
      )

      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'new value' } })

      expect(input).toHaveValue('new value')
    })

    it('shows unsaved changes indicator', () => {
      render(
        <SettingField
          path="test.path"
          label="Test"
          value="initial"
          type="text"
        />
      )

      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'modified' } })

      expect(screen.getByText('Unsaved changes...')).toBeInTheDocument()
    })

    it('calls onChange after debounce', () => {
      const onChange = vi.fn()
      render(
        <SettingField
          path="test.path"
          label="Test"
          value="initial"
          type="text"
          onChange={onChange}
        />
      )

      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'new' } })

      expect(onChange).not.toHaveBeenCalled()

      act(() => {
        vi.advanceTimersByTime(1500)
      })

      expect(onChange).toHaveBeenCalledWith('test.path', 'new')
    })

    it('shows revert button when dirty', () => {
      render(
        <SettingField
          path="test.path"
          label="Test"
          value="initial"
          type="text"
        />
      )

      expect(screen.queryByText('↶ REVERT')).not.toBeInTheDocument()

      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'modified' } })

      expect(screen.getByText('↶ REVERT')).toBeInTheDocument()
    })

    it('reverts value on revert click', () => {
      render(
        <SettingField
          path="test.path"
          label="Test"
          value="initial"
          type="text"
        />
      )

      const input = screen.getByRole('textbox')
      fireEvent.change(input, { target: { value: 'changed' } })

      expect(input).toHaveValue('changed')

      fireEvent.click(screen.getByText('↶ REVERT'))

      expect(input).toHaveValue('initial')
      expect(screen.queryByText('Unsaved changes...')).not.toBeInTheDocument()
    })

    it('disables input when disabled', () => {
      render(
        <SettingField
          path="test.path"
          label="Test"
          value="test"
          type="text"
          disabled
        />
      )

      expect(screen.getByRole('textbox')).toBeDisabled()
    })
  })

  describe('number input', () => {
    it('renders number input', () => {
      render(
        <SettingField
          path="test.port"
          label="Port"
          value={8000}
          type="number"
        />
      )

      const input = screen.getByRole('spinbutton')
      expect(input).toHaveValue(8000)
    })

    it('respects min/max/step', () => {
      render(
        <SettingField
          path="test.port"
          label="Port"
          value={8000}
          type="number"
          min={1}
          max={65535}
          step={1}
        />
      )

      const input = screen.getByRole('spinbutton')
      expect(input).toHaveAttribute('min', '1')
      expect(input).toHaveAttribute('max', '65535')
      expect(input).toHaveAttribute('step', '1')
    })

    it('handles empty value as null', () => {
      const onChange = vi.fn()
      render(
        <SettingField
          path="test.port"
          label="Port"
          value={8000}
          type="number"
          onChange={onChange}
        />
      )

      const input = screen.getByRole('spinbutton')
      fireEvent.change(input, { target: { value: '' } })

      act(() => {
        vi.advanceTimersByTime(1500)
      })

      expect(onChange).toHaveBeenCalledWith('test.port', null)
    })
  })

  describe('boolean input', () => {
    it('renders checkbox', () => {
      render(
        <SettingField
          path="test.enabled"
          label="Enabled"
          value={true}
          type="boolean"
        />
      )

      const checkbox = screen.getByRole('checkbox')
      expect(checkbox).toBeChecked()
    })

    it('shows Enabled label when true', () => {
      render(
        <SettingField
          path="test.enabled"
          label="Test"
          value={true}
          type="boolean"
        />
      )

      expect(screen.getByText('Enabled')).toBeInTheDocument()
    })

    it('shows Disabled label when false', () => {
      render(
        <SettingField
          path="test.enabled"
          label="Test"
          value={false}
          type="boolean"
        />
      )

      expect(screen.getByText('Disabled')).toBeInTheDocument()
    })

    it('toggles value on click', () => {
      const onChange = vi.fn()
      render(
        <SettingField
          path="test.enabled"
          label="Test"
          value={false}
          type="boolean"
          onChange={onChange}
        />
      )

      fireEvent.click(screen.getByRole('checkbox'))

      act(() => {
        vi.advanceTimersByTime(1500)
      })

      expect(onChange).toHaveBeenCalledWith('test.enabled', true)
    })
  })

  describe('select input', () => {
    const options = [
      { label: 'Debug', value: 'DEBUG' },
      { label: 'Info', value: 'INFO' },
      { label: 'Warning', value: 'WARNING' },
    ]

    it('renders select with options', () => {
      render(
        <SettingField
          path="logging.level"
          label="Log Level"
          value="INFO"
          type="select"
          options={options}
        />
      )

      const select = screen.getByRole('combobox')
      expect(select).toHaveValue('INFO')
    })

    it('renders all options', () => {
      render(
        <SettingField
          path="logging.level"
          label="Log Level"
          value="INFO"
          type="select"
          options={options}
        />
      )

      expect(screen.getByRole('option', { name: 'Debug' })).toBeInTheDocument()
      expect(screen.getByRole('option', { name: 'Info' })).toBeInTheDocument()
      expect(screen.getByRole('option', { name: 'Warning' })).toBeInTheDocument()
    })

    it('calls onChange on selection', () => {
      const onChange = vi.fn()
      render(
        <SettingField
          path="logging.level"
          label="Log Level"
          value="INFO"
          type="select"
          options={options}
          onChange={onChange}
        />
      )

      fireEvent.change(screen.getByRole('combobox'), { target: { value: 'DEBUG' } })

      act(() => {
        vi.advanceTimersByTime(1500)
      })

      expect(onChange).toHaveBeenCalledWith('logging.level', 'DEBUG')
    })
  })

  describe('array input', () => {
    it('renders textarea for array', () => {
      render(
        <SettingField
          path="test.items"
          label="Items"
          value={['item1', 'item2']}
          type="array"
        />
      )

      const textarea = screen.getByRole('textbox')
      expect(textarea).toHaveValue('item1\nitem2')
    })

    it('shows placeholder', () => {
      render(
        <SettingField
          path="test.items"
          label="Items"
          value={[]}
          type="array"
        />
      )

      expect(screen.getByPlaceholderText('One item per line')).toBeInTheDocument()
    })

    it('splits newlines into array', () => {
      const onChange = vi.fn()
      render(
        <SettingField
          path="test.items"
          label="Items"
          value={[]}
          type="array"
          onChange={onChange}
        />
      )

      fireEvent.change(screen.getByRole('textbox'), { target: { value: 'a\nb\nc' } })

      act(() => {
        vi.advanceTimersByTime(1500)
      })

      expect(onChange).toHaveBeenCalledWith('test.items', ['a', 'b', 'c'])
    })

    it('filters empty lines', () => {
      const onChange = vi.fn()
      render(
        <SettingField
          path="test.items"
          label="Items"
          value={[]}
          type="array"
          onChange={onChange}
        />
      )

      fireEvent.change(screen.getByRole('textbox'), { target: { value: 'a\n\nb' } })

      act(() => {
        vi.advanceTimersByTime(1500)
      })

      // Empty lines are filtered out
      expect(onChange).toHaveBeenCalledWith('test.items', ['a', 'b'])
    })
  })

  describe('safety badge', () => {
    it('renders safety badge for requires_reload', () => {
      render(
        <SettingField
          path="test.path"
          label="Test"
          value="test"
          safetyLevel="requires_reload"
        />
      )

      expect(screen.getByText('RELOAD REQUIRED')).toBeInTheDocument()
    })

    it('renders safety badge for affects_state', () => {
      render(
        <SettingField
          path="test.path"
          label="Test"
          value="test"
          safetyLevel="affects_state"
        />
      )

      expect(screen.getByText('RESTART REQUIRED')).toBeInTheDocument()
    })

    it('does not render badge for safe level', () => {
      render(
        <SettingField
          path="test.path"
          label="Test"
          value="test"
          safetyLevel="safe"
        />
      )

      // SafetyBadge returns null for "safe" level
      expect(screen.queryByText('SAFE')).not.toBeInTheDocument()
      expect(screen.queryByText('RELOAD REQUIRED')).not.toBeInTheDocument()
      expect(screen.queryByText('RESTART REQUIRED')).not.toBeInTheDocument()
    })
  })

  describe('value sync', () => {
    it('updates local value when prop changes', () => {
      const { rerender } = render(
        <SettingField
          path="test.path"
          label="Test"
          value="initial"
          type="text"
        />
      )

      expect(screen.getByRole('textbox')).toHaveValue('initial')

      rerender(
        <SettingField
          path="test.path"
          label="Test"
          value="updated"
          type="text"
        />
      )

      expect(screen.getByRole('textbox')).toHaveValue('updated')
    })

    it('clears dirty state when prop changes', () => {
      const { rerender } = render(
        <SettingField
          path="test.path"
          label="Test"
          value="initial"
          type="text"
        />
      )

      fireEvent.change(screen.getByRole('textbox'), { target: { value: 'dirty' } })
      expect(screen.getByText('Unsaved changes...')).toBeInTheDocument()

      rerender(
        <SettingField
          path="test.path"
          label="Test"
          value="new value"
          type="text"
        />
      )

      expect(screen.queryByText('Unsaved changes...')).not.toBeInTheDocument()
    })
  })
})
