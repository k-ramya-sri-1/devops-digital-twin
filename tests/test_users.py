from fastapi.testclient import TestClient


def test_users_endpoint(client: TestClient) -> None:
    response = client.get("/api/users")

    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)
    assert users
    assert users == [
        {"id": 1, "name": "Alice Johnson", "email": "alice@example.com"},
        {"id": 2, "name": "Bob Smith", "email": "bob@example.com"},
    ]
    assert all({"id", "name", "email"} <= user.keys() for user in users)
