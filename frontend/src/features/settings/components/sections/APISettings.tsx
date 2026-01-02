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
  const auth = api.auth || {}

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
            {auth.app_key === undefined && ' The API key may be excluded from the response for security.'}
          </div>

          <SettingField
            path={`apis.${apiName}.auth.app_key`}
            label="API Key"
            description="IMVDb API authentication key"
            value={auth.app_key || ''}
            type="text"
            safetyLevel="safe"
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
            {(auth.api_key === undefined || auth.api_secret === undefined) && ' API credentials may be excluded from the response for security.'}
          </div>

          <SettingField
            path={`apis.${apiName}.auth.api_key`}
            label="API Key"
            description="Discogs API key"
            value={auth.api_key || ''}
            type="text"
            safetyLevel="safe"
            onChange={handleFieldChange}
          />

          <SettingField
            path={`apis.${apiName}.auth.api_secret`}
            label="API Secret"
            description="Discogs API secret"
            value={auth.api_secret || ''}
            type="text"
            safetyLevel="safe"
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
            {(auth.client_id === undefined || auth.client_secret === undefined) && ' API credentials may be excluded from the response for security.'}
          </div>

          <SettingField
            path={`apis.${apiName}.auth.client_id`}
            label="Client ID"
            description="Spotify Client ID"
            value={auth.client_id || ''}
            type="text"
            safetyLevel="safe"
            onChange={handleFieldChange}
          />

          <SettingField
            path={`apis.${apiName}.auth.client_secret`}
            label="Client Secret"
            description="Spotify Client Secret"
            value={auth.client_secret || ''}
            type="text"
            safetyLevel="safe"
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
        <div style={{
          padding: 'var(--space-3)',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-subtle)',
          marginBottom: 'var(--space-4)',
          fontFamily: 'var(--font-body)',
          fontSize: 'var(--text-sm)',
          lineHeight: '1.6'
        }}>
          Rate limiting, caching, and connection settings use sensible defaults.
          For advanced configuration, see <code style={{
            background: 'rgba(0,0,0,0.2)',
            padding: '2px 6px',
            fontFamily: 'monospace'
          }}>docs/advanced-config.md</code>
        </div>
      </SettingSection>

      {renderAuthSection()}

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
