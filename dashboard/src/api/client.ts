import type {
  ActualKubernetesResult,
  DeploymentImpactReport,
  ExecuteExperimentRequest,
  ExecutionResult,
  Experiment,
  ExperimentCreateRequest,
  RecommendationReport,
  ValidationResult,
} from '../types/experiment'

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined
export const API_BASE_URL = (configuredBaseUrl?.trim() || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const payload: unknown = await response.json()
    if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
      const detail = payload.detail
      if (typeof detail === 'string') return detail
    }
  } catch {
    // Use the status text when the server does not return JSON.
  }
  return response.statusText || `API request failed with status ${response.status}`
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response))
  }
  return response.json() as Promise<T>
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) })
}

export function getExperiments(): Promise<Experiment[]> {
  return request<Experiment[]>('/experiments')
}

export function getExperiment(experimentId: string): Promise<Experiment> {
  return request<Experiment>(`/experiments/${encodeURIComponent(experimentId)}`)
}

export function getExecutionResult(experimentId: string): Promise<ExecutionResult> {
  return request<ExecutionResult>(`/experiments/${encodeURIComponent(experimentId)}/result`)
}

export function getDeploymentImpact(experimentId: string): Promise<DeploymentImpactReport> {
  return request<DeploymentImpactReport>(`/experiments/${encodeURIComponent(experimentId)}/impact`)
}

export function getRecommendations(experimentId: string): Promise<RecommendationReport> {
  return request<RecommendationReport>(`/experiments/${encodeURIComponent(experimentId)}/recommendations`)
}

export function createExperiment(payload: ExperimentCreateRequest): Promise<Experiment> {
  return postJson<Experiment>('/experiments', payload)
}

export function executeExperiment(
  experimentId: string,
  payload: ExecuteExperimentRequest,
): Promise<ExecutionResult> {
  return postJson<ExecutionResult>(
    `/experiments/${encodeURIComponent(experimentId)}/execute`,
    payload,
  )
}

export function validateExperiment(experimentId: string): Promise<ValidationResult> {
  return postJson<ValidationResult>(
    `/experiments/${encodeURIComponent(experimentId)}/validate`,
    {},
  )
}

export type { ActualKubernetesResult }