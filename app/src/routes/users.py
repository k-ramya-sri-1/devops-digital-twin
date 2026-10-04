from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/users", tags=["users"])


class User(BaseModel):
    id: int
    name: str
    email: str


SAMPLE_USERS = [
    User(id=1, name="Alice Johnson", email="alice@example.com"),
    User(id=2, name="Bob Smith", email="bob@example.com"),
]


@router.get("", response_model=list[User])
def get_users() -> list[User]:
    return SAMPLE_USERS
