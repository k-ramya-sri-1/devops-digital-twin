export function Infrastructure() {
  return (
    <div className="main-inner">
      <header className="page-header">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1 className="page-title">Infrastructure</h1>
          <p className="page-subtitle">Current deployment telemetry for the Digital Twin environment.</p>
        </div>
      </header>
      <section className="panel placeholder-panel" aria-labelledby="infrastructure-title">
        <div className="panel-heading">
          <h2 className="panel-title" id="infrastructure-title">Telemetry unavailable</h2>
          <p className="panel-note">API coverage</p>
        </div>
        <div className="panel-body">
          <p className="placeholder-copy">
            Infrastructure telemetry is not available through the current API. There is no read-only endpoint for current Kubernetes deployment state, so deployment name, namespace, replica counts, CPU, memory, and health cannot be shown here.
          </p>
        </div>
      </section>
    </div>
  )
}