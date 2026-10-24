import importlib

import httpx
import pytest


collector_module = importlib.import_module("digital-twin.collector")
models = importlib.import_module("digital-twin.models")
Infrastructure = models.Infrastructure
InstanceStatus = models.InstanceStatus
PrometheusCollector = collector_module.PrometheusCollector
PrometheusCollectorError = collector_module.PrometheusCollectorError
KubernetesContainerMetrics = collector_module.KubernetesContainerMetrics
KubernetesContainerResourceLimits = importlib.import_module(
    "digital-twin.kubernetes_adapter"
).KubernetesContainerResourceLimits


def response_for(payload: object, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("GET", "http://prometheus/api/v1/query")
    return httpx.Response(status_code, json=payload, request=request)


def successful_payload(
    value: str,
    labels: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {
                    "metric": labels or {},
                    "value": ["1710000000", value],
                }
            ],
        },
    }


def successful_samples_payload(
    samples: list[tuple[str, dict[str, str]]],
) -> dict[str, object]:
    return {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {
                    "metric": labels,
                    "value": ["1710000000", value],
                }
                for value, labels in samples
            ],
        },
    }


def collector_for(handler):
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return PrometheusCollector("http://prometheus/", client=client)


def test_successful_prometheus_query() -> None:
    collector = collector_for(lambda request: response_for(successful_payload("333")))

    samples = collector.query("http_requests_total")

    assert samples[0].value == 333.0
    assert samples[0].labels == {}


def test_prometheus_error_response() -> None:
    payload = {
        "status": "error",
        "errorType": "bad_data",
        "error": "invalid query",
    }
    collector = collector_for(lambda request: response_for(payload))

    with pytest.raises(PrometheusCollectorError, match="invalid query"):
        collector.query("bad query")


def test_empty_result() -> None:
    payload = {"status": "success", "data": {"resultType": "vector", "result": []}}
    collector = collector_for(lambda request: response_for(payload))

    assert collector.query("up") == []


def test_connection_failure() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    collector = collector_for(fail)

    with pytest.raises(PrometheusCollectorError, match="could not connect"):
        collector.query("up")


def test_query_container_metrics_merges_cpu_and_memory_by_pod() -> None:
    cpu_query = PrometheusCollector.CONTAINER_CPU_QUERY
    memory_query = PrometheusCollector.CONTAINER_MEMORY_QUERY
    payloads = {
        cpu_query: successful_samples_payload(
            [
                ("0.01", {"pod": "devops-digital-twin-a"}),
                ("0.02", {"pod": "devops-digital-twin-b"}),
                ("0.03", {"pod": "devops-digital-twin-c"}),
            ]
        ),
        memory_query: successful_samples_payload(
            [
                ("100", {"pod": "devops-digital-twin-c"}),
                ("200", {"pod": "devops-digital-twin-a"}),
                ("300", {"pod": "devops-digital-twin-b"}),
            ]
        ),
    }

    def respond(request: httpx.Request) -> httpx.Response:
        return response_for(payloads[request.url.params["query"]])

    metrics = collector_for(respond).query_container_metrics()

    assert metrics == [
        KubernetesContainerMetrics("devops-digital-twin-a", 0.01, 200.0),
        KubernetesContainerMetrics("devops-digital-twin-b", 0.02, 300.0),
        KubernetesContainerMetrics("devops-digital-twin-c", 0.03, 100.0),
    ]


def test_query_container_metrics_returns_empty_for_empty_queries() -> None:
    payload = {"status": "success", "data": {"resultType": "vector", "result": []}}
    collector = collector_for(lambda request: response_for(payload))

    assert collector.query_container_metrics() == []


@pytest.mark.parametrize(
    ("cpu_payload", "memory_payload", "expected"),
    [
        (
            successful_samples_payload(
                [("0.01", {"pod": "devops-digital-twin-a"})]
            ),
            successful_samples_payload([]),
            [KubernetesContainerMetrics("devops-digital-twin-a", 0.01, None)],
        ),
        (
            successful_samples_payload([]),
            successful_samples_payload(
                [("100", {"pod": "devops-digital-twin-a"})]
            ),
            [KubernetesContainerMetrics("devops-digital-twin-a", None, 100.0)],
        ),
    ],
)
def test_query_container_metrics_preserves_missing_metric_as_none(
    cpu_payload: dict[str, object],
    memory_payload: dict[str, object],
    expected: list[KubernetesContainerMetrics],
) -> None:
    payloads = {
        PrometheusCollector.CONTAINER_CPU_QUERY: cpu_payload,
        PrometheusCollector.CONTAINER_MEMORY_QUERY: memory_payload,
    }

    def respond(request: httpx.Request) -> httpx.Response:
        return response_for(payloads[request.url.params["query"]])

    assert collector_for(respond).query_container_metrics() == expected


def test_query_container_metrics_raises_for_connection_failure() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(PrometheusCollectorError, match="could not connect"):
        collector_for(fail).query_container_metrics()


def test_query_container_metrics_raises_for_api_error() -> None:
    payload = {
        "status": "error",
        "errorType": "bad_data",
        "error": "invalid query",
    }
    collector = collector_for(lambda request: response_for(payload))

    with pytest.raises(PrometheusCollectorError, match="invalid query"):
        collector.query_container_metrics()


def test_query_container_metrics_raises_for_missing_pod_label() -> None:
    payload = successful_payload("0.01")
    collector = collector_for(lambda request: response_for(payload))

    with pytest.raises(PrometheusCollectorError, match="pod label"):
        collector.query_container_metrics()


def test_collects_request_latency_and_health_metrics() -> None:
    payloads = {
        "http_requests_total": successful_payload("333", {"job": "devops-digital-twin"}),
        "http_request_duration_seconds_count": successful_payload(
            "120", {"job": "devops-digital-twin"}
        ),
        "up": successful_payload("1", {"job": "devops-digital-twin"}),
    }

    def respond(request: httpx.Request) -> httpx.Response:
        query = request.url.params["query"]
        return response_for(payloads[query])

    state = collector_for(respond).collect()
    instance = state.get_service("devops-digital-twin").get_instance(
        "devops-digital-twin-service"
    )

    assert instance.request_count == 333.0
    assert instance.request_rate == 333.0
    assert instance.request_latency_count == 120.0
    assert instance.status is InstanceStatus.HEALTHY
    assert instance.cpu_capacity == 0.0
    assert instance.memory_capacity == 0.0


def test_collect_aggregates_container_usage_against_live_limits() -> None:
    payloads = {
        "http_requests_total": successful_payload("333", {"job": "devops-digital-twin"}),
        "http_request_duration_seconds_count": successful_payload(
            "120", {"job": "devops-digital-twin"}
        ),
        "up": successful_payload("1", {"job": "devops-digital-twin"}),
        PrometheusCollector.CONTAINER_CPU_QUERY: successful_samples_payload(
            [
                ("0.1", {"pod": "devops-digital-twin-a"}),
                ("0.2", {"pod": "devops-digital-twin-b"}),
            ]
        ),
        PrometheusCollector.CONTAINER_MEMORY_QUERY: successful_samples_payload(
            [
                ("67108864", {"pod": "devops-digital-twin-a"}),
                ("134217728", {"pod": "devops-digital-twin-b"}),
            ]
        ),
    }

    def respond(request: httpx.Request) -> httpx.Response:
        return response_for(payloads[request.url.params["query"]])

    state = collector_for(respond).collect(
        resource_limits=KubernetesContainerResourceLimits(0.5, 268435456.0)
    )
    instance = state.get_service("devops-digital-twin").get_instance(
        "devops-digital-twin-service"
    )

    assert instance.cpu_capacity == 1.0
    assert instance.memory_capacity == 536870912.0
    assert instance.cpu_utilization == pytest.approx(30.0)
    assert instance.memory_utilization == 37.5


def test_collect_preserves_zero_usage_and_missing_resource_independently() -> None:
    payloads = {
        "http_requests_total": successful_payload("1"),
        "http_request_duration_seconds_count": successful_payload("1"),
        "up": successful_payload("1"),
        PrometheusCollector.CONTAINER_CPU_QUERY: successful_samples_payload(
            [("0", {"pod": "devops-digital-twin-a"})]
        ),
        PrometheusCollector.CONTAINER_MEMORY_QUERY: successful_samples_payload([]),
    }

    def respond(request: httpx.Request) -> httpx.Response:
        return response_for(payloads[request.url.params["query"]])

    state = collector_for(respond).collect(
        resource_limits=KubernetesContainerResourceLimits(0.5, 268435456.0)
    )
    instance = state.get_service("devops-digital-twin").get_instance(
        "devops-digital-twin-service"
    )

    assert instance.cpu_capacity == 0.5
    assert instance.cpu_utilization == 0.0
    assert instance.memory_capacity is None
    assert instance.memory_utilization is None


def test_collect_updates_existing_state_without_replacing_service() -> None:
    payload = successful_payload("1", {"job": "devops-digital-twin"})
    collector = collector_for(lambda request: response_for(payload))
    state = Infrastructure()

    result = collector.collect(state)

    assert result is state
    assert list(state.services) == ["devops-digital-twin"]


def test_unhealthy_target_is_mapped_to_unhealthy_instance() -> None:
    payloads = {
        "http_requests_total": successful_payload("1"),
        "http_request_duration_seconds_count": successful_payload("1"),
        "up": successful_payload("0", {"job": "devops-digital-twin"}),
    }

    def respond(request: httpx.Request) -> httpx.Response:
        return response_for(payloads[request.url.params["query"]])

    state = collector_for(respond).collect()

    assert len(state.unhealthy_instances) == 1
    assert state.unhealthy_instances[0].status is InstanceStatus.UNHEALTHY