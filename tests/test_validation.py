from unittest.mock import MagicMock
import importlib

import pytest


actual_result_module = importlib.import_module("digital-twin.actual_result")
analyzer_module = importlib.import_module("digital-twin.prediction_comparison")
experiment_module = importlib.import_module("digital-twin.experiment")
executor_module = importlib.import_module("digital-twin.executor")
validation_module = importlib.import_module("digital-twin.validation")

ActualKubernetesResult = actual_result_module.ActualKubernetesResult
PredictionMetricComparison = analyzer_module.PredictionMetricComparison
PredictionVsActualResult = analyzer_module.PredictionVsActualResult
Experiment = experiment_module.Experiment
ExperimentStatus = experiment_module.ExperimentStatus
ScenarioParameters = experiment_module.ScenarioParameters
ScenarioType = experiment_module.ScenarioType
ExecutionResult = executor_module.ExecutionResult
ExperimentValidationService = validation_module.ExperimentValidationService
ValidationError = validation_module.ValidationError


def make_experiment(status: ExperimentStatus) -> Experiment:
    return Experiment(
        experiment_id="EXP-VALIDATION",
        name="validation test",
        scenario_type=ScenarioType.SCALE_OUT,
        scenario_parameters=ScenarioParameters.scale_out(1),
        status=status,
    )


def make_actual_result(experiment_id: str = "EXP-VALIDATION") -> ActualKubernetesResult:
    return ActualKubernetesResult(
        experiment_id=experiment_id,
        deployment_name="devops-digital-twin",
        namespace="default",
        desired_replicas=3,
        ready_replicas=3,
        available_replicas=3,
        updated_replicas=3,
    )


def make_comparison() -> PredictionVsActualResult:
    return PredictionVsActualResult(
        experiment_id="EXP-VALIDATION",
        comparisons=(
            PredictionMetricComparison(
                metric_name="replica_count",
                expected=3,
                actual=3,
                absolute_error=0.0,
                percentage_error=0.0,
                status="MATCH",
            ),
        ),
        overall_status="MATCH",
    )


def make_service(status=ExperimentStatus.EXECUTED):
    experiment_repository = MagicMock()
    experiment_repository.get_by_id.return_value = make_experiment(status)
    experiment_result_repository = MagicMock()
    execution_result = MagicMock(spec=ExecutionResult)
    experiment_result_repository.get_by_experiment_id.return_value = execution_result
    actual_result_collector = MagicMock()
    actual_result_collector.collect.return_value = make_actual_result()
    metric_mapper = MagicMock()
    metric_mapper.return_value = (
        {"replica_count": 3},
        {"replica_count": 3},
    )
    analyzer = MagicMock()
    analyzer.compare.return_value = make_comparison()
    service = ExperimentValidationService(
        experiment_repository,
        experiment_result_repository,
        actual_result_collector,
        metric_mapper,
        analyzer,
    )
    return (
        service,
        experiment_repository,
        experiment_result_repository,
        actual_result_collector,
        metric_mapper,
        analyzer,
    )


def test_successful_validation_persists_before_status_transition() -> None:
    service, experiment_repository, result_repository, collector, mapper, analyzer = (
        make_service()
    )
    experiment = experiment_repository.get_by_id.return_value
    events = []
    result_repository.update_actual_comparison.side_effect = lambda *args: events.append(
        "persist"
    )
    original_transition = experiment.transition_to
    experiment.transition_to = MagicMock(
        side_effect=lambda status: (events.append("transition"), original_transition(status))[1]
    )

    result = service.validate("EXP-VALIDATION")

    collector.collect.assert_called_once_with("EXP-VALIDATION")
    mapper.assert_called_once_with(
        result_repository.get_by_experiment_id.return_value,
        collector.collect.return_value,
    )
    analyzer.compare.assert_called_once_with(
        "EXP-VALIDATION", {"replica_count": 3}, {"replica_count": 3}
    )
    result_repository.update_actual_comparison.assert_called_once_with(
        "EXP-VALIDATION", collector.collect.return_value, analyzer.compare.return_value
    )
    experiment_repository.update_status.assert_called_once_with(
        "EXP-VALIDATION", ExperimentStatus.VALIDATED
    )
    assert result.actual_result is collector.collect.return_value
    assert result.prediction_comparison is analyzer.compare.return_value
    assert experiment.status is ExperimentStatus.VALIDATED
    assert events == ["persist", "transition"]


def test_missing_experiment_is_rejected() -> None:
    service, experiment_repository, *_ = make_service()
    experiment_repository.get_by_id.return_value = None

    with pytest.raises(ValidationError, match="not found"):
        service.validate("MISSING")


@pytest.mark.parametrize(
    "status", [ExperimentStatus.CREATED, ExperimentStatus.SIMULATED, ExperimentStatus.VALIDATED]
)
def test_only_executed_experiments_are_accepted(status) -> None:
    service, *_ = make_service(status)

    with pytest.raises(ValidationError, match="EXECUTED"):
        service.validate("EXP-VALIDATION")


def test_missing_persisted_execution_result_is_rejected() -> None:
    service, _, result_repository, *_ = make_service()
    result_repository.get_by_experiment_id.return_value = None

    with pytest.raises(ValidationError, match="persisted execution result"):
        service.validate("EXP-VALIDATION")


def test_collection_failure_keeps_experiment_executed() -> None:
    service, experiment_repository, result_repository, collector, *_ = make_service()
    collector.collect.side_effect = RuntimeError("Kubernetes unavailable")
    experiment = experiment_repository.get_by_id.return_value

    with pytest.raises(ValidationError, match="collected"):
        service.validate("EXP-VALIDATION")

    assert experiment.status is ExperimentStatus.EXECUTED
    result_repository.update_actual_comparison.assert_not_called()


def test_mapping_failure_keeps_experiment_executed() -> None:
    service, experiment_repository, result_repository, _, mapper, _ = make_service()
    mapper.side_effect = RuntimeError("unsupported mapping")

    with pytest.raises(ValidationError, match="mapped"):
        service.validate("EXP-VALIDATION")

    assert experiment_repository.get_by_id.return_value.status is ExperimentStatus.EXECUTED
    result_repository.update_actual_comparison.assert_not_called()


def test_comparison_failure_keeps_experiment_executed() -> None:
    service, experiment_repository, result_repository, _, _, analyzer = make_service()
    analyzer.compare.side_effect = RuntimeError("comparison failed")

    with pytest.raises(ValidationError, match="compared"):
        service.validate("EXP-VALIDATION")

    assert experiment_repository.get_by_id.return_value.status is ExperimentStatus.EXECUTED
    result_repository.update_actual_comparison.assert_not_called()


def test_persistence_failure_keeps_experiment_executed() -> None:
    service, experiment_repository, result_repository, *_ = make_service()
    result_repository.update_actual_comparison.side_effect = RuntimeError(
        "database unavailable"
    )

    with pytest.raises(ValidationError, match="persisted"):
        service.validate("EXP-VALIDATION")

    assert experiment_repository.get_by_id.return_value.status is ExperimentStatus.EXECUTED
    experiment_repository.update_status.assert_not_called()


def test_actual_result_id_mismatch_keeps_experiment_executed() -> None:
    service, experiment_repository, result_repository, collector, *_ = make_service()
    collector.collect.return_value = make_actual_result("OTHER-EXPERIMENT")

    with pytest.raises(ValidationError, match="does not match"):
        service.validate("EXP-VALIDATION")

    assert experiment_repository.get_by_id.return_value.status is ExperimentStatus.EXECUTED
    result_repository.update_actual_comparison.assert_not_called()


def test_transition_failure_is_controlled_and_not_persisted_as_validated() -> None:
    service, experiment_repository, result_repository, *_ = make_service()
    experiment = experiment_repository.get_by_id.return_value
    experiment.transition_to = MagicMock(side_effect=RuntimeError("transition failed"))

    with pytest.raises(ValidationError, match="transition"):
        service.validate("EXP-VALIDATION")

    result_repository.update_actual_comparison.assert_called_once()
    experiment_repository.update_status.assert_not_called()