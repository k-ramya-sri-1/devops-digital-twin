import importlib
import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.src.services.prometheus import get_prometheus_collector

kubernetes_adapter_module = importlib.import_module("digital-twin.kubernetes_adapter")
collector_module = importlib.import_module("digital-twin.collector")
KubernetesDeploymentState = kubernetes_adapter_module.KubernetesDeploymentState
KubernetesExperimentAdapter = kubernetes_adapter_module.KubernetesExperimentAdapter
KubernetesExperimentError = kubernetes_adapter_module.KubernetesExperimentError
KubernetesContainerMetrics = collector_module.KubernetesContainerMetrics
PrometheusCollector = collector_module.PrometheusCollector
PrometheusCollectorError = collector_module.PrometheusCollectorError

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str


class InfrastructureStatusResponse(BaseModel):
    deployment_name: str
    namespace: str
    desired_replicas: int
    ready_replicas: int
    available_replicas: int
    updated_replicas: int


class ContainerMetricResponse(BaseModel):
    pod_name: str
    cpu_cores: float | None
    memory_bytes: float | None


class InfrastructureMetricsResponse(BaseModel):
    deployment_name: str
    namespace: str
    pods: list[ContainerMetricResponse]


def get_kubernetes_adapter() -> KubernetesExperimentAdapter:
    try:
        return KubernetesExperimentAdapter(
            deployment_name=os.getenv(
                "KUBERNETES_DEPLOYMENT_NAME", "devops-digital-twin"
            ),
            namespace=os.getenv("KUBERNETES_NAMESPACE", "default"),
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kubernetes deployment status unavailable",
        ) from error


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(status="healthy", service="devops-digital-twin")


@router.get(
    "/infrastructure/status",
    response_model=InfrastructureStatusResponse,
)
def get_infrastructure_status(
    adapter: KubernetesExperimentAdapter = Depends(get_kubernetes_adapter),
) -> InfrastructureStatusResponse:
    try:
        state: KubernetesDeploymentState = adapter.get_deployment_state()
    except KubernetesExperimentError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kubernetes deployment status unavailable",
        ) from error
    return InfrastructureStatusResponse(
        deployment_name=state.name,
        namespace=state.namespace,
        desired_replicas=state.desired_replicas,
        ready_replicas=state.ready_replicas,
        available_replicas=state.available_replicas,
        updated_replicas=state.updated_replicas,
    )


@router.get(
    "/infrastructure/metrics",
    response_model=InfrastructureMetricsResponse,
)
def get_infrastructure_metrics(
    collector: PrometheusCollector = Depends(get_prometheus_collector),
) -> InfrastructureMetricsResponse:
    try:
        metrics: list[KubernetesContainerMetrics] = (
            collector.query_container_metrics()
        )
    except PrometheusCollectorError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prometheus container metrics unavailable",
        ) from error

    return InfrastructureMetricsResponse(
        deployment_name=os.getenv(
            "KUBERNETES_DEPLOYMENT_NAME", "devops-digital-twin"
        ),
        namespace=os.getenv("KUBERNETES_NAMESPACE", "default"),
        pods=[
            ContainerMetricResponse(
                pod_name=metric.pod_name,
                cpu_cores=metric.cpu_cores,
                memory_bytes=metric.memory_bytes,
            )
            for metric in metrics
        ],
    )


@router.get("/metrics")
def get_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
