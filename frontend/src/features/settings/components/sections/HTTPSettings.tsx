import { useState } from 'react'
import SettingSection from '../SettingSection'
import SettingField from '../SettingField'
import ConfirmChangeModal from '../ConfirmChangeModal'
import { useConfigUpdate } from '../../hooks/useConfigUpdate'
import type { ConfigConflictError } from '../../../../lib/api/endpoints/config'

interface HTTPSettingsProps {
  config: any
}

export default function HTTPSettings({ config }: HTTPSettingsProps) {
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

    // Re-submit with force=true
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

  const http = config?.http || {}
  const retry = http.retry || {}

  return (
    <>
      <SettingSection
        title="HTTP Client Configuration"
        description="Global settings for HTTP requests across all API clients"
      >
        <SettingField
          path="http.timeout"
          label="Request Timeout"
          description="Maximum time to wait for HTTP requests (seconds)"
          value={http.timeout}
          type="number"
          min={1}
          max={300}
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="http.max_redirects"
          label="Maximum Redirects"
          description="Maximum number of redirects to follow"
          value={http.max_redirects}
          type="number"
          min={0}
          max={20}
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="http.verify_ssl"
          label="Verify SSL Certificates"
          description="Enable SSL certificate verification for HTTPS requests"
          value={http.verify_ssl}
          type="boolean"
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="http.max_connections"
          label="Maximum Connections"
          description="Maximum number of connections in the pool"
          value={http.max_connections}
          type="number"
          min={1}
          max={1000}
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="http.max_keepalive_connections"
          label="Maximum Keep-Alive Connections"
          description="Maximum number of keep-alive connections"
          value={http.max_keepalive_connections}
          type="number"
          min={0}
          max={100}
          safetyLevel="safe"
          onChange={handleFieldChange}
        />
      </SettingSection>

      <SettingSection
        title="Retry Configuration"
        description="Exponential backoff settings for failed requests"
      >
        <SettingField
          path="http.retry.max_attempts"
          label="Maximum Retry Attempts"
          description="Number of times to retry failed requests"
          value={retry.max_attempts}
          type="number"
          min={1}
          max={10}
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="http.retry.backoff_multiplier"
          label="Backoff Multiplier"
          description="Multiplier for exponential backoff calculation"
          value={retry.backoff_multiplier}
          type="number"
          min={0.1}
          max={10}
          step={0.1}
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="http.retry.min_wait"
          label="Minimum Wait Time"
          description="Minimum time to wait between retries (seconds)"
          value={retry.min_wait}
          type="number"
          min={0.1}
          max={60}
          step={0.1}
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="http.retry.max_wait"
          label="Maximum Wait Time"
          description="Maximum time to wait between retries (seconds)"
          value={retry.max_wait}
          type="number"
          min={1}
          max={300}
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="http.retry.status_codes"
          label="Retry Status Codes"
          description="HTTP status codes that trigger a retry (one per line)"
          value={retry.status_codes}
          type="array"
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
