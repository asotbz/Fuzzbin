import { useHealth } from '../../../../api/health'
import { APP_VERSION } from '../../../../lib/version'
import SettingSection from '../SettingSection'

export default function AboutSettings() {
  const healthQuery = useHealth()

  return (
    <SettingSection
      title="About Fuzzbin"
      description="Version information and system status"
    >
      <div className="aboutGrid">
        <div className="aboutItem">
          <div className="aboutLabel">Frontend Version</div>
          <div className="aboutValue">{APP_VERSION}</div>
        </div>

        <div className="aboutItem">
          <div className="aboutLabel">Backend Version</div>
          <div className="aboutValue">
            {healthQuery.isLoading ? (
              <span className="aboutLoading">Loading...</span>
            ) : healthQuery.isError ? (
              <span className="aboutError">Unavailable</span>
            ) : (
              healthQuery.data?.version
            )}
          </div>
        </div>

        <div className="aboutItem">
          <div className="aboutLabel">API Status</div>
          <div className="aboutValue">
            {healthQuery.isLoading ? (
              <span className="aboutLoading">Checking...</span>
            ) : healthQuery.isError ? (
              <span className="aboutError">Offline</span>
            ) : (
              <span className="aboutOnline">Online</span>
            )}
          </div>
        </div>

        <div className="aboutItem">
          <div className="aboutLabel">Authentication</div>
          <div className="aboutValue">
            {healthQuery.isLoading ? (
              <span className="aboutLoading">Checking...</span>
            ) : healthQuery.isError ? (
              <span className="aboutError">Unknown</span>
            ) : healthQuery.data?.auth_enabled ? (
              <span className="aboutEnabled">Enabled</span>
            ) : (
              <span className="aboutDisabled">Disabled</span>
            )}
          </div>
        </div>
      </div>

      <div className="aboutLinks">
        <a
          href="https://github.com/asotbz/fuzzbin"
          target="_blank"
          rel="noopener noreferrer"
          className="aboutLink"
        >
          GitHub Repository
        </a>
        <a
          href="https://github.com/asotbz/fuzzbin/issues"
          target="_blank"
          rel="noopener noreferrer"
          className="aboutLink"
        >
          Report an Issue
        </a>
      </div>
    </SettingSection>
  )
}
