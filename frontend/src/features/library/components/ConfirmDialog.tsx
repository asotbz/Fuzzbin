import { useState } from 'react'
import './ConfirmDialog.css'

interface ConfirmDialogProps {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'warning' | 'info'
  checkboxLabel?: string
  checkboxDefaultChecked?: boolean
  onConfirm: (checkboxValue?: boolean) => void
  onCancel: () => void
}

export default function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'warning',
  checkboxLabel,
  checkboxDefaultChecked = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [checkboxValue, setCheckboxValue] = useState(checkboxDefaultChecked)

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onCancel()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onCancel()
    } else if (e.key === 'Enter') {
      onConfirm(checkboxLabel ? checkboxValue : undefined)
    }
  }

  return (
    <div
      className="confirmDialogOverlay"
      onClick={handleOverlayClick}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className={`confirmDialog confirmDialog-${variant}`}>
        <div className="confirmDialogHeader">
          <h2 id="confirm-dialog-title" className="confirmDialogTitle">
            {title}
          </h2>
        </div>

        <div className="confirmDialogBody">
          <p className="confirmDialogMessage">{message}</p>

          {checkboxLabel && (
            <label className="confirmDialogCheckbox">
              <input
                type="checkbox"
                checked={checkboxValue}
                onChange={(e) => setCheckboxValue(e.target.checked)}
                className="confirmDialogCheckboxInput"
              />
              <span className="confirmDialogCheckboxLabel">{checkboxLabel}</span>
            </label>
          )}
        </div>

        <div className="confirmDialogFooter">
          <button
            type="button"
            className="confirmDialogButton confirmDialogButtonCancel"
            onClick={onCancel}
            autoFocus
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`confirmDialogButton confirmDialogButtonConfirm confirmDialogButtonConfirm-${variant}`}
            onClick={() => onConfirm(checkboxLabel ? checkboxValue : undefined)}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
