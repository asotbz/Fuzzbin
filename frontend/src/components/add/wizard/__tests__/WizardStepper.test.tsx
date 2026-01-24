import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import WizardStepper from '../WizardStepper'

describe('WizardStepper', () => {
  const steps = ['Search', 'Review', 'Confirm']

  it('renders all steps', () => {
    render(<WizardStepper steps={steps} currentStep={0} />)

    expect(screen.getByText('Search')).toBeInTheDocument()
    expect(screen.getByText('Review')).toBeInTheDocument()
    expect(screen.getByText('Confirm')).toBeInTheDocument()
  })

  it('shows step numbers', () => {
    render(<WizardStepper steps={steps} currentStep={0} />)

    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('marks current step', () => {
    const { container } = render(<WizardStepper steps={steps} currentStep={1} />)

    const currentStep = container.querySelectorAll('.wizardStep')[1]
    expect(currentStep).toHaveClass('wizardStepCurrent')
  })

  it('marks completed steps', () => {
    const { container } = render(<WizardStepper steps={steps} currentStep={2} />)

    const completedSteps = container.querySelectorAll('.wizardStepCompleted')
    expect(completedSteps).toHaveLength(2)
  })

  it('shows checkmark for completed steps', () => {
    const { container } = render(<WizardStepper steps={steps} currentStep={1} />)

    // First step should show checkmark (SVG)
    const firstStep = container.querySelectorAll('.wizardStepNumber')[0]
    expect(firstStep.querySelector('svg')).toBeInTheDocument()
  })

  it('calls onStepClick when completed step is clicked', async () => {
    const user = userEvent.setup()
    const onStepClick = vi.fn()
    render(<WizardStepper steps={steps} currentStep={1} onStepClick={onStepClick} />)

    await user.click(screen.getByText('Search'))

    expect(onStepClick).toHaveBeenCalledWith(0)
  })

  it('calls onStepClick when current step is clicked', async () => {
    const user = userEvent.setup()
    const onStepClick = vi.fn()
    render(<WizardStepper steps={steps} currentStep={1} onStepClick={onStepClick} />)

    await user.click(screen.getByText('Review'))

    expect(onStepClick).toHaveBeenCalledWith(1)
  })

  it('disables future steps', async () => {
    const user = userEvent.setup()
    const onStepClick = vi.fn()
    render(<WizardStepper steps={steps} currentStep={0} onStepClick={onStepClick} />)

    await user.click(screen.getByText('Confirm'))

    expect(onStepClick).not.toHaveBeenCalled()
  })

  it('disables all steps when no onStepClick provided', () => {
    const { container } = render(<WizardStepper steps={steps} currentStep={1} />)

    const buttons = container.querySelectorAll('button')
    buttons.forEach((button) => {
      expect(button).toBeDisabled()
    })
  })

  it('sets progress bar width based on current step', () => {
    const { container } = render(<WizardStepper steps={steps} currentStep={1} />)

    const progressBar = container.querySelector('.wizardStepperProgressBar') as HTMLElement
    expect(progressBar.style.width).toBe('50%')
  })

  it('sets progress bar to 0% at first step', () => {
    const { container } = render(<WizardStepper steps={steps} currentStep={0} />)

    const progressBar = container.querySelector('.wizardStepperProgressBar') as HTMLElement
    expect(progressBar.style.width).toBe('0%')
  })

  it('sets progress bar to 100% at last step', () => {
    const { container } = render(<WizardStepper steps={steps} currentStep={2} />)

    const progressBar = container.querySelector('.wizardStepperProgressBar') as HTMLElement
    expect(progressBar.style.width).toBe('100%')
  })
})
