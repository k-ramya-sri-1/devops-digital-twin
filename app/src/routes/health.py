from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(status="healthy", service="devops-digital-twin")


@router.get("/metrics")
def get_metrics() -> dict[str, str | int]:
    return {
        "service": "devops-digital-twin",
        "status": "running",
        "metrics_format": "basic-json",
    }
