from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/orders", tags=["orders"])


class Order(BaseModel):
    order_id: int
    user_id: int
    amount: float
    status: str


SAMPLE_ORDERS = [
    Order(order_id=1001, user_id=1, amount=249.99, status="completed"),
    Order(order_id=1002, user_id=2, amount=89.50, status="processing"),
]


@router.get("", response_model=list[Order])
def get_orders() -> list[Order]:
    return SAMPLE_ORDERS
