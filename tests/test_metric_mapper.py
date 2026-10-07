from dataclasses import replace
import importlib

import pytest


actual_result_module = importlib.import_module("digital-twin.actual_result")
analyzer_module = importlib.import_module("digital-twin.analyzer")
experiment_module = importlib.import_module("digital-twin.experiment")
executor_module = importlib.import_module("digital-twin.executor")
mapper_module = importlib.import_module("digital-twin.metric_mapper")

ActualKubernetesResult = actual_result_module.ActualKubernetesResult
CapacitySnapshot = analyzer_module.CapacitySnapshot
ScaleOutImpactResult = analyzer_module.ScaleOutImpactResult
ScenarioType = experiment_module.ScenarioType
ExecutionResult = executor_module.ExecutionResult
MetricMappingError = mapper_module.MetricMappingError
map_scale_out_replica_metrics = mapper_module.map_scale_out_replica_metrics


def make_execution_result(
    scenario_type: ScenarioType = ScenarioType.SCALE_OUT,
    simulated_instance_count: int = 4,
) -> ExecutionResult:
    impact = ScaleOutImpactResult(
        service_name="devops-digital-twin",
        original_instance_count=2,
        simulated_instance_count=simulated_instance_count,
        instance_count_change=simulated_instance_count - 2,
        original_capacity=CapacitySnapshot(cpu=4.0, memory=2048.0),
        simulated_capacity=CapacitySnapshot(cpu=8.0, memory=4096.0),
        capacity_change=CapacitySnapshot(cpu=4.0, memory=2048.0),
    )
    return ExecutionResult(
        experiment_id="EXP-026B",
        scenario_type=scenario_type,
        service_name="devops-digital-twin",
        simulation=object(),
        impact=impact,
        prediction=object(),
        bottleneck=object(),
    )


def make_actual_result(
    experiment_id: str = "EXP-026B", desired_replicas: int = 4
) -> ActualKubernetesResult:
    return ActualKubernetesResult(
        experiment_id=experiment_id,
        deployment_name="devops-digital-twin",
        namespace="default",
        desired_replicas=desired_replicas,
        ready_replicas=desired_replicas,
        available_replicas=desired_replicas,
        updated_replicas=desired_replicas,
    )


def test_successful_exact_scale_out_mapping() -> None:
    expected, actual = map_scale_out_replica_metrics(
        make_execution_result(), make_actual_result()
    )

    assert expected == {"replica_count": 4}
    assert actual == {"replica_count": 4}


def test_successful_mismatch_mapping() -> None:
    expected, actual = map_scale_out_replica_metrics(
        make_execution_result(simulated_instance_count=5),
        make_actual_result(desired_replicas=4),
    )

    assert expected == {"replica_count": 5}
    assert actual == {"replica_count": 4}


def test_rejects_non_scale_out_scenario() -> None:
    with pytest.raises(MetricMappingError, match="SCALE_OUT"):
        map_scale_out_replica_metrics(
            make_execution_result(ScenarioType.TRAFFIC_SURGE), make_actual_result()
        )


def test_rejects_missing_execution_result() -> None:
    with pytest.raises(MetricMappingError, match="execution_result"):
        map_scale_out_replica_metrics(None, make_actual_result())


def test_rejects_missing_actual_result() -> None:
    with pytest.raises(MetricMappingError, match="actual_result"):
        map_scale_out_replica_metrics(make_execution_result(), None)


def test_rejects_experiment_id_mismatch() -> None:
    with pytest.raises(MetricMappingError, match="experiment IDs"):
        map_scale_out_replica_metrics(
            make_execution_result(), make_actual_result("OTHER-EXPERIMENT")
        )


def test_rejects_missing_simulated_instance_count() -> None:
    execution_result = make_execution_result()
    execution_result = replace(execution_result, impact=object())

    with pytest.raises(MetricMappingError, match="simulated_instance_count"):
        map_scale_out_replica_metrics(execution_result, make_actual_result())


@pytest.mark.parametrize("value", [-1, 1.5, True, "4", None])
def test_rejects_invalid_predicted_replica_value(value) -> None:
    execution_result = make_execution_result()
    execution_result = replace(
        execution_result,
        impact=replace(execution_result.impact, simulated_instance_count=value),
    )

    with pytest.raises(MetricMappingError, match="predicted replica count"):
        map_scale_out_replica_metrics(execution_result, make_actual_result())


@pytest.mark.parametrize("value", [-1, True])
def test_rejects_invalid_actual_replica_value(value) -> None:
    actual_result = object.__new__(ActualKubernetesResult)
    object.__setattr__(actual_result, "experiment_id", "EXP-026B")
    object.__setattr__(actual_result, "desired_replicas", value)

    with pytest.raises(MetricMappingError, match="actual replica count"):
        map_scale_out_replica_metrics(make_execution_result(), actual_result)


def test_returned_dictionaries_contain_only_replica_count() -> None:
    expected, actual = map_scale_out_replica_metrics(
        make_execution_result(), make_actual_result()
    )

    assert set(expected) == {"replica_count"}
    assert set(actual) == {"replica_count"}


def test_cpu_memory_request_rate_are_not_added() -> None:
    expected, actual = map_scale_out_replica_metrics(
        make_execution_result(), make_actual_result()
    )

    for metric_name in ("cpu", "memory", "request_rate"):
        assert metric_name not in expected
        assert metric_name not in actual


def test_mapping_is_deterministic() -> None:
    execution_result = make_execution_result(simulated_instance_count=6)
    actual_result = make_actual_result(desired_replicas=5)

    first = map_scale_out_replica_metrics(execution_result, actual_result)
    second = map_scale_out_replica_metrics(execution_result, actual_result)

    assert first == second