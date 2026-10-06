type SummaryCardProps = { label: string; value: number }

const summaryCards: SummaryCardProps[] = [
  { label: 'Total Experiments', value: 12 },
  { label: 'Created', value: 5 },
  { label: 'Executed', value: 5 },
  { label: 'Validated', value: 2 },
]

const recentExperiments = [
  { id: 'EXP-001', name: 'Traffic Surge Test', scenario: 'TRAFFIC_SURGE', status: 'CREATED' },
  { id: 'EXP-002', name: 'Pod Failure Test', scenario: 'INSTANCE_FAILURE', status: 'EXECUTED' },
  { id: 'EXP-003', name: 'Scale Out Test', scenario: 'SCALE_OUT', status: 'VALIDATED' },
]

export function Dashboard() {
  return (
    <div className="main-inner" id="dashboard">
      <header className="page-header">
        <div>
          <p className="eyebrow">Operations overview</p>
          <h1 className="page-title">DevOps Digital Twin</h1>
          <p className="page-subtitle">Infrastructure Simulation, What-If Analysis and Deployment Impact Prediction</p>
        </div>
        <div className="connection-state"><span className="state-dot" aria-hidden="true" />Placeholder data · API pending</div>
      </header>
      <section className="summary-grid" aria-label="Experiment summary">
        {summaryCards.map((card) => (
          <article className="summary-card" key={card.label}>
            <p className="summary-label">{card.label}</p>
            <p className="summary-value">{card.value}</p>
            <div className="summary-accent" aria-hidden="true" />
          </article>
        ))}
      </section>
      <div className="content-grid">
        <section className="panel" aria-labelledby="recent-experiments-title">
          <div className="panel-heading"><h2 className="panel-title" id="recent-experiments-title">Recent experiments</h2><p className="panel-note">Placeholder records</p></div>
          <table className="experiment-table">
            <thead><tr><th scope="col">ID</th><th scope="col">Name</th><th scope="col">Scenario</th><th scope="col">Status</th></tr></thead>
            <tbody>{recentExperiments.map((experiment) => (
              <tr key={experiment.id}><td>{experiment.id}</td><td className="experiment-name">{experiment.name}</td><td className="scenario-name">{experiment.scenario}</td><td><span className={`status-badge ${experiment.status.toLowerCase()}`}>{experiment.status}</span></td></tr>
            ))}</tbody>
          </table>
        </section>
        <section className="panel" aria-labelledby="system-posture-title">
          <div className="panel-heading"><h2 className="panel-title" id="system-posture-title">System posture</h2><p className="panel-note">Foundation</p></div>
          <ul className="posture-list">
            <li className="posture-row">API layer <span className="posture-status">Not connected</span></li>
            <li className="posture-row">Digital twin <span className="posture-status ready">Ready</span></li>
            <li className="posture-row">Monitoring <span className="posture-status">Not connected</span></li>
          </ul>
          <p className="placeholder-copy">Live infrastructure and experiment data will appear here when the dashboard API layer is connected.</p>
        </section>
      </div>
    </div>
  )
}