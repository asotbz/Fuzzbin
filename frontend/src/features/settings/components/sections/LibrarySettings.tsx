/* eslint-disable @typescript-eslint/no-explicit-any -- Settings system uses dynamic config types */
import { useState } from 'react'
import SettingSection from '../SettingSection'
import SettingField from '../SettingField'
import ConfirmChangeModal from '../ConfirmChangeModal'
import { useConfigUpdate } from '../../hooks/useConfigUpdate'
import type { ConfigConflictError } from '../../../../lib/api/endpoints/config'

interface LibrarySettingsProps {
  config: any
  section: 'organizer' | 'tags' | 'trash'
}

export default function LibrarySettings({ config, section }: LibrarySettingsProps) {
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

  const organizer = config?.organizer || {}
  const tags = config?.tags || {}
  const trash = config?.trash || {}

  const renderOrganizerSettings = () => (
    <SettingSection
      title="File Organizer"
      description="Automatic file organization and path patterns"
    >
      <SettingField
        path="organizer.enabled"
        label="Enable Auto-Organization"
        description="Automatically organize imported files"
        value={organizer.enabled}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="organizer.path_pattern"
        label="Path Pattern"
        description="Organization pattern (use {artist}, {title}, {year} placeholders)"
        value={organizer.path_pattern}
        type="text"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="organizer.create_artist_dirs"
        label="Create Artist Directories"
        description="Group videos by artist in separate directories"
        value={organizer.create_artist_dirs}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="organizer.sanitize_filenames"
        label="Sanitize Filenames"
        description="Remove invalid characters from filenames"
        value={organizer.sanitize_filenames}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />
    </SettingSection>
  )

  const renderTagsSettings = () => (
    <SettingSection
      title="Tag Management"
      description="Video metadata tagging configuration"
    >
      <SettingField
        path="tags.normalize"
        label="Normalize Tags"
        description="Convert tags to lowercase for consistency"
        value={tags.normalize}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="tags.auto_decade.enabled"
        label="Auto Decade Tagging"
        description="Automatically add decade tags based on release year"
        value={tags.auto_decade?.enabled}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="tags.auto_decade.format"
        label="Decade Tag Format"
        description="Format for decade tags (must contain {decade})"
        value={tags.auto_decade?.format}
        type="text"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />
    </SettingSection>
  )

  const renderTrashSettings = () => (
    <SettingSection
      title="Trash Management"
      description="Soft-delete and automatic cleanup settings"
    >
      <SettingField
        path="trash.trash_dir"
        label="Trash Directory"
        description="Directory for deleted files (relative to library directory)"
        value={trash.trash_dir}
        type="text"
        safetyLevel="affects_state"
        onChange={handleFieldChange}
      />

      <SettingField
        path="trash.enabled"
        label="Enable Auto Cleanup"
        description="Automatically clean up old items from trash"
        value={trash.enabled}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="trash.retention_days"
        label="Retention Days"
        description="Delete items from trash older than this many days"
        value={trash.retention_days}
        type="number"
        min={1}
        max={365}
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="trash.schedule"
        label="Cleanup Schedule"
        description="Cron expression for cleanup schedule (e.g., '0 3 * * *' for daily at 3 AM)"
        value={trash.schedule}
        type="text"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />
    </SettingSection>
  )

  return (
    <>
      {section === 'organizer' && renderOrganizerSettings()}
      {section === 'tags' && renderTagsSettings()}
      {section === 'trash' && renderTrashSettings()}

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
