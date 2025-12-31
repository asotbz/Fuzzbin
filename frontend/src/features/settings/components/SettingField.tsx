/* eslint-disable @typescript-eslint/no-explicit-any -- Settings system uses dynamic config types */
import { useState, useEffect, useCallback } from 'react'
import SafetyBadge from './SafetyBadge'
import type { SafetyLevel } from '../../../lib/api/endpoints/config'
import './SettingField.css'

interface SettingFieldProps {
  path: string
  label: string
  description?: string
  value: any
  type?: 'text' | 'number' | 'boolean' | 'select' | 'array'
  safetyLevel?: SafetyLevel
  min?: number
  max?: number
  step?: number
  options?: Array<{ label: string; value: any }>
  disabled?: boolean
  onChange?: (path: string, value: any) => void
}

export default function SettingField({
  path,
  label,
  description,
  value,
  type = 'text',
  safetyLevel = 'safe',
  min,
  max,
  step = 1,
  options,
  disabled = false,
  onChange,
}: SettingFieldProps) {
  const [localValue, setLocalValue] = useState(value)
  const [isDirty, setIsDirty] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Update local value when prop changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Syncing prop to local state is a valid pattern
    setLocalValue(value)
     
    setIsDirty(false)
  }, [value])

  // Debounced save
  useEffect(() => {
    if (!isDirty || !onChange) return

    const timer = setTimeout(() => {
      onChange(path, localValue)
      setIsDirty(false)
    }, 300)

    return () => clearTimeout(timer)
  }, [localValue, isDirty, onChange, path])

  const handleChange = useCallback((newValue: any) => {
    setLocalValue(newValue)
    setIsDirty(true)
    setError(null)
  }, [])

  const handleRevert = useCallback(() => {
    setLocalValue(value)
    setIsDirty(false)
    setError(null)
  }, [value])

  const renderInput = () => {
    switch (type) {
      case 'boolean':
        return (
          <label className="fieldToggle">
            <input
              type="checkbox"
              checked={Boolean(localValue)}
              onChange={(e) => handleChange(e.target.checked)}
              disabled={disabled}
              className="fieldToggleInput"
            />
            <span className="fieldToggleSlider"></span>
            <span className="fieldToggleLabel">
              {localValue ? 'Enabled' : 'Disabled'}
            </span>
          </label>
        )

      case 'number':
        return (
          <input
            type="number"
            value={localValue ?? ''}
            onChange={(e) => {
              const val = e.target.value === '' ? null : Number(e.target.value)
              handleChange(val)
            }}
            min={min}
            max={max}
            step={step}
            disabled={disabled}
            className="fieldInput fieldInputNumber"
          />
        )

      case 'select':
        return (
          <select
            value={localValue ?? ''}
            onChange={(e) => handleChange(e.target.value)}
            disabled={disabled}
            className="fieldInput fieldInputSelect"
          >
            {options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        )

      case 'array':
        return (
          <div className="fieldArray">
            <textarea
              value={Array.isArray(localValue) ? localValue.join('\n') : ''}
              onChange={(e) => {
                const arr = e.target.value.split('\n').filter((s) => s.trim())
                handleChange(arr)
              }}
              disabled={disabled}
              className="fieldInput fieldInputTextarea"
              rows={5}
              placeholder="One item per line"
            />
          </div>
        )

      case 'text':
      default:
        return (
          <input
            type="text"
            value={localValue ?? ''}
            onChange={(e) => handleChange(e.target.value)}
            disabled={disabled}
            className="fieldInput fieldInputText"
          />
        )
    }
  }

  return (
    <div className={`settingField ${isDirty ? 'settingFieldDirty' : ''} ${error ? 'settingFieldError' : ''}`}>
      <div className="fieldHeader">
        <div className="fieldLabelGroup">
          <label className="fieldLabel">{label}</label>
          <SafetyBadge level={safetyLevel} />
        </div>
        {isDirty && (
          <button
            className="fieldRevert"
            onClick={handleRevert}
            title="Revert changes"
          >
            ↶ REVERT
          </button>
        )}
      </div>

      {description && <p className="fieldDescription">{description}</p>}

      <div className="fieldInput">
        {renderInput()}
      </div>

      {error && <div className="fieldError">{error}</div>}

      {isDirty && <div className="fieldStatus">Unsaved changes...</div>}

      <div className="fieldPath">{path}</div>
    </div>
  )
}
