import type { ReactNode } from 'react'
import { NAV_GROUPS, type SectionId } from './sections'
import './Sidebar.css'

interface Props {
  current: SectionId
  onSelect: (id: SectionId) => void
  collapsed: boolean
  onToggle: () => void
  status: ReactNode
}

export function Sidebar({ current, onSelect, collapsed, onToggle, status }: Props) {
  return (
    <nav className={`sidebar${collapsed ? ' sidebar-collapsed' : ''}`} aria-label="Secciones">
      <div className="sidebar-top">
        <h1 className="sidebar-logo">
          <span aria-hidden="true">♠</span>
          <span className="sidebar-text">POKKER</span>
        </h1>
        <button
          type="button"
          className="sidebar-toggle"
          aria-label={collapsed ? 'Desplegar menú' : 'Plegar menú'}
          aria-expanded={!collapsed}
          title={collapsed ? 'Desplegar menú' : 'Plegar menú'}
          onClick={onToggle}
        >
          <span aria-hidden="true">{collapsed ? '»' : '«'}</span>
        </button>
      </div>

      {NAV_GROUPS.map((group) => (
        <div key={group.title} role="group" aria-label={group.title} className="sidebar-group">
          <div className="sidebar-group-title" aria-hidden="true">
            {group.title}
          </div>
          {group.items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`sidebar-item${current === item.id ? ' sidebar-item-active' : ''}`}
              aria-current={current === item.id ? 'page' : undefined}
              title={item.label}
              onClick={() => onSelect(item.id)}
            >
              <span className="sidebar-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span className="sidebar-text">{item.label}</span>
            </button>
          ))}
        </div>
      ))}

      <div className="sidebar-status" aria-live="polite">
        <span className="sidebar-text">{status}</span>
      </div>
    </nav>
  )
}
