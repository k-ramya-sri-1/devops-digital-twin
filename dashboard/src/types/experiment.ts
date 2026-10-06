export type ScenarioType = 'TRAFFIC_SURGE' | 'INSTANCE_FAILURE' | 'SCALE_OUT'
export type ExperimentStatus = 'CREATED' | 'SIMULATED' | 'EXECUTED' | 'VALIDATED'

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
}