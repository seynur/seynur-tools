from fastapi import APIRouter

from app.models.environment import EnvironmentsResponse
from app.services.config_reader import ConfigReader

router = APIRouter()
_reader = ConfigReader()


@router.get("/environments", response_model=EnvironmentsResponse)
def get_environments() -> EnvironmentsResponse:
    return EnvironmentsResponse(environments=_reader.read_environments())
