/* eslint-disable @typescript-eslint/no-explicit-any -- Settings system uses dynamic config types */
import { useState } from 'react'
import SettingSection from '../SettingSection'
import SettingField from '../SettingField'
import ConfirmChangeModal from '../ConfirmChangeModal'
import { useConfigUpdate } from '../../hooks/useConfigUpdate'
import type { ConfigConflictError } from '../../../../lib/api/endpoints/config'

interface AdvancedSettingsProps {
  config: any
  section: 'advanced' | 'backup'
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

  const advanced = config?.advanced || {}
  const backup = config?.backup || {}

  const renderAdvancedSettings = () => (
    <SettingSection
      title="Advanced Configuration"
      description="Advanced features and experimental settings"
    >
      <SettingField
        path="advanced.enable_bulk_operations"
        label="Enable Bulk Operations"
        description="Allow bulk update/delete operations"
        value={advanced.enable_bulk_operations}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="advanced.max_concurrent_jobs"
        label="Max Concurrent Jobs"
        description="Maximum number of concurrent background jobs"
        value={advanced.max_concurrent_jobs}
        type="number"
        min={1}
        max={20}
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="advanced.enable_debug_mode"
        label="Enable Debug Mode"
        description="Enable additional debugging features"
        value={advanced.enable_debug_mode}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />
    </SettingSection>
  )

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
        path="backup.backup_dir"
        label="Backup Directory"
        description="Directory for storing database backups"
        value={backup.backup_dir}
        type="text"
        safetyLevel="affects_state"
        onChange={handleFieldChange}
      />

      <SettingField
        path="backup.retention_days"
        label="Retention Period (Days)"
        description="How long to keep old backups"
        value={backup.retention_days}
        type="number"
        min={1}
        max={365}
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="backup.interval_hours"
        label="Backup Interval (Hours)"
        description="How often to create automatic backups"
        value={backup.interval_hours}
        type="number"
        min={1}
        max={168}
        safetyLevel="safe"
        onChange={handleFieldChange}
      />
    </SettingSection>
  )

  return (
    <>
      {section === 'advanced' && renderAdvancedSettings()}
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
