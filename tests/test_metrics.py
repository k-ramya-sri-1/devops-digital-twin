from fastapi.testclient import TestClient


def test_metrics_endpoint(client: TestClient) -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# HELP http_requests_total" in response.text
    assert "# TYPE http_requests_total counter" in response.text
    assert "# HELP http_request_duration_seconds" in response.text
    assert "# TYPE http_request_duration_seconds histogram" in response.text
