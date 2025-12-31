import type { ReactNode } from 'react'
import './SettingSection.css'

interface SettingSectionProps {
  title: string
  description?: string
  children: ReactNode
}

export default function SettingSection({ title, description, children }: SettingSectionProps) {
  return (
    <div className="settingSection">
      <div className="settingSectionHeader">
        <h3 className="settingSectionTitle">{title}</h3>
        {description && <p className="settingSectionDescription">{description}</p>}
      </div>
      <div className="settingSectionFields">
        {children}
      </div>
    </div>
  )
}
