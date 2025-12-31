import { useState } from 'react'
import SettingSection from '../SettingSection'
import SettingField from '../SettingField'
import ConfirmChangeModal from '../ConfirmChangeModal'
import { useConfigUpdate } from '../../hooks/useConfigUpdate'
import type { ConfigConflictError } from '../../../../lib/api/endpoints/config'

interface CacheSettingsProps {
  config: any
}

export default function CacheSettings({ config }: CacheSettingsProps) {
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

  const cache = config?.cache || {}

  return (
    <>
      <SettingSection
        title="HTTP Response Cache"
        description="Hishel-based HTTP response caching configuration"
      >
        <SettingField
          path="cache.enabled"
          label="Enable Caching"
          description="Enable HTTP response caching for API requests"
          value={cache.enabled}
          type="boolean"
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="cache.storage_path"
          label="Cache Storage Path"
          description="Path to cache database (relative to config directory)"
          value={cache.storage_path}
          type="text"
          safetyLevel="affects_state"
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
