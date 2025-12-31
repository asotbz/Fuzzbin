import { useState } from 'react'
import SettingSection from '../SettingSection'
import SettingField from '../SettingField'
import ConfirmChangeModal from '../ConfirmChangeModal'
import { useConfigUpdate } from '../../hooks/useConfigUpdate'
import type { ConfigConflictError } from '../../../../lib/api/endpoints/config'

interface LoggingSettingsProps {
  config: any
}

export default function LoggingSettings({ config }: LoggingSettingsProps) {
  const [conflictError, setConflictError] = useState<ConfigConflictError | null>(null)
  const updateMutation = useConfigUpdate({
    onConflict: (error) => setConflictError(error),
  })

  const handleFieldChange = (path: string, value: any) => {
    updateMutation.mutate({
      updates: { [path]: value },
      description: `Updated ${path}`,
      force: false,
    })
  }

  const handleConfirmChange = () => {
    if (!conflictError) return

    const updates = conflictError.affected_fields.reduce((acc, field) => {
      acc[field.path] = field.requested_value
      return acc
    }, {} as Record<string, any>)

    updateMutation.mutate({
      updates,
      description: 'Forced configuration update',
      force: true,
    })

    setConflictError(null)
  }

  const logging = config?.logging || {}

  return (
    <>
      <SettingSection
        title="Logging Configuration"
        description="Control log levels, formats, and output destinations"
      >
        <SettingField
          path="logging.level"
          label="Log Level"
          description="Minimum log level to output"
          value={logging.level}
          type="select"
          options={[
            { label: 'DEBUG', value: 'DEBUG' },
            { label: 'INFO', value: 'INFO' },
            { label: 'WARNING', value: 'WARNING' },
            { label: 'ERROR', value: 'ERROR' },
            { label: 'CRITICAL', value: 'CRITICAL' },
          ]}
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="logging.format"
          label="Log Format"
          description="Output format for log messages"
          value={logging.format}
          type="select"
          options={[
            { label: 'JSON (recommended for production)', value: 'json' },
            { label: 'Text (better for development)', value: 'text' },
          ]}
          safetyLevel="safe"
          onChange={handleFieldChange}
        />
      </SettingSection>

      {conflictError && (
        <ConfirmChangeModal
          conflict={conflictError}
          onConfirm={handleConfirmChange}
          onCancel={() => setConflictError(null)}
        />
      )}
    </>
  )
}
