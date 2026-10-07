from types import SimpleNamespace
import importlib
from unittest.mock import Mock

import pytest


adapter_module = importlib.import_module("digital-twin.kubernetes_adapter")
KubernetesDeploymentState = adapter_module.KubernetesDeploymentState
KubernetesExperimentAdapter = adapter_module.KubernetesExperimentAdapter
KubernetesExperimentError = adapter_module.KubernetesExperimentError


def deployment(name="devops-digital-twin", namespace="default", replicas=3, ready=None, available=None, updated=None):
    return SimpleNamespace(
        metadata=SimpleNamespace(name=name, namespace=namespace),
        spec=SimpleNamespace(replicas=replicas),
        status=SimpleNamespace(
            ready_replicas=replicas if ready is None else ready,
            available_replicas=replicas if available is None else available,
            updated_replicas=replicas if updated is None else updated,
        ),
    )


def make_adapter(api, **kwargs):
    return KubernetesExperimentAdapter(
        "devops-digital-twin",
        apps_api_client=api,
        **kwargs,
    )


def test_get_deployment_state_returns_replica_state():
    api = Mock()
    api.read_namespaced_deployment.return_value = deployment(
        replicas=3, ready=2, available=2, updated=3
    )

    state = make_adapter(api).get_deployment_state()

    assert state == KubernetesDeploymentState(
        "devops-digital-twin", "default", 3, 2, 2, 3
    )


def test_get_deployment_state_converts_api_failure():
    api = Mock()
    api.read_namespaced_deployment.side_effect = RuntimeError("api unavailable")

    with pytest.raises(KubernetesExperimentError):
        make_adapter(api).get_deployment_state()


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "3"])
def test_invalid_replica_values_are_rejected(value):
    adapter = make_adapter(Mock())

    with pytest.raises(ValueError):
        adapter.scale_replicas(value)


def test_scale_replicas_patches_only_replica_count():
    api = Mock()

    make_adapter(api).scale_replicas(5)

    api.patch_namespaced_deployment_scale.assert_called_once_with(
        name="devops-digital-twin",
        namespace="default",
        body={"spec": {"replicas": 5}},
    )


def test_scale_replicas_converts_api_failure():
    api = Mock()
    api.patch_namespaced_deployment_scale.side_effect = RuntimeError("api unavailable")

    with pytest.raises(KubernetesExperimentError):
        make_adapter(api).scale_replicas(4)


def test_wait_for_rollout_succeeds_after_polling():
    api = Mock()
    api.read_namespaced_deployment.side_effect = [
        deployment(replicas=3, ready=1, available=1),
        deployment(replicas=3, ready=3, available=3),
    ]

    state = make_adapter(api, rollout_timeout_seconds=1, poll_interval_seconds=0).wait_for_rollout(3)

    assert state.ready_replicas == 3
    assert api.read_namespaced_deployment.call_count == 2


def test_wait_for_rollout_times_out():
    api = Mock()
    api.read_namespaced_deployment.return_value = deployment(
        replicas=3, ready=2, available=2
    )

    with pytest.raises(KubernetesExperimentError, match="timed out"):
        make_adapter(api, rollout_timeout_seconds=0, poll_interval_seconds=0).wait_for_rollout(3)


def test_scale_and_wait_scales_then_returns_final_state():
    api = Mock()
    api.read_namespaced_deployment.return_value = deployment(replicas=4)

    state = make_adapter(api, poll_interval_seconds=0).scale_and_wait(4)

    assert state.desired_replicas == 4
    api.patch_namespaced_deployment_scale.assert_called_once()


def test_restore_replicas_scales_back_and_waits():
    api = Mock()
    api.read_namespaced_deployment.return_value = deployment(replicas=3)

    state = make_adapter(api, poll_interval_seconds=0).restore_replicas(3)

    assert state == KubernetesDeploymentState(
        "devops-digital-twin", "default", 3, 3, 3, 3
    )
    api.patch_namespaced_deployment_scale.assert_called_once_with(
        name="devops-digital-twin",
        namespace="default",
        body={"spec": {"replicas": 3}},
    )


def test_restore_replicas_converts_scaling_failure():
    api = Mock()
    api.patch_namespaced_deployment_scale.side_effect = RuntimeError("api unavailable")

    with pytest.raises(KubernetesExperimentError):
        make_adapter(api).restore_replicas(3)