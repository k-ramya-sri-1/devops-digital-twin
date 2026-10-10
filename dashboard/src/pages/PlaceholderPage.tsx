type PlaceholderPageProps = { title: string }

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div className="main-inner">
      <header className="page-header">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1 className="page-title">{title}</h1>
        </div>
      </header>
      <section className="panel placeholder-panel" aria-labelledby={`${title.toLowerCase()}-title`}>
        <div className="panel-heading">
          <h2 className="panel-title" id={`${title.toLowerCase()}-title`}>{title} workspace</h2>
          <p className="panel-note">Coming later</p>
        </div>
        <div className="panel-body">
          <p className="placeholder-copy">This page is planned for a later phase. No {title.toLowerCase()} data is available here yet.</p>
        </div>
      </section>
    </div>
  )
}