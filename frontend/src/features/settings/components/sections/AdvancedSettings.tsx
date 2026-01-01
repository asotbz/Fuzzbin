/* eslint-disable @typescript-eslint/no-explicit-any -- Settings system uses dynamic config types */
import { useState } from 'react'
import SettingSection from '../SettingSection'
import SettingField from '../SettingField'
import ConfirmChangeModal from '../ConfirmChangeModal'
import { useConfigUpdate } from '../../hooks/useConfigUpdate'
import type { ConfigConflictError } from '../../../../lib/api/endpoints/config'

interface AdvancedSettingsProps {
  config: any
  section: 'backup'
}

export default function AdvancedSettings({ config, section }: AdvancedSettingsProps) {
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

  const backup = config?.backup || {}

  const renderBackupSettings = () => (
    <SettingSection
      title="Backup Configuration"
      description="Automatic database backup settings"
    >
      <SettingField
        path="backup.enabled"
        label="Enable Auto-Backup"
        description="Automatically backup database periodically"
        value={backup.enabled}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="backup.output_dir"
        label="Backup Directory"
        description="Directory for storing backup archives (relative to config_dir)"
        value={backup.output_dir}
        type="text"
        safetyLevel="affects_state"
        onChange={handleFieldChange}
      />

      <SettingField
        path="backup.retention_count"
        label="Retention Count"
        description="Number of backup archives to retain (oldest are deleted)"
        value={backup.retention_count}
        type="number"
        min={1}
        max={365}
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="backup.schedule"
        label="Backup Schedule (Cron)"
        description="Cron expression for backup schedule (default: daily at 2 AM)"
        value={backup.schedule}
        type="text"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />
    </SettingSection>
  )

  return (
    <>
      {section === 'backup' && renderBackupSettings()}

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
