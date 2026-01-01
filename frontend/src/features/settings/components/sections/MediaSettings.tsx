/* eslint-disable @typescript-eslint/no-explicit-any -- Settings system uses dynamic config types */
import { useState } from 'react'
import SettingSection from '../SettingSection'
import SettingField from '../SettingField'
import ConfirmChangeModal from '../ConfirmChangeModal'
import { useConfigUpdate } from '../../hooks/useConfigUpdate'
import type { ConfigConflictError } from '../../../../lib/api/endpoints/config'

interface MediaSettingsProps {
  config: any
  section: 'ytdlp' | 'ffprobe' | 'thumbnail' | 'nfo'
}

export default function MediaSettings({ config, section }: MediaSettingsProps) {
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

  const sectionConfig = config?.[section] || {}

  // Render based on section type
  const renderYtdlpSettings = () => (
    <>
      <SettingSection
        title="yt-dlp Configuration"
        description="YouTube downloader settings and options"
      >
        <SettingField
          path="ytdlp.binary_path"
          label="Binary Path"
          description="Path to yt-dlp executable"
          value={sectionConfig.binary_path}
          type="text"
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="ytdlp.default_download_path"
          label="Default Download Path"
          description="Default directory for downloads"
          value={sectionConfig.default_download_path}
          type="text"
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="ytdlp.format"
          label="Video Format"
          description="Preferred video format selector"
          value={sectionConfig.format}
          type="text"
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="ytdlp.extract_audio"
          label="Extract Audio"
          description="Extract audio track separately"
          value={sectionConfig.extract_audio}
          type="boolean"
          safetyLevel="safe"
          onChange={handleFieldChange}
        />

        <SettingField
          path="ytdlp.audio_format"
          label="Audio Format"
          description="Preferred audio format when extracting"
          value={sectionConfig.audio_format}
          type="select"
          options={[
            { label: 'MP3', value: 'mp3' },
            { label: 'AAC', value: 'aac' },
            { label: 'FLAC', value: 'flac' },
            { label: 'Opus', value: 'opus' },
          ]}
          safetyLevel="safe"
          onChange={handleFieldChange}
        />
      </SettingSection>
    </>
  )

  const renderFfprobeSettings = () => (
    <SettingSection
      title="ffprobe Configuration"
      description="Media file analysis tool settings"
    >
      <SettingField
        path="ffprobe.binary_path"
        label="Binary Path"
        description="Path to ffprobe executable"
        value={sectionConfig.binary_path}
        type="text"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />
    </SettingSection>
  )

  const renderThumbnailSettings = () => (
    <SettingSection
      title="Thumbnail Configuration"
      description="Video thumbnail generation and caching"
    >
      <SettingField
        path="thumbnail.cache_dir"
        label="Cache Directory"
        description="Directory for storing generated thumbnails"
        value={sectionConfig.cache_dir}
        type="text"
        safetyLevel="affects_state"
        onChange={handleFieldChange}
      />

      <div style={{
        padding: 'var(--space-3)',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border-subtle)',
        marginTop: 'var(--space-4)',
        fontFamily: 'var(--font-body)',
        fontSize: 'var(--text-sm)',
        lineHeight: '1.6'
      }}>
        Thumbnail quality and dimensions use sensible defaults.
        For advanced configuration, see <code style={{
          background: 'rgba(0,0,0,0.2)',
          padding: '2px 6px',
          fontFamily: 'monospace'
        }}>docs/advanced-config.md</code>
      </div>
    </SettingSection>
  )

  const renderNFOSettings = () => (
    <SettingSection
      title="NFO File Configuration"
      description="Kodi-compatible NFO metadata file settings"
    >
      <SettingField
        path="nfo.write_musicvideo_nfo"
        label="Write Video NFO Files"
        description="Generate &lt;basename&gt;.nfo files for each music video"
        value={sectionConfig.write_musicvideo_nfo}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />

      <SettingField
        path="nfo.write_artist_nfo"
        label="Write Artist NFO Files"
        description="Generate artist.nfo files in artist directories"
        value={sectionConfig.write_artist_nfo}
        type="boolean"
        safetyLevel="safe"
        onChange={handleFieldChange}
      />
    </SettingSection>
  )

  return (
    <>
      {section === 'ytdlp' && renderYtdlpSettings()}
      {section === 'ffprobe' && renderFfprobeSettings()}
      {section === 'thumbnail' && renderThumbnailSettings()}
      {section === 'nfo' && renderNFOSettings()}

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
