from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/data", tags=["data"])


class ApplicationData(BaseModel):
    id: int
    name: str
    value: float


SAMPLE_DATA = [
    ApplicationData(id=1, name="cpu_utilization", value=42.5),
    ApplicationData(id=2, name="memory_utilization", value=58.0),
]


@router.get("", response_model=list[ApplicationData])
def get_data() -> list[ApplicationData]:
    return SAMPLE_DATA
