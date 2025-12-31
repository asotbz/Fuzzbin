/* eslint-disable @typescript-eslint/no-explicit-any -- Settings system uses dynamic config types */
import { useState } from 'react'
import SettingSection from '../SettingSection'
import SettingField from '../SettingField'
import ConfirmChangeModal from '../ConfirmChangeModal'
import { useConfigUpdate } from '../../hooks/useConfigUpdate'
import type { ConfigConflictError } from '../../../../lib/api/endpoints/config'

interface LibrarySettingsProps {
  config: any
  section: 'organizer' | 'tags' | 'file-manager'
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
  const fileManager = config?.file_manager || {}

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
        path="tags.auto_genre_tagging"
        label="Auto Genre Tagging"
        description="Automatically tag videos with genre metadata"
        value={tags.auto_genre_tagging}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="tags.deduplicate"
        label="Deduplicate Tags"
        description="Remove duplicate tags automatically"
        value={tags.deduplicate}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />
    </SettingSection>
  )

  const renderFileManagerSettings = () => (
    <SettingSection
      title="File Manager"
      description="File operations and trash management"
    >
      <SettingField
        path="file_manager.trash_dir"
        label="Trash Directory"
        description="Directory for deleted files (relative to library directory)"
        value={fileManager.trash_dir}
        type="text"
        safetyLevel="affects_state"
        onChange={handleFieldChange}
      />

      <SettingField
        path="file_manager.auto_empty_trash_days"
        label="Auto-Empty Trash (Days)"
        description="Automatically empty trash after N days (0 = disabled)"
        value={fileManager.auto_empty_trash_days}
        type="number"
        min={0}
        max={365}
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="file_manager.verify_file_integrity"
        label="Verify File Integrity"
        description="Verify file integrity during operations"
        value={fileManager.verify_file_integrity}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />
    </SettingSection>
  )

  return (
    <>
      {section === 'organizer' && renderOrganizerSettings()}
      {section === 'tags' && renderTagsSettings()}
      {section === 'file-manager' && renderFileManagerSettings()}

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
