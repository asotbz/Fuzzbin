import type { CSSProperties, ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import './PageHeader.css'

type PageHeaderNavItem = {
  label: string
  to: string
  end?: boolean
  ariaLabel?: string
}

type PageHeaderProps = {
  title: string
  iconSrc?: string
  iconAlt?: string
  accent?: string
  actions?: ReactNode
  navItems?: PageHeaderNavItem[]
  subNavItems?: PageHeaderNavItem[]
  navLabel?: string
  subNavLabel?: string
  className?: string
}

export default function PageHeader({
  title,
  iconSrc,
  iconAlt,
  accent,
  actions,
  navItems = [],
  subNavItems = [],
  navLabel = 'Primary',
  subNavLabel,
  className,
}: PageHeaderProps) {
  const style = accent
    ? ({ '--header-accent': accent, '--nav-accent': accent } as CSSProperties)
    : undefined

  const renderNavItems = (items: PageHeaderNavItem[]) =>
    items.map((item) => (
      <NavLink
        key={`${item.to}-${item.label}`}
        to={item.to}
        end={item.end}
        aria-label={item.ariaLabel}
        className={({ isActive }) => `addNavLink${isActive ? ' addNavLinkActive' : ''}`}
      >
        {item.label}
      </NavLink>
    ))

  return (
    <header className={['pageHeader', className].filter(Boolean).join(' ')} style={style}>
      <div className="pageHeaderTop">
        <div className="pageHeaderTitleContainer">
          {iconSrc ? <img src={iconSrc} alt={iconAlt ?? title} className="pageHeaderIcon" /> : null}
          <h1 className="pageHeaderTitle">{title}</h1>
        </div>
        {actions ? <div className="pageHeaderActions">{actions}</div> : null}
      </div>

      {navItems.length > 0 ? (
        <nav className="pageHeaderNav addNav" aria-label={navLabel}>
          {renderNavItems(navItems)}
        </nav>
      ) : null}

      {subNavItems.length > 0 ? (
        <div className="pageHeaderSubNav">
          {subNavLabel ? <div className="pageHeaderSubNavLabel">{subNavLabel}</div> : null}
          <nav className="addNav" aria-label={subNavLabel ?? 'Secondary'}>
            {renderNavItems(subNavItems)}
          </nav>
        </div>
      ) : null}
    </header>
  )
}
