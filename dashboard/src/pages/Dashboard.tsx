import { useEffect, useState } from 'react'

import { ApiError, getExperiments } from '../api/client'
import type { Experiment } from '../types/experiment'

type SummaryCardProps = { label: string; value: number }

export function Dashboard() {
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    getExperiments()
      .then((experimentList) => {
        if (!isMounted) return
        setExperiments(experimentList)
        setErrorMessage(null)
      })
      .catch((error: unknown) => {
        if (!isMounted) return
        const message = error instanceof ApiError
          ? error.detail
          : error instanceof Error
            ? error.message
            : 'Unable to load experiments.'
        setErrorMessage(message)
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [])

  const summaryCards: SummaryCardProps[] = [
    { label: 'Total Experiments', value: experiments.length },
    { label: 'Created', value: experiments.filter((experiment) => experiment.status === 'CREATED').length },
    { label: 'Executed', value: experiments.filter((experiment) => experiment.status === 'EXECUTED').length },
    { label: 'Validated', value: experiments.filter((experiment) => experiment.status === 'VALIDATED').length },
  ]

  return (
    <div className="main-inner" id="dashboard">
      <header className="page-header">
        <div>
          <p className="eyebrow">Operations overview</p>
          <h1 className="page-title">DevOps Digital Twin</h1>
          <p className="page-subtitle">Infrastructure Simulation, What-If Analysis and Deployment Impact Prediction</p>
        </div>
        <div className="connection-state"><span className="state-dot" aria-hidden="true" />Live experiment data</div>
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
          <div className="panel-heading"><h2 className="panel-title" id="recent-experiments-title">Recent experiments</h2><p className="panel-note">Live records</p></div>
          <table className="experiment-table">
            <thead><tr><th scope="col">ID</th><th scope="col">Name</th><th scope="col">Scenario</th><th scope="col">Status</th></tr></thead>
            <tbody>
              {isLoading && <tr><td colSpan={4}>Loading experiments...</td></tr>}
              {!isLoading && errorMessage && <tr><td colSpan={4}>Unable to load experiments: {errorMessage}</td></tr>}
              {!isLoading && !errorMessage && experiments.length === 0 && <tr><td colSpan={4}>No experiments found.</td></tr>}
              {!isLoading && !errorMessage && experiments.map((experiment) => (
                <tr key={experiment.experiment_id}>
                  <td>{experiment.experiment_id}</td>
                  <td className="experiment-name">{experiment.name}</td>
                  <td className="scenario-name">{experiment.scenario_type}</td>
                  <td><span className={`status-badge ${experiment.status.toLowerCase()}`}>{experiment.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="panel" aria-labelledby="system-posture-title">
          <div className="panel-heading"><h2 className="panel-title" id="system-posture-title">System posture</h2><p className="panel-note">Foundation</p></div>
          <ul className="posture-list">
            <li className="posture-row">API layer <span className="posture-status ready">Connected</span></li>
            <li className="posture-row">Digital twin <span className="posture-status ready">Ready</span></li>
            <li className="posture-row">Monitoring <span className="posture-status">Not connected</span></li>
          </ul>
          <p className="placeholder-copy">Live infrastructure and experiment data will appear here as the dashboard expands.</p>
        </section>
      </div>
    </div>
  )
}