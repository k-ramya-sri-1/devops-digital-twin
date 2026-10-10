import { useEffect, useState } from 'react'

import {
  ApiError,
  executeExperiment,
  getDeploymentImpact,
  getExperiment,
  getExecutionResult,
  getRecommendations,
  validateExperiment,
} from '../api/client'
import type {
  ActualKubernetesResult,
  BottleneckResult,
  DeploymentImpactReport,
  ExecutionResult,
  Experiment,
  ImpactResult,
  RecommendationReport,
  ResourcePredictionResult,
} from '../types/experiment'

type ExperimentDetailsProps = { experimentId: string }

type LoadState = {
  experiment: Experiment | null
  isLoading: boolean
  errorMessage: string | null
  isNotFound: boolean
}

type ResultLoadState = {
  result: ExecutionResult | null
  isLoading: boolean
  errorMessage: string | null
  isNotFound: boolean
}

type ImpactLoadState = {
  report: DeploymentImpactReport | null
  isLoading: boolean
  errorMessage: string | null
  isNotFound: boolean
}

type RecommendationLoadState = {
  report: RecommendationReport | null
  isLoading: boolean
  errorMessage: string | null
  isNotFound: boolean
}

type ActionType = 'execute' | 'validate'

type ActionState = {
  active: ActionType | null
  message: string | null
  errorMessage: string | null
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.detail
    : error instanceof Error
      ? error.message
      : fallback
}

function ActualResultFields({ actualResult }: { actualResult: ActualKubernetesResult }) {
  return <dl className="details-grid result-grid">
    <div><dt>Experiment ID</dt><dd>{actualResult.experiment_id}</dd></div>
    <div><dt>Deployment</dt><dd>{actualResult.deployment_name}</dd></div>
    <div><dt>Namespace</dt><dd>{actualResult.namespace}</dd></div>
    <div><dt>Desired replicas</dt><dd>{actualResult.desired_replicas}</dd></div>
    <div><dt>Ready replicas</dt><dd>{actualResult.ready_replicas}</dd></div>
    <div><dt>Available replicas</dt><dd>{actualResult.available_replicas}</dd></div>
    <div><dt>Updated replicas</dt><dd>{actualResult.updated_replicas}</dd></div>
  </dl>
}

function PredictionFields({ prediction }: { prediction: ResourcePredictionResult }) {
  return <dl className="details-grid result-grid">
    <div><dt>Baseline request rate</dt><dd>{prediction.original_request_rate}</dd></div>
    <div><dt>Simulated request rate</dt><dd>{prediction.simulated_request_rate ?? 'Not available'}</dd></div>
    <div><dt>Workload multiplier</dt><dd>{prediction.workload_multiplier ?? 'Not available'}</dd></div>
    <div><dt>Projected CPU demand</dt><dd>{prediction.projected_cpu_demand ?? 'Not available'}</dd></div>
    <div><dt>Projected memory demand</dt><dd>{prediction.projected_memory_demand ?? 'Not available'}</dd></div>
    <div><dt>CPU capacity</dt><dd>{prediction.cpu_capacity}</dd></div>
    <div><dt>Memory capacity</dt><dd>{prediction.memory_capacity}</dd></div>
    <div><dt>CPU status</dt><dd>{prediction.cpu_status}</dd></div>
    <div><dt>Memory status</dt><dd>{prediction.memory_status}</dd></div>
  </dl>
}

function BottleneckFields({ bottleneck }: { bottleneck: BottleneckResult }) {
  return <dl className="details-grid result-grid">
    <div><dt>Overall status</dt><dd>{bottleneck.overall_status}</dd></div>
    <div><dt>CPU status</dt><dd>{bottleneck.cpu_status}</dd></div>
    <div><dt>Memory status</dt><dd>{bottleneck.memory_status}</dd></div>
    <div><dt>CPU utilization</dt><dd>{bottleneck.cpu_utilization ?? 'Not available'}</dd></div>
    <div><dt>Memory utilization</dt><dd>{bottleneck.memory_utilization ?? 'Not available'}</dd></div>
    <div><dt>Healthy instances</dt><dd>{bottleneck.healthy_instance_count}</dd></div>
    <div><dt>Unhealthy instances</dt><dd>{bottleneck.unhealthy_instance_count}</dd></div>
    <div><dt>Reasons</dt><dd>{bottleneck.reasons.join('; ')}</dd></div>
  </dl>
}

function SimulationFields({ result }: { result: ExecutionResult }) {
  const simulation = result.simulation

  if ('multiplier' in simulation) {
    return <>
      <div><dt>Scenario</dt><dd>TRAFFIC_SURGE</dd></div>
      <div><dt>Multiplier</dt><dd>{simulation.multiplier}</dd></div>
      <div><dt>Original request rate</dt><dd>{simulation.original_request_rate}</dd></div>
      <div><dt>Simulated request rate</dt><dd>{simulation.simulated_request_rate}</dd></div>
    </>
  }

  if ('instance_name' in simulation) {
    return <>
      <div><dt>Scenario</dt><dd>INSTANCE_FAILURE</dd></div>
      <div><dt>Instance name</dt><dd>{simulation.instance_name}</dd></div>
      <div><dt>Healthy instances</dt><dd>{simulation.healthy_instance_count}</dd></div>
      <div><dt>Unhealthy instances</dt><dd>{simulation.unhealthy_instance_count}</dd></div>
      <div><dt>Remaining CPU capacity</dt><dd>{simulation.remaining_cpu_capacity}</dd></div>
      <div><dt>Remaining memory capacity</dt><dd>{simulation.remaining_memory_capacity}</dd></div>
    </>
  }

  return <>
    <div><dt>Scenario</dt><dd>SCALE_OUT</dd></div>
    <div><dt>Additional instances</dt><dd>{simulation.additional_instances}</dd></div>
    <div><dt>Simulated instance count</dt><dd>{simulation.simulated_instance_count}</dd></div>
    <div><dt>Total CPU capacity</dt><dd>{simulation.total_cpu_capacity}</dd></div>
    <div><dt>Total memory capacity</dt><dd>{simulation.total_memory_capacity}</dd></div>
  </>
}

function ImpactFields({ impact }: { impact: ImpactResult }) {

  if ('percentage_change' in impact) {
    return <>
      <div><dt>Original request rate</dt><dd>{impact.original_request_rate}</dd></div>
      <div><dt>Simulated request rate</dt><dd>{impact.simulated_request_rate}</dd></div>
      <div><dt>Absolute change</dt><dd>{impact.absolute_change}</dd></div>
      <div><dt>Percentage change</dt><dd>{impact.percentage_change}%</dd></div>
    </>
  }

  if ('healthy_instance_change' in impact) {
    return <>
      <div><dt>Original instances</dt><dd>{impact.original_instance_count}</dd></div>
      <div><dt>Simulated instances</dt><dd>{impact.simulated_instance_count}</dd></div>
      <div><dt>Healthy instance change</dt><dd>{impact.healthy_instance_change}</dd></div>
      <div><dt>Capacity CPU change</dt><dd>{impact.capacity_change.cpu}</dd></div>
      <div><dt>Capacity memory change</dt><dd>{impact.capacity_change.memory}</dd></div>
    </>
  }

  return <>
    <div><dt>Original instances</dt><dd>{impact.original_instance_count}</dd></div>
    <div><dt>Simulated instances</dt><dd>{impact.simulated_instance_count}</dd></div>
    <div><dt>Instance count change</dt><dd>{impact.instance_count_change}</dd></div>
    <div><dt>Capacity CPU change</dt><dd>{impact.capacity_change.cpu}</dd></div>
    <div><dt>Capacity memory change</dt><dd>{impact.capacity_change.memory}</dd></div>
  </>
}

export function ExperimentDetails({ experimentId }: ExperimentDetailsProps) {
  const [state, setState] = useState<LoadState>({
    experiment: null,
    isLoading: true,
    errorMessage: null,
    isNotFound: false,
  })
  const [resultState, setResultState] = useState<ResultLoadState>({
    result: null,
    isLoading: true,
    errorMessage: null,
    isNotFound: false,
  })
  const [impactState, setImpactState] = useState<ImpactLoadState>({
    report: null,
    isLoading: true,
    errorMessage: null,
    isNotFound: false,
  })
  const [recommendationState, setRecommendationState] = useState<RecommendationLoadState>({
    report: null,
    isLoading: true,
    errorMessage: null,
    isNotFound: false,
  })
  const [serviceName, setServiceName] = useState('devops-digital-twin')
  const [refreshKey, setRefreshKey] = useState(0)
  const [actionState, setActionState] = useState<ActionState>({
    active: null,
    message: null,
    errorMessage: null,
  })

  const loadedExperimentId = state.experiment?.experiment_id

  const refreshAfterAction = () => {
    setState((currentState) => ({
      ...currentState,
      isLoading: true,
      errorMessage: null,
      isNotFound: false,
    }))
    setResultState((currentState) => ({
      ...currentState,
      isLoading: true,
      errorMessage: null,
      isNotFound: false,
    }))
    setImpactState((currentState) => ({
      ...currentState,
      isLoading: true,
      errorMessage: null,
      isNotFound: false,
    }))
    setRecommendationState((currentState) => ({
      ...currentState,
      isLoading: true,
      errorMessage: null,
      isNotFound: false,
    }))
    setRefreshKey((currentKey) => currentKey + 1)
  }

  const handleExecute = async () => {
    if (!state.experiment || state.experiment.status !== 'CREATED' || actionState.active) return
    const selectedServiceName = serviceName.trim()
    if (!selectedServiceName) {
      setActionState({ active: null, message: null, errorMessage: 'Service name is required to execute an experiment.' })
      return
    }

    setActionState({ active: 'execute', message: null, errorMessage: null })
    try {
      await executeExperiment(experimentId, { service_name: selectedServiceName })
      setActionState({ active: null, message: 'Experiment execution completed.', errorMessage: null })
      refreshAfterAction()
    } catch (error: unknown) {
      setActionState({ active: null, message: null, errorMessage: getErrorMessage(error, 'Unable to execute the experiment.') })
    }
  }

  const handleValidate = async () => {
    if (!state.experiment || state.experiment.status !== 'EXECUTED' || actionState.active) return

    setActionState({ active: 'validate', message: null, errorMessage: null })
    try {
      await validateExperiment(experimentId)
      setActionState({ active: null, message: 'Experiment validation completed.', errorMessage: null })
      refreshAfterAction()
    } catch (error: unknown) {
      setActionState({ active: null, message: null, errorMessage: getErrorMessage(error, 'Unable to validate the experiment.') })
    }
  }

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
        const errorMessage = getErrorMessage(error, 'Unable to load this experiment.')
        setState({ experiment: null, isLoading: false, errorMessage, isNotFound })
      })

    return () => {
      isMounted = false
    }
  }, [experimentId, refreshKey])

  useEffect(() => {
    if (!loadedExperimentId) return

    let isMounted = true

    getExecutionResult(experimentId)
      .then((result) => {
        if (!isMounted) return
        setResultState({ result, isLoading: false, errorMessage: null, isNotFound: false })
      })
      .catch((error: unknown) => {
        if (!isMounted) return
        const isNotFound = error instanceof ApiError && error.status === 404
        const errorMessage = getErrorMessage(error, 'Unable to load the execution result.')
        setResultState({ result: null, isLoading: false, errorMessage, isNotFound })
      })

    return () => {
      isMounted = false
    }
  }, [experimentId, loadedExperimentId, refreshKey])

  useEffect(() => {
    if (!loadedExperimentId) return

    let isMounted = true

    getRecommendations(experimentId)
      .then((report) => {
        if (!isMounted) return
        setRecommendationState({ report, isLoading: false, errorMessage: null, isNotFound: false })
      })
      .catch((error: unknown) => {
        if (!isMounted) return
        const isNotFound = error instanceof ApiError && (error.status === 404 || error.status === 409)
        const errorMessage = getErrorMessage(error, 'Unable to load recommendations.')
        setRecommendationState({ report: null, isLoading: false, errorMessage, isNotFound })
      })

    return () => {
      isMounted = false
    }
  }, [experimentId, loadedExperimentId, refreshKey])

  useEffect(() => {
    if (!loadedExperimentId) return

    let isMounted = true

    getDeploymentImpact(experimentId)
      .then((report) => {
        if (!isMounted) return
        setImpactState({ report, isLoading: false, errorMessage: null, isNotFound: false })
      })
      .catch((error: unknown) => {
        if (!isMounted) return
        const isNotFound = error instanceof ApiError && (error.status === 404 || error.status === 409)
        const errorMessage = getErrorMessage(error, 'Unable to load the deployment impact report.')
        setImpactState({ report: null, isLoading: false, errorMessage, isNotFound })
      })

    return () => {
      isMounted = false
    }
  }, [experimentId, loadedExperimentId, refreshKey])

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
      {!state.isLoading && state.experiment && (
        <section className="panel action-panel" aria-labelledby="experiment-actions-title">
          <div className="panel-heading">
            <h2 className="panel-title" id="experiment-actions-title">Experiment Actions</h2>
            <p className="panel-note">Current status: <strong>{state.experiment.status}</strong></p>
          </div>
          <div className="action-content">
            <label className="service-field">
              <span>Service name</span>
              <input
                value={serviceName}
                onChange={(event) => setServiceName(event.target.value)}
                disabled={actionState.active !== null}
                aria-describedby="service-name-help"
              />
              <small id="service-name-help">Required for execution.</small>
            </label>
            <div className="action-buttons">
              <button
                className="action-button primary-action"
                type="button"
                onClick={handleExecute}
                disabled={state.experiment.status !== 'CREATED' || actionState.active !== null}
              >
                {actionState.active === 'execute' ? 'Executing...' : 'Execute'}
              </button>
              <button
                className="action-button secondary-action"
                type="button"
                onClick={handleValidate}
                disabled={state.experiment.status !== 'EXECUTED' || actionState.active !== null}
              >
                {actionState.active === 'validate' ? 'Validating...' : 'Validate'}
              </button>
            </div>
            {actionState.message && <p className="action-message success-message" role="status">{actionState.message}</p>}
            {actionState.errorMessage && <p className="action-message error-message" role="alert">{actionState.errorMessage}</p>}
          </div>
        </section>
      )}
      {!state.isLoading && state.experiment && resultState.isLoading && (
        <section className="panel details-state result-state" aria-live="polite">
          Loading execution result...
        </section>
      )}
      {!state.isLoading && state.experiment && !resultState.isLoading && resultState.isNotFound && (
        <section className="panel details-state result-state" aria-live="polite">
          <h2 className="panel-title">Execution result not yet available</h2>
          <p className="placeholder-copy">{resultState.errorMessage}</p>
        </section>
      )}
      {!state.isLoading && state.experiment && !resultState.isLoading && !resultState.isNotFound && resultState.errorMessage && (
        <section className="panel details-state result-state" aria-live="polite">
          <h2 className="panel-title">Unable to load execution result</h2>
          <p className="placeholder-copy">{resultState.errorMessage}</p>
        </section>
      )}
      {!state.isLoading && state.experiment && resultState.result && (
        <section className="panel execution-panel" aria-labelledby="execution-result-title">
          <div className="panel-heading">
            <h2 className="panel-title" id="execution-result-title">Execution Result</h2>
            <span className="panel-note">{resultState.result.scenario_type}</span>
          </div>
          <dl className="details-grid result-grid">
            <div><dt>Experiment ID</dt><dd>{resultState.result.experiment_id}</dd></div>
            <div><dt>Scenario type</dt><dd>{resultState.result.scenario_type}</dd></div>
            <div><dt>Service name</dt><dd>{resultState.result.service_name}</dd></div>
          </dl>
          <div className="result-sections">
            <section className="result-section" aria-labelledby="simulation-result-title">
              <h3 id="simulation-result-title">Simulation</h3>
              <dl className="details-grid result-grid"><SimulationFields result={resultState.result} /></dl>
            </section>
            <section className="result-section" aria-labelledby="impact-result-title">
              <h3 id="impact-result-title">Impact</h3>
              <dl className="details-grid result-grid"><ImpactFields impact={resultState.result.impact} /></dl>
            </section>
            <section className="result-section" aria-labelledby="prediction-result-title">
              <h3 id="prediction-result-title">Predicted resource demand</h3>
              <PredictionFields prediction={resultState.result.prediction} />
            </section>
            <section className="result-section" aria-labelledby="bottleneck-result-title">
              <h3 id="bottleneck-result-title">Bottleneck</h3>
              <BottleneckFields bottleneck={resultState.result.bottleneck} />
            </section>
          </div>
        </section>
      )}
      {!state.isLoading && state.experiment && impactState.isLoading && (
        <section className="panel details-state impact-state" aria-live="polite">
          Loading deployment impact...
        </section>
      )}
      {!state.isLoading && state.experiment && !impactState.isLoading && impactState.isNotFound && (
        <section className="panel details-state impact-state" aria-live="polite">
          <h2 className="panel-title">Deployment impact not yet available</h2>
          <p className="placeholder-copy">{impactState.errorMessage}</p>
        </section>
      )}
      {!state.isLoading && state.experiment && !impactState.isLoading && !impactState.isNotFound && impactState.errorMessage && (
        <section className="panel details-state impact-state" aria-live="polite">
          <h2 className="panel-title">Unable to load deployment impact</h2>
          <p className="placeholder-copy">{impactState.errorMessage}</p>
        </section>
      )}
      {!state.isLoading && state.experiment && impactState.report && (
        <section className="panel execution-panel impact-panel" aria-labelledby="deployment-impact-title">
          <div className="panel-heading">
            <h2 className="panel-title" id="deployment-impact-title">Deployment Impact</h2>
            <span className={`status-badge severity-${impactState.report.overall_severity.toLowerCase()}`}>
              {impactState.report.overall_severity}
            </span>
          </div>
          <dl className="details-grid result-grid">
            <div><dt>Experiment ID</dt><dd>{impactState.report.experiment_id}</dd></div>
            <div><dt>Scenario type</dt><dd>{impactState.report.scenario_type}</dd></div>
            <div><dt>Service name</dt><dd>{impactState.report.service_name}</dd></div>
            <div><dt>Overall severity</dt><dd>{impactState.report.overall_severity}</dd></div>
          </dl>
          <div className="result-sections">
            <section className="result-section" aria-labelledby="impact-simulated-title">
              <h3 id="impact-simulated-title">Simulated impact</h3>
              <dl className="details-grid result-grid"><ImpactFields impact={impactState.report.simulated_impact} /></dl>
            </section>
            <section className="result-section" aria-labelledby="impact-predicted-title">
              <h3 id="impact-predicted-title">Predicted demand</h3>
              <PredictionFields prediction={impactState.report.predicted_demand} />
            </section>
            <section className="result-section" aria-labelledby="impact-bottleneck-title">
              <h3 id="impact-bottleneck-title">Bottleneck</h3>
              <BottleneckFields bottleneck={impactState.report.bottleneck} />
            </section>
            <section className="result-section" aria-labelledby="impact-actual-title">
              <h3 id="impact-actual-title">Actual result</h3>
              {impactState.report.actual_result
                ? <ActualResultFields actualResult={impactState.report.actual_result} />
                : <p className="result-note">Not available before validation.</p>}
            </section>
            <section className="result-section" aria-labelledby="impact-accuracy-title">
              <h3 id="impact-accuracy-title">Prediction accuracy</h3>
              {impactState.report.prediction_accuracy
                ? <>
                  <p className="result-note">Overall status: {impactState.report.prediction_accuracy.overall_status}</p>
                  <ul className="result-list">
                    {impactState.report.prediction_accuracy.comparisons.map((comparison) => (
                      <li key={comparison.metric_name}>
                        <strong>{comparison.metric_name}</strong>: {comparison.status}
                        {' '}(expected {String(comparison.expected)}, actual {String(comparison.actual)})
                      </li>
                    ))}
                  </ul>
                </>
                : <p className="result-note">Not available before validation.</p>}
            </section>
            <section className="result-section" aria-labelledby="impact-limitations-title">
              <h3 id="impact-limitations-title">Limitations</h3>
              {impactState.report.limitations.length > 0
                ? <ul className="result-list">
                  {impactState.report.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
                </ul>
                : <p className="result-note">None reported.</p>}
            </section>
          </div>
        </section>
      )}
      {!state.isLoading && state.experiment && recommendationState.isLoading && (
        <section className="panel details-state recommendation-state" aria-live="polite">
          Loading recommendations...
        </section>
      )}
      {!state.isLoading && state.experiment && !recommendationState.isLoading && recommendationState.isNotFound && (
        <section className="panel details-state recommendation-state" aria-live="polite">
          <h2 className="panel-title">Recommendations not yet available</h2>
          <p className="placeholder-copy">{recommendationState.errorMessage}</p>
        </section>
      )}
      {!state.isLoading && state.experiment && !recommendationState.isLoading && !recommendationState.isNotFound && recommendationState.errorMessage && (
        <section className="panel details-state recommendation-state" aria-live="polite">
          <h2 className="panel-title">Unable to load recommendations</h2>
          <p className="placeholder-copy">{recommendationState.errorMessage}</p>
        </section>
      )}
      {!state.isLoading && state.experiment && recommendationState.report && (
        <section className="panel execution-panel recommendation-panel" aria-labelledby="recommendations-title">
          <div className="panel-heading">
            <h2 className="panel-title" id="recommendations-title">Recommendations</h2>
            <span className="panel-note">{recommendationState.report.overall_priority}</span>
          </div>
          {recommendationState.report.recommendations.length === 0
            ? <p className="result-note recommendation-empty">No recommendations reported.</p>
            : <div className="recommendation-list">
              {recommendationState.report.recommendations.map((recommendation) => (
                <article className="recommendation-item" key={`${recommendation.action}-${recommendation.priority}-${recommendation.reason}`}>
                  <div className="recommendation-heading">
                    <h3>{recommendation.action}</h3>
                    <span className={`status-badge priority-${recommendation.priority.toLowerCase()}`}>
                      {recommendation.priority}
                    </span>
                  </div>
                  <p className="recommendation-reason">{recommendation.reason}</p>
                  <dl className="recommendation-meta">
                    <div><dt>Experiment ID</dt><dd>{recommendation.experiment_id}</dd></div>
                    <div><dt>Evidence</dt><dd>{recommendation.evidence.join('; ')}</dd></div>
                  </dl>
                </article>
              ))}
            </div>}
          {recommendationState.report.limitations.length > 0 && (
            <div className="recommendation-limitations">
              <h3>Limitations</h3>
              <ul className="result-list">
                {recommendationState.report.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
