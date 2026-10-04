from fastapi.testclient import TestClient


def test_data_endpoint(client: TestClient) -> None:
    response = client.get("/api/data")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data
    assert data == [
        {"id": 1, "name": "cpu_utilization", "value": 42.5},
        {"id": 2, "name": "memory_utilization", "value": 58.0},
    ]
    assert all({"id", "name", "value"} <= item.keys() for item in data)
