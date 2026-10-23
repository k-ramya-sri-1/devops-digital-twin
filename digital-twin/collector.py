"""Prometheus adapter for synchronizing observed application state."""

from dataclasses import dataclass
from math import isfinite
from typing import Any, Protocol

import httpx

from .models import Infrastructure, Instance, InstanceStatus, Service


class PrometheusCollectorError(RuntimeError):
    """Raised when Prometheus data cannot be queried or parsed."""


class HttpClient(Protocol):
    """Minimal HTTP client interface used by :class:`PrometheusCollector`."""

    def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        """Execute an HTTP GET request."""


@dataclass(frozen=True)
class PrometheusSample:
    """A parsed instant-vector sample returned by Prometheus."""

    labels: dict[str, str]
    value: float


@dataclass(frozen=True)
class KubernetesContainerMetrics:
    """CPU and memory usage reported for one Kubernetes pod."""

    pod_name: str
    cpu_cores: float | None
    memory_bytes: float | None


class PrometheusCollector:
    """Query Prometheus and map observed application metrics to twin state."""

    REQUESTS_QUERY = "http_requests_total"
    LATENCY_COUNT_QUERY = "http_request_duration_seconds_count"
    HEALTH_QUERY = "up"
    CONTAINER_CPU_QUERY = (
        'rate(container_cpu_usage_seconds_total{'
        'container="devops-digital-twin-app",'
        'namespace="default",'
        'pod=~"devops-digital-twin-.*"}[5m])'
    )
    CONTAINER_MEMORY_QUERY = (
        'container_memory_working_set_bytes{'
        'container="devops-digital-twin-app",'
        'namespace="default",'
        'pod=~"devops-digital-twin-.*"}'
    )
    SERVICE_NAME = "devops-digital-twin"
    TARGET_INSTANCE_NAME = "devops-digital-twin-service"
    APPLICATION_JOB = "devops-digital-twin"

    def __init__(
        self,
        base_url: str,
        client: HttpClient | None = None,
        timeout: float = 5.0,
    ) -> None:
        """Create a collector for a configurable Prometheus base URL."""
        normalized_url = base_url.strip().rstrip("/")
        if not normalized_url:
            raise ValueError("base_url must not be empty")
        if timeout <= 0 or not isfinite(timeout):
            raise ValueError("timeout must be a positive finite number")

        self.base_url = normalized_url
        self.timeout = timeout
        self._client = client or httpx.Client()

    def query(self, promql: str) -> list[PrometheusSample]:
        """Execute an instant PromQL query and return parsed samples.

        Empty Prometheus results are returned as an empty list. Transport,
        HTTP, Prometheus API, and malformed payload errors raise
        ``PrometheusCollectorError``.
        """
        if not promql or not promql.strip():
            raise ValueError("promql must not be empty")

        try:
            response = self._client.get(
                f"{self.base_url}/api/v1/query",
                params={"query": promql},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.RequestError as error:
            raise PrometheusCollectorError(
                f"could not connect to Prometheus: {error}"
            ) from error
        except httpx.HTTPStatusError as error:
            raise PrometheusCollectorError(
                f"Prometheus returned HTTP {error.response.status_code}"
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise PrometheusCollectorError(
                "Prometheus returned invalid JSON"
            ) from error

        if not isinstance(payload, dict) or payload.get("status") != "success":
            error_message = self._error_message(payload)
            raise PrometheusCollectorError(
                f"Prometheus query failed: {error_message}"
            )

        try:
            data = payload["data"]
            results = data["result"]
            if not isinstance(data, dict) or not isinstance(results, list):
                raise TypeError
            return [self._parse_sample(result) for result in results]
        except (KeyError, TypeError, ValueError) as error:
            raise PrometheusCollectorError(
                "Prometheus returned an invalid query result"
            ) from error

    def query_container_metrics(self) -> list[KubernetesContainerMetrics]:
        """Query and merge current CPU and memory metrics by pod name."""
        cpu_samples = self.query(self.CONTAINER_CPU_QUERY)
        memory_samples = self.query(self.CONTAINER_MEMORY_QUERY)
        cpu_by_pod = self._container_samples_by_pod(cpu_samples)
        memory_by_pod = self._container_samples_by_pod(memory_samples)

        return [
            KubernetesContainerMetrics(
                pod_name=pod_name,
                cpu_cores=cpu_by_pod.get(pod_name),
                memory_bytes=memory_by_pod.get(pod_name),
            )
            for pod_name in sorted(cpu_by_pod.keys() | memory_by_pod.keys())
        ]

    def collect(self, infrastructure: Infrastructure | None = None) -> Infrastructure:
        """Collect current application metrics into an infrastructure state.

        The current Prometheus setup exposes service-level metrics through a
        ClusterIP Service, so this creates one aggregate observed instance.
        CPU and memory fields remain zero because those metrics are not
        currently collected.
        """
        request_samples = self.query(self.REQUESTS_QUERY)
        latency_samples = self.query(self.LATENCY_COUNT_QUERY)
        health_samples = self.query(self.HEALTH_QUERY)

        state = infrastructure or Infrastructure()
        service = state.services.get(self.SERVICE_NAME)
        if service is None:
            service = Service(name=self.SERVICE_NAME)
            state.add_service(service)

        request_count = self._total(request_samples)
        latency_count = self._total(latency_samples)
        instance = Instance(
            name=self.TARGET_INSTANCE_NAME,
            cpu_capacity=0.0,
            memory_capacity=0.0,
            request_rate=request_count,
            request_count=request_count,
            request_latency_count=latency_count,
            status=self._health_status(health_samples),
        )
        service.instances[instance.name] = instance
        return state

    def close(self) -> None:
        """Close the underlying HTTP client when it supports closing."""
        close = getattr(self._client, "close", None)
        if close is not None:
            close()

    @staticmethod
    def _parse_sample(result: Any) -> PrometheusSample:
        if not isinstance(result, dict):
            raise TypeError("sample must be an object")
        labels = result.get("metric", {})
        raw_value = result.get("value")
        if not isinstance(labels, dict) or not isinstance(raw_value, list):
            raise TypeError("sample has invalid labels or value")
        if len(raw_value) != 2:
            raise ValueError("sample value must contain timestamp and value")
        value = float(raw_value[1])
        if not isfinite(value):
            raise ValueError("sample value must be finite")
        return PrometheusSample(
            labels={str(key): str(label) for key, label in labels.items()},
            value=value,
        )

    @staticmethod
    def _error_message(payload: Any) -> str:
        if isinstance(payload, dict):
            error_type = payload.get("errorType")
            error = payload.get("error")
            if error_type or error:
                return f"{error_type or 'unknown'}: {error or 'unknown error'}"
        return "invalid response"

    @staticmethod
    def _total(samples: list[PrometheusSample]) -> float:
        return sum(sample.value for sample in samples)

    @staticmethod
    def _container_samples_by_pod(
        samples: list[PrometheusSample],
    ) -> dict[str, float]:
        by_pod: dict[str, float] = {}
        for sample in samples:
            pod_name = sample.labels.get("pod")
            if not pod_name:
                raise PrometheusCollectorError(
                    "Prometheus returned a container metric without a pod label"
                )
            by_pod[pod_name] = sample.value
        return by_pod

    @classmethod
    def _health_status(cls, samples: list[PrometheusSample]) -> InstanceStatus:
        application_samples = [
            sample
            for sample in samples
            if sample.labels.get("job") == cls.APPLICATION_JOB
            or sample.labels.get("instance") == "devops-digital-twin-service:8000"
        ]
        if not application_samples and len(samples) == 1:
            application_samples = samples
        if application_samples and all(sample.value > 0 for sample in application_samples):
            return InstanceStatus.HEALTHY
        return InstanceStatus.UNHEALTHY