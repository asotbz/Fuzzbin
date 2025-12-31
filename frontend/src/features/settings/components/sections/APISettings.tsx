/* eslint-disable @typescript-eslint/no-explicit-any -- Settings system uses dynamic config types */
import { useState } from 'react'
import SettingSection from '../SettingSection'
import SettingField from '../SettingField'
import ConfirmChangeModal from '../ConfirmChangeModal'
import { useConfigUpdate } from '../../hooks/useConfigUpdate'
import type { ConfigConflictError } from '../../../../lib/api/endpoints/config'

interface APISettingsProps {
  config: any
  apiName: 'imvdb' | 'discogs' | 'spotify'
}

export default function APISettings({ config, apiName }: APISettingsProps) {
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

  const apis = config?.apis || {}
  const api = apis[apiName] || {}
  const rateLimit = api.rate_limit || {}

  const apiTitles: Record<string, string> = {
    imvdb: 'IMVDb API',
    discogs: 'Discogs API',
    spotify: 'Spotify API',
  }

  const apiDescriptions: Record<string, string> = {
    imvdb: 'Internet Music Video Database - music video metadata',
    discogs: 'Discogs - music database with album and artist information',
    spotify: 'Spotify - streaming service with rich metadata',
  }

  return (
    <>
      <SettingSection
        title={apiTitles[apiName]}
        description={apiDescriptions[apiName]}
      >
        <SettingField
          path={`apis.${apiName}.enabled`}
          label="Enable API Client"
          description={`Enable ${apiTitles[apiName]} integration`}
          value={api.enabled}
          type="boolean"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.timeout`}
          label="Request Timeout"
          description="Maximum time to wait for API requests (seconds)"
          value={api.timeout}
          type="number"
          min={1}
          max={300}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />
      </SettingSection>

      <SettingSection
        title="Rate Limiting"
        description="Control request frequency to avoid API throttling"
      >
        <SettingField
          path={`apis.${apiName}.rate_limit.max_requests`}
          label="Maximum Requests"
          description="Maximum requests allowed per time window"
          value={rateLimit.max_requests}
          type="number"
          min={1}
          max={1000}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.rate_limit.time_window`}
          label="Time Window"
          description="Time window for rate limiting (seconds)"
          value={rateLimit.time_window}
          type="number"
          min={1}
          max={3600}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.rate_limit.burst_size`}
          label="Burst Size"
          description="Maximum burst size for rapid requests"
          value={rateLimit.burst_size}
          type="number"
          min={1}
          max={100}
          safetyLevel="requires_reload"
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
