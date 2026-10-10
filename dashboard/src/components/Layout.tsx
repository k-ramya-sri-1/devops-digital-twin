import type { ReactNode } from 'react'

type LayoutProps = { children: ReactNode }

const navigation = [
  { label: 'Dashboard', mark: '01', route: '#dashboard' },
  { label: 'Experiments', mark: '02', route: '#experiments' },
  { label: 'Infrastructure', mark: '03', route: '#infrastructure' },
  { label: 'Results', mark: '04', route: '#results' },
]

type LayoutPropsWithRoute = LayoutProps & { currentHash: string }

export function Layout({ children, currentHash }: LayoutPropsWithRoute) {
  const workspaceRoutes = navigation.map((item) => item.route)
  const activeHash = workspaceRoutes.includes(currentHash)
    ? currentHash
    : currentHash.startsWith('#experiment/')
      ? null
      : '#dashboard'

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
                  className={`nav-item${activeHash === item.route ? ' active' : ''}`}
                  href={item.route}
                  aria-current={activeHash === item.route ? 'page' : undefined}
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