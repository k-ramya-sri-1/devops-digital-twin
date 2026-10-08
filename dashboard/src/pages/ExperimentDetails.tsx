import { useEffect, useState } from 'react'

import { ApiError, getExperiment } from '../api/client'
import type { Experiment } from '../types/experiment'

type ExperimentDetailsProps = { experimentId: string }

type LoadState = {
  experiment: Experiment | null
  isLoading: boolean
  errorMessage: string | null
  isNotFound: boolean
}

export function ExperimentDetails({ experimentId }: ExperimentDetailsProps) {
  const [state, setState] = useState<LoadState>({
    experiment: null,
    isLoading: true,
    errorMessage: null,
    isNotFound: false,
  })

  useEffect(() => {
    let isMounted = true

    getExperiment(experimentId)
      .then((experiment) => {
        if (!isMounted) return
        setState({ experiment, isLoading: false, errorMessage: null, isNotFound: false })
      })
      .catch((error: unknown) => {
        if (!isMounted) return
        const isNotFound = error instanceof ApiError && error.status === 404
        const errorMessage = error instanceof ApiError
          ? error.detail
          : error instanceof Error
            ? error.message
            : 'Unable to load this experiment.'
        setState({ experiment: null, isLoading: false, errorMessage, isNotFound })
      })

    return () => {
      isMounted = false
    }
  }, [experimentId])

  return (
    <div className="main-inner" id="experiment-details">
      <a className="back-link" href="#dashboard">Back to dashboard</a>
      <header className="page-header details-header">
        <div>
          <p className="eyebrow">Experiment details</p>
          <h1 className="page-title">{experimentId}</h1>
          <p className="page-subtitle">Metadata for the selected Digital Twin experiment.</p>
        </div>
      </header>
      {state.isLoading && <section className="panel details-state" aria-live="polite">Loading experiment...</section>}
      {!state.isLoading && state.isNotFound && (
        <section className="panel details-state" aria-live="polite">
          <h2 className="panel-title">Experiment not found</h2>
          <p className="placeholder-copy">{state.errorMessage}</p>
        </section>
      )}
      {!state.isLoading && !state.isNotFound && state.errorMessage && (
        <section className="panel details-state" aria-live="polite">
          <h2 className="panel-title">Unable to load experiment</h2>
          <p className="placeholder-copy">{state.errorMessage}</p>
        </section>
      )}
      {!state.isLoading && state.experiment && (
        <section className="panel details-panel" aria-labelledby="experiment-metadata-title">
          <div className="panel-heading">
            <h2 className="panel-title" id="experiment-metadata-title">Experiment metadata</h2>
            <span className={`status-badge ${state.experiment.status.toLowerCase()}`}>{state.experiment.status}</span>
          </div>
          <dl className="details-grid">
            <div><dt>Experiment ID</dt><dd>{state.experiment.experiment_id}</dd></div>
            <div><dt>Name</dt><dd>{state.experiment.name}</dd></div>
            <div><dt>Scenario type</dt><dd>{state.experiment.scenario_type}</dd></div>
            <div><dt>Status</dt><dd>{state.experiment.status}</dd></div>
            <div><dt>Traffic multiplier</dt><dd>{state.experiment.scenario_parameters.multiplier ?? 'Not provided'}</dd></div>
            <div><dt>Instance name</dt><dd>{state.experiment.scenario_parameters.instance_name ?? 'Not provided'}</dd></div>
            <div><dt>Additional instances</dt><dd>{state.experiment.scenario_parameters.additional_instances ?? 'Not provided'}</dd></div>
          </dl>
        </section>
      )}
    </div>
  )
}
