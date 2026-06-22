from fastapi import APIRouter
from pydantic import BaseModel

from app.config import DEPLOYMENT_ROOT

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    deployment_root: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        deployment_root=str(DEPLOYMENT_ROOT),
    )
