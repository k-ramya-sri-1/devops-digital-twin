export type ScenarioType = 'TRAFFIC_SURGE' | 'INSTANCE_FAILURE' | 'SCALE_OUT'
export type ExperimentStatus = 'CREATED' | 'SIMULATED' | 'EXECUTED' | 'VALIDATED'
export type ResourceStatus = 'SUFFICIENT' | 'INSUFFICIENT' | 'INSUFFICIENT_DATA'
export type BottleneckStatus = 'NORMAL' | 'WARNING' | 'BOTTLENECK' | 'INSUFFICIENT_DATA' | 'NO_BOTTLENECK'
export type ValidationStatus = 'MATCH' | 'MISMATCH' | 'INSUFFICIENT_DATA'
export type ImpactSeverity = 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT_DATA'
export type RecommendationPriority = 'HIGH' | 'MEDIUM' | 'LOW' | 'INFORMATIONAL'
export type RecommendationAction =
  | 'SCALE_OUT'
  | 'MAINTAIN'
  | 'INVESTIGATE_BOTTLENECK'
  | 'MONITOR'
  | 'COLLECT_DATA'
  | 'REVIEW_PREDICTION'

export type ScenarioParameters = {
  multiplier?: number | null
  instance_name?: string | null
  additional_instances?: number | null
}

export type Experiment = {
  experiment_id: string
  name: string
  scenario_type: ScenarioType
  status: ExperimentStatus
  scenario_parameters: ScenarioParameters
  created_at?: string | null
}

export type ExperimentCreateRequest = {
  experiment_id: string
  name: string
  scenario_type: ScenarioType
  scenario_parameters: ScenarioParameters
}

export type ExecuteExperimentRequest = {
  service_name: string
}

export type InstanceExecution = {
  name: string
  cpu_capacity: number
  memory_capacity: number
  cpu_utilization: number
  memory_utilization: number
  request_rate: number
  status: 'healthy' | 'unhealthy' | 'starting' | 'stopped'
  request_count: number
  request_latency_count: number
}

export type ServiceExecution = {
  name: string
  dependencies: string[]
  instances: Record<string, InstanceExecution>
}

export type InfrastructureExecution = {
  services: Record<string, ServiceExecution>
}

export type TrafficSurgeSimulation = {
  infrastructure: InfrastructureExecution
  service_name: string
  multiplier: number
  original_request_rate: number
  simulated_request_rate: number
}

export type InstanceFailureSimulation = {
  infrastructure: InfrastructureExecution
  service_name: string
  instance_name: string
  healthy_instance_count: number
  unhealthy_instance_count: number
  remaining_cpu_capacity: number
  remaining_memory_capacity: number
}

export type ScaleOutSimulation = {
  infrastructure: InfrastructureExecution
  service_name: string
  additional_instances: number
  simulated_instance_count: number
  total_cpu_capacity: number
  total_memory_capacity: number
}

export type SimulationResult =
  | TrafficSurgeSimulation
  | InstanceFailureSimulation
  | ScaleOutSimulation

export type CapacitySnapshot = {
  cpu: number
  memory: number
}

export type TrafficImpact = {
  service_name: string
  original_request_rate: number
  simulated_request_rate: number
  absolute_change: number
  percentage_change: number
}

export type InstanceFailureImpact = {
  service_name: string
  original_instance_count: number
  simulated_instance_count: number
  original_healthy_instance_count: number
  simulated_healthy_instance_count: number
  original_capacity: CapacitySnapshot
  simulated_capacity: CapacitySnapshot
  capacity_change: CapacitySnapshot
  healthy_instance_change: number
}

export type ScaleOutImpact = {
  service_name: string
  original_instance_count: number
  simulated_instance_count: number
  instance_count_change: number
  original_capacity: CapacitySnapshot
  simulated_capacity: CapacitySnapshot
  capacity_change: CapacitySnapshot
}

export type ImpactResult = TrafficImpact | InstanceFailureImpact | ScaleOutImpact

export type ResourcePredictionResult = {
  service_name: string
  original_request_rate: number
  simulated_request_rate: number | null
  workload_multiplier: number | null
  healthy_instance_count: number
  total_instance_count: number
  cpu_capacity: number
  memory_capacity: number
  healthy_cpu_capacity: number
  healthy_memory_capacity: number
  projected_cpu_demand: number | null
  projected_memory_demand: number | null
  cpu_status: ResourceStatus
  memory_status: ResourceStatus
  insufficient_data: string[]
}

export type BottleneckResult = {
  service_name: string
  cpu_utilization: number | null
  memory_utilization: number | null
  cpu_status: BottleneckStatus
  memory_status: BottleneckStatus
  total_instance_count: number
  healthy_instance_count: number
  unhealthy_instance_count: number
  total_cpu_capacity: number
  total_memory_capacity: number
  healthy_cpu_capacity: number
  healthy_memory_capacity: number
  overall_status: BottleneckStatus
  reasons: string[]
}

export type ExecutionResult = {
  experiment_id: string
  scenario_type: ScenarioType
  service_name: string
  simulation: SimulationResult
  impact: ImpactResult
  prediction: ResourcePredictionResult
  bottleneck: BottleneckResult
}

export type ActualKubernetesResult = {
  experiment_id: string
  deployment_name: string
  namespace: string
  desired_replicas: number
  ready_replicas: number
  available_replicas: number
  updated_replicas: number
}

export type PredictionMetricComparison = {
  metric_name: string
  expected: unknown
  actual: unknown
  absolute_error: number | null
  percentage_error: number | null
  status: ValidationStatus
}

export type PredictionVsActualResult = {
  experiment_id: string
  comparisons: PredictionMetricComparison[]
  overall_status: ValidationStatus
}

export type ValidationResult = {
  experiment_id: string
  actual_result: ActualKubernetesResult
  prediction_comparison: PredictionVsActualResult
}

export type DeploymentImpactReport = {
  experiment_id: string
  scenario_type: ScenarioType
  service_name: string
  simulated_impact: ImpactResult
  predicted_demand: ResourcePredictionResult
  bottleneck: BottleneckResult
  actual_result: ActualKubernetesResult | null
  prediction_accuracy: PredictionVsActualResult | null
  overall_severity: ImpactSeverity
  limitations: string[]
}

export type Recommendation = {
  action: RecommendationAction
  priority: RecommendationPriority
  reason: string
  evidence: string[]
  experiment_id: string
}

export type RecommendationReport = {
  experiment_id: string
  recommendations: Recommendation[]
  overall_priority: RecommendationPriority
  limitations: string[]
}