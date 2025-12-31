import type { SafetyLevel } from '../../../lib/api/endpoints/config'
import './SafetyBadge.css'

interface SafetyBadgeProps {
  level: SafetyLevel
  className?: string
}

export default function SafetyBadge({ level, className = '' }: SafetyBadgeProps) {
  const badges = {
    safe: {
      icon: '✓',
      label: 'SAFE',
      title: 'Changes apply immediately without side effects',
    },
    requires_reload: {
      icon: '↻',
      label: 'RELOAD REQUIRED',
      title: 'Component reload needed for changes to take effect',
    },
    affects_state: {
      icon: '⚠',
      label: 'RESTART REQUIRED',
      title: 'Application restart may be required',
    },
  }

  const badge = badges[level]

  return (
    <span
      className={`safetyBadge safetyBadge--${level} ${className}`}
      title={badge.title}
    >
      <span className="safetyBadge__icon">{badge.icon}</span>
      <span className="safetyBadge__label">{badge.label}</span>
    </span>
  )
}
