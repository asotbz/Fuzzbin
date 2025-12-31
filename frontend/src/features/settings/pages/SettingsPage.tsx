import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useConfig } from '../hooks/useConfig'
import HTTPSettings from '../components/sections/HTTPSettings'
import LoggingSettings from '../components/sections/LoggingSettings'
import DatabaseSettings from '../components/sections/DatabaseSettings'
import CacheSettings from '../components/sections/CacheSettings'
import APISettings from '../components/sections/APISettings'
import MediaSettings from '../components/sections/MediaSettings'
import LibrarySettings from '../components/sections/LibrarySettings'
import AdvancedSettings from '../components/sections/AdvancedSettings'
import './SettingsPage.css'

interface ConfigSection {
  id: string
  title: string
  group: string
}

const CONFIG_SECTIONS: ConfigSection[] = [
  // Core System
  { id: 'http', title: 'HTTP Client', group: 'Core System' },
  { id: 'logging', title: 'Logging', group: 'Core System' },
  { id: 'database', title: 'Database', group: 'Core System' },
  { id: 'cache', title: 'Cache', group: 'Core System' },

  // API Integrations
  { id: 'api-imvdb', title: 'IMVDb', group: 'API Integrations' },
  { id: 'api-discogs', title: 'Discogs', group: 'API Integrations' },
  { id: 'api-spotify', title: 'Spotify', group: 'API Integrations' },

  // Media Processing
  { id: 'ytdlp', title: 'yt-dlp', group: 'Media Processing' },
  { id: 'ffprobe', title: 'ffprobe', group: 'Media Processing' },
  { id: 'thumbnail', title: 'Thumbnails', group: 'Media Processing' },
  { id: 'nfo', title: 'NFO Files', group: 'Media Processing' },

  // Library Management
  { id: 'organizer', title: 'Organizer', group: 'Library Management' },
  { id: 'tags', title: 'Tags', group: 'Library Management' },
  { id: 'file-manager', title: 'File Manager', group: 'Library Management' },

  // Advanced
  { id: 'advanced', title: 'Advanced', group: 'Advanced' },
  { id: 'backup', title: 'Backup', group: 'Advanced' },
]

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState<string>(
    () => localStorage.getItem('fuzzbin-settings-section') || 'http'
  )

  const configQuery = useConfig()

  const handleSectionChange = (sectionId: string) => {
    setActiveSection(sectionId)
    localStorage.setItem('fuzzbin-settings-section', sectionId)
  }

  // Group sections
  const groups = CONFIG_SECTIONS.reduce((acc, section) => {
    if (!acc[section.group]) {
      acc[section.group] = []
    }
    acc[section.group].push(section)
    return acc
  }, {} as Record<string, ConfigSection[]>)

  const activeConfig = configQuery.data?.config

  return (
    <div className="settingsPage">
      {/* MTV-style Header */}
      <header className="settingsHeader">
        <div className="settingsHeaderTop">
          <div className="settingsTitleContainer">
            <img
              src="/fuzzbin-icon.png"
              alt="Fuzzbin"
              className="settingsIcon"
            />
            <h1 className="settingsTitle">SETTINGS</h1>
          </div>

          <div className="settingsActions">
            <button
              className="settingsActionButton"
              title="Undo last change"
            >
              <span className="actionIcon">↶</span>
              <span className="actionLabel">UNDO</span>
            </button>
            <button
              className="settingsActionButton"
              title="Redo change"
            >
              <span className="actionIcon">↷</span>
              <span className="actionLabel">REDO</span>
            </button>
          </div>
        </div>

        <nav className="settingsTopNav">
          <Link className="navButton" to="/library">
            <span className="navButtonInner">LIBRARY</span>
          </Link>
          <Link className="navButton" to="/activity">
            <span className="navButtonInner">ACTIVITY</span>
          </Link>
          <Link className="navButton" to="/add">
            <span className="navButtonInner">IMPORT HUB</span>
          </Link>
        </nav>
      </header>

      <main className="settingsMain">
        {/* Left Sidebar Navigation */}
        <aside className="settingsNav">
          <div className="navHeader">
            <div className="navHeaderIcon">⚙</div>
            <div className="navHeaderTitle">CONFIGURATION</div>
          </div>

          {Object.entries(groups).map(([groupName, sections]) => (
            <div key={groupName} className="navGroup">
              <div className="navGroupTitle">{groupName}</div>
              <div className="navGroupItems">
                {sections.map((section) => (
                  <button
                    key={section.id}
                    className={
                      activeSection === section.id
                        ? 'navItem navItemActive'
                        : 'navItem'
                    }
                    onClick={() => handleSectionChange(section.id)}
                  >
                    <span className="navItemDot">●</span>
                    <span className="navItemLabel">{section.title}</span>
                    {activeSection === section.id && (
                      <span className="navItemIndicator">▶</span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </aside>

        {/* Main Content Area */}
        <div className="settingsContent">
          <div className="settingsContentHeader">
            <h2 className="sectionTitle">
              {CONFIG_SECTIONS.find(s => s.id === activeSection)?.title || 'Settings'}
            </h2>
            <div className="sectionPath">
              CONFIG / {CONFIG_SECTIONS.find(s => s.id === activeSection)?.group.toUpperCase()} / {CONFIG_SECTIONS.find(s => s.id === activeSection)?.title.toUpperCase()}
            </div>
          </div>

          <div className="settingsPanel">
            {configQuery.isLoading && (
              <div className="settingsLoading">
                <div className="loadingSpinner"></div>
                <div className="loadingText">LOADING CONFIGURATION...</div>
              </div>
            )}

            {configQuery.isError && (
              <div className="settingsError">
                <div className="errorIcon">⚠</div>
                <div className="errorTitle">FAILED TO LOAD CONFIGURATION</div>
                <div className="errorMessage">
                  {configQuery.error instanceof Error
                    ? configQuery.error.message
                    : 'Unknown error'}
                </div>
              </div>
            )}

            {configQuery.isSuccess && activeConfig && (
              <div className="settingsFields">
                {/* Core System */}
                {activeSection === 'http' && <HTTPSettings config={activeConfig} />}
                {activeSection === 'logging' && <LoggingSettings config={activeConfig} />}
                {activeSection === 'database' && <DatabaseSettings config={activeConfig} />}
                {activeSection === 'cache' && <CacheSettings config={activeConfig} />}

                {/* API Integrations */}
                {activeSection === 'api-imvdb' && <APISettings config={activeConfig} apiName="imvdb" />}
                {activeSection === 'api-discogs' && <APISettings config={activeConfig} apiName="discogs" />}
                {activeSection === 'api-spotify' && <APISettings config={activeConfig} apiName="spotify" />}

                {/* Media Processing */}
                {activeSection === 'ytdlp' && <MediaSettings config={activeConfig} section="ytdlp" />}
                {activeSection === 'ffprobe' && <MediaSettings config={activeConfig} section="ffprobe" />}
                {activeSection === 'thumbnail' && <MediaSettings config={activeConfig} section="thumbnail" />}
                {activeSection === 'nfo' && <MediaSettings config={activeConfig} section="nfo" />}

                {/* Library Management */}
                {activeSection === 'organizer' && <LibrarySettings config={activeConfig} section="organizer" />}
                {activeSection === 'tags' && <LibrarySettings config={activeConfig} section="tags" />}
                {activeSection === 'file-manager' && <LibrarySettings config={activeConfig} section="file-manager" />}

                {/* Advanced */}
                {activeSection === 'advanced' && <AdvancedSettings config={activeConfig} section="advanced" />}
                {activeSection === 'backup' && <AdvancedSettings config={activeConfig} section="backup" />}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
