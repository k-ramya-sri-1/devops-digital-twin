from fastapi.testclient import TestClient


def test_orders_endpoint(client: TestClient) -> None:
    response = client.get("/api/orders")

    assert response.status_code == 200
    orders = response.json()
    assert isinstance(orders, list)
    assert orders
    assert orders == [
        {"order_id": 1001, "user_id": 1, "amount": 249.99, "status": "completed"},
        {"order_id": 1002, "user_id": 2, "amount": 89.5, "status": "processing"},
    ]
    assert all(
        {"order_id", "user_id", "amount", "status"} <= order.keys()
        for order in orders
    )
