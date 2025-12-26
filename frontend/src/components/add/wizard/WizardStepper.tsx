import './WizardStepper.css'

interface WizardStepperProps {
  steps: string[]
  currentStep: number
  onStepClick?: (step: number) => void
}

export default function WizardStepper({ steps, currentStep, onStepClick }: WizardStepperProps) {
  return (
    <div className="wizardStepper">
      <div className="wizardStepperProgress">
        <div
          className="wizardStepperProgressBar"
          style={{ width: `${(currentStep / (steps.length - 1)) * 100}%` }}
        />
      </div>

      <div className="wizardStepperSteps">
        {steps.map((step, index) => {
          const isCompleted = index < currentStep
          const isCurrent = index === currentStep
          const isClickable = onStepClick && (isCompleted || isCurrent)

          return (
            <button
              key={index}
              type="button"
              className={`
                wizardStep
                ${isCurrent ? 'wizardStepCurrent' : ''}
                ${isCompleted ? 'wizardStepCompleted' : ''}
                ${!isCurrent && !isCompleted ? 'wizardStepPending' : ''}
              `}
              onClick={() => isClickable && onStepClick(index)}
              disabled={!isClickable}
            >
              <div className="wizardStepNumber">
                {isCompleted ? (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <span>{index + 1}</span>
                )}
              </div>
              <div className="wizardStepLabel">{step}</div>
              {isCurrent && <div className="wizardStepGlow" />}
            </button>
          )
        })}
      </div>
    </div>
  )
}
