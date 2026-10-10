import { useEffect, useState } from 'react'

import { ApiError, getDeploymentImpact, getExecutionResult, getExperiments } from '../api/client'
import type { DeploymentImpactReport, ExecutionResult, Experiment } from '../types/experiment'

type ExperimentResult = {
  experiment: Experiment
  execution: ExecutionResult | null
  impact: DeploymentImpactReport | null
  errorMessage: string | null
}

type ResultsState = {
  rows: ExperimentResult[]
  isLoading: boolean
  errorMessage: string | null
}

function getErrorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.detail
    : error instanceof Error
      ? error.message
      : 'Unable to load experiment results.'
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return 'Not available'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return 'Not available'
  }
}

async function loadExperimentResult(experiment: Experiment): Promise<ExperimentResult> {
  const [executionResponse, impactResponse] = await Promise.allSettled([
    getExecutionResult(experiment.experiment_id),
    getDeploymentImpact(experiment.experiment_id),
  ])

  const execution = executionResponse.status === 'fulfilled' ? executionResponse.value : null
  const impact = impactResponse.status === 'fulfilled' ? impactResponse.value : null
  const errors = [executionResponse, impactResponse]
    .filter((response): response is PromiseRejectedResult => response.status === 'rejected')
    .filter((response) => !(response.reason instanceof ApiError && response.reason.status === 404))
    .map((response) => getErrorMessage(response.reason))

  return {
    experiment,
    execution,
    impact,
    errorMessage: errors.length > 0 ? errors.join(' ') : null,
  }
}

function ResultSummary({ row }: { row: ExperimentResult }) {
  if (row.errorMessage) return <p className="result-note error-message">{row.errorMessage}</p>
  if (!row.execution && !row.impact) return <p className="result-note">No persisted result is available.</p>

  return (
    <div className="result-summary">
      {row.execution && (
        <dl className="result-summary-grid">
          <div><dt>Service</dt><dd>{row.execution.service_name}</dd></div>
          <div><dt>CPU status</dt><dd>{row.execution.prediction.cpu_status}</dd></div>
          <div><dt>Memory status</dt><dd>{row.execution.prediction.memory_status}</dd></div>
          <div><dt>Bottleneck</dt><dd>{row.execution.bottleneck.overall_status}</dd></div>
        </dl>
      )}
      {row.impact?.prediction_accuracy && (
        <div className="comparison-summary">
          <p className="result-note">
            Prediction comparison: <strong>{row.impact.prediction_accuracy.overall_status}</strong>
          </p>
          <dl className="comparison-list">
            {row.impact.prediction_accuracy.comparisons.map((comparison) => (
              <div key={comparison.metric_name}>
                <dt>{comparison.metric_name} ({comparison.status})</dt>
                <dd>Expected: {formatValue(comparison.expected)}; Actual: {formatValue(comparison.actual)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      {row.impact && !row.impact.prediction_accuracy && (
        <p className="result-note">Prediction comparison is not available for this result.</p>
      )}
    </div>
  )
}

export function Results() {
  const [state, setState] = useState<ResultsState>({ rows: [], isLoading: true, errorMessage: null })

  useEffect(() => {
    let isMounted = true

    getExperiments()
      .then(async (experiments) => {
        const eligibleExperiments = experiments.filter(
          (experiment) => experiment.status === 'EXECUTED' || experiment.status === 'VALIDATED',
        )
        const rows = await Promise.all(eligibleExperiments.map(loadExperimentResult))
        if (isMounted) setState({ rows, isLoading: false, errorMessage: null })
      })
      .catch((error: unknown) => {
        if (isMounted) setState({ rows: [], isLoading: false, errorMessage: getErrorMessage(error) })
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
          <h1 className="page-title">Results</h1>
          <p className="page-subtitle">Execution and prediction comparison results from persisted experiments.</p>
        </div>
      </header>
      <section className="panel results-panel" aria-labelledby="results-title">
        <div className="panel-heading">
          <h2 className="panel-title" id="results-title">Experiment results</h2>
          <p className="panel-note">Executed and validated</p>
        </div>
        {state.isLoading && <p className="empty-state">Loading experiment results...</p>}
        {!state.isLoading && state.errorMessage && <p className="empty-state">Unable to load results: {state.errorMessage}</p>}
        {!state.isLoading && !state.errorMessage && state.rows.length === 0 && <p className="empty-state">No executed or validated experiments found.</p>}
        {!state.isLoading && !state.errorMessage && state.rows.length > 0 && (
          <div className="results-list">
            {state.rows.map((row) => (
              <article className="result-card" key={row.experiment.experiment_id}>
                <div className="result-card-heading">
                  <div>
                    <h3><a className="experiment-link" href={`#experiment/${encodeURIComponent(row.experiment.experiment_id)}`}>{row.experiment.name}</a></h3>
                    <p className="result-card-meta">
                      <a className="experiment-link" href={`#experiment/${encodeURIComponent(row.experiment.experiment_id)}`}>{row.experiment.experiment_id}</a>
                      <span>{row.experiment.scenario_type}</span>
                    </p>
                  </div>
                  <span className={`status-badge ${row.experiment.status.toLowerCase()}`}>{row.experiment.status}</span>
                </div>
                <ResultSummary row={row} />
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}