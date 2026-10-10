import { useEffect, useState } from 'react'

import { ApiError, getExperiments } from '../api/client'
import type { Experiment } from '../types/experiment'

function getErrorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.detail
    : error instanceof Error
      ? error.message
      : 'Unable to load experiments.'
}

function formatCreationTime(experiment: Experiment): string {
  if (!experiment.created_at) return 'Not available'
  const timestamp = new Date(experiment.created_at)
  return Number.isNaN(timestamp.getTime()) ? experiment.created_at : timestamp.toLocaleString()
}

export function Experiments() {
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
        if (isMounted) setErrorMessage(getErrorMessage(error))
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [])

  return (
    <div className="main-inner">
      <header className="page-header">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1 className="page-title">Experiments</h1>
          <p className="page-subtitle">Browse the experiment records available from the Digital Twin API.</p>
        </div>
      </header>
      <section className="panel experiments-panel" aria-labelledby="experiments-title">
        <div className="panel-heading">
          <h2 className="panel-title" id="experiments-title">All experiments</h2>
          <p className="panel-note">Backend records</p>
        </div>
        {isLoading && <p className="empty-state">Loading experiments...</p>}
        {!isLoading && errorMessage && <p className="empty-state">Unable to load experiments: {errorMessage}</p>}
        {!isLoading && !errorMessage && experiments.length === 0 && <p className="empty-state">No experiments found.</p>}
        {!isLoading && !errorMessage && experiments.length > 0 && (
          <div className="experiments-table-wrap">
            <table className="experiment-table">
              <thead>
                <tr>
                  <th scope="col">Experiment ID</th>
                  <th scope="col">Name</th>
                  <th scope="col">Scenario type</th>
                  <th scope="col">Status</th>
                  <th scope="col">Creation time</th>
                </tr>
              </thead>
              <tbody>
                {experiments.map((experiment) => (
                  <tr key={experiment.experiment_id}>
                    <td><a className="experiment-link" href={`#experiment/${encodeURIComponent(experiment.experiment_id)}`}>{experiment.experiment_id}</a></td>
                    <td className="experiment-name"><a className="experiment-link" href={`#experiment/${encodeURIComponent(experiment.experiment_id)}`}>{experiment.name}</a></td>
                    <td className="scenario-name">{experiment.scenario_type}</td>
                    <td><span className={`status-badge ${experiment.status.toLowerCase()}`}>{experiment.status}</span></td>
                    <td>{formatCreationTime(experiment)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}