import type { ReactNode } from 'react'

type LayoutProps = { children: ReactNode }

const navigation = [
  { label: 'Dashboard', mark: '01', active: true },
  { label: 'Experiments', mark: '02', active: false },
  { label: 'Infrastructure', mark: '03', active: false },
  { label: 'Results', mark: '04', active: false },
]

export function Layout({ children }: LayoutProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">DT</span>
          <div>
            <p className="brand-name">DevOps Digital Twin</p>
            <p className="brand-caption">Control surface</p>
          </div>
        </div>
        <p className="nav-label">Workspace</p>
        <nav aria-label="Primary navigation">
          <ul className="nav-list">
            {navigation.map((item) => (
              <li key={item.label}>
                <a
                  className={`nav-item${item.active ? ' active' : ''}`}
                  href={item.active ? '#dashboard' : `#${item.label.toLowerCase()}`}
                  aria-current={item.active ? 'page' : undefined}
                >
                  <span className="nav-mark" aria-hidden="true">{item.mark}</span>
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <p className="sidebar-footer">
          Phase 23 foundation<br />
          Local workspace / static data
        </p>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  )
}