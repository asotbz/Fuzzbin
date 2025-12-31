import SafetyBadge from './SafetyBadge'
import type { ConfigConflictError } from '../../../lib/api/endpoints/config'
import './ConfirmChangeModal.css'

interface ConfirmChangeModalProps {
  conflict: ConfigConflictError
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmChangeModal({
  conflict,
  onConfirm,
  onCancel,
}: ConfirmChangeModalProps) {
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onCancel()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onCancel()
    }
  }

  return (
    <div
      className="confirmChangeOverlay"
      onClick={handleOverlayClick}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-change-title"
    >
      <div className="confirmChangeModal">
        <div className="confirmChangeHeader">
          <div className="confirmChangeIcon">⚠</div>
          <h2 id="confirm-change-title" className="confirmChangeTitle">
            CONFIRM CONFIGURATION CHANGE
          </h2>
          <button
            className="confirmChangeClose"
            onClick={onCancel}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="confirmChangeBody">
          <div className="confirmChangeWarning">
            <p>{conflict.message}</p>
          </div>

          {conflict.affected_fields.length > 0 && (
            <div className="confirmChangeSection">
              <h3 className="confirmChangeSectionTitle">AFFECTED FIELDS</h3>
              <div className="affectedFields">
                {conflict.affected_fields.map((field) => (
                  <div key={field.path} className="affectedField">
                    <div className="affectedFieldHeader">
                      <div className="affectedFieldPath">{field.path}</div>
                      <SafetyBadge level={field.safety_level} />
                    </div>
                    <div className="affectedFieldChange">
                      <div className="changeValue changeValueOld">
                        <div className="changeValueLabel">CURRENT:</div>
                        <div className="changeValueContent">
                          {JSON.stringify(field.current_value)}
                        </div>
                      </div>
                      <div className="changeArrow">→</div>
                      <div className="changeValue changeValueNew">
                        <div className="changeValueLabel">NEW:</div>
                        <div className="changeValueContent">
                          {JSON.stringify(field.requested_value)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {conflict.required_actions.length > 0 && (
            <div className="confirmChangeSection">
              <h3 className="confirmChangeSectionTitle">REQUIRED ACTIONS</h3>
              <ul className="requiredActions">
                {conflict.required_actions.map((action, index) => (
                  <li key={index} className="requiredAction">
                    <span className="requiredActionIcon">▸</span>
                    <span className="requiredActionText">{action.description}</span>
                  </li>
                ))}
              </ul>
              <div className="requiredActionsNote">
                These actions will NOT be performed automatically. You may need to reload
                components or restart the application manually.
              </div>
            </div>
          )}
        </div>

        <div className="confirmChangeFooter">
          <button
            className="confirmChangeButton confirmChangeButtonCancel"
            onClick={onCancel}
            autoFocus
          >
            CANCEL
          </button>
          <button
            className="confirmChangeButton confirmChangeButtonConfirm"
            onClick={onConfirm}
          >
            APPLY CHANGES
          </button>
        </div>
      </div>
    </div>
  )
}
