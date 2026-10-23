import importlib
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.src.main import app
from app.src.routes.health import get_kubernetes_adapter, get_prometheus_collector
from app.src.services.prometheus import get_prometheus_collector as create_prometheus_collector

kubernetes_adapter_module = importlib.import_module("digital-twin.kubernetes_adapter")
collector_module = importlib.import_module("digital-twin.collector")
KubernetesDeploymentState = kubernetes_adapter_module.KubernetesDeploymentState
KubernetesExperimentError = kubernetes_adapter_module.KubernetesExperimentError
KubernetesContainerMetrics = collector_module.KubernetesContainerMetrics
PrometheusCollectorError = collector_module.PrometheusCollectorError


def test_prometheus_provider_uses_configured_url(monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEUS_URL", "http://prometheus.internal:9090")

    collector = create_prometheus_collector()

    assert collector.base_url == "http://prometheus.internal:9090"


def test_prometheus_provider_uses_default_url(monkeypatch) -> None:
    monkeypatch.delenv("PROMETHEUS_URL", raising=False)

    collector = create_prometheus_collector()

    assert collector.base_url == "http://localhost:9090"


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "healthy",
        "service": "devops-digital-twin",
    }


def test_infrastructure_status_endpoint_returns_deployment_state(
    client: TestClient,
) -> None:
    adapter = Mock()
    adapter.get_deployment_state.return_value = KubernetesDeploymentState(
        "devops-digital-twin", "default", 3, 2, 2, 3
    )
    app.dependency_overrides[get_kubernetes_adapter] = lambda: adapter

    try:
        response = client.get("/infrastructure/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "deployment_name": "devops-digital-twin",
        "namespace": "default",
        "desired_replicas": 3,
        "ready_replicas": 2,
        "available_replicas": 2,
        "updated_replicas": 3,
    }
    adapter.get_deployment_state.assert_called_once_with()


def test_infrastructure_status_endpoint_maps_kubernetes_failure(
    client: TestClient,
) -> None:
    adapter = Mock()
    adapter.get_deployment_state.side_effect = KubernetesExperimentError(
        "private Kubernetes error"
    )
    app.dependency_overrides[get_kubernetes_adapter] = lambda: adapter

    try:
        response = client.get("/infrastructure/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Kubernetes deployment status unavailable",
    }


def test_infrastructure_metrics_endpoint_returns_multiple_pods(
    client: TestClient,
) -> None:
    collector = Mock()
    collector.query_container_metrics.return_value = [
        KubernetesContainerMetrics("devops-digital-twin-a", 0.01, 100.0),
        KubernetesContainerMetrics("devops-digital-twin-b", 0.02, 200.0),
    ]
    app.dependency_overrides[get_prometheus_collector] = lambda: collector

    try:
        response = client.get("/infrastructure/metrics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "deployment_name": "devops-digital-twin",
        "namespace": "default",
        "pods": [
            {
                "pod_name": "devops-digital-twin-a",
                "cpu_cores": 0.01,
                "memory_bytes": 100.0,
            },
            {
                "pod_name": "devops-digital-twin-b",
                "cpu_cores": 0.02,
                "memory_bytes": 200.0,
            },
        ],
    }
    collector.query_container_metrics.assert_called_once_with()


def test_infrastructure_metrics_endpoint_returns_empty_pods(
    client: TestClient,
) -> None:
    collector = Mock()
    collector.query_container_metrics.return_value = []
    app.dependency_overrides[get_prometheus_collector] = lambda: collector

    try:
        response = client.get("/infrastructure/metrics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["pods"] == []


def test_infrastructure_metrics_endpoint_preserves_partial_metrics(
    client: TestClient,
) -> None:
    collector = Mock()
    collector.query_container_metrics.return_value = [
        KubernetesContainerMetrics("devops-digital-twin-a", None, 100.0),
        KubernetesContainerMetrics("devops-digital-twin-b", 0.02, None),
    ]
    app.dependency_overrides[get_prometheus_collector] = lambda: collector

    try:
        response = client.get("/infrastructure/metrics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["pods"] == [
        {
            "pod_name": "devops-digital-twin-a",
            "cpu_cores": None,
            "memory_bytes": 100.0,
        },
        {
            "pod_name": "devops-digital-twin-b",
            "cpu_cores": 0.02,
            "memory_bytes": None,
        },
    ]


def test_infrastructure_metrics_endpoint_maps_prometheus_failure(
    client: TestClient,
) -> None:
    collector = Mock()
    collector.query_container_metrics.side_effect = PrometheusCollectorError(
        "private Prometheus error"
    )
    app.dependency_overrides[get_prometheus_collector] = lambda: collector

    try:
        response = client.get("/infrastructure/metrics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Prometheus container metrics unavailable",
    }


def test_documentation_endpoints(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
