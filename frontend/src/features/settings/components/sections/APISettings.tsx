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
  const http = api.http || {}
  const retry = http.retry || {}
  const rateLimit = api.rate_limit || {}
  const concurrency = api.concurrency || {}
  const cache = api.cache || {}
  const custom = api.custom || {}

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

  // Render authentication section based on API type
  const renderAuthSection = () => {
    if (apiName === 'imvdb') {
      return (
        <SettingSection
          title="API Authentication"
          description="API keys and authentication credentials"
        >
          <div style={{
            padding: 'var(--space-3)',
            background: 'var(--mtv-yellow)',
            borderLeft: '4px solid #ca8a04',
            marginBottom: 'var(--space-4)',
            color: 'var(--bg-base)',
            fontFamily: 'var(--font-body)',
            fontSize: 'var(--text-sm)',
            lineHeight: '1.6'
          }}>
            <strong>Note:</strong> Environment variable <code style={{
              background: 'rgba(0,0,0,0.2)',
              padding: '2px 6px',
              fontFamily: 'monospace'
            }}>IMVDB_APP_KEY</code> takes precedence over this value.
            {custom.app_key === undefined && ' The API key may be excluded from the response for security.'}
          </div>

          <SettingField
            path={`apis.${apiName}.custom.app_key`}
            label="API Key"
            description="IMVDb API authentication key (stored in config.yaml as fallback)"
            value={custom.app_key || ''}
            type="text"
            safetyLevel="requires_reload"
            onChange={handleFieldChange}
          />
        </SettingSection>
      )
    }

    if (apiName === 'discogs') {
      return (
        <SettingSection
          title="API Authentication"
          description="API keys and authentication credentials"
        >
          <div style={{
            padding: 'var(--space-3)',
            background: 'var(--mtv-yellow)',
            borderLeft: '4px solid #ca8a04',
            marginBottom: 'var(--space-4)',
            color: 'var(--bg-base)',
            fontFamily: 'var(--font-body)',
            fontSize: 'var(--text-sm)',
            lineHeight: '1.6'
          }}>
            <strong>Note:</strong> Environment variables <code style={{
              background: 'rgba(0,0,0,0.2)',
              padding: '2px 6px',
              fontFamily: 'monospace'
            }}>DISCOGS_API_KEY</code> and <code style={{
              background: 'rgba(0,0,0,0.2)',
              padding: '2px 6px',
              fontFamily: 'monospace'
            }}>DISCOGS_API_SECRET</code> take precedence over these values.
            {(custom.api_key === undefined || custom.api_secret === undefined) && ' API credentials may be excluded from the response for security.'}
          </div>

          <SettingField
            path={`apis.${apiName}.custom.api_key`}
            label="API Key"
            description="Discogs API key (stored in config.yaml as fallback)"
            value={custom.api_key || ''}
            type="text"
            safetyLevel="requires_reload"
            onChange={handleFieldChange}
          />

          <SettingField
            path={`apis.${apiName}.custom.api_secret`}
            label="API Secret"
            description="Discogs API secret (stored in config.yaml as fallback)"
            value={custom.api_secret || ''}
            type="text"
            safetyLevel="requires_reload"
            onChange={handleFieldChange}
          />
        </SettingSection>
      )
    }

    if (apiName === 'spotify') {
      return (
        <SettingSection
          title="API Authentication"
          description="API keys and authentication credentials"
        >
          <div style={{
            padding: 'var(--space-3)',
            background: 'var(--mtv-yellow)',
            borderLeft: '4px solid #ca8a04',
            marginBottom: 'var(--space-4)',
            color: 'var(--bg-base)',
            fontFamily: 'var(--font-body)',
            fontSize: 'var(--text-sm)',
            lineHeight: '1.6'
          }}>
            <strong>Note:</strong> Environment variables <code style={{
              background: 'rgba(0,0,0,0.2)',
              padding: '2px 6px',
              fontFamily: 'monospace'
            }}>SPOTIFY_CLIENT_ID</code> and <code style={{
              background: 'rgba(0,0,0,0.2)',
              padding: '2px 6px',
              fontFamily: 'monospace'
            }}>SPOTIFY_CLIENT_SECRET</code> take precedence over these values.
            {(custom.client_id === undefined || custom.client_secret === undefined) && ' API credentials may be excluded from the response for security.'}
          </div>

          <SettingField
            path={`apis.${apiName}.custom.client_id`}
            label="Client ID"
            description="Spotify Client ID (stored in config.yaml as fallback)"
            value={custom.client_id || ''}
            type="text"
            safetyLevel="requires_reload"
            onChange={handleFieldChange}
          />

          <SettingField
            path={`apis.${apiName}.custom.client_secret`}
            label="Client Secret"
            description="Spotify Client Secret (stored in config.yaml as fallback)"
            value={custom.client_secret || ''}
            type="text"
            safetyLevel="requires_reload"
            onChange={handleFieldChange}
          />
        </SettingSection>
      )
    }

    return null
  }

  return (
    <>
      <SettingSection
        title={apiTitles[apiName]}
        description={apiDescriptions[apiName]}
      >
        <SettingField
          path={`apis.${apiName}.name`}
          label="API Client Name"
          description="Internal identifier for this API client"
          value={api.name}
          type="text"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.base_url`}
          label="Base URL"
          description="Base URL for API requests"
          value={api.base_url}
          type="text"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />
      </SettingSection>

      {renderAuthSection()}

      <SettingSection
        title="HTTP Configuration"
        description="Request timeout and retry settings for this API"
      >
        <SettingField
          path={`apis.${apiName}.http.timeout`}
          label="Request Timeout"
          description="Maximum time to wait for API requests (seconds)"
          value={http.timeout}
          type="number"
          min={1}
          max={300}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.http.retry.max_attempts`}
          label="Max Retry Attempts"
          description="Number of times to retry failed requests"
          value={retry.max_attempts}
          type="number"
          min={0}
          max={10}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.http.retry.backoff_multiplier`}
          label="Backoff Multiplier"
          description="Exponential backoff multiplier"
          value={retry.backoff_multiplier}
          type="number"
          min={0.1}
          max={10}
          step={0.1}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.http.retry.min_wait`}
          label="Min Wait Time"
          description="Minimum wait between retries (seconds)"
          value={retry.min_wait}
          type="number"
          min={0.1}
          max={60}
          step={0.1}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.http.retry.max_wait`}
          label="Max Wait Time"
          description="Maximum wait between retries (seconds)"
          value={retry.max_wait}
          type="number"
          min={1}
          max={300}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.http.retry.status_codes`}
          label="Retry Status Codes"
          description="HTTP status codes that trigger retries (one per line)"
          value={retry.status_codes}
          type="array"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />
      </SettingSection>

      <SettingSection
        title="Rate Limiting"
        description="Control request frequency to avoid API throttling"
      >
        <SettingField
          path={`apis.${apiName}.rate_limit.enabled`}
          label="Enable Rate Limiting"
          description="Enable rate limiting for this API client"
          value={rateLimit.enabled}
          type="boolean"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.rate_limit.requests_per_minute`}
          label="Requests Per Minute"
          description="Maximum requests allowed per minute"
          value={rateLimit.requests_per_minute}
          type="number"
          min={1}
          max={10000}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.rate_limit.requests_per_second`}
          label="Requests Per Second"
          description="Maximum requests allowed per second (optional)"
          value={rateLimit.requests_per_second}
          type="number"
          min={1}
          max={1000}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.rate_limit.requests_per_hour`}
          label="Requests Per Hour"
          description="Maximum requests allowed per hour (optional)"
          value={rateLimit.requests_per_hour}
          type="number"
          min={1}
          max={100000}
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
          max={1000}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />
      </SettingSection>

      <SettingSection
        title="Concurrency Control"
        description="Manage concurrent request limits"
      >
        <SettingField
          path={`apis.${apiName}.concurrency.max_concurrent_requests`}
          label="Max Concurrent Requests"
          description="Maximum number of simultaneous requests"
          value={concurrency.max_concurrent_requests}
          type="number"
          min={1}
          max={1000}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.concurrency.per_host_limit`}
          label="Per-Host Limit"
          description="Maximum concurrent requests per host (optional)"
          value={concurrency.per_host_limit}
          type="number"
          min={1}
          max={100}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />
      </SettingSection>

      <SettingSection
        title="Response Caching"
        description="HTTP response caching using Hishel"
      >
        <SettingField
          path={`apis.${apiName}.cache.enabled`}
          label="Enable Caching"
          description="Enable HTTP response caching"
          value={cache.enabled}
          type="boolean"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.cache.storage_path`}
          label="Cache Storage Path"
          description="Path to SQLite cache database"
          value={cache.storage_path}
          type="text"
          safetyLevel="affects_state"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.cache.ttl`}
          label="Time To Live (TTL)"
          description="Default cache duration in seconds"
          value={cache.ttl}
          type="number"
          min={1}
          max={86400}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.cache.stale_while_revalidate`}
          label="Stale While Revalidate"
          description="Serve stale responses while revalidating (seconds)"
          value={cache.stale_while_revalidate}
          type="number"
          min={0}
          max={3600}
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.cache.cacheable_methods`}
          label="Cacheable HTTP Methods"
          description="HTTP methods that can be cached (one per line)"
          value={cache.cacheable_methods}
          type="array"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path={`apis.${apiName}.cache.cacheable_status_codes`}
          label="Cacheable Status Codes"
          description="HTTP status codes that can be cached (one per line)"
          value={cache.cacheable_status_codes}
          type="array"
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
