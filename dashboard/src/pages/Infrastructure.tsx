import { useEffect, useState } from 'react'

import { ApiError, getDeploymentStatus, getInfrastructureMetrics } from '../api/client'
import type { ContainerMetric, DeploymentStatus, InfrastructureMetrics } from '../types/experiment'

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError
    ? error.detail
    : error instanceof Error
      ? error.message
      : fallback
}

function DeploymentStatusFields({ status }: { status: DeploymentStatus }) {
  return (
    <dl className="details-grid">
      <div><dt>Deployment name</dt><dd>{status.deployment_name}</dd></div>
      <div><dt>Namespace</dt><dd>{status.namespace}</dd></div>
      <div><dt>Desired replicas</dt><dd>{status.desired_replicas}</dd></div>
      <div><dt>Ready replicas</dt><dd>{status.ready_replicas}</dd></div>
      <div><dt>Available replicas</dt><dd>{status.available_replicas}</dd></div>
      <div><dt>Updated replicas</dt><dd>{status.updated_replicas}</dd></div>
    </dl>
  )
}

function formatCpu(cpuCores: number | null): string {
  if (cpuCores === null) return 'Not available'
  if (cpuCores >= 1) return `${cpuCores.toFixed(2)} cores`
  return `${(cpuCores * 1000).toFixed(2)} mCores`
}

function formatMemory(memoryBytes: number | null): string {
  if (memoryBytes === null) return 'Not available'
  const mebibytes = memoryBytes / (1024 * 1024)
  if (mebibytes >= 1024) return `${(mebibytes / 1024).toFixed(2)} GiB`
  return `${mebibytes.toFixed(2)} MiB`
}

function ContainerMetricsTable({ pods }: { pods: ContainerMetric[] }) {
  return (
    <div className="experiments-table-wrap">
      <table className="experiment-table" aria-label="Per-pod CPU and memory usage">
        <thead>
          <tr>
            <th scope="col">Pod name</th>
            <th scope="col">CPU usage</th>
            <th scope="col">Memory working set</th>
          </tr>
        </thead>
        <tbody>
          {pods.map((pod) => (
            <tr key={pod.pod_name}>
              <td className="experiment-name">{pod.pod_name}</td>
              <td>{formatCpu(pod.cpu_cores)}</td>
              <td>{formatMemory(pod.memory_bytes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Infrastructure() {
  const [deploymentStatus, setDeploymentStatus] = useState<DeploymentStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [infrastructureMetrics, setInfrastructureMetrics] = useState<InfrastructureMetrics | null>(null)
  const [isMetricsLoading, setIsMetricsLoading] = useState(true)
  const [metricsErrorMessage, setMetricsErrorMessage] = useState<string | null>(null)
  const [metricsRetryKey, setMetricsRetryKey] = useState(0)

  useEffect(() => {
    let isMounted = true

    getDeploymentStatus()
      .then((status) => {
        if (isMounted) setDeploymentStatus(status)
      })
      .catch((error: unknown) => {
        if (isMounted) {
          setDeploymentStatus(null)
          setErrorMessage(getErrorMessage(error, 'Unable to load deployment status.'))
        }
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [retryKey])

  useEffect(() => {
    let isMounted = true

    getInfrastructureMetrics()
      .then((metrics) => {
        if (isMounted) setInfrastructureMetrics(metrics)
      })
      .catch((error: unknown) => {
        if (isMounted) {
          setInfrastructureMetrics(null)
          setMetricsErrorMessage(getErrorMessage(error, 'Unable to load container metrics.'))
        }
      })
      .finally(() => {
        if (isMounted) setIsMetricsLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [metricsRetryKey])

  function retryLoading() {
    setIsLoading(true)
    setErrorMessage(null)
    setRetryKey((key) => key + 1)
  }

  function retryMetricsLoading() {
    setIsMetricsLoading(true)
    setMetricsErrorMessage(null)
    setMetricsRetryKey((key) => key + 1)
  }

  const isHealthy = deploymentStatus !== null
    && deploymentStatus.desired_replicas > 0
    && deploymentStatus.ready_replicas === deploymentStatus.desired_replicas
    && deploymentStatus.available_replicas === deploymentStatus.desired_replicas

  return (
    <div className="main-inner">
      <header className="page-header">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1 className="page-title">Infrastructure</h1>
          <p className="page-subtitle">Current deployment telemetry for the Digital Twin environment.</p>
        </div>
      </header>
      <section className="panel details-panel" aria-labelledby="infrastructure-title">
        <div className="panel-heading">
          <h2 className="panel-title" id="infrastructure-title">Deployment status</h2>
          <p className="panel-note">Kubernetes</p>
        </div>
        {isLoading && <p className="empty-state">Loading deployment status...</p>}
        {!isLoading && errorMessage && (
          <div className="details-state">
            <p className="result-note error-message">Unable to load deployment status: {errorMessage}</p>
            <button className="action-button secondary-action" type="button" onClick={retryLoading}>
              Retry
            </button>
          </div>
        )}
        {!isLoading && !errorMessage && deploymentStatus && (
          <>
            <div className="posture-list">
              <div className="posture-row">
                <span>Deployment health</span>
                <span className={`status-badge ${isHealthy ? 'executed' : ''}`}>
                  {isHealthy ? 'Healthy' : 'Degraded'}
                </span>
              </div>
            </div>
            <DeploymentStatusFields status={deploymentStatus} />
          </>
        )}
      </section>
      <section className="panel details-panel" aria-labelledby="container-metrics-title">
        <div className="panel-heading">
          <h2 className="panel-title" id="container-metrics-title">Container Resource Usage</h2>
          <p className="panel-note">Prometheus</p>
        </div>
        <p className="placeholder-copy">
          CPU is shown as a five-minute usage rate. Memory is the container working-set measurement.
        </p>
        {isMetricsLoading && <p className="empty-state">Loading container metrics...</p>}
        {!isMetricsLoading && metricsErrorMessage && (
          <div className="details-state">
            <p className="result-note error-message">Unable to load container metrics: {metricsErrorMessage}</p>
            <button className="action-button secondary-action" type="button" onClick={retryMetricsLoading}>
              Retry
            </button>
          </div>
        )}
        {!isMetricsLoading && !metricsErrorMessage && infrastructureMetrics?.pods.length === 0 && (
          <p className="empty-state">No container metrics are currently available.</p>
        )}
        {!isMetricsLoading && !metricsErrorMessage && infrastructureMetrics && infrastructureMetrics.pods.length > 0 && (
          <ContainerMetricsTable pods={infrastructureMetrics.pods} />
        )}
      </section>
    </div>
  )
}