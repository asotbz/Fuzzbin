import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SourceComparison, { type ComparisonField } from '../SourceComparison'

describe('SourceComparison', () => {
  const createField = (
    key: string,
    label: string,
    imvdb: string | null,
    discogs: string | null
  ): ComparisonField => ({
    key,
    label,
    imvdbValue: imvdb,
    discogsValue: discogs,
  })

  const defaultFields: ComparisonField[] = [
    createField('title', 'Title', 'IMVDb Title', 'Discogs Title'),
    createField('year', 'Year', '2020', '2020'),
    createField('artist', 'Artist', 'IMVDb Artist', null),
  ]

  const defaultProps = {
    fields: defaultFields,
    onFieldSelect: vi.fn(),
    selectedFields: {} as Record<string, 'imvdb' | 'discogs'>,
  }

  it('renders header', () => {
    render(<SourceComparison {...defaultProps} />)

    expect(screen.getByText('Compare Sources')).toBeInTheDocument()
    expect(screen.getByText('Select the best value for each field')).toBeInTheDocument()
  })

  it('renders source headers', () => {
    render(<SourceComparison {...defaultProps} />)

    expect(screen.getByText('IMVDb')).toBeInTheDocument()
    expect(screen.getByText('Discogs')).toBeInTheDocument()
  })

  it('renders field labels', () => {
    render(<SourceComparison {...defaultProps} />)

    expect(screen.getByText('Title')).toBeInTheDocument()
    expect(screen.getByText('Year')).toBeInTheDocument()
    expect(screen.getByText('Artist')).toBeInTheDocument()
  })

  it('renders field values', () => {
    render(<SourceComparison {...defaultProps} />)

    expect(screen.getByText('IMVDb Title')).toBeInTheDocument()
    expect(screen.getByText('Discogs Title')).toBeInTheDocument()
    expect(screen.getByText('IMVDb Artist')).toBeInTheDocument()
  })

  it('shows "No data" for null values', () => {
    render(<SourceComparison {...defaultProps} />)

    // Artist has null discogs value
    expect(screen.getAllByText('No data').length).toBeGreaterThanOrEqual(1)
  })

  it('shows "Different" badge for differing values', () => {
    render(<SourceComparison {...defaultProps} />)

    expect(screen.getByText('Different')).toBeInTheDocument()
  })

  it('does not show "Different" badge for matching values', () => {
    const fields = [createField('year', 'Year', '2020', '2020')]
    render(
      <SourceComparison
        {...defaultProps}
        fields={fields}
      />
    )

    expect(screen.queryByText('Different')).not.toBeInTheDocument()
  })

  it('calls onFieldSelect when selecting IMVDb option', async () => {
    const user = userEvent.setup()
    const onFieldSelect = vi.fn()
    render(
      <SourceComparison
        {...defaultProps}
        onFieldSelect={onFieldSelect}
      />
    )

    const imvdbRadios = screen.getAllByRole('radio')
    await user.click(imvdbRadios[0]) // First radio is IMVDb for Title

    expect(onFieldSelect).toHaveBeenCalledWith('title', 'imvdb')
  })

  it('calls onFieldSelect when selecting Discogs option', async () => {
    const user = userEvent.setup()
    const onFieldSelect = vi.fn()
    render(
      <SourceComparison
        {...defaultProps}
        onFieldSelect={onFieldSelect}
      />
    )

    const radios = screen.getAllByRole('radio')
    await user.click(radios[1]) // Second radio is Discogs for Title

    expect(onFieldSelect).toHaveBeenCalledWith('title', 'discogs')
  })

  it('disables options with null values', () => {
    render(<SourceComparison {...defaultProps} />)

    // Find the radio button for Artist's Discogs option (which is null)
    const radios = screen.getAllByRole('radio')
    // Last radio should be disabled (Artist's Discogs option)
    expect(radios[radios.length - 1]).toBeDisabled()
  })

  it('shows selected state for selected fields', () => {
    const { container } = render(
      <SourceComparison
        {...defaultProps}
        selectedFields={{ title: 'imvdb' }}
      />
    )

    const selectedOptions = container.querySelectorAll('.sourceComparisonOptionSelected')
    expect(selectedOptions).toHaveLength(1)
  })
})
