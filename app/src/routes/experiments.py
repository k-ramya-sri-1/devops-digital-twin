"""FastAPI routes for experiment metadata management."""

import importlib
import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from database.connection import DatabaseError
from database.experiment_repository import ExperimentRepository
from database.experiment_result_repository import ExperimentResultRepository


experiment_module = importlib.import_module("digital-twin.experiment")
Experiment = experiment_module.Experiment
ExperimentError = experiment_module.ExperimentError
ExperimentStatus = experiment_module.ExperimentStatus
ScenarioParameters = experiment_module.ScenarioParameters
ScenarioType = experiment_module.ScenarioType
collector_module = importlib.import_module("digital-twin.collector")
current_state_module = importlib.import_module("digital-twin.current_state")
executor_module = importlib.import_module("digital-twin.executor")
analyzer_module = importlib.import_module("digital-twin.analyzer")
bottleneck_module = importlib.import_module("digital-twin.bottleneck")
models_module = importlib.import_module("digital-twin.models")
predictor_module = importlib.import_module("digital-twin.predictor")
actual_result_module = importlib.import_module("digital-twin.actual_result")
comparison_module = importlib.import_module("digital-twin.prediction_comparison")
mapper_module = importlib.import_module("digital-twin.metric_mapper")
validation_module = importlib.import_module("digital-twin.validation")
kubernetes_adapter_module = importlib.import_module("digital-twin.kubernetes_adapter")
PrometheusCollector = collector_module.PrometheusCollector
PrometheusCollectorError = collector_module.PrometheusCollectorError
CurrentStateService = current_state_module.CurrentStateService
ExperimentExecutionError = executor_module.ExperimentExecutionError
ExecutionResult = executor_module.ExecutionResult
ExperimentExecutor = executor_module.ExperimentExecutor
TrafficSurgeResult = executor_module.TrafficSurgeResult
InstanceFailureResult = executor_module.InstanceFailureResult
ScaleOutResult = executor_module.ScaleOutResult
TrafficImpactResult = analyzer_module.TrafficImpactResult
InstanceFailureImpactResult = analyzer_module.InstanceFailureImpactResult
ScaleOutImpactResult = analyzer_module.ScaleOutImpactResult
ResourcePredictionResult = predictor_module.ResourcePredictionResult
ResourceStatus = predictor_module.ResourceStatus
BottleneckResult = bottleneck_module.BottleneckResult
BottleneckStatus = bottleneck_module.BottleneckStatus
InstanceStatus = models_module.InstanceStatus
ActualKubernetesResult = actual_result_module.ActualKubernetesResult
PredictionMetricComparison = comparison_module.PredictionMetricComparison
PredictionVsActualResult = comparison_module.PredictionVsActualResult
ActualResultCollector = actual_result_module.ActualResultCollector
PredictionVsActualAnalyzer = comparison_module.PredictionVsActualAnalyzer
map_scale_out_replica_metrics = mapper_module.map_scale_out_replica_metrics
ExperimentValidationService = validation_module.ExperimentValidationService
ValidationError = validation_module.ValidationError
KubernetesExperimentAdapter = kubernetes_adapter_module.KubernetesExperimentAdapter


router = APIRouter(tags=["experiments"])


class ScenarioParametersRequest(BaseModel):
    multiplier: float | None = None
    instance_name: str | None = None
    additional_instances: int | None = None


class ExperimentCreateRequest(BaseModel):
    experiment_id: str
    name: str
    scenario_type: ScenarioType
    scenario_parameters: ScenarioParametersRequest


class ScenarioParametersResponse(BaseModel):
    multiplier: float | None
    instance_name: str | None
    additional_instances: int | None


class ExperimentResponse(BaseModel):
    experiment_id: str
    name: str
    scenario_type: ScenarioType
    status: ExperimentStatus
    scenario_parameters: ScenarioParametersResponse


class ExecuteExperimentRequest(BaseModel):
    service_name: str


class InstanceExecutionResponse(BaseModel):
    name: str
    cpu_capacity: float
    memory_capacity: float
    cpu_utilization: float
    memory_utilization: float
    request_rate: float
    status: InstanceStatus
    request_count: float
    request_latency_count: float


class ServiceExecutionResponse(BaseModel):
    name: str
    dependencies: list[str]
    instances: dict[str, InstanceExecutionResponse]


class InfrastructureExecutionResponse(BaseModel):
    services: dict[str, ServiceExecutionResponse]


class TrafficSurgeSimulationResponse(BaseModel):
    infrastructure: InfrastructureExecutionResponse
    service_name: str
    multiplier: float
    original_request_rate: float
    simulated_request_rate: float


class InstanceFailureSimulationResponse(BaseModel):
    infrastructure: InfrastructureExecutionResponse
    service_name: str
    instance_name: str
    healthy_instance_count: int
    unhealthy_instance_count: int
    remaining_cpu_capacity: float
    remaining_memory_capacity: float


class ScaleOutSimulationResponse(BaseModel):
    infrastructure: InfrastructureExecutionResponse
    service_name: str
    additional_instances: int
    simulated_instance_count: int
    total_cpu_capacity: float
    total_memory_capacity: float


class CapacitySnapshotResponse(BaseModel):
    cpu: float
    memory: float


class TrafficImpactResponse(BaseModel):
    service_name: str
    original_request_rate: float
    simulated_request_rate: float
    absolute_change: float
    percentage_change: float


class InstanceFailureImpactResponse(BaseModel):
    service_name: str
    original_instance_count: int
    simulated_instance_count: int
    original_healthy_instance_count: int
    simulated_healthy_instance_count: int
    original_capacity: CapacitySnapshotResponse
    simulated_capacity: CapacitySnapshotResponse
    capacity_change: CapacitySnapshotResponse
    healthy_instance_change: int


class ScaleOutImpactResponse(BaseModel):
    service_name: str
    original_instance_count: int
    simulated_instance_count: int
    instance_count_change: int
    original_capacity: CapacitySnapshotResponse
    simulated_capacity: CapacitySnapshotResponse
    capacity_change: CapacitySnapshotResponse


class ResourcePredictionResponse(BaseModel):
    service_name: str
    original_request_rate: float
    simulated_request_rate: float | None
    workload_multiplier: float | None
    healthy_instance_count: int
    total_instance_count: int
    cpu_capacity: float
    memory_capacity: float
    healthy_cpu_capacity: float
    healthy_memory_capacity: float
    projected_cpu_demand: float | None
    projected_memory_demand: float | None
    cpu_status: ResourceStatus
    memory_status: ResourceStatus
    insufficient_data: list[str]


class BottleneckResponse(BaseModel):
    service_name: str
    cpu_utilization: float | None
    memory_utilization: float | None
    cpu_status: BottleneckStatus
    memory_status: BottleneckStatus
    total_instance_count: int
    healthy_instance_count: int
    unhealthy_instance_count: int
    total_cpu_capacity: float
    total_memory_capacity: float
    healthy_cpu_capacity: float
    healthy_memory_capacity: float
    overall_status: BottleneckStatus
    reasons: list[str]


class ExecutionResponse(BaseModel):
    experiment_id: str
    scenario_type: ScenarioType
    service_name: str
    simulation: (
        TrafficSurgeSimulationResponse
        | InstanceFailureSimulationResponse
        | ScaleOutSimulationResponse
    )
    impact: (
        TrafficImpactResponse
        | InstanceFailureImpactResponse
        | ScaleOutImpactResponse
    )
    prediction: ResourcePredictionResponse
    bottleneck: BottleneckResponse


class ActualKubernetesResponse(BaseModel):
    experiment_id: str
    deployment_name: str
    namespace: str
    desired_replicas: int
    ready_replicas: int
    available_replicas: int
    updated_replicas: int


class PredictionMetricComparisonResponse(BaseModel):
    metric_name: str
    expected: object | None
    actual: object | None
    absolute_error: float | None
    percentage_error: float | None
    status: str


class PredictionVsActualResponse(BaseModel):
    experiment_id: str
    comparisons: list[PredictionMetricComparisonResponse]
    overall_status: str


class ValidationResponse(BaseModel):
    experiment_id: str
    actual_result: ActualKubernetesResponse
    prediction_comparison: PredictionVsActualResponse


def get_experiment_repository() -> ExperimentRepository:
    """Provide a repository for one API request."""
    return ExperimentRepository()


def get_experiment_result_repository() -> ExperimentResultRepository:
    """Provide an execution-result repository for one API request."""
    return ExperimentResultRepository()


def get_current_state_service() -> CurrentStateService:
    """Provide a current-state service backed by the configured Prometheus URL."""
    prometheus_url = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    return CurrentStateService(PrometheusCollector(prometheus_url))


def get_experiment_executor(
    repository: ExperimentRepository = Depends(get_experiment_repository),
    result_repository: ExperimentResultRepository = Depends(
        get_experiment_result_repository
    ),
) -> ExperimentExecutor:
    """Provide an executor with both persistence repositories injected."""
    return ExperimentExecutor(
        repository=repository,
        result_repository=result_repository,
    )


def get_actual_result_collector() -> ActualResultCollector:
    """Provide a collector for the configured Kubernetes Deployment."""
    deployment_name = os.getenv("KUBERNETES_DEPLOYMENT_NAME", "devops-digital-twin")
    namespace = os.getenv("KUBERNETES_NAMESPACE", "default")
    return ActualResultCollector(
        KubernetesExperimentAdapter(
            deployment_name=deployment_name,
            namespace=namespace,
        )
    )


def get_validation_service(
    experiment_repository: ExperimentRepository = Depends(get_experiment_repository),
    experiment_result_repository: ExperimentResultRepository = Depends(
        get_experiment_result_repository
    ),
    actual_result_collector: ActualResultCollector = Depends(
        get_actual_result_collector
    ),
) -> ExperimentValidationService:
    """Provide the dependency-injected experiment validation service."""
    return ExperimentValidationService(
        experiment_repository=experiment_repository,
        experiment_result_repository=experiment_result_repository,
        actual_result_collector=actual_result_collector,
        metric_mapper=map_scale_out_replica_metrics,
        prediction_vs_actual_analyzer=PredictionVsActualAnalyzer(),
    )


def _to_experiment(request: ExperimentCreateRequest) -> object:
    parameters = ScenarioParameters(
        multiplier=request.scenario_parameters.multiplier,
        instance_name=request.scenario_parameters.instance_name,
        additional_instances=request.scenario_parameters.additional_instances,
    )
    parameters.validate(request.scenario_type)
    return Experiment(
        experiment_id=request.experiment_id,
        name=request.name,
        scenario_type=request.scenario_type,
        scenario_parameters=parameters,
    )


def _to_response(experiment: object) -> ExperimentResponse:
    parameters = experiment.scenario_parameters
    return ExperimentResponse(
        experiment_id=experiment.experiment_id,
        name=experiment.name,
        scenario_type=experiment.scenario_type,
        status=experiment.status,
        scenario_parameters=ScenarioParametersResponse(
            multiplier=parameters.multiplier,
            instance_name=parameters.instance_name,
            additional_instances=parameters.additional_instances,
        ),
    )


def _infrastructure_to_response(infrastructure: object) -> InfrastructureExecutionResponse:
    return InfrastructureExecutionResponse(
        services={
            name: ServiceExecutionResponse(
                name=service.name,
                dependencies=sorted(service.dependencies),
                instances={
                    instance_name: InstanceExecutionResponse(
                        name=instance.name,
                        cpu_capacity=instance.cpu_capacity,
                        memory_capacity=instance.memory_capacity,
                        cpu_utilization=instance.cpu_utilization,
                        memory_utilization=instance.memory_utilization,
                        request_rate=instance.request_rate,
                        status=instance.status,
                        request_count=instance.request_count,
                        request_latency_count=instance.request_latency_count,
                    )
                    for instance_name, instance in service.instances.items()
                },
            )
            for name, service in infrastructure.services.items()
        }
    )


def _to_execution_response(result: ExecutionResult) -> ExecutionResponse:
    simulation = result.simulation
    if isinstance(simulation, TrafficSurgeResult):
        simulation_response = TrafficSurgeSimulationResponse(
            infrastructure=_infrastructure_to_response(simulation.infrastructure),
            service_name=simulation.service_name,
            multiplier=simulation.multiplier,
            original_request_rate=simulation.original_request_rate,
            simulated_request_rate=simulation.simulated_request_rate,
        )
    elif isinstance(simulation, InstanceFailureResult):
        simulation_response = InstanceFailureSimulationResponse(
            infrastructure=_infrastructure_to_response(simulation.infrastructure),
            service_name=simulation.service_name,
            instance_name=simulation.instance_name,
            healthy_instance_count=simulation.healthy_instance_count,
            unhealthy_instance_count=simulation.unhealthy_instance_count,
            remaining_cpu_capacity=simulation.remaining_cpu_capacity,
            remaining_memory_capacity=simulation.remaining_memory_capacity,
        )
    elif isinstance(simulation, ScaleOutResult):
        simulation_response = ScaleOutSimulationResponse(
            infrastructure=_infrastructure_to_response(simulation.infrastructure),
            service_name=simulation.service_name,
            additional_instances=simulation.additional_instances,
            simulated_instance_count=simulation.simulated_instance_count,
            total_cpu_capacity=simulation.total_cpu_capacity,
            total_memory_capacity=simulation.total_memory_capacity,
        )
    else:
        raise ValueError("unsupported execution simulation result")

    impact = result.impact
    if isinstance(impact, TrafficImpactResult):
        impact_response = TrafficImpactResponse(**impact.__dict__)
    elif isinstance(impact, InstanceFailureImpactResult):
        impact_response = InstanceFailureImpactResponse(
            service_name=impact.service_name,
            original_instance_count=impact.original_instance_count,
            simulated_instance_count=impact.simulated_instance_count,
            original_healthy_instance_count=impact.original_healthy_instance_count,
            simulated_healthy_instance_count=impact.simulated_healthy_instance_count,
            original_capacity=CapacitySnapshotResponse(**impact.original_capacity.__dict__),
            simulated_capacity=CapacitySnapshotResponse(**impact.simulated_capacity.__dict__),
            capacity_change=CapacitySnapshotResponse(**impact.capacity_change.__dict__),
            healthy_instance_change=impact.healthy_instance_change,
        )
    elif isinstance(impact, ScaleOutImpactResult):
        impact_response = ScaleOutImpactResponse(
            service_name=impact.service_name,
            original_instance_count=impact.original_instance_count,
            simulated_instance_count=impact.simulated_instance_count,
            instance_count_change=impact.instance_count_change,
            original_capacity=CapacitySnapshotResponse(**impact.original_capacity.__dict__),
            simulated_capacity=CapacitySnapshotResponse(**impact.simulated_capacity.__dict__),
            capacity_change=CapacitySnapshotResponse(**impact.capacity_change.__dict__),
        )
    else:
        raise ValueError("unsupported execution impact result")

    prediction: ResourcePredictionResult = result.prediction
    bottleneck: BottleneckResult = result.bottleneck
    return ExecutionResponse(
        experiment_id=result.experiment_id,
        scenario_type=result.scenario_type,
        service_name=result.service_name,
        simulation=simulation_response,
        impact=impact_response,
        prediction=ResourcePredictionResponse(
            service_name=prediction.service_name,
            original_request_rate=prediction.original_request_rate,
            simulated_request_rate=prediction.simulated_request_rate,
            workload_multiplier=prediction.workload_multiplier,
            healthy_instance_count=prediction.healthy_instance_count,
            total_instance_count=prediction.total_instance_count,
            cpu_capacity=prediction.cpu_capacity,
            memory_capacity=prediction.memory_capacity,
            healthy_cpu_capacity=prediction.healthy_cpu_capacity,
            healthy_memory_capacity=prediction.healthy_memory_capacity,
            projected_cpu_demand=prediction.projected_cpu_demand,
            projected_memory_demand=prediction.projected_memory_demand,
            cpu_status=prediction.cpu_status,
            memory_status=prediction.memory_status,
            insufficient_data=list(prediction.insufficient_data),
        ),
        bottleneck=BottleneckResponse(
            service_name=bottleneck.service_name,
            cpu_utilization=bottleneck.cpu_utilization,
            memory_utilization=bottleneck.memory_utilization,
            cpu_status=bottleneck.cpu_status,
            memory_status=bottleneck.memory_status,
            total_instance_count=bottleneck.total_instance_count,
            healthy_instance_count=bottleneck.healthy_instance_count,
            unhealthy_instance_count=bottleneck.unhealthy_instance_count,
            total_cpu_capacity=bottleneck.total_cpu_capacity,
            total_memory_capacity=bottleneck.total_memory_capacity,
            healthy_cpu_capacity=bottleneck.healthy_cpu_capacity,
            healthy_memory_capacity=bottleneck.healthy_memory_capacity,
            overall_status=bottleneck.overall_status,
            reasons=list(bottleneck.reasons),
        ),
    )


@router.post(
    "/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_experiment(
    request: ExperimentCreateRequest,
    repository: ExperimentRepository = Depends(get_experiment_repository),
) -> ExperimentResponse:
    try:
        experiment = _to_experiment(request)
    except ExperimentError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        repository.create(experiment)
    except DatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="experiment database unavailable",
        ) from error
    return _to_response(experiment)


@router.get("/experiments", response_model=list[ExperimentResponse])
def list_experiments(
    repository: ExperimentRepository = Depends(get_experiment_repository),
) -> list[ExperimentResponse]:
    try:
        experiments = repository.list_all()
    except DatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="experiment database unavailable",
        ) from error
    return [_to_response(experiment) for experiment in experiments]


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(
    experiment_id: str,
    repository: ExperimentRepository = Depends(get_experiment_repository),
) -> ExperimentResponse:
    try:
        experiment = repository.get_by_id(experiment_id)
    except DatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="experiment database unavailable",
        ) from error
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="experiment not found")
    return _to_response(experiment)


@router.post(
    "/experiments/{experiment_id}/execute",
    response_model=ExecutionResponse,
)
def execute_experiment(
    experiment_id: str,
    request: ExecuteExperimentRequest,
    repository: ExperimentRepository = Depends(get_experiment_repository),
    current_state_service: CurrentStateService = Depends(get_current_state_service),
    executor: ExperimentExecutor = Depends(get_experiment_executor),
) -> ExecutionResponse:
    try:
        experiment = repository.get_by_id(experiment_id)
    except DatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="experiment database unavailable",
        ) from error
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="experiment not found")
    if experiment.status is not ExperimentStatus.CREATED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="experiment is not in CREATED status",
        )
    if not request.service_name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="service_name must not be blank",
        )

    try:
        baseline = current_state_service.get_current_state()
    except PrometheusCollectorError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="current infrastructure state unavailable",
        ) from error

    try:
        result = executor.execute(experiment, baseline, request.service_name)
    except ExperimentExecutionError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="experiment execution failed",
        ) from error
    return _to_execution_response(result)


@router.get(
    "/experiments/{experiment_id}/result",
    response_model=ExecutionResponse,
)
def get_execution_result(
    experiment_id: str,
    result_repository: ExperimentResultRepository = Depends(
        get_experiment_result_repository
    ),
) -> ExecutionResponse:
    try:
        result = result_repository.get_by_experiment_id(experiment_id)
    except DatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="experiment result database unavailable",
        ) from error
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="execution result not found",
        )
    return _to_execution_response(result)


def _to_validation_response(result: object) -> ValidationResponse:
    actual_result: ActualKubernetesResult = result.actual_result
    comparison: PredictionVsActualResult = result.prediction_comparison
    return ValidationResponse(
        experiment_id=result.experiment_id,
        actual_result=ActualKubernetesResponse(
            experiment_id=actual_result.experiment_id,
            deployment_name=actual_result.deployment_name,
            namespace=actual_result.namespace,
            desired_replicas=actual_result.desired_replicas,
            ready_replicas=actual_result.ready_replicas,
            available_replicas=actual_result.available_replicas,
            updated_replicas=actual_result.updated_replicas,
        ),
        prediction_comparison=PredictionVsActualResponse(
            experiment_id=comparison.experiment_id,
            comparisons=[
                PredictionMetricComparisonResponse(
                    metric_name=item.metric_name,
                    expected=item.expected,
                    actual=item.actual,
                    absolute_error=item.absolute_error,
                    percentage_error=item.percentage_error,
                    status=item.status,
                )
                for item in comparison.comparisons
            ],
            overall_status=comparison.overall_status,
        ),
    )


@router.post(
    "/experiments/{experiment_id}/validate",
    response_model=ValidationResponse,
)
def validate_experiment(
    experiment_id: str,
    validation_service: ExperimentValidationService = Depends(
        get_validation_service
    ),
) -> ValidationResponse:
    try:
        result = validation_service.validate(experiment_id)
    except DatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="experiment validation database unavailable",
        ) from error
    except ValidationError as error:
        detail = str(error)
        if "experiment not found" in detail:
            response_status = status.HTTP_404_NOT_FOUND
        elif "persisted execution result not found" in detail:
            response_status = status.HTTP_404_NOT_FOUND
        elif "must be in EXECUTED status" in detail:
            response_status = status.HTTP_409_CONFLICT
        elif (
            "could not be loaded" in detail
            or "database" in detail
            or "actual Kubernetes result" in detail
            or "could not be persisted" in detail
            or "status could not be persisted" in detail
        ):
            response_status = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            response_status = status.HTTP_422_UNPROCESSABLE_CONTENT
        raise HTTPException(status_code=response_status, detail=detail) from error
    return _to_validation_response(result)