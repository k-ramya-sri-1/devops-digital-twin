import importlib
from unittest.mock import Mock

import pytest


adapter_module = importlib.import_module("digital-twin.kubernetes_adapter")
actual_result_module = importlib.import_module("digital-twin.actual_result")

KubernetesDeploymentState = adapter_module.KubernetesDeploymentState
ActualKubernetesResult = actual_result_module.ActualKubernetesResult
ActualResultCollector = actual_result_module.ActualResultCollector
ActualResultError = actual_result_module.ActualResultError


def make_state(**overrides):
    values = {
        "name": "devops-digital-twin",
        "namespace": "default",
        "desired_replicas": 5,
        "ready_replicas": 5,
        "available_replicas": 5,
        "updated_replicas": 5,
    }
    values.update(overrides)
    return KubernetesDeploymentState(**values)


def make_collector(state=None):
    adapter = Mock()
    adapter.get_deployment_state.return_value = state or make_state()
    return ActualResultCollector(adapter), adapter


def test_collect_returns_actual_kubernetes_result():
    collector, adapter = make_collector()

    result = collector.collect("EXP-025")

    assert result == ActualKubernetesResult(
        experiment_id="EXP-025",
        deployment_name="devops-digital-twin",
        namespace="default",
        desired_replicas=5,
        ready_replicas=5,
        available_replicas=5,
        updated_replicas=5,
    )
    adapter.get_deployment_state.assert_called_once_with()


@pytest.mark.parametrize("experiment_id", [None, 1, True])
def test_collect_rejects_invalid_experiment_id_types(experiment_id):
    collector, adapter = make_collector()

    with pytest.raises(ActualResultError):
        collector.collect(experiment_id)

    adapter.get_deployment_state.assert_not_called()


def test_collect_rejects_empty_experiment_id():
    collector, adapter = make_collector()

    with pytest.raises(ActualResultError, match="experiment_id"):
        collector.collect(" ")

    adapter.get_deployment_state.assert_not_called()


def test_collect_converts_adapter_failure_with_context():
    adapter = Mock()
    adapter.get_deployment_state.side_effect = RuntimeError("Kubernetes unavailable")
    collector = ActualResultCollector(adapter)

    with pytest.raises(ActualResultError, match="EXP-025.*Kubernetes unavailable"):
        collector.collect("EXP-025")


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"namespace": ""},
        {"desired_replicas": -1},
    ],
)
def test_collect_rejects_invalid_deployment_state(overrides):
    collector, _ = make_collector(make_state(**overrides))

    with pytest.raises(ActualResultError):
        collector.collect("EXP-025")


@pytest.mark.parametrize(
    "field_name",
    ["ready_replicas", "available_replicas", "updated_replicas"],
)
def test_collect_rejects_replica_counts_greater_than_desired(field_name):
    collector, _ = make_collector(make_state(**{field_name: 6}))

    with pytest.raises(ActualResultError, match=field_name):
        collector.collect("EXP-025")


@pytest.mark.parametrize(
    "field_name",
    [
        "desired_replicas",
        "ready_replicas",
        "available_replicas",
        "updated_replicas",
    ],
)
def test_collect_rejects_bool_replica_values(field_name):
    collector, _ = make_collector(make_state(**{field_name: True}))

    with pytest.raises(ActualResultError, match=field_name):
        collector.collect("EXP-025")


def test_to_dict_contains_only_actual_result_fields():
    result = ActualKubernetesResult(
        "EXP-025", "devops-digital-twin", "default", 3, 3, 3, 3
    )

    assert result.to_dict() == {
        "experiment_id": "EXP-025",
        "deployment_name": "devops-digital-twin",
        "namespace": "default",
        "desired_replicas": 3,
        "ready_replicas": 3,
        "available_replicas": 3,
        "updated_replicas": 3,
    }