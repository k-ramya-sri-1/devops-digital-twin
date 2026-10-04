from fastapi.testclient import TestClient


def test_metrics_endpoint(client: TestClient) -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "service": "devops-digital-twin",
        "status": "running",
        "metrics_format": "basic-json",
    }
