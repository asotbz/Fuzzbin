/* eslint-disable @typescript-eslint/no-explicit-any -- Settings system uses dynamic config types */
import { useState } from 'react'
import SettingSection from '../SettingSection'
import SettingField from '../SettingField'
import ConfirmChangeModal from '../ConfirmChangeModal'
import { useConfigUpdate } from '../../hooks/useConfigUpdate'
import type { ConfigConflictError } from '../../../../lib/api/endpoints/config'

interface OIDCSettingsProps {
  config: any
}

export default function OIDCSettings({ config }: OIDCSettingsProps) {
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

  const oidc = config?.oidc || {}

  return (
    <>
      <SettingSection
        title="OpenID Connect (OIDC)"
        description="Single sign-on via an external identity provider using Authorization Code + PKCE. When enabled, a login button appears on the login page allowing users to authenticate through the configured provider. The authenticated identity is bound to a single local user account."
      >
        <SettingField
          path="oidc.enabled"
          label="Enable OIDC"
          description="When enabled, an SSO login button is displayed on the login page. Requires issuer URL, client ID, and redirect URI to be configured. Password-based login remains available alongside OIDC."
          value={oidc.enabled}
          type="boolean"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path="oidc.issuer_url"
          label="Issuer URL"
          description="The base URL of the OIDC identity provider. Used to discover endpoints via .well-known/openid-configuration. Example: https://auth.example.com/realms/main"
          value={oidc.issuer_url}
          type="text"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path="oidc.client_id"
          label="Client ID"
          description="The client identifier registered with the identity provider for this application."
          value={oidc.client_id}
          type="text"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path="oidc.client_secret"
          label="Client Secret"
          description="The client secret for confidential clients. Leave empty for public clients using PKCE only (recommended for most setups)."
          value={oidc.client_secret}
          type="text"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path="oidc.redirect_uri"
          label="Redirect URI"
          description="The callback URL where the identity provider redirects after authentication. Must match the URI registered with the provider. Example: https://fuzzbin.example.com/oidc/callback"
          value={oidc.redirect_uri}
          type="text"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path="oidc.scopes"
          label="Scopes"
          description="Space-separated list of OIDC scopes to request. 'openid' is required. Add 'email' and 'profile' to receive user info claims, or 'groups' if your provider returns group membership in the ID token."
          value={oidc.scopes}
          type="text"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path="oidc.provider_name"
          label="Provider Name"
          description="Display label shown on the OIDC login button (e.g. 'SSO', 'Keycloak', 'Google'). This is purely cosmetic."
          value={oidc.provider_name}
          type="text"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />
      </SettingSection>

      <SettingSection
        title="Identity Binding"
        description="Controls which identity provider user is mapped to the local Fuzzbin account. On the first OIDC login, the provider's issuer and subject identifiers are permanently bound to the target local user. Subsequent logins from a different identity will be rejected."
      >
        <SettingField
          path="oidc.target_username"
          label="Target Username"
          description="The local Fuzzbin user account that OIDC logins are mapped to. The identity provider's subject claim will be bound to this user on first OIDC login."
          value={oidc.target_username}
          type="text"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path="oidc.allowed_subject"
          label="Allowed Subject"
          description="If set, only the identity provider user with this exact 'sub' claim value will be accepted. Useful to lock down which IdP account can authenticate. Leave empty to allow any authenticated user (subject to group restrictions)."
          value={oidc.allowed_subject}
          type="text"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />
      </SettingSection>

      <SettingSection
        title="Group Gating"
        description="Optionally restrict OIDC login to users who are members of a specific group in the identity provider. The group membership is checked on each login, so removing a user from the required group in the IdP will immediately prevent further access."
      >
        <SettingField
          path="oidc.required_group"
          label="Required Group"
          description="If set, the ID token must contain this group value in the groups claim. Users not in this group will be denied access. Leave empty to allow any authenticated user."
          value={oidc.required_group}
          type="text"
          safetyLevel="requires_reload"
          onChange={handleFieldChange}
        />

        <SettingField
          path="oidc.groups_claim"
          label="Groups Claim Name"
          description="The name of the JWT claim that contains group memberships. Most providers use 'groups', but some (e.g. Azure AD) use 'roles' or a custom claim name."
          value={oidc.groups_claim}
          type="text"
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
