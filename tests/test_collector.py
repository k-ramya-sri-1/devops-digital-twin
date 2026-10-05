import importlib

import httpx
import pytest


collector_module = importlib.import_module("digital-twin.collector")
models = importlib.import_module("digital-twin.models")
Infrastructure = models.Infrastructure
InstanceStatus = models.InstanceStatus
PrometheusCollector = collector_module.PrometheusCollector
PrometheusCollectorError = collector_module.PrometheusCollectorError


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