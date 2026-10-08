import { useEffect, useState } from 'react'

import { ApiError, getExperiment, getExecutionResult } from '../api/client'
import type { ExecutionResult, Experiment } from '../types/experiment'

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

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.detail
    : error instanceof Error
      ? error.message
      : fallback
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

function ImpactFields({ result }: { result: ExecutionResult }) {
  const impact = result.impact

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
  }, [experimentId])

  useEffect(() => {
    if (!state.experiment) return

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
  }, [experimentId, state.experiment])

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
              <dl className="details-grid result-grid"><ImpactFields result={resultState.result} /></dl>
            </section>
            <section className="result-section" aria-labelledby="prediction-result-title">
              <h3 id="prediction-result-title">Predicted resource demand</h3>
              <dl className="details-grid result-grid">
                <div><dt>Baseline request rate</dt><dd>{resultState.result.prediction.original_request_rate}</dd></div>
                <div><dt>Simulated request rate</dt><dd>{resultState.result.prediction.simulated_request_rate ?? 'Not available'}</dd></div>
                <div><dt>Workload multiplier</dt><dd>{resultState.result.prediction.workload_multiplier ?? 'Not available'}</dd></div>
                <div><dt>Projected CPU demand</dt><dd>{resultState.result.prediction.projected_cpu_demand ?? 'Not available'}</dd></div>
                <div><dt>Projected memory demand</dt><dd>{resultState.result.prediction.projected_memory_demand ?? 'Not available'}</dd></div>
                <div><dt>CPU capacity</dt><dd>{resultState.result.prediction.cpu_capacity}</dd></div>
                <div><dt>Memory capacity</dt><dd>{resultState.result.prediction.memory_capacity}</dd></div>
                <div><dt>CPU status</dt><dd>{resultState.result.prediction.cpu_status}</dd></div>
                <div><dt>Memory status</dt><dd>{resultState.result.prediction.memory_status}</dd></div>
              </dl>
            </section>
            <section className="result-section" aria-labelledby="bottleneck-result-title">
              <h3 id="bottleneck-result-title">Bottleneck</h3>
              <dl className="details-grid result-grid">
                <div><dt>Overall status</dt><dd>{resultState.result.bottleneck.overall_status}</dd></div>
                <div><dt>CPU status</dt><dd>{resultState.result.bottleneck.cpu_status}</dd></div>
                <div><dt>Memory status</dt><dd>{resultState.result.bottleneck.memory_status}</dd></div>
                <div><dt>CPU utilization</dt><dd>{resultState.result.bottleneck.cpu_utilization ?? 'Not available'}</dd></div>
                <div><dt>Memory utilization</dt><dd>{resultState.result.bottleneck.memory_utilization ?? 'Not available'}</dd></div>
                <div><dt>Healthy instances</dt><dd>{resultState.result.bottleneck.healthy_instance_count}</dd></div>
                <div><dt>Unhealthy instances</dt><dd>{resultState.result.bottleneck.unhealthy_instance_count}</dd></div>
                <div><dt>Reasons</dt><dd>{resultState.result.bottleneck.reasons.join('; ')}</dd></div>
              </dl>
            </section>
          </div>
        </section>
      )}
    </div>
  )
}
