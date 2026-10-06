from copy import deepcopy
from dataclasses import replace
from unittest.mock import MagicMock

import importlib
import pytest


models = importlib.import_module("digital-twin.models")
experiment_module = importlib.import_module("digital-twin.experiment")
simulator_module = importlib.import_module("digital-twin.simulator")
analyzer_module = importlib.import_module("digital-twin.analyzer")
predictor_module = importlib.import_module("digital-twin.predictor")
bottleneck_module = importlib.import_module("digital-twin.bottleneck")
executor_module = importlib.import_module("digital-twin.executor")

Infrastructure = models.Infrastructure
Instance = models.Instance
InstanceStatus = models.InstanceStatus
Service = models.Service
Experiment = experiment_module.Experiment
ExperimentError = experiment_module.ExperimentError
ExperimentStatus = experiment_module.ExperimentStatus
ScenarioParameters = experiment_module.ScenarioParameters
ScenarioType = experiment_module.ScenarioType
SimulationError = simulator_module.SimulationError
AnalysisError = analyzer_module.AnalysisError
PredictionError = predictor_module.PredictionError
BottleneckError = bottleneck_module.BottleneckError
TrafficSurgeResult = simulator_module.TrafficSurgeResult
InstanceFailureResult = simulator_module.InstanceFailureResult
ScaleOutResult = simulator_module.ScaleOutResult
CapacitySnapshot = analyzer_module.CapacitySnapshot
TrafficImpactResult = analyzer_module.TrafficImpactResult
InstanceFailureImpactResult = analyzer_module.InstanceFailureImpactResult
ScaleOutImpactResult = analyzer_module.ScaleOutImpactResult
ResourcePredictionResult = predictor_module.ResourcePredictionResult
ResourceStatus = predictor_module.ResourceStatus
BottleneckResult = bottleneck_module.BottleneckResult
BottleneckStatus = bottleneck_module.BottleneckStatus
DigitalTwinSimulator = simulator_module.DigitalTwinSimulator
ScenarioImpactAnalyzer = analyzer_module.ScenarioImpactAnalyzer
ResourceDemandPredictor = predictor_module.ResourceDemandPredictor
BottleneckDetector = bottleneck_module.BottleneckDetector
ExperimentExecutionError = executor_module.ExperimentExecutionError
ExecutionResult = executor_module.ExecutionResult
ExperimentExecutor = executor_module.ExperimentExecutor


SERVICE_NAME = "devops-digital-twin"


def make_infrastructure() -> Infrastructure:
    service = Service(name=SERVICE_NAME)
    service.add_instance(
        Instance(
            name="instance-1",
            cpu_capacity=2.0,
            memory_capacity=1024.0,
            cpu_utilization=50.0,
            memory_utilization=25.0,
            request_rate=100.0,
            status=InstanceStatus.HEALTHY,
        )
    )
    service.add_instance(
        Instance(
            name="instance-2",
            cpu_capacity=2.0,
            memory_capacity=1024.0,
            cpu_utilization=50.0,
            memory_utilization=25.0,
            request_rate=50.0,
            status=InstanceStatus.HEALTHY,
        )
    )
    infrastructure = Infrastructure()
    infrastructure.add_service(service)
    return infrastructure


def make_experiment(scenario_type: ScenarioType) -> Experiment:
    parameters = {
        ScenarioType.TRAFFIC_SURGE: ScenarioParameters.traffic_surge(2.0),
        ScenarioType.INSTANCE_FAILURE: ScenarioParameters.instance_failure(
            "instance-1"
        ),
        ScenarioType.SCALE_OUT: ScenarioParameters.scale_out(1),
    }[scenario_type]
    return Experiment("EXP-TEST", "executor test", scenario_type, parameters)


def make_simulation(scenario_type: ScenarioType, baseline: Infrastructure):
    simulated = deepcopy(baseline)
    if scenario_type is ScenarioType.TRAFFIC_SURGE:
        return TrafficSurgeResult(
            simulated, SERVICE_NAME, 2.0, 150.0, 300.0
        )
    if scenario_type is ScenarioType.INSTANCE_FAILURE:
        return InstanceFailureResult(
            simulated,
            SERVICE_NAME,
            "instance-1",
            1,
            1,
            2.0,
            1024.0,
        )
    return ScaleOutResult(simulated, SERVICE_NAME, 1, 3, 6.0, 3072.0)


def make_impact(scenario_type: ScenarioType):
    if scenario_type is ScenarioType.TRAFFIC_SURGE:
        return TrafficImpactResult(SERVICE_NAME, 150.0, 300.0, 150.0, 100.0)
    if scenario_type is ScenarioType.INSTANCE_FAILURE:
        original = CapacitySnapshot(4.0, 2048.0)
        simulated = CapacitySnapshot(2.0, 1024.0)
        return InstanceFailureImpactResult(
            SERVICE_NAME,
            2,
            2,
            2,
            1,
            original,
            simulated,
            CapacitySnapshot(-2.0, -1024.0),
            -1,
        )
    original = CapacitySnapshot(4.0, 2048.0)
    simulated = CapacitySnapshot(6.0, 3072.0)
    return ScaleOutImpactResult(
        SERVICE_NAME,
        2,
        3,
        1,
        original,
        simulated,
        CapacitySnapshot(2.0, 1024.0),
    )


def make_prediction() -> ResourcePredictionResult:
    return ResourcePredictionResult(
        SERVICE_NAME,
        150.0,
        300.0,
        2.0,
        2,
        2,
        4.0,
        2048.0,
        4.0,
        2048.0,
        4.0,
        1024.0,
        ResourceStatus.SUFFICIENT,
        ResourceStatus.SUFFICIENT,
        (),
    )


def make_bottleneck() -> BottleneckResult:
    return BottleneckResult(
        SERVICE_NAME,
        50.0,
        25.0,
        BottleneckStatus.NORMAL,
        BottleneckStatus.NORMAL,
        2,
        2,
        0,
        4.0,
        2048.0,
        4.0,
        2048.0,
        BottleneckStatus.NO_BOTTLENECK,
        ("no measured resource or health bottleneck detected",),
    )


@pytest.fixture
def components():
    return {
        "repository": MagicMock(),
        "result_repository": MagicMock(),
        "simulator": MagicMock(spec=DigitalTwinSimulator),
        "analyzer": MagicMock(spec=ScenarioImpactAnalyzer),
        "predictor": MagicMock(spec=ResourceDemandPredictor),
        "bottleneck_detector": MagicMock(spec=BottleneckDetector),
    }


@pytest.mark.parametrize(
    ("scenario_type", "simulator_method", "analyzer_method"),
    [
        (ScenarioType.TRAFFIC_SURGE, "traffic_surge", "analyze_traffic"),
        (
            ScenarioType.INSTANCE_FAILURE,
            "instance_failure",
            "analyze_instance_failure",
        ),
        (ScenarioType.SCALE_OUT, "scale_out", "analyze_scale_out"),
    ],
)
def test_execute_orchestrates_each_scenario(
    scenario_type, simulator_method, analyzer_method, components
) -> None:
    baseline = make_infrastructure()
    simulation = make_simulation(scenario_type, baseline)
    impact = make_impact(scenario_type)
    prediction = make_prediction()
    bottleneck = make_bottleneck()
    getattr(components["simulator"], simulator_method).return_value = simulation
    getattr(components["analyzer"], analyzer_method).return_value = impact
    components["predictor"].predict.return_value = prediction
    components["bottleneck_detector"].analyze.return_value = bottleneck
    experiment = make_experiment(scenario_type)

    result = ExperimentExecutor(**components).execute(
        experiment, baseline, SERVICE_NAME
    )

    assert isinstance(result, ExecutionResult)
    assert result.experiment_id == "EXP-TEST"
    assert result.scenario_type is scenario_type
    assert result.service_name == SERVICE_NAME
    assert result.simulation is simulation
    assert result.impact is impact
    assert result.prediction is prediction
    assert result.bottleneck is bottleneck
    getattr(components["simulator"], simulator_method).assert_called_once()
    getattr(components["analyzer"], analyzer_method).assert_called_once_with(
        baseline, simulation
    )
    components["predictor"].predict.assert_called_once_with(
        baseline, SERVICE_NAME, simulation
    )
    components["bottleneck_detector"].analyze.assert_called_once_with(
        simulation.infrastructure, SERVICE_NAME
    )
    components["repository"].update_status.assert_called_once_with(
        "EXP-TEST", ExperimentStatus.EXECUTED
    )
    components["result_repository"].create.assert_called_once_with(result)
    assert experiment.status is ExperimentStatus.EXECUTED


def test_result_persistence_happens_before_executed_transition(components) -> None:
    baseline = make_infrastructure()
    experiment = make_experiment(ScenarioType.TRAFFIC_SURGE)
    components["simulator"].traffic_surge.return_value = make_simulation(
        ScenarioType.TRAFFIC_SURGE, baseline
    )
    components["analyzer"].analyze_traffic.return_value = make_impact(
        ScenarioType.TRAFFIC_SURGE
    )
    components["predictor"].predict.return_value = make_prediction()
    components["bottleneck_detector"].analyze.return_value = make_bottleneck()

    def assert_simulated(result) -> None:
        assert experiment.status is ExperimentStatus.SIMULATED
        assert isinstance(result, ExecutionResult)

    components["result_repository"].create.side_effect = assert_simulated

    result = ExperimentExecutor(**components).execute(
        experiment, baseline, SERVICE_NAME
    )

    assert result.experiment_id == "EXP-TEST"
    assert experiment.status is ExperimentStatus.EXECUTED


def test_result_persistence_failure_prevents_executed_transition(components) -> None:
    baseline = make_infrastructure()
    experiment = make_experiment(ScenarioType.TRAFFIC_SURGE)
    components["simulator"].traffic_surge.return_value = make_simulation(
        ScenarioType.TRAFFIC_SURGE, baseline
    )
    components["analyzer"].analyze_traffic.return_value = make_impact(
        ScenarioType.TRAFFIC_SURGE
    )
    components["predictor"].predict.return_value = make_prediction()
    components["bottleneck_detector"].analyze.return_value = make_bottleneck()
    components["result_repository"].create.side_effect = RuntimeError("storage failed")

    with pytest.raises(ExperimentExecutionError, match="result"):
        ExperimentExecutor(**components).execute(
            experiment, baseline, SERVICE_NAME
        )

    assert experiment.status is ExperimentStatus.SIMULATED
    components["repository"].update_status.assert_not_called()


def test_execute_without_repository_keeps_lifecycle_and_returns_typed_results() -> None:
    baseline = make_infrastructure()
    executor = ExperimentExecutor(
        simulator=DigitalTwinSimulator(),
        analyzer=ScenarioImpactAnalyzer(),
        predictor=ResourceDemandPredictor(),
        bottleneck_detector=BottleneckDetector(),
    )
    experiment = make_experiment(ScenarioType.TRAFFIC_SURGE)

    result = executor.execute(experiment, baseline, SERVICE_NAME)

    assert experiment.status is ExperimentStatus.EXECUTED
    assert isinstance(result.simulation, TrafficSurgeResult)
    assert isinstance(result.impact, TrafficImpactResult)
    assert isinstance(result.prediction, ResourcePredictionResult)
    assert isinstance(result.bottleneck, BottleneckResult)


def test_missing_baseline_is_rejected() -> None:
    experiment = make_experiment(ScenarioType.TRAFFIC_SURGE)

    with pytest.raises(ExperimentExecutionError, match="baseline"):
        ExperimentExecutor().execute(experiment, None, SERVICE_NAME)

    assert experiment.status is ExperimentStatus.CREATED


def test_invalid_experiment_status_is_rejected() -> None:
    experiment = make_experiment(ScenarioType.TRAFFIC_SURGE)
    experiment.status = ExperimentStatus.SIMULATED

    with pytest.raises(ExperimentExecutionError, match="CREATED"):
        ExperimentExecutor().execute(experiment, make_infrastructure(), SERVICE_NAME)


def test_invalid_scenario_parameters_are_rejected_before_execution() -> None:
    with pytest.raises(ExperimentError):
        Experiment(
            "EXP-INVALID",
            "invalid",
            ScenarioType.TRAFFIC_SURGE,
            ScenarioParameters(multiplier=0),
        )


def test_unknown_service_is_wrapped_and_does_not_advance_lifecycle() -> None:
    experiment = make_experiment(ScenarioType.TRAFFIC_SURGE)

    with pytest.raises(ExperimentExecutionError) as error:
        ExperimentExecutor().execute(experiment, make_infrastructure(), "missing")

    assert isinstance(error.value.__cause__, SimulationError)
    assert experiment.status is ExperimentStatus.CREATED


def test_unknown_instance_is_wrapped_and_does_not_advance_lifecycle() -> None:
    experiment = Experiment(
        "EXP-FAILURE",
        "failure",
        ScenarioType.INSTANCE_FAILURE,
        ScenarioParameters.instance_failure("missing"),
    )

    with pytest.raises(ExperimentExecutionError) as error:
        ExperimentExecutor().execute(experiment, make_infrastructure(), SERVICE_NAME)

    assert isinstance(error.value.__cause__, SimulationError)
    assert experiment.status is ExperimentStatus.CREATED


def test_simulator_failure_does_not_transition_to_simulated(components) -> None:
    components["simulator"].traffic_surge.side_effect = SimulationError("failed")
    experiment = make_experiment(ScenarioType.TRAFFIC_SURGE)

    with pytest.raises(ExperimentExecutionError):
        ExperimentExecutor(**components).execute(
            experiment, make_infrastructure(), SERVICE_NAME
        )

    assert experiment.status is ExperimentStatus.CREATED
    components["repository"].update_status.assert_not_called()


@pytest.mark.parametrize(
    ("component", "exception", "status"),
    [
        ("analyzer", AnalysisError("failed"), ExperimentStatus.SIMULATED),
        ("predictor", PredictionError("failed"), ExperimentStatus.SIMULATED),
        ("bottleneck_detector", BottleneckError("failed"), ExperimentStatus.SIMULATED),
    ],
)
def test_post_simulation_failures_do_not_transition_to_executed(
    components, component, exception, status
) -> None:
    baseline = make_infrastructure()
    simulation = make_simulation(ScenarioType.TRAFFIC_SURGE, baseline)
    components["simulator"].traffic_surge.return_value = simulation
    components["analyzer"].analyze_traffic.return_value = make_impact(
        ScenarioType.TRAFFIC_SURGE
    )
    components["predictor"].predict.return_value = make_prediction()
    components["bottleneck_detector"].analyze.return_value = make_bottleneck()
    if component == "analyzer":
        components[component].analyze_traffic.side_effect = exception
    elif component == "bottleneck_detector":
        components[component].analyze.side_effect = exception
    else:
        components[component].predict.side_effect = exception
    experiment = make_experiment(ScenarioType.TRAFFIC_SURGE)

    with pytest.raises(ExperimentExecutionError):
        ExperimentExecutor(**components).execute(experiment, baseline, SERVICE_NAME)

    assert experiment.status is status
    components["repository"].update_status.assert_not_called()


def test_original_baseline_and_experiment_data_are_not_mutated_by_execution() -> None:
    baseline = make_infrastructure()
    before = deepcopy(baseline)
    experiment = make_experiment(ScenarioType.SCALE_OUT)
    parameters_before = experiment.parameters

    ExperimentExecutor().execute(experiment, baseline, SERVICE_NAME)

    assert baseline == before
    assert experiment.parameters == parameters_before
    assert experiment.baseline_state is None
    assert experiment.actual_result is None