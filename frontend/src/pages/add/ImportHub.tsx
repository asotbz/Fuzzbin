import { Link } from 'react-router-dom'
import './ImportHub.css'

export default function ImportHub() {
  return (
    <div className="importHub">
      <header className="importHubHeader">
        <div className="importHubHeaderTop">
          <div className="importHubTitleContainer">
            <img src="/fuzzbin-icon.png" alt="Fuzzbin" className="importHubIcon" />
            <h1 className="importHubTitle">Import Hub</h1>
          </div>
        </div>

        <nav className="importHubNav">
          <Link to="/library" className="primaryButton">
            Video Library
          </Link>
          <Link to="/activity" className="primaryButton">
            Activity Monitor
          </Link>
          <Link to="/settings" className="primaryButton">
            Settings
          </Link>
        </nav>
      </header>

      <div className="importHubGrid">
        {/* Artist/Title Search Card */}
        <Link to="/add/search" className="importCard importCardPrimary">
          <div className="importCardGlow" />
          <div className="importCardIcon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <path d="M21 21l-4.35-4.35" />
              <path d="M11 8v6" />
              <path d="M8 11h6" />
            </svg>
          </div>
          <div className="importCardContent">
            <h2 className="importCardTitle">Artist/Title Search</h2>
            <p className="importCardDescription">
              Curated import with full metadata control. Search across IMVDb, Discogs, and YouTube.
              Review, edit, and merge sources before import.
            </p>
            <div className="importCardFeatures">
              <span className="importCardFeature">Multi-source search</span>
              <span className="importCardFeature">Metadata editing</span>
              <span className="importCardFeature">Source comparison</span>
            </div>
          </div>
          <div className="importCardCta">
            <span>Launch Wizard</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </div>
        </Link>

        {/* Spotify Playlist Card */}
        <Link to="/add/spotify" className="importCard">
          <div className="importCardGlow" />
          <div className="importCardIcon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M8 8h8M8 12h8M8 16h8" />
            </svg>
          </div>
          <div className="importCardContent">
            <h2 className="importCardTitle">Spotify Playlist</h2>
            <p className="importCardDescription">
              Batch import entire playlists. Preview tracks, detect existing items,
              and configure import settings.
            </p>
            <div className="importCardFeatures">
              <span className="importCardFeature">Batch processing</span>
              <span className="importCardFeature">Duplicate detection</span>
            </div>
          </div>
          <div className="importCardCta">
            <span>Import Playlist</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </div>
        </Link>

        {/* NFO Directory Card */}
        <Link to="/add/nfo" className="importCard">
          <div className="importCardGlow" />
          <div className="importCardIcon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
              <polyline points="13 2 13 9 20 9" />
              <path d="M9 13h6M9 17h6" />
            </svg>
          </div>
          <div className="importCardContent">
            <h2 className="importCardTitle">NFO Directory Scan</h2>
            <p className="importCardDescription">
              Import from local filesystem. Scan directories for .nfo files with full or
              discovery mode.
            </p>
            <div className="importCardFeatures">
              <span className="importCardFeature">Recursive scan</span>
              <span className="importCardFeature">NFO parsing</span>
            </div>
          </div>
          <div className="importCardCta">
            <span>Scan Directory</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </div>
        </Link>
      </div>

      <div className="importHubFooter">
        <Link to="/library" className="importHubBackLink">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Back to Library
        </Link>
      </div>
    </div>
  )
}
